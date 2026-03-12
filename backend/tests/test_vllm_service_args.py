from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import VllmError
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


def test_apply_startup_stability_defaults_adds_enforce_eager() -> None:
    prepared = vllm_service._apply_startup_stability_defaults({})

    assert prepared["--enforce-eager"] == "true"


def test_apply_startup_stability_defaults_preserves_user_override() -> None:
    prepared = vllm_service._apply_startup_stability_defaults({"--enforce-eager": "false"})

    assert prepared["--enforce-eager"] == "false"


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
