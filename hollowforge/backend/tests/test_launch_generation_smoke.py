from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "launch_generation_smoke.py"
    spec = importlib.util.spec_from_file_location("launch_generation_smoke", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_checkpoint_prefers_explicit_cli_value() -> None:
    module = _load_module()

    def fail_request_json(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("model lookup should not happen when checkpoint is provided")

    module._request_json = fail_request_json

    assert module._resolve_checkpoint(
        base_url="http://127.0.0.1:8000",
        explicit_checkpoint="waiIllustriousSDXL_v160.safetensors",
    ) == "waiIllustriousSDXL_v160.safetensors"


def test_resolve_checkpoint_uses_first_model_when_not_provided() -> None:
    module = _load_module()

    calls: list[tuple[str, str]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url))
        return {
            "checkpoints": [
                "prefectIllustriousXL_v70.safetensors",
                "waiIllustriousSDXL_v160.safetensors",
            ]
        }

    module._request_json = fake_request_json

    checkpoint = module._resolve_checkpoint(
        base_url="http://127.0.0.1:8000",
        explicit_checkpoint=None,
    )

    assert checkpoint == "prefectIllustriousXL_v70.safetensors"
    assert calls == [("GET", "http://127.0.0.1:8000/api/v1/system/models")]


def test_build_generation_request_applies_overrides() -> None:
    module = _load_module()

    payload = module._build_generation_request(
        prompt="smoke portrait prompt",
        checkpoint="prefectIllustriousXL_v70.safetensors",
        request_overrides={"width": 1024, "tags": ["smoke", "still-image"]},
    )

    assert payload["prompt"] == "smoke portrait prompt"
    assert payload["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
    assert payload["width"] == 1024
    assert payload["tags"] == ["smoke", "still-image"]
