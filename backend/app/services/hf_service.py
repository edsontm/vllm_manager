from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import AsyncIterator

import structlog
from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.utils import HfHubHTTPError

from app.config import settings
from app.core.exceptions import HuggingFaceError
from app.schemas.model import HFModelInfo, LocalModelInfo, ModelPrefill

logger = structlog.get_logger()


def _estimate_vram_gb(siblings) -> float | None:
    """Sum .safetensors shard sizes and add ~20 % overhead for KV cache + activations."""
    total_bytes = sum(
        getattr(s, "size", 0) or 0
        for s in (siblings or [])
        if getattr(s, "rfilename", "").endswith(".safetensors")
    )
    if total_bytes == 0:
        return None
    return round((total_bytes / 1e9) * 1.2, 1)


def _extract_params_b_from_name(model_id: str) -> float | None:
    """Parse parameter count from model name (examples: 7B, 1.5B, 405B)."""
    import re

    tail = model_id.split("/")[-1]
    match = re.search(r"(\d+(?:\.\d+)?)\s*[Bb](?:[^a-zA-Z]|$)", tail)
    if not match:
        return None
    return float(match.group(1))


def _estimate_parameter_count_b(siblings, model_id: str, safetensors_info: object | None = None) -> float | None:
    """Estimate parameters in billions from safetensors size or model name fallback."""
    total_from_safetensors = getattr(safetensors_info, "total", None)
    if isinstance(total_from_safetensors, (int, float)) and total_from_safetensors > 0:
        return round(float(total_from_safetensors) / 1e9, 1)

    total_bytes = sum(
        getattr(s, "size", 0) or 0
        for s in (siblings or [])
        if getattr(s, "rfilename", "").endswith(".safetensors")
    )
    if total_bytes > 0:
        # Default BF16/FP16 weight size ~= 2 bytes per parameter.
        return round((total_bytes / 2) / 1e9, 1)
    return _extract_params_b_from_name(model_id)


def _estimate_vram_from_name(model_id: str) -> float | None:
    """
    Estimate VRAM from the parameter count embedded in the model name.
    Matches patterns like 7B, 8b, 1.5B, 70B, 405B in the model id tail.
    Formula: params_in_billions * 2 bytes (BF16) * 1.2 overhead → GB.
    """
    params_b = _extract_params_b_from_name(model_id)
    if params_b is None:
        return None
    # 2 bytes per param (BF16) + 20% overhead for KV cache / activations
    vram_gb = params_b * 2 * 1.2
    return round(vram_gb, 1)


def _model_id_to_slug(model_id: str) -> str:
    tail = model_id.split("/")[-1]
    slug = tail.lower().replace("_", "-").replace(" ", "-")
    import re
    slug = re.sub(r"[^a-z0-9-]", "", slug)[:48]
    return slug.strip("-")


def _slug_to_display(model_id: str) -> str:
    tail = model_id.split("/")[-1]
    return tail.replace("-", " ").replace("_", " ").title()

_hf_api: HfApi | None = None


def _get_api() -> HfApi:
    global _hf_api
    if _hf_api is None:
        _hf_api = HfApi(token=settings.hf_token or None)
    return _hf_api


def _sibling_names(info: object) -> set[str]:
    siblings = getattr(info, "siblings", None) or []
    names = {
        str(getattr(s, "rfilename", ""))
        for s in siblings
        if str(getattr(s, "rfilename", ""))
    }
    return names


def _has_tokenizer_files(names: set[str]) -> bool:
    tokenizer_markers = (
        "tokenizer.json",
        "tokenizer.model",
        "tokenizer_config.json",
        "spiece.model",
        "vocab.json",
        "merges.txt",
    )
    lowered = {n.lower() for n in names}
    return any(any(n.endswith(marker) for marker in tokenizer_markers) for n in lowered)


# Architectures supported by vLLM (extracted from vllm.model_executor.models.registry)
_VLLM_SUPPORTED_ARCHITECTURES: frozenset[str] = frozenset({
    "AfmoeForCausalLM", "ApertusForCausalLM", "AquilaForCausalLM", "AquilaModel",
    "ArceeForCausalLM", "ArcticForCausalLM", "BaiChuanForCausalLM", "BaichuanForCausalLM",
    "BailingMoeForCausalLM", "BailingMoeV2ForCausalLM", "BambaForCausalLM",
    "BertForSequenceClassification", "BertForTokenClassification", "BertModel",
    "BertSpladeSparseEmbeddingModel", "BgeM3EmbeddingModel", "BloomForCausalLM",
    "CLIPModel", "ChatGLMForConditionalGeneration", "ChatGLMModel",
    "Cohere2ForCausalLM", "CohereForCausalLM", "CwmForCausalLM", "DbrxForCausalLM",
    "DeciLMForCausalLM", "DeepseekForCausalLM", "DeepseekV2ForCausalLM",
    "DeepseekV32ForCausalLM", "DeepseekV3ForCausalLM", "Dots1ForCausalLM",
    "Ernie4_5ForCausalLM", "Ernie4_5_MoeForCausalLM", "Exaone4ForCausalLM",
    "ExaoneForCausalLM", "ExaoneMoEForCausalLM", "Fairseq2LlamaForCausalLM",
    "FalconForCausalLM", "FalconH1ForCausalLM", "FalconMambaForCausalLM",
    "FlexOlmoForCausalLM", "GPT2ForSequenceClassification", "GPT2LMHeadModel",
    "GPTBigCodeForCausalLM", "GPTJForCausalLM", "GPTNeoXForCausalLM",
    "Gemma2ForCausalLM", "Gemma2Model", "Gemma3ForCausalLM", "Gemma3TextModel",
    "Gemma3nForCausalLM", "GemmaForCausalLM", "Glm4ForCausalLM", "Glm4MoeForCausalLM",
    "Glm4MoeLiteForCausalLM", "GlmForCausalLM", "GlmMoeDsaForCausalLM",
    "GptOssForCausalLM", "GraniteForCausalLM", "GraniteMoeForCausalLM",
    "GraniteMoeHybridForCausalLM", "GraniteMoeSharedForCausalLM", "GritLM",
    "Grok1ForCausalLM", "Grok1ModelForCausalLM", "GteModel",
    "GteNewForSequenceClassification", "GteNewModel", "HCXVisionForCausalLM",
    "HF_ColBERT", "HunYuanDenseV1ForCausalLM", "HunYuanMoEV1ForCausalLM",
    "IQuestCoderForCausalLM", "IQuestLoopCoderForCausalLM", "InternLM2ForCausalLM",
    "InternLM2ForRewardModel", "InternLM2VEForCausalLM", "InternLM3ForCausalLM",
    "InternLMForCausalLM", "JAISLMHeadModel", "Jais2ForCausalLM",
    "JambaForCausalLM", "JambaForSequenceClassification", "JinaVLForRanking",
    "KimiLinearForCausalLM", "LLaMAForCausalLM", "Lfm2ForCausalLM",
    "Lfm2MoeForCausalLM", "Llama4ForCausalLM",
    "LlamaBidirectionalForSequenceClassification", "LlamaBidirectionalModel",
    "LlamaForCausalLM", "LlamaModel", "LlavaNextForConditionalGeneration",
    "LongcatFlashForCausalLM", "MPTForCausalLM", "Mamba2ForCausalLM",
    "MambaForCausalLM", "MiMoForCausalLM", "MiMoV2FlashForCausalLM",
    "MiniCPM3ForCausalLM", "MiniCPMForCausalLM", "MiniMaxForCausalLM",
    "MiniMaxM1ForCausalLM", "MiniMaxM2ForCausalLM", "MiniMaxText01ForCausalLM",
    "MistralForCausalLM", "MistralLarge3ForCausalLM", "MistralModel",
    "MixtralForCausalLM", "ModernBertForSequenceClassification",
    "ModernBertForTokenClassification", "ModernBertModel", "MptForCausalLM",
    "NemotronForCausalLM", "NemotronHForCausalLM", "NemotronHPuzzleForCausalLM",
    "NomicBertModel", "OPTForCausalLM", "Olmo2ForCausalLM", "Olmo3ForCausalLM",
    "OlmoForCausalLM", "OlmoeForCausalLM", "OrionForCausalLM", "OuroForCausalLM",
    "PanguEmbeddedForCausalLM", "PanguProMoEV2ForCausalLM", "PanguUltraMoEForCausalLM",
    "PersimmonForCausalLM", "Phi3ForCausalLM", "Phi3VForCausalLM", "PhiForCausalLM",
    "PhiMoEForCausalLM", "Plamo2ForCausalLM", "Plamo3ForCausalLM",
    "PrithviGeoSpatialMAE", "QWenLMHeadModel", "Qwen2ForCausalLM",
    "Qwen2ForProcessRewardModel", "Qwen2ForRewardModel", "Qwen2Model",
    "Qwen2MoeForCausalLM", "Qwen2VLForConditionalGeneration", "Qwen3ForCausalLM",
    "Qwen3MoeForCausalLM", "Qwen3NextForCausalLM", "RWForCausalLM",
    "RobertaForMaskedLM", "RobertaForSequenceClassification", "RobertaModel",
    "SeedOssForCausalLM", "SiglipModel", "SolarForCausalLM",
    "StableLMEpochForCausalLM", "StableLmForCausalLM", "Starcoder2ForCausalLM",
    "Step1ForCausalLM", "Step3TextForCausalLM", "Step3p5ForCausalLM",
    "TeleChat2ForCausalLM", "TeleChatForCausalLM", "TeleFLMForCausalLM",
    "Terratorch", "VoyageQwen3BidirectionalEmbedModel",
    "XLMRobertaForSequenceClassification", "XLMRobertaModel", "XverseForCausalLM",
    "Zamba2ForCausalLM",
})


def _extract_base_model_candidates(info: object) -> list[str]:
    candidates: list[str] = []
    card_data = getattr(info, "cardData", None)
    if isinstance(card_data, dict):
        base = card_data.get("base_model")
        if isinstance(base, str) and base.strip():
            candidates.append(base.strip())
        elif isinstance(base, list):
            candidates.extend(str(item).strip() for item in base if str(item).strip())

    for tag in list(getattr(info, "tags", None) or []):
        if isinstance(tag, str) and tag.startswith("base_model:"):
            value = tag.split(":", 1)[1].strip()
            if value:
                candidates.append(value)

    dedup: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        if c not in seen:
            dedup.append(c)
            seen.add(c)
    return dedup


# Multimodal architectures that support image inputs
_MULTIMODAL_ARCHITECTURES: frozenset[str] = frozenset({
    "Florence2ForConditionalGeneration",
    "LlavaNextForConditionalGeneration",
    "LlavaForConditionalGeneration",
    "LlavaMistralForConditionalGeneration",
    "LlavaLlamaForConditionalGeneration",
    "Qwen2VLForConditionalGeneration",
    "Qwen2VisionLanguageModel",
    "Qwen2VisionTransformer",
    "HCXVisionForCausalLM",
    "MiniCPM3ForCausalLM",
    "MiniCPMForCausalLM",
    "LLaVANextImprovedForConditionalGeneration",
    "MoE-Vision",
    "VisionLanguageModelForCausalLM",
    "XComposerForCausalLM",
    "DeepseekVLForCausalLM",
    "Qwen3ForCausalLM",  # Some Qwen3 versions support vision
    "CharacterGLMForCausalLM",
})

_COMPATIBLE_ARCHITECTURE_OVERRIDES: frozenset[str] = frozenset({
    # vLLM supports Florence-2, but this architecture may lag in static registries.
    "Florence2ForConditionalGeneration",
})

_KNOWN_PIPELINE_TAGS: frozenset[str] = frozenset({
    "automatic-speech-recognition",
    "conversational",
    "feature-extraction",
    "fill-mask",
    "image-classification",
    "image-segmentation",
    "image-text-to-text",
    "image-to-text",
    "object-detection",
    "question-answering",
    "sentence-similarity",
    "summarization",
    "table-question-answering",
    "text-classification",
    "text-generation",
    "text-to-audio",
    "text-to-image",
    "text2text-generation",
    "token-classification",
    "translation",
    "video-text-to-text",
    "visual-question-answering",
    "zero-shot-classification",
})


def _is_multimodal(info: object) -> bool:
    """Check if model supports image/vision inputs."""
    model_config = getattr(info, "config", None) or {}
    architectures: list[str] = model_config.get("architectures", []) if isinstance(model_config, dict) else []
    if architectures:
        return any(arch in _MULTIMODAL_ARCHITECTURES for arch in architectures)

    # Fallback: check model_id and tags for vision keywords
    model_id = getattr(info, "id", "").lower()
    tags = [str(t).lower() for t in (getattr(info, "tags", None) or [])]

    vision_keywords = ["llava", "vision", "multimodal", "visual", "image", "qwen-vl", "deepseek-vl"]
    for keyword in vision_keywords:
        if keyword in model_id or any(keyword in tag for tag in tags):
            return True

    return False


def _normalize_capability(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower().replace("_", "-")
    return normalized or None


def _infer_capabilities(info: object) -> list[str]:
    capabilities: list[str] = []

    pipeline_tag = _normalize_capability(getattr(info, "pipeline_tag", None))
    if pipeline_tag:
        capabilities.append(pipeline_tag)

    for tag in list(getattr(info, "tags", None) or []):
        normalized_tag = _normalize_capability(str(tag))
        if normalized_tag in _KNOWN_PIPELINE_TAGS:
            capabilities.append(normalized_tag)

    if _is_multimodal(info):
        capabilities.append("image")

    deduped: list[str] = []
    seen: set[str] = set()
    for capability in capabilities:
        if capability not in seen:
            deduped.append(capability)
            seen.add(capability)
    return deduped


def _matches_compatibility_override(info: object) -> bool:
    model_config = getattr(info, "config", None) or {}
    architectures: list[str] = model_config.get("architectures", []) if isinstance(model_config, dict) else []
    if any(arch in _COMPATIBLE_ARCHITECTURE_OVERRIDES for arch in architectures):
        return True

    model_id = (getattr(info, "id", "") or "").lower()
    if model_id.startswith("microsoft/florence-2"):
        return True

    tags = {str(tag).lower() for tag in (getattr(info, "tags", None) or [])}
    if "vllm" in tags or "vllm-compatible" in tags:
        return True

    return False


def _is_model_compatible(info: object, api: HfApi, tokenizer_repo_cache: dict[str, bool]) -> bool:
    # Primary check: use architectures from config.json to match against vLLM whitelist.
    model_config = getattr(info, "config", None) or {}
    architectures: list[str] = model_config.get("architectures", []) if isinstance(model_config, dict) else []
    if architectures:
        if any(arch in _VLLM_SUPPORTED_ARCHITECTURES for arch in architectures):
            return True
        if _matches_compatibility_override(info):
            return True

    # Fallback for models without an architectures field (e.g. GGUF-only repos):
    # require at least safetensors/pytorch weights + config.json.
    names = _sibling_names(info)
    lowered = {n.lower() for n in names}
    has_config = "config.json" in names
    has_safetensors = any(n.endswith(".safetensors") or n.endswith(".safetensors.index.json") for n in lowered)
    has_pytorch_bin = any(n.endswith("pytorch_model.bin") or n.endswith("pytorch_model.bin.index.json") for n in lowered)
    if has_safetensors or has_pytorch_bin:
        return has_config

    if _matches_compatibility_override(info):
        return True

    return False


async def list_models(
    query: str = "",
    limit: int = 20,
    sort: str = "downloads",
    task: str = "all",
) -> list[HFModelInfo]:
    task_filter = task.strip().lower() if task else "all"
    try:
        models = list(_get_api().list_models(
            search=query or None,
            task=None if task_filter == "all" else task_filter,
            limit=limit,
            sort=sort if sort in ("downloads", "trending", "likes", "created_at") else "downloads",
        ))
    except HfHubHTTPError as exc:
        raise HuggingFaceError(str(exc)) from exc

    api = _get_api()
    tokenizer_repo_cache: dict[str, bool] = {}
    compatible: list[HFModelInfo] = []

    for m in models:
        try:
            info = api.model_info(m.id, files_metadata=True)
        except HfHubHTTPError:
            continue
        except Exception:
            continue

        if not _is_model_compatible(info, api, tokenizer_repo_cache):
            continue

        compatible.append(
            HFModelInfo(
                model_id=info.id,
                author=info.author,
                pipeline_tag=info.pipeline_tag,
                downloads=info.downloads or 0,
                likes=info.likes or 0,
                tags=list(info.tags or []),
                last_modified=str(info.last_modified) if info.last_modified else None,
                parameter_count_b=_estimate_parameter_count_b(
                    getattr(info, "siblings", None),
                    info.id,
                    getattr(info, "safetensors", None),
                ),
                vram_required_gb=(
                    _estimate_vram_gb(getattr(info, "siblings", None))
                    or _estimate_vram_from_name(info.id)
                ),
                supports_image=_is_multimodal(info),
                capabilities=_infer_capabilities(info),
            )
        )

    return compatible


async def model_info(model_id: str) -> HFModelInfo:
    try:
        info = _get_api().model_info(model_id, files_metadata=True)
    except HfHubHTTPError as exc:
        raise HuggingFaceError(str(exc)) from exc

    return HFModelInfo(
        model_id=info.id,
        author=info.author,
        pipeline_tag=info.pipeline_tag,
        downloads=info.downloads or 0,
        likes=info.likes or 0,
        tags=list(info.tags or []),
        last_modified=str(info.last_modified) if info.last_modified else None,
        parameter_count_b=_estimate_parameter_count_b(
            getattr(info, "siblings", None),
            info.id,
            getattr(info, "safetensors", None),
        ),
        vram_required_gb=(
            _estimate_vram_gb(getattr(info, "siblings", None))
            or _estimate_vram_from_name(info.id)
        ),
        supports_image=_is_multimodal(info),
        capabilities=_infer_capabilities(info),
    )


async def download_model(model_id: str, revision: str | None = None) -> AsyncIterator[dict]:
    """Async generator yielding progress events."""
    yield {"status": "downloading", "model_id": model_id}
    try:
        path = snapshot_download(
            model_id,
            revision=revision,
            cache_dir=settings.hf_cache_dir,
            token=settings.hf_token or None,
        )
        yield {"status": "done", "model_id": model_id, "path": path}
    except HfHubHTTPError as exc:
        raise HuggingFaceError(str(exc)) from exc


async def list_local_models() -> list[LocalModelInfo]:
    results: list[LocalModelInfo] = []
    base = Path(settings.hf_cache_dir)
    if not base.exists():
        return results
    for entry in base.glob("models--*"):
        if not entry.is_dir():
            continue
        model_id = entry.name.replace("models--", "").replace("--", "/")
        size_bytes = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
        size_gb = size_bytes / 1024 ** 3
        # Estimate VRAM from local .safetensors file sizes
        safetensors_bytes = sum(
            f.stat().st_size for f in entry.rglob("*.safetensors") if f.is_file()
        )
        vram_gb = round((safetensors_bytes / 1e9) * 1.2, 1) if safetensors_bytes else None
        results.append(LocalModelInfo(
            model_id=model_id,
            cache_path=str(entry),
            size_gb=round(size_gb, 3),
            vram_required_gb=vram_gb,
        ))
    return results

async def model_prefill(model_id: str) -> ModelPrefill:
    """Lightweight metadata fetch for the Create Instance prefill flow."""
    info = await model_info(model_id)
    return ModelPrefill(
        model_id=model_id,
        suggested_slug=_model_id_to_slug(model_id),
        suggested_display_name=_slug_to_display(model_id),
        vram_required_gb=info.vram_required_gb,
    )