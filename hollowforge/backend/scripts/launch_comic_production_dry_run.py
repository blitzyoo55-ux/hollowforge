"""Run a production dry-run for comic handoff validation."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
PLACEHOLDER_ASSET_MARKER = "comics/previews/smoke_assets"
DEFAULT_LAYOUT_TEMPLATE_ID = "jp_2x2_v1"
DEFAULT_MANUSCRIPT_PROFILE_ID = "jp_manga_rightbound_v1"


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    if not body.strip():
        return {}
    return json.loads(body)


def _build_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    url = f"{base_url.rstrip('/')}{path}"
    if not params:
        return url

    from urllib.parse import urlencode

    encoded = urlencode(
        {key: value for key, value in params.items() if value is not None and value != ""}
    )
    return f"{url}?{encoded}" if encoded else url


def _require_object(payload: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object for {label}")
    return payload


def _require_list(payload: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(f"Expected JSON list for {label}")
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError(f"Expected JSON object rows for {label}")
        rows.append(item)
    return rows


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_data_path(path: Path) -> str:
    return str(path.resolve().relative_to(settings.DATA_DIR.resolve())).replace("\\", "/")


def _print_marker(key: str, value: Any) -> None:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    print(f"{key}: {rendered}")


def _reports_dir() -> Path:
    return settings.DATA_DIR / "comics" / "reports"


def _extract_panel_ids(episode_detail: dict[str, Any]) -> list[str]:
    scenes = episode_detail.get("scenes")
    if not isinstance(scenes, list):
        raise RuntimeError("Comic episode detail is missing scenes")

    panel_ids: list[str] = []
    for scene_detail in scenes:
        if not isinstance(scene_detail, dict):
            continue
        panels = scene_detail.get("panels")
        if not isinstance(panels, list):
            continue
        for panel in panels:
            if not isinstance(panel, dict):
                continue
            panel_id = str(panel.get("id") or "").strip()
            if panel_id:
                panel_ids.append(panel_id)
    if not panel_ids:
        raise RuntimeError("Comic episode detail did not include any panel ids")
    return panel_ids


def _extract_selected_panel_assets(assembly_detail: dict[str, Any]) -> list[dict[str, Any]]:
    teaser_handoff_manifest_path = str(
        assembly_detail.get("teaser_handoff_manifest_path") or ""
    ).strip()
    if not teaser_handoff_manifest_path:
        raise RuntimeError("Comic assembly detail is missing teaser_handoff_manifest_path")

    manifest_path = settings.DATA_DIR / teaser_handoff_manifest_path
    if not manifest_path.is_file():
        raise RuntimeError(f"Comic teaser handoff manifest not found: {manifest_path}")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected_assets = payload.get("selected_panel_assets") if isinstance(payload, dict) else None
    assets = _require_list(selected_assets or [], label="selected_panel_assets")
    for asset in assets:
        storage_path = str(asset.get("storage_path") or "").strip()
        if PLACEHOLDER_ASSET_MARKER in storage_path:
            raise RuntimeError(
                f"Refusing placeholder comic asset path in production dry-run: {storage_path}"
            )
    return assets


def _validate_export_zip(export_zip_path: str) -> None:
    zip_path = settings.DATA_DIR / export_zip_path
    if not zip_path.is_file():
        raise RuntimeError(f"Comic export ZIP not found: {zip_path}")

    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if PLACEHOLDER_ASSET_MARKER in name:
                raise RuntimeError(
                    f"Refusing placeholder comic asset path in export ZIP: {name}"
                )


def _write_report(
    *,
    episode_id: str,
    layout_template_id: str,
    manuscript_profile_id: str,
    episode_detail: dict[str, Any],
    assembly_detail: dict[str, Any],
    export_detail: dict[str, Any],
    selected_panel_assets: list[dict[str, Any]],
) -> Path:
    _reports_dir().mkdir(parents=True, exist_ok=True)
    report_path = _reports_dir() / (
        f"{episode_id}_{layout_template_id}_{manuscript_profile_id}_dry_run.json"
    )
    report = {
        "episode_id": episode_id,
        "layout_template_id": layout_template_id,
        "manuscript_profile_id": manuscript_profile_id,
        "panel_count": len(_extract_panel_ids(episode_detail)),
        "selected_panel_asset_count": len(selected_panel_assets),
        "page_count": len(export_detail.get("pages") or []),
        "export_zip_path": export_detail.get("export_zip_path"),
        "teaser_handoff_manifest_path": export_detail.get("teaser_handoff_manifest_path"),
        "episode_detail": episode_detail,
        "assembly_detail": assembly_detail,
        "export_detail": export_detail,
        "teaser_handoff_manifest": {
            "selected_panel_assets": selected_panel_assets,
        },
        "created_at": _now_iso(),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _ensure_exported_episode(
    *,
    base_url: str,
    episode_id: str,
    layout_template_id: str,
    manuscript_profile_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    episode_detail = _require_object(
        _request_json("GET", _build_url(base_url, f"/api/v1/comic/episodes/{episode_id}")),
        label="comic episode detail",
    )
    pages = _require_list(episode_detail.get("pages") or [], label="comic episode pages")
    needs_assemble = not pages

    assembly_detail: dict[str, Any] = {
        "episode_id": episode_id,
        "layout_template_id": layout_template_id,
        "manuscript_profile_id": manuscript_profile_id,
    }
    if needs_assemble:
        assembly_detail = _require_object(
            _request_json(
                "POST",
                _build_url(
                    base_url,
                    f"/api/v1/comic/episodes/{episode_id}/pages/assemble",
                    {
                        "layout_template_id": layout_template_id,
                        "manuscript_profile_id": manuscript_profile_id,
                    },
                ),
            ),
            label="comic episode assembly",
        )

    export_detail = _require_object(
        _request_json(
            "POST",
            _build_url(
                base_url,
                f"/api/v1/comic/episodes/{episode_id}/pages/export",
                {
                    "layout_template_id": layout_template_id,
                    "manuscript_profile_id": manuscript_profile_id,
                },
            ),
        ),
        label="comic episode export",
    )
    if not needs_assemble:
        assembly_detail = export_detail

    episode_detail = _require_object(
        _request_json("GET", _build_url(base_url, f"/api/v1/comic/episodes/{episode_id}")),
        label="comic episode detail",
    )
    return episode_detail, assembly_detail, export_detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--layout-template-id", default=DEFAULT_LAYOUT_TEMPLATE_ID)
    parser.add_argument(
        "--manuscript-profile-id",
        default=DEFAULT_MANUSCRIPT_PROFILE_ID,
    )
    args = parser.parse_args()

    episode_detail, assembly_detail, export_detail = _ensure_exported_episode(
        base_url=args.base_url,
        episode_id=args.episode_id,
        layout_template_id=args.layout_template_id,
        manuscript_profile_id=args.manuscript_profile_id,
    )
    panel_ids = _extract_panel_ids(episode_detail)
    selected_panel_assets = _extract_selected_panel_assets(assembly_detail)
    _validate_export_zip(str(export_detail.get("export_zip_path") or ""))

    report_path = _write_report(
        episode_id=args.episode_id,
        layout_template_id=args.layout_template_id,
        manuscript_profile_id=args.manuscript_profile_id,
        episode_detail=episode_detail,
        assembly_detail=assembly_detail,
        export_detail=export_detail,
        selected_panel_assets=selected_panel_assets,
    )

    _print_marker("dry_run_success", True)
    _print_marker("episode_id", args.episode_id)
    _print_marker("panel_count", len(panel_ids))
    _print_marker("selected_panel_asset_count", len(selected_panel_assets))
    _print_marker("page_count", len(export_detail.get("pages") or []))
    _print_marker("manuscript_profile_id", args.manuscript_profile_id)
    _print_marker("report_path", _relative_data_path(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
