from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_preflight_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "check_local_animation_preflight.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_local_animation_preflight",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_check_asset_preserves_optional_required_flag_when_asset_exists(
    tmp_path: Path,
) -> None:
    preflight = _load_preflight_module()
    asset_path = tmp_path / "models" / "ipadapter" / "optional-faceid.bin"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"ok")

    result = preflight._check_asset(
        "optional-faceid.bin",
        [asset_path],
        result_name="ipadapter_faceid_model",
        required=False,
        missing_detail="missing optional asset",
    )

    assert result.ok is True
    assert result.required is False
    assert "optional-faceid.bin" in result.detail


def test_optional_noobai_checkpoint_accepts_diffusion_models_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = _load_preflight_module()
    comfy_models_dir = tmp_path / "models"
    checkpoint_path = (
        comfy_models_dir / "diffusion_models" / "noobaiXLNAIXL_vPred10Version.safetensors"
    )
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes(b"ok")
    monkeypatch.setattr(preflight, "COMFY_MODELS_DIR", comfy_models_dir)

    result = preflight._check_optional_noobai_checkpoint()

    assert result.ok is True
    assert result.required is False
    assert str(checkpoint_path) in result.detail


def test_run_marks_present_optional_assets_as_optional_pass(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    preflight = _load_preflight_module()

    monkeypatch.setattr(
        preflight,
        "_api_check",
        lambda name, url, success_detail: preflight.CheckResult(
            name=name,
            ok=True,
            detail=success_detail,
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_backend_executor_config",
        lambda: preflight.CheckResult(
            name="backend_animation_executor",
            ok=True,
            detail="executor ready",
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_required_checkpoint",
        lambda: preflight.CheckResult(
            name="ltxv_checkpoint",
            ok=True,
            detail="required checkpoint present",
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_required_text_encoder",
        lambda: preflight.CheckResult(
            name="ltxv_text_encoder",
            ok=True,
            detail="text encoder present",
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_required_ipadapter_model",
        lambda: preflight.CheckResult(
            name="ipadapter_model",
            ok=True,
            detail="general adapter present",
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_required_plus_face_ipadapter_model",
        lambda: preflight.CheckResult(
            name="ipadapter_plus_face_model",
            ok=True,
            detail="plus-face present",
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_required_clip_vision",
        lambda: preflight.CheckResult(
            name="clip_vision_model",
            ok=True,
            detail="clip vision present",
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_optional_faceid_ipadapter_model",
        lambda: preflight.CheckResult(
            name="ipadapter_faceid_model",
            ok=True,
            detail="faceid present",
            required=False,
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_optional_faceid_lora_model",
        lambda: preflight.CheckResult(
            name="ipadapter_faceid_lora",
            ok=True,
            detail="faceid lora present",
            required=False,
        ),
    )
    monkeypatch.setattr(
        preflight,
        "_check_optional_noobai_checkpoint",
        lambda: preflight.CheckResult(
            name="noobai_checkpoint",
            ok=True,
            detail="noobai present",
            required=False,
        ),
    )
    monkeypatch.setattr(preflight, "REQUIRED_NODES", [])
    monkeypatch.setattr(preflight, "REQUIRED_IPADAPTER_NODES", [])

    exit_code = preflight.run()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "[PASS(optional)] ipadapter_faceid_model: faceid present" in output
    assert "[PASS(optional)] noobai_checkpoint: noobai present" in output
