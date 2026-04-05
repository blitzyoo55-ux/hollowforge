# HollowForge Comic Teaser Derivative Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote one selected comic panel asset from a stable one-shot result into one animation preset job and verify one completed mp4 teaser output.

**Architecture:** Keep the comic side as source truth and reuse the existing stable helpers instead of adding new backend routes. The new helper resolves a real selected panel asset from an exported comic episode, launches an existing animation preset against that asset, polls the existing animation job surface to completion, and validates the resulting mp4 file while preserving comic lineage in its printed summary.

**Tech Stack:** Python 3.11, existing backend helper scripts, FastAPI animation/comic routes, urllib JSON requests, pytest, stable launchd backend, stable launchd animation worker

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for each task.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint.
- Treat [2026-04-05-hollowforge-comic-teaser-derivative-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/docs/superpowers/specs/2026-04-05-hollowforge-comic-teaser-derivative-design.md) as the source spec.
- Reuse existing helpers before adding new request/DB surfaces.
- Do not introduce `animation_shots` persistence in this phase.
- Keep the helper local-backend-only, matching the existing comic production helpers.
- Preserve the current stable runtime path and worker contract.

## File Map

### Helper and tests

- Create: `backend/scripts/launch_comic_teaser_animation_smoke.py`
  - resolves a stable comic teaser source, launches an animation preset, polls for completion, validates mp4 output, and prints lineage markers
- Create: `backend/tests/test_launch_comic_teaser_animation_smoke.py`
  - covers local-backend guardrails, selected asset validation, latest-report fallback, launch success markers, and failure surfaces

### Existing helper reuse

- Reuse from: `backend/scripts/launch_comic_production_dry_run.py`
  - `_ensure_exported_episode()`
  - `_extract_selected_panel_assets()`
- Reuse from: `backend/scripts/launch_animation_preset_smoke.py`
  - `_launch_job()`
  - `_poll_job()`
- Reuse from: `backend/scripts/launch_comic_mvp_smoke.py`
  - `_is_local_backend_url()`
  - `_print_marker()` and JSON request utilities

### Docs

- Modify: `README.md`
  - add the canonical teaser smoke command and required flags
- Modify: `STATE.md`
  - update resume notes with teaser derivative helper and latest validation target

## Task 1: Add The Helper Contract And Local Guardrails

**Files:**
- Create: `backend/tests/test_launch_comic_teaser_animation_smoke.py`
- Create: `backend/scripts/launch_comic_teaser_animation_smoke.py`

- [ ] **Step 1: Write the failing bootstrap tests**

```python
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
```

```python
def test_main_rejects_placeholder_selected_asset(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(module, "_resolve_source_asset", lambda **_: {
        "storage_path": "comics/previews/smoke_assets/panel-01.png",
    })
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "placeholder selected asset is not allowed" in captured.out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: FAIL because the helper script does not exist yet.

- [ ] **Step 3: Add the helper skeleton with summary markers**

Required behavior:

- parse:
  - `--base-url`
  - `--episode-id`
  - `--panel-index`
  - `--preset-id`
  - `--poll-sec`
  - `--timeout-sec`
- print summary markers for:
  - `episode_id`
  - `scene_panel_id`
  - `selected_render_asset_id`
  - `generation_id`
  - `preset_id`
  - `animation_job_id`
  - `output_path`
  - `teaser_success`
  - `overall_success`
- reject non-local backend URLs
- reject placeholder or missing selected asset paths before any animation launch

Minimal skeleton:

```python
def _is_placeholder_asset(storage_path: str) -> bool:
    return storage_path.startswith("comics/previews/smoke_assets/")


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        comic_smoke._print_marker(key, value)
```

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: PASS for the guardrail cases.

- [ ] **Step 5: Commit the helper contract**

```bash
git add backend/scripts/launch_comic_teaser_animation_smoke.py \
  backend/tests/test_launch_comic_teaser_animation_smoke.py
git commit -m "feat(hollowforge): add comic teaser smoke helper contract"
```

## Task 2: Resolve A Real Selected Panel Asset From Stable Comic Output

**Files:**
- Modify: `backend/scripts/launch_comic_teaser_animation_smoke.py`
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`

- [ ] **Step 1: Write the failing source-resolution tests**

```python
def test_main_uses_latest_successful_dry_run_report_when_episode_id_is_missing(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = _load_module()
    report_path = tmp_path / "comic_dry_run.json"
    report_path.write_text(json.dumps({
        "dry_run_success": True,
        "episode_id": "episode-latest-1",
    }))
    monkeypatch.setattr(module, "_find_latest_successful_dry_run_report", lambda: report_path)
    monkeypatch.setattr(module, "_resolve_source_asset", lambda **_: {
        "episode_id": "episode-latest-1",
        "scene_panel_id": "panel-1",
        "selected_render_asset_id": "asset-1",
        "generation_id": "gen-1",
        "storage_path": "outputs/panel-1.png",
    })
    monkeypatch.setattr(module.animation_smoke, "_launch_job", lambda **_: "job-1")
    monkeypatch.setattr(module.animation_smoke, "_poll_job", lambda **_: {
        "id": "job-1",
        "status": "completed",
        "output_path": "outputs/teaser-1.mp4",
    })
    monkeypatch.setattr(module, "_validate_output_path", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 0
```

```python
def test_resolve_source_asset_rejects_missing_selected_assets(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module.comic_dry_run, "_ensure_exported_episode", lambda **_: ({}, {}, {
        "teaser_handoff_manifest_path": "comics/manifests/empty.json",
    }))
    monkeypatch.setattr(module.comic_dry_run, "_extract_selected_panel_assets", lambda *_: [])
    with pytest.raises(RuntimeError, match="No selected panel assets found"):
        module._resolve_source_asset(
            base_url="http://127.0.0.1:8000",
            episode_id="episode-empty",
            panel_index=0,
            layout_template_id="jp_2x2_v1",
            manuscript_profile_id="jp_manga_rightbound_v1",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: FAIL because latest-report fallback and selected-asset resolution are not implemented.

- [ ] **Step 3: Implement comic source resolution**

Required behavior:

- if `--episode-id` is present, use it directly
- otherwise, scan `data/comics/reports/*_dry_run.json` for the newest report with:
  - `dry_run_success == true`
  - non-empty `episode_id`
- call `comic_dry_run._ensure_exported_episode(...)` to reuse the current export path
- call `comic_dry_run._extract_selected_panel_assets(...)`
- choose one entry by `panel_index`
- return:
  - `episode_id`
  - `scene_panel_id`
  - `selected_render_asset_id`
  - `generation_id`
  - `storage_path`

Suggested implementation shape:

```python
def _resolve_source_asset(... ) -> dict[str, Any]:
    _, assembly_detail, _ = comic_dry_run._ensure_exported_episode(...)
    selected_assets = comic_dry_run._extract_selected_panel_assets(assembly_detail)
    if not selected_assets:
        raise RuntimeError("No selected panel assets found for teaser source")
    asset = selected_assets[panel_index]
    return {
        "episode_id": episode_id,
        "scene_panel_id": asset["scene_panel_id"],
        "selected_render_asset_id": asset["id"],
        "generation_id": asset["generation_id"],
        "storage_path": asset["storage_path"],
    }
```

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: PASS for latest-report fallback and selected-asset resolution.

- [ ] **Step 5: Commit the source-resolution flow**

```bash
git add backend/scripts/launch_comic_teaser_animation_smoke.py \
  backend/tests/test_launch_comic_teaser_animation_smoke.py
git commit -m "feat(hollowforge): resolve comic teaser source assets"
```

## Task 3: Launch The Existing Animation Preset And Validate One Mp4

**Files:**
- Modify: `backend/scripts/launch_comic_teaser_animation_smoke.py`
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`

- [ ] **Step 1: Write the failing animation-launch test**

```python
def test_main_launches_animation_preset_and_prints_teaser_success(
    monkeypatch,
    tmp_path,
    capsys,
):
    module = _load_module()
    output_path = tmp_path / "outputs" / "teaser-1.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake-mp4")

    monkeypatch.setattr(module, "_resolve_source_asset", lambda **_: {
        "episode_id": "episode-teaser-1",
        "scene_panel_id": "panel-1",
        "selected_render_asset_id": "asset-1",
        "generation_id": "gen-1",
        "storage_path": "outputs/panel-1.png",
    })
    monkeypatch.setattr(module.animation_smoke, "_launch_job", lambda **kwargs: "job-teaser-1")
    monkeypatch.setattr(module.animation_smoke, "_poll_job", lambda **_: {
        "id": "job-teaser-1",
        "status": "completed",
        "output_path": str(output_path),
    })
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py", "--episode-id", "episode-teaser-1"])

    assert module.main() == 0
    captured = capsys.readouterr()
    assert "preset_id: sdxl_ipadapter_microanim_v2" in captured.out
    assert "animation_job_id: job-teaser-1" in captured.out
    assert "teaser_success: true" in captured.out
    assert "overall_success: true" in captured.out
```

```python
def test_main_fails_when_animation_job_completes_without_mp4(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(module, "_resolve_source_asset", lambda **_: {
        "episode_id": "episode-teaser-1",
        "scene_panel_id": "panel-1",
        "selected_render_asset_id": "asset-1",
        "generation_id": "gen-1",
        "storage_path": "outputs/panel-1.png",
    })
    monkeypatch.setattr(module.animation_smoke, "_launch_job", lambda **_: "job-teaser-1")
    monkeypatch.setattr(module.animation_smoke, "_poll_job", lambda **_: {
        "id": "job-teaser-1",
        "status": "completed",
        "output_path": "outputs/teaser-1.png",
    })
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py", "--episode-id", "episode-teaser-1"])
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "completed animation job did not produce an mp4 output" in captured.out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: FAIL because the helper does not yet launch the preset or validate mp4 output.

- [ ] **Step 3: Implement preset launch, polling, and mp4 validation**

Required behavior:

- default `preset_id = "sdxl_ipadapter_microanim_v2"`
- launch via `animation_smoke._launch_job(...)` with:
  - `generation_id = selected source generation id`
  - `preset_id = chosen preset`
  - `dispatch_immediately = True`
- poll via `animation_smoke._poll_job(...)`
- fail unless:
  - job status is `completed`
  - `output_path` is non-empty
  - path ends with `.mp4`
  - local file exists

Suggested validation:

```python
def _validate_output_path(output_path: str) -> None:
    if not output_path or not output_path.endswith(".mp4"):
        raise RuntimeError("Completed animation job did not produce an mp4 output")
    output_file = Path(output_path)
    if not output_file.is_absolute():
        output_file = settings.DATA_DIR / output_path
    if not output_file.exists():
        raise RuntimeError(f"Animation output is missing: {output_path}")
```

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: PASS for success and mp4 validation cases.

- [ ] **Step 5: Commit the animation bridge**

```bash
git add backend/scripts/launch_comic_teaser_animation_smoke.py \
  backend/tests/test_launch_comic_teaser_animation_smoke.py
git commit -m "feat(hollowforge): launch comic teaser animation preset"
```

## Task 4: Document And Live-Verify The Canonical Teaser Flow

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`

- [ ] **Step 1: Add the failing doc-oriented regression test**

```python
def test_main_defaults_to_stable_teaser_preset(monkeypatch, capsys):
    module = _load_module()
    launch_args = {}

    def fake_launch_job(**kwargs):
        launch_args.update(kwargs)
        return "job-default-preset"

    monkeypatch.setattr(module, "_resolve_source_asset", lambda **_: {
        "episode_id": "episode-doc-1",
        "scene_panel_id": "panel-1",
        "selected_render_asset_id": "asset-1",
        "generation_id": "gen-1",
        "storage_path": "outputs/panel-1.png",
    })
    monkeypatch.setattr(module.animation_smoke, "_launch_job", fake_launch_job)
    monkeypatch.setattr(module.animation_smoke, "_poll_job", lambda **_: {
        "id": "job-default-preset",
        "status": "completed",
        "output_path": "outputs/teaser-1.mp4",
    })
    monkeypatch.setattr(module, "_validate_output_path", lambda *_: None)
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py", "--episode-id", "episode-doc-1"])

    assert module.main() == 0
    assert launch_args["preset_id"] == "sdxl_ipadapter_microanim_v2"
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py::test_main_defaults_to_stable_teaser_preset
```

Expected: FAIL until docs and default wiring are finalized.

- [ ] **Step 3: Update docs and default runbook**

README additions:

- canonical command:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800
```

STATE additions:

- note the latest validated comic episode id
- note that teaser validation expects stable launchd backend + stable launchd animation worker
- note that the helper is local-backend-only

- [ ] **Step 4: Run full verification and the live helper**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800
```

Expected:

- tests PASS
- helper prints:
  - `teaser_success: true`
  - `overall_success: true`
  - one non-empty `animation_job_id`
  - one `.mp4` `output_path`

- [ ] **Step 5: Commit docs and verification lane**

```bash
git add backend/scripts/launch_comic_teaser_animation_smoke.py \
  backend/tests/test_launch_comic_teaser_animation_smoke.py \
  README.md \
  STATE.md
git commit -m "docs(hollowforge): add comic teaser animation smoke runbook"
```
