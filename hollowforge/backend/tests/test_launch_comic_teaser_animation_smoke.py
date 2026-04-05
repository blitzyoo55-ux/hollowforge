from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_teaser_animation_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_teaser_animation_smoke",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_rejects_remote_backend_urls_for_comic_teaser_smoke(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_teaser_animation_smoke.py",
            "--base-url",
            "https://remote.example.com",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "overall_success: false" in captured.out
    assert "failed_step: bootstrap" in captured.out


def test_main_rejects_placeholder_selected_asset(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "storage_path": "comics/previews/smoke_assets/panel-01.png",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "placeholder selected asset is not allowed" in captured.out
