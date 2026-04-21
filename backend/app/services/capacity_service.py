"""Capacity planner — validates that a model's VRAM demand fits the selected GPUs.

Fetches the model's config.json from HuggingFace to estimate KV-cache bytes per
token, then decides whether the requested/default `max_model_len` is feasible
given the selected GPUs' total VRAM × `gpu_memory_utilization`. If not, clamps
the effective `max_model_len` to the largest safe value and emits a warning
that is surfaced to the UI.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

import structlog
from huggingface_hub.utils import HfHubHTTPError

from app.services import hf_service

log = structlog.get_logger(__name__)

# Conservative fraction of gpu_memory_utilization's budget that's actually
# available for KV cache, after weights + CUDA/vLLM overhead.
_WEIGHTS_OVERHEAD_GB = 1.0         # CUDA context, vLLM worker, activations
_KV_SAFETY_FACTOR = 1.3            # pad our estimate; vLLM's block allocator
                                   # and prefix cache consume ~30% more than
                                   # the raw tensor size.

_BYTES_PER_ELEMENT_BY_DTYPE = {
    "float16": 2, "fp16": 2, "half": 2,
    "bfloat16": 2, "bf16": 2,
    "float32": 4, "fp32": 4, "float": 4,
    "int8": 1, "fp8": 1,
}

# Fallback per-model-size rough estimates when config.json is unavailable.
# Returns (num_hidden_layers, hidden_size). Picked to be slightly pessimistic
# so we clamp a bit lower than strictly necessary.
_SIZE_HEURISTIC_BY_PARAMS_B: list[tuple[float, tuple[int, int]]] = [
    (1.5, (22, 1024)),
    (3.5, (28, 1536)),
    (8.5, (32, 4096)),
    (15.0, (40, 5120)),
    (35.0, (60, 6656)),
    (80.0, (80, 8192)),
]


@dataclass
class CapacityPlan:
    effective_max_model_len: int | None
    was_adjusted: bool = False
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


def _lookup_gpu_total_mib(gpu_indices: list[int]) -> int | None:
    """Return total VRAM (MiB) across the selected indices, via nvidia-smi."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if out.returncode != 0:
            return None
        total = 0
        wanted = set(gpu_indices) if gpu_indices else {0}
        found = False
        for line in out.stdout.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 2:
                continue
            try:
                idx = int(parts[0])
                mib = int(parts[1])
            except ValueError:
                continue
            if idx in wanted:
                total += mib
                found = True
        return total if found else None
    except Exception as exc:
        log.debug("nvidia_smi_query_failed", error=str(exc))
        return None


def _extract_text_config(config: dict | None) -> dict:
    """Qwen-VL, LLaVA-next etc. nest text params under `text_config`."""
    if not isinstance(config, dict):
        return {}
    text_cfg = config.get("text_config")
    return text_cfg if isinstance(text_cfg, dict) else config


def _kv_bytes_per_token(config: dict | None, param_count_b: float | None, dtype_str: str) -> int | None:
    """Estimate KV-cache size per token in bytes."""
    text_cfg = _extract_text_config(config)
    num_layers = text_cfg.get("num_hidden_layers")
    hidden_size = text_cfg.get("hidden_size") or text_cfg.get("n_embd")

    if not (isinstance(num_layers, int) and isinstance(hidden_size, int) and num_layers > 0 and hidden_size > 0):
        # Fall back to a rule-of-thumb sized by parameter count.
        if param_count_b is None:
            return None
        chosen: tuple[int, int] | None = None
        for cap, guess in _SIZE_HEURISTIC_BY_PARAMS_B:
            if param_count_b <= cap:
                chosen = guess
                break
        if chosen is None:
            chosen = _SIZE_HEURISTIC_BY_PARAMS_B[-1][1]
        num_layers, hidden_size = chosen

    num_kv_heads = text_cfg.get("num_key_value_heads")
    num_attn_heads = text_cfg.get("num_attention_heads")
    if isinstance(num_kv_heads, int) and isinstance(num_attn_heads, int) and num_attn_heads > 0:
        # Grouped-query attention: KV is 1/(num_attn_heads/num_kv_heads) of full.
        effective_kv_dim = int(hidden_size * (num_kv_heads / num_attn_heads))
    else:
        effective_kv_dim = hidden_size

    bytes_per_elem = _BYTES_PER_ELEMENT_BY_DTYPE.get((dtype_str or "").strip().lower(), 2)
    # K and V tensors → factor 2.
    raw = 2 * effective_kv_dim * num_layers * bytes_per_elem
    return int(raw * _KV_SAFETY_FACTOR)


def _detect_quantization(config: dict | None) -> dict | None:
    """Read `quantization_config` from config.json and return an effective
    bits-per-weight + a human-readable method label.

    Handles GPTQ/AWQ (`bits` field), bitsandbytes (`load_in_4bit`,
    `load_in_8bit`), FP8/INT8 weight-only flags, and the convention used by
    some NVFP4/NVFP8 repos (`weight_precision`/`num_bits`). Returns None when
    no quantization is detected.
    """
    if not isinstance(config, dict):
        return None

    qc = config.get("quantization_config")
    if not isinstance(qc, dict):
        # Some FP8 repos expose torch_dtype="float8_e4m3fn" without a
        # quantization_config block.
        tdt = str(config.get("torch_dtype") or "").lower()
        if "float8" in tdt or tdt in ("fp8", "e4m3", "e5m2"):
            return {"bits": 8, "method": "fp8"}
        return None

    method = str(qc.get("quant_method") or qc.get("method") or "").lower()

    if qc.get("load_in_4bit") is True:
        return {"bits": 4, "method": method or "bitsandbytes-4bit"}
    if qc.get("load_in_8bit") is True:
        return {"bits": 8, "method": method or "bitsandbytes-8bit"}

    # GPTQ/AWQ/compressed-tensors all expose `bits` as an int.
    for key in ("bits", "num_bits", "weight_bits"):
        v = qc.get(key)
        if isinstance(v, int) and v > 0:
            return {"bits": int(v), "method": method or key}

    # compressed-tensors uses a nested `config_groups` with `num_bits`.
    groups = qc.get("config_groups")
    if isinstance(groups, dict):
        for group in groups.values():
            if isinstance(group, dict):
                weights = group.get("weights") or {}
                if isinstance(weights, dict):
                    v = weights.get("num_bits")
                    if isinstance(v, int) and v > 0:
                        return {"bits": int(v), "method": method or "compressed-tensors"}

    # FP8 without explicit bits (e.g. fbgemm_fp8, fp8_e4m3).
    if "fp8" in method or "float8" in method:
        return {"bits": 8, "method": method}

    return None


_CONFIG_CACHE: dict[str, dict] = {}


def _fetch_model_config(model_id: str) -> dict:
    """Return parsed config.json (best effort, cached)."""
    cached = _CONFIG_CACHE.get(model_id)
    if cached is not None:
        return cached
    try:
        api = hf_service.get_hf_api()
        info = api.model_info(model_id, files_metadata=False)
        cfg = getattr(info, "config", None)
        if isinstance(cfg, dict):
            _CONFIG_CACHE[model_id] = cfg
            return cfg
    except HfHubHTTPError as exc:
        log.warning("capacity_model_info_failed", model_id=model_id, error=str(exc))
    except Exception as exc:
        log.warning("capacity_model_info_error", model_id=model_id, error=str(exc))
    return {}


def _bits_per_weight(dtype_str: str, quant: dict | None) -> tuple[float, str]:
    """Return (bits_per_weight, source_label) honoring detected quantization."""
    if quant and isinstance(quant.get("bits"), int) and quant["bits"] > 0:
        return float(quant["bits"]), quant.get("method") or "quant"
    bytes_per_elem = _BYTES_PER_ELEMENT_BY_DTYPE.get((dtype_str or "").strip().lower(), 2)
    return 8.0 * bytes_per_elem, f"dtype={dtype_str or 'bf16'}"


def _estimate_weights_gb(
    model_id: str,
    dtype_str: str,
    param_count_b: float | None = None,
    quant: dict | None = None,
) -> tuple[float, str]:
    """Best-effort weights size in GB and a label describing the basis.

    Order of preference:
      1. Live safetensors shard sizes (from the HF file-metadata API).
      2. `safetensors.total` (parameter-element count) × bytes-per-element
         derived from quantization bits or the configured dtype.
      3. Catalog parameter_count_b × bits/8 (when HF API is unreachable).
    """
    bits, source = _bits_per_weight(dtype_str, quant)
    try:
        api = hf_service.get_hf_api()
        info = api.model_info(model_id, files_metadata=True)

        siblings = getattr(info, "siblings", None) or []
        total_bytes = sum(
            getattr(s, "size", 0) or 0
            for s in siblings
            if getattr(s, "rfilename", "").endswith((".safetensors", ".gguf", ".bin"))
        )
        if total_bytes > 0:
            return float(total_bytes) / (1024 ** 3), "file_bytes"

        st = getattr(info, "safetensors", None)
        total = getattr(st, "total", None) if st is not None else None
        if isinstance(total, (int, float)) and total > 0:
            return float(total) * (bits / 8.0) / (1024 ** 3), f"safetensors.total × {source}"
    except Exception as exc:
        log.debug("capacity_weights_live_probe_failed", model_id=model_id, error=str(exc))

    if param_count_b is not None and param_count_b > 0:
        return float(param_count_b) * 1e9 * (bits / 8.0) / (1024 ** 3), f"param_count × {source}"
    return 0.0, "unknown"


def _model_max_position_embeddings(config: dict) -> int | None:
    text_cfg = _extract_text_config(config)
    for key in ("max_position_embeddings", "max_sequence_length", "n_positions"):
        v = text_cfg.get(key)
        if isinstance(v, int) and v > 0:
            return v
    return None


def compute_plan(
    *,
    model_id: str,
    requested_max_model_len: int | None,
    gpu_memory_utilization: float,
    gpu_indices: list[int],
    dtype: str = "auto",
    param_count_b: float | None = None,
    cpu_offload_gb: float = 0.0,
) -> CapacityPlan:
    """Decide the feasible max_model_len given the selected hardware.

    Returns a CapacityPlan whose `effective_max_model_len` is the value to
    feed into vLLM. `warnings` contains user-facing messages when the
    requested config does not fit.
    """
    warnings: list[str] = []
    details: dict[str, Any] = {"model_id": model_id, "gpu_indices": gpu_indices}

    total_mib = _lookup_gpu_total_mib(gpu_indices)
    if total_mib is None:
        # Can't probe the GPU — don't block the start, just return as-is.
        return CapacityPlan(
            effective_max_model_len=requested_max_model_len,
            was_adjusted=False,
            warnings=[],
            details={**details, "gpu_probe": "unavailable"},
        )
    total_gb = total_mib / 1024.0
    budget_gb = total_gb * max(0.05, min(0.98, gpu_memory_utilization))
    details["total_vram_gb"] = round(total_gb, 1)
    details["budget_gb"] = round(budget_gb, 2)

    # Use the configured dtype or fall back to bf16 for KV estimation.
    effective_dtype = dtype if dtype and dtype != "auto" else "bf16"

    # Fetch config early so we can read quantization_config for weight sizing.
    config = _fetch_model_config(model_id)
    quant = _detect_quantization(config)
    if quant:
        details["quantization"] = {"method": quant["method"], "bits": quant["bits"]}

    full_weights_gb, weights_source = _estimate_weights_gb(
        model_id, effective_dtype, param_count_b, quant=quant
    )
    details["weights_gb"] = round(full_weights_gb, 2)
    details["weights_source"] = weights_source

    # `--cpu-offload-gb` moves that many GB of weights out of GPU memory;
    # the capacity plan should see only the resident portion.
    cpu_offload_gb = max(0.0, float(cpu_offload_gb or 0.0))
    if cpu_offload_gb > 0:
        details["cpu_offload_gb"] = round(cpu_offload_gb, 2)
    resident_weights_gb = max(0.0, full_weights_gb - cpu_offload_gb)
    details["resident_weights_gb"] = round(resident_weights_gb, 2)

    kv_headroom_gb = budget_gb - resident_weights_gb - _WEIGHTS_OVERHEAD_GB
    details["kv_headroom_gb"] = round(kv_headroom_gb, 2)

    if resident_weights_gb > 0 and resident_weights_gb >= budget_gb:
        extra = (
            f" after offloading {cpu_offload_gb:.0f} GB to CPU" if cpu_offload_gb > 0 else ""
        )
        warnings.append(
            f"Model weights on GPU (~{resident_weights_gb:.1f} GB{extra}) exceed "
            f"the GPU budget (~{budget_gb:.1f} GB). Increase --cpu-offload-gb, pick "
            f"a smaller/lower-bit quantization, or add more GPUs."
        )
        return CapacityPlan(
            effective_max_model_len=requested_max_model_len,
            was_adjusted=False,
            warnings=warnings,
            details=details,
        )

    model_native_max = _model_max_position_embeddings(config)
    details["model_native_max"] = model_native_max

    kv_per_token = _kv_bytes_per_token(config, param_count_b, effective_dtype)
    if kv_per_token is None or kv_per_token <= 0:
        # Not enough info to compute; trust the user.
        return CapacityPlan(
            effective_max_model_len=requested_max_model_len,
            was_adjusted=False,
            warnings=[],
            details={**details, "kv_estimate": "unavailable"},
        )
    details["kv_bytes_per_token"] = kv_per_token

    if kv_headroom_gb <= 0.1:
        warnings.append(
            f"Almost no KV-cache headroom on the selected GPU(s) after loading "
            f"weights (~{resident_weights_gb:.1f} GB). You need a larger GPU or a lower "
            f"gpu_memory_utilization on other processes."
        )
        return CapacityPlan(
            effective_max_model_len=requested_max_model_len,
            was_adjusted=False,
            warnings=warnings,
            details=details,
        )

    kv_headroom_bytes = kv_headroom_gb * (1024 ** 3)
    max_safe_context = int(kv_headroom_bytes / kv_per_token)
    # Round to a kinder multiple of 1024.
    max_safe_context = (max_safe_context // 1024) * 1024
    if max_safe_context < 512:
        max_safe_context = 512
    if model_native_max:
        max_safe_context = min(max_safe_context, model_native_max)
    details["max_safe_context"] = max_safe_context

    # Determine what the user *would* get without any adjustment.
    effective_requested = requested_max_model_len
    if effective_requested is None and model_native_max:
        effective_requested = model_native_max

    if effective_requested and effective_requested > max_safe_context:
        warnings.append(
            f"The selected GPU(s) ({total_gb:.0f} GB total) can only hold "
            f"~{max_safe_context} tokens of context for '{model_id}' "
            f"(weights ≈ {resident_weights_gb:.1f} GB on GPU). Clamped max_model_len from "
            f"{effective_requested} to {max_safe_context}."
        )
        return CapacityPlan(
            effective_max_model_len=max_safe_context,
            was_adjusted=True,
            warnings=warnings,
            details=details,
        )

    # When we can't determine the native max (e.g. HF rate-limited) and the
    # user didn't set one, default to the safe value to avoid vLLM OOMing on
    # the model's internal default.
    if requested_max_model_len is None and model_native_max is None:
        warnings.append(
            f"HuggingFace metadata for '{model_id}' was not reachable; set "
            f"max_model_len to {max_safe_context} (largest size that fits "
            f"{total_gb:.0f} GB of VRAM) as a safe default."
        )
        return CapacityPlan(
            effective_max_model_len=max_safe_context,
            was_adjusted=True,
            warnings=warnings,
            details=details,
        )

    return CapacityPlan(
        effective_max_model_len=requested_max_model_len,
        was_adjusted=False,
        warnings=[],
        details=details,
    )
