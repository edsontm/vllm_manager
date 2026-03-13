from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import VllmError
from app.schemas.instance import InstanceUpdate
from app.services import vllm_service
from app.workers import queue_worker


def _fake_instance(**overrides):
    data = {
        "model_id": "org/model-7b",
        "internal_port": 9003,
        "tensor_parallel_size": 1,
        "gpu_memory_utilization": 0.9,
        "max_model_len": None,
        "quantization": None,
        "dtype": "auto",
        "extra_args": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_build_vllm_args_uses_positional_model() -> None:
    instance = _fake_instance()

    args = vllm_service._build_vllm_args(instance)

    assert args[0] == "org/model-7b"
    assert "--model" not in args
    assert "--host" in args
    assert "--port" in args


def test_prepare_extra_args_for_gguf_auto_adds_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vllm_service, "_infer_tokenizer_repo_for_gguf", lambda _model_id: "google/gemma-3-12b-it")

    prepared = vllm_service._prepare_extra_args_for_model(
        "MaziyarPanahi/gemma-3-12b-it-GGUF",
        {},
    )

    assert prepared["--load-format"] == "gguf"
    assert prepared["--tokenizer"] == "google/gemma-3-12b-it"
    assert prepared["--hf-config-path"] == "google/gemma-3-12b-it"


def test_prepare_extra_args_for_gguf_raises_when_tokenizer_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(vllm_service, "_infer_tokenizer_repo_for_gguf", lambda _model_id: None)

    with pytest.raises(VllmError):
        vllm_service._prepare_extra_args_for_model("MaziyarPanahi/gemma-3-12b-it-GGUF", {})


def test_prepare_extra_args_for_gguf_sets_hf_config_path_from_existing_tokenizer() -> None:
    prepared = vllm_service._prepare_extra_args_for_model(
        "MaziyarPanahi/gemma-3-12b-it-GGUF",
        {"--tokenizer": "google/gemma-3-12b-it", "--load-format": "gguf"},
    )

    assert prepared["--hf-config-path"] == "google/gemma-3-12b-it"


def test_prepare_model_reference_for_vllm_selects_gguf_file(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Sibling:
        def __init__(self, name: str):
            self.rfilename = name

    class _Info:
        siblings = [
            _Sibling("gemma-3-12b-it-q8_0.gguf"),
            _Sibling("gemma-3-12b-it-q4_k_m.gguf"),
        ]

    class _Api:
        def model_info(self, _repo_id: str):
            return _Info()

    monkeypatch.setattr(vllm_service, "HfApi", lambda token=None: _Api())

    resolved = vllm_service._prepare_model_reference_for_vllm(
        "MaziyarPanahi/gemma-3-12b-it-GGUF",
        {"--load-format": "gguf"},
    )

    assert resolved.endswith("/gemma-3-12b-it-q4_k_m.gguf")


def test_build_vllm_args_accepts_model_ref_override() -> None:
    instance = _fake_instance(model_id="org/model")
    args = vllm_service._build_vllm_args(instance, model_ref="org/model/file.gguf")
    assert args[0] == "org/model/file.gguf"


def test_build_container_gpu_device_config_remaps_nonzero_host_gpu() -> None:
    devices, host_gpu_str, container_gpu_str = vllm_service._build_container_gpu_device_config([1])

    assert "/dev/nvidia1:/dev/nvidia0:rwm" in devices
    assert host_gpu_str == "1"
    assert container_gpu_str == "0"


def test_build_container_gpu_device_config_remaps_multi_gpu_selection() -> None:
    devices, host_gpu_str, container_gpu_str = vllm_service._build_container_gpu_device_config([1, 3])

    assert "/dev/nvidia1:/dev/nvidia0:rwm" in devices
    assert "/dev/nvidia3:/dev/nvidia1:rwm" in devices
    assert host_gpu_str == "1,3"
    assert container_gpu_str == "0,1"


def test_candidate_health_urls_prefers_container_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = _fake_instance(container_id="abc123", internal_port=9002)

    monkeypatch.setattr(vllm_service, "_resolve_container_ip", lambda _container_id: "172.30.0.9")

    urls = vllm_service._candidate_health_urls(instance)

    assert urls == [
        "http://172.30.0.9:9002/health",
        "http://127.0.0.1:9002/health",
    ]


def test_apply_startup_stability_defaults_adds_enforce_eager() -> None:
    prepared = vllm_service._apply_startup_stability_defaults({})

    assert prepared["--enforce-eager"] == "true"


def test_apply_startup_stability_defaults_preserves_user_override() -> None:
    prepared = vllm_service._apply_startup_stability_defaults({"--enforce-eager": "false"})

    assert prepared["--enforce-eager"] == "false"


def test_apply_startup_stability_defaults_does_not_force_kv_cache_dtype() -> None:
    prepared = vllm_service._apply_startup_stability_defaults({})

    assert "--kv-cache-dtype" not in prepared


def test_apply_model_compatibility_defaults_downgrades_gemma3_fp8_kv_cache() -> None:
    prepared = vllm_service._apply_model_compatibility_defaults(
        "google/gemma-3-12b-it",
        {"--kv-cache-dtype": "fp8"},
    )

    assert prepared["--kv-cache-dtype"] == "auto"


def test_apply_model_compatibility_defaults_keeps_non_gemma_model_unchanged() -> None:
    prepared = vllm_service._apply_model_compatibility_defaults(
        "meta-llama/Llama-3.1-8B-Instruct",
        {"--kv-cache-dtype": "fp8"},
    )

    assert prepared["--kv-cache-dtype"] == "fp8"


def test_apply_model_compatibility_defaults_relaxes_default_enforce_eager_for_gemma3() -> None:
    prepared = vllm_service._apply_model_compatibility_defaults(
        "google/gemma-3-12b-it",
        {"--enforce-eager": "true"},
    )

    assert "--enforce-eager" not in prepared


def test_apply_model_compatibility_defaults_preserves_user_enforce_eager_for_gemma3() -> None:
    prepared = vllm_service._apply_model_compatibility_defaults(
        "google/gemma-3-12b-it",
        {"--enforce-eager": "true"},
        user_extra_args={"--enforce-eager": "true"},
    )

    assert prepared["--enforce-eager"] == "true"


def test_build_vllm_args_defaults_gemma3_max_model_len_when_unset() -> None:
    instance = _fake_instance(model_id="google/gemma-3-12b-it", max_model_len=None, extra_args={})

    args = vllm_service._build_vllm_args(instance)

    max_len_index = args.index("--max-model-len")
    assert args[max_len_index + 1] == "8192"


def test_build_vllm_args_omits_false_boolean_extra_flag() -> None:
    instance = _fake_instance(extra_args={"--enforce-eager": "false"})

    args = vllm_service._build_vllm_args(instance)

    assert "--enforce-eager" not in args
    assert "false" not in args


def test_apply_creation_time_model_profile_sets_gemma3_defaults() -> None:
    max_len, extra = vllm_service._apply_creation_time_model_profile(
        "google/gemma-3-12b-it",
        max_model_len=None,
        raw_extra_args={},
    )

    assert max_len == 8192
    assert extra["--enable-prefix-caching"] == "true"


def test_apply_creation_time_model_profile_downgrades_gemma3_fp8_kv_cache() -> None:
    max_len, extra = vllm_service._apply_creation_time_model_profile(
        "google/gemma-3-12b-it",
        max_model_len=None,
        raw_extra_args={"--kv-cache-dtype": "fp8"},
    )

    assert max_len == 8192
    assert extra["--kv-cache-dtype"] == "auto"


def test_apply_creation_time_model_profile_keeps_non_gemma_inputs() -> None:
    max_len, extra = vllm_service._apply_creation_time_model_profile(
        "meta-llama/Llama-3.1-8B-Instruct",
        max_model_len=None,
        raw_extra_args={"--foo": "bar"},
    )

    assert max_len is None
    assert extra == {"--foo": "bar"}


@pytest.mark.asyncio
async def test_update_instance_model_applies_gemma_profile_on_model_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _fake_instance(model_id="org/model-7b", max_model_len=None, extra_args={})

    async def _fake_get_instance(_db, _instance_id):
        return instance

    monkeypatch.setattr(vllm_service, "get_instance", _fake_get_instance)

    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    updated = await vllm_service.update_instance_model(db, 1, "google/gemma-3-12b-it")

    assert updated.model_id == "google/gemma-3-12b-it"
    assert updated.max_model_len == 8192
    assert updated.extra_args["--enable-prefix-caching"] == "true"


@pytest.mark.asyncio
async def test_update_instance_applies_gemma_profile_on_model_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _fake_instance(model_id="org/model-7b", max_model_len=None, extra_args={})

    async def _fake_get_instance(_db, _instance_id):
        return instance

    monkeypatch.setattr(vllm_service, "get_instance", _fake_get_instance)

    body = InstanceUpdate(model_id="google/gemma-3-12b-it")
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    updated = await vllm_service.update_instance(db, 1, body)

    assert updated.model_id == "google/gemma-3-12b-it"
    assert updated.max_model_len == 8192
    assert updated.extra_args["--enable-prefix-caching"] == "true"


@pytest.mark.asyncio
async def test_update_instance_preserves_explicit_user_enforce_eager_on_model_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _fake_instance(model_id="org/model-7b", max_model_len=None, extra_args={})

    async def _fake_get_instance(_db, _instance_id):
        return instance

    monkeypatch.setattr(vllm_service, "get_instance", _fake_get_instance)

    body = InstanceUpdate(
        model_id="google/gemma-3-12b-it",
        extra_args={"--enforce-eager": "true"},
    )
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    updated = await vllm_service.update_instance(db, 1, body)

    assert updated.extra_args["--enforce-eager"] == "true"


def test_prepare_model_reference_for_vllm_raises_when_repo_lacks_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Sibling:
        def __init__(self, name: str):
            self.rfilename = name

    class _Info:
        siblings = [_Sibling("gemma-3-12b-it.Q4_K_M.gguf")]

    class _Api:
        def model_info(self, _repo_id: str):
            return _Info()

    monkeypatch.setattr(vllm_service, "HfApi", lambda token=None: _Api())

    with pytest.raises(VllmError, match="does not include config.json"):
        vllm_service._prepare_model_reference_for_vllm(
            "MaziyarPanahi/gemma-3-12b-it-GGUF",
            {"--load-format": "gguf", "--hf-config-path": "google/gemma-3-12b-it"},
        )


def test_decode_job_body_supports_base64_payload() -> None:
    payload = b'{"messages":[{"role":"user","content":[{"type":"text","text":"hi"},{"type":"image_url","image_url":{"url":"https://example.com/x.png"}}]}]}'
    import base64

    body = queue_worker._decode_job_body({"body_b64": base64.b64encode(payload).decode("ascii")})

    assert body == payload


def test_strip_stream_from_json_body_removes_stream_only_for_json() -> None:
    body = b'{"model":"x","stream":true,"messages":[{"role":"user","content":"hi"}]}'

    stripped = queue_worker._strip_stream_from_json_body(body, "application/json")

    assert b'"stream"' not in stripped
    assert b'"messages"' in stripped


def test_strip_stream_from_json_body_keeps_non_json_payload() -> None:
    multipart_like = b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n\r\n..."

    unchanged = queue_worker._strip_stream_from_json_body(multipart_like, "multipart/form-data; boundary=boundary")

    assert unchanged == multipart_like
