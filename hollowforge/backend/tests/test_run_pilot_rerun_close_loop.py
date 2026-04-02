from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_pilot_rerun_close_loop.py"
    assert module_path.exists(), f"runner missing: {module_path}"
    spec = importlib.util.spec_from_file_location("run_pilot_rerun_close_loop", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(module, argv: list[str], request_json, sleep_fn=None):  # type: ignore[no-untyped-def]
    original_argv = sys.argv
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        sys.argv = argv
        module._request_json = request_json
        if sleep_fn is not None:
            module.time.sleep = sleep_fn
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = module.main()
    finally:
        sys.argv = original_argv
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _plan_result() -> dict[str, object]:
    return {
        "story_prompt": "Bathhouse corridor prompt",
        "lane": "adult_nsfw",
        "policy_pack_id": "canon_adult_nsfw_v1",
        "approval_token": "a" * 64,
        "anchor_render": {
            "policy_pack_id": "canon_adult_nsfw_v1",
            "anchor_prompt": "anchor prompt",
            "negative_prompt": "negative",
            "checkpoint": "wai",
            "width": 832,
            "height": 1216,
            "sampler": "dpmpp_2m",
            "scheduler": "karras",
            "steps": 28,
            "cfg": 6.5,
            "theme_keywords": ["steam"],
            "material_cues": ["tile"],
            "control_cues": ["depth"],
            "camera_cues": ["35mm"],
            "environment_cues": ["corridor"],
            "exposure_cues": ["moonlit"],
            "negative_prompt": "negative",
        },
        "resolved_cast": [
            {
                "role": "lead",
                "source_type": "registry",
                "character_id": "hana_seo",
                "display_name": "Hana Seo",
                "summary": "Lead",
            },
            {
                "role": "support",
                "source_type": "freeform",
                "display_name": "Attendant",
                "summary": "Support",
                "freeform_description": "quiet bathhouse attendant",
            },
        ],
        "location": {
            "name": "Moonlit Bathhouse Corridor",
            "slug": "moonlit_bathhouse_corridor",
            "summary": "Steam and tile",
            "lighting": "soft moonlight",
            "camera_bias": "waist-up",
        },
        "episode_brief": {
            "title": "Closing Time Signal",
            "summary": "Hana tests the corridor hush.",
            "emotional_arc": "curious to teasing",
            "continuity_notes": ["Keep corridor framing consistent."],
        },
        "shots": [
            {
                "shot_no": 1,
                "title": "Entry glance",
                "camera": "wide",
                "framing": "full body",
                "action": "Hana turns into the corridor.",
                "anchor_visuals": ["tile", "steam"],
                "continuity_notes": ["wet hair"],
            },
            {
                "shot_no": 2,
                "title": "Pause",
                "camera": "medium",
                "framing": "mid shot",
                "action": "The attendant closes in.",
                "anchor_visuals": ["robe", "lamp"],
                "continuity_notes": ["same corridor"],
            },
            {
                "shot_no": 3,
                "title": "Signal",
                "camera": "close",
                "framing": "portrait",
                "action": "Hana lifts a finger.",
                "anchor_visuals": ["steam", "necklace"],
                "continuity_notes": ["same props"],
            },
            {
                "shot_no": 4,
                "title": "Departure",
                "camera": "wide",
                "framing": "full body",
                "action": "They part ways.",
                "anchor_visuals": ["corridor exit"],
                "continuity_notes": ["same wardrobe"],
            },
        ],
    }


def _queue_result() -> dict[str, object]:
    return {
        "lane": "adult_nsfw",
        "requested_shot_count": 4,
        "queued_generation_count": 8,
        "queued_shots": [
            {"shot_no": 1, "generation_ids": ["gen-s1-c1", "gen-s1-c2"]},
            {"shot_no": 2, "generation_ids": ["gen-s2-c1", "gen-s2-c2"]},
            {"shot_no": 3, "generation_ids": ["gen-s3-c1", "gen-s3-c2"]},
            {"shot_no": 4, "generation_ids": ["gen-s4-c1", "gen-s4-c2"]},
        ],
    }


def _readiness_result() -> dict[str, object]:
    return {
        "caption_generation_ready": True,
        "draft_publish_ready": True,
        "degraded_mode": "full",
        "provider": "openrouter",
        "model": "grok-vision",
        "missing_requirements": [],
        "notes": [],
    }


def test_select_generation_id_is_deterministic_for_requested_shot_and_candidate() -> None:
    module = _load_module()

    selected = module._select_generation_id(
        _queue_result(),
        select_shot=3,
        select_candidate=2,
    )

    assert selected == "gen-s3-c2"


def test_wait_for_generation_completion_fails_immediately_for_terminal_failure_status() -> None:
    module = _load_module()
    sleeps: list[float] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        assert method == "GET"
        assert url == "http://127.0.0.1:8000/api/v1/generations/gen-s1-c1/status"
        assert payload is None
        return {"id": "gen-s1-c1", "status": "failed", "generation_time_sec": None}

    module._request_json = fake_request_json
    module.time.sleep = lambda seconds: sleeps.append(seconds)

    try:
        module._wait_for_generation_completion(
            base_url="http://127.0.0.1:8000",
            generation_id="gen-s1-c1",
        )
    except RuntimeError as exc:
        assert str(exc) == "Generation gen-s1-c1 reached terminal non-success status: failed"
    else:
        raise AssertionError("expected RuntimeError for terminal failure status")

    assert sleeps == []


def test_runner_stops_when_selected_generation_never_reaches_completed() -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []
    sleeps: list[float] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/publishing/readiness"):
            return _readiness_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            assert payload == {
                "story_prompt": (
                    "Hana Seo slips through the Moonlit Bathhouse corridor after closing, "
                    "trading a charged look with a quiet attendant in a narrow, steam-bright passage."
                ),
                "lane": "adult_nsfw",
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": "hana_seo",
                    },
                    {
                        "role": "support",
                        "source_type": "freeform",
                        "freeform_description": "quiet bathhouse attendant in a dark robe with damp hair",
                    },
                ],
            }
            return _plan_result()
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            assert payload == {
                "approved_plan": _plan_result(),
                "candidate_count": 2,
            }
            return _queue_result()
        if url.endswith("/api/v1/generations/gen-s1-c1/status"):
            return {"id": "gen-s1-c1", "status": "processing", "generation_time_sec": None}
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "run_pilot_rerun_close_loop.py",
            "--base-url",
            "http://127.0.0.1:8000",
        ],
        fake_request_json,
        sleep_fn=lambda seconds: sleeps.append(seconds),
    )

    assert exit_code == 1
    assert "never reached completed" in stdout + stderr
    assert "selected_generation:" in stdout
    assert "shot_no: 1" in stdout
    assert "candidate_no: 1" in stdout
    assert "generation_id: gen-s1-c1" in stdout
    assert all(not url.endswith("/ready") for _, url, _ in calls)
    assert sleeps == [2.0] * 150


def test_runner_executes_ready_caption_approve_publish_in_order() -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/publishing/readiness"):
            return _readiness_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result()
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        if url.endswith("/api/v1/generations/gen-s2-c2/status"):
            return {"id": "gen-s2-c2", "status": "completed", "generation_time_sec": 9.2}
        if url.endswith("/api/v1/generations/gen-s2-c2"):
            return {
                "id": "gen-s2-c2",
                "prompt": "prompt",
                "negative_prompt": "negative",
                "checkpoint": "wai",
                "workflow_lane": "sdxl_illustrious",
                "loras": [],
                "seed": 42,
                "steps": 28,
                "cfg": 6.5,
                "width": 832,
                "height": 1216,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "status": "completed",
                "image_path": "images/gen-s2-c2.png",
                "thumbnail_path": "thumbs/gen-s2-c2.jpg",
                "workflow_path": "workflows/gen-s2-c2.json",
                "created_at": "2026-04-02T00:00:00Z",
                "completed_at": "2026-04-02T00:00:09Z",
            }
        if url.endswith("/api/v1/generations/gen-s2-c2/ready"):
            return {"id": "gen-s2-c2", "publish_approved": 1, "curated_at": "2026-04-02T00:01:00Z"}
        if url.endswith("/api/v1/publishing/generations/gen-s2-c2/captions/generate"):
            assert payload == {
                "platform": "pixiv",
                "tone": "teaser",
                "channel": "social_short",
                "approved": False,
            }
            return {
                "id": "caption-222",
                "generation_id": "gen-s2-c2",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "grok-vision",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#bathhouse",
                "approved": False,
                "created_at": "2026-04-02T00:02:00Z",
                "updated_at": "2026-04-02T00:02:00Z",
            }
        if url.endswith("/api/v1/publishing/captions/caption-222/approve"):
            return {
                "id": "caption-222",
                "generation_id": "gen-s2-c2",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "grok-vision",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#bathhouse",
                "approved": True,
                "created_at": "2026-04-02T00:02:00Z",
                "updated_at": "2026-04-02T00:03:00Z",
            }
        if url.endswith("/api/v1/publishing/posts"):
            assert payload == {
                "generation_id": "gen-s2-c2",
                "caption_variant_id": "caption-222",
                "platform": "pixiv",
                "status": "draft",
            }
            return {
                "id": "publish-job-222",
                "generation_id": "gen-s2-c2",
                "caption_variant_id": "caption-222",
                "platform": "pixiv",
                "status": "draft",
                "scheduled_at": None,
                "published_at": None,
                "external_post_id": None,
                "external_post_url": None,
                "notes": None,
                "created_at": "2026-04-02T00:04:00Z",
                "updated_at": "2026-04-02T00:04:00Z",
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "run_pilot_rerun_close_loop.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--select-shot",
            "2",
            "--select-candidate",
            "2",
        ],
        fake_request_json,
        sleep_fn=lambda seconds: None,
    )

    assert exit_code == 0
    assert stderr == ""
    assert [
        (method, url.rsplit("/api/v1/", 1)[-1])
        for method, url, _ in calls
    ] == [
        ("GET", "publishing/readiness"),
        ("POST", "tools/story-planner/plan"),
        ("POST", "tools/story-planner/generate-anchors"),
        ("GET", "generations/gen-s2-c2/status"),
        ("GET", "generations/gen-s2-c2"),
        ("POST", "generations/gen-s2-c2/ready"),
        ("POST", "publishing/generations/gen-s2-c2/captions/generate"),
        ("POST", "publishing/captions/caption-222/approve"),
        ("POST", "publishing/posts"),
    ]
    assert "selected_generation:" in stdout
    assert "generation_id: gen-s2-c2" in stdout
    assert "ready_result:" in stdout
    assert "caption_result:" in stdout
    assert (
        "caption_result:\n"
        "id: caption-222\n"
        "generation_id: gen-s2-c2\n"
        "approved: False\n"
        "platform: pixiv\n"
        "tone: teaser\n"
        "channel: social_short\n"
        "provider: openrouter\n"
        "model: grok-vision"
    ) in stdout
    assert "approval_result:" in stdout
    assert "publish_job_result:" in stdout


def test_runner_fails_when_ready_postcondition_does_not_hold() -> None:
    module = _load_module()

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if url.endswith("/api/v1/publishing/readiness"):
            return _readiness_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result()
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        if url.endswith("/api/v1/generations/gen-s1-c1/status"):
            return {"id": "gen-s1-c1", "status": "completed", "generation_time_sec": 5.2}
        if url.endswith("/api/v1/generations/gen-s1-c1"):
            return {
                "id": "gen-s1-c1",
                "prompt": "prompt",
                "negative_prompt": "negative",
                "checkpoint": "wai",
                "loras": [],
                "seed": 42,
                "steps": 28,
                "cfg": 6.5,
                "width": 832,
                "height": 1216,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "status": "completed",
                "image_path": "images/gen-s1-c1.png",
                "created_at": "2026-04-02T00:00:00Z",
                "completed_at": "2026-04-02T00:00:05Z",
            }
        if url.endswith("/api/v1/generations/gen-s1-c1/ready"):
            return {"id": "gen-s1-c1", "publish_approved": 0, "curated_at": "2026-04-02T00:01:00Z"}
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        ["run_pilot_rerun_close_loop.py", "--base-url", "http://127.0.0.1:8000"],
        fake_request_json,
        sleep_fn=lambda seconds: None,
    )

    assert exit_code == 1
    assert "ready endpoint did not set publish_approved=1" in stdout + stderr


def test_runner_fails_when_approval_postcondition_does_not_hold() -> None:
    module = _load_module()

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if url.endswith("/api/v1/publishing/readiness"):
            return _readiness_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result()
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        if url.endswith("/api/v1/generations/gen-s1-c1/status"):
            return {"id": "gen-s1-c1", "status": "completed", "generation_time_sec": 5.2}
        if url.endswith("/api/v1/generations/gen-s1-c1"):
            return {
                "id": "gen-s1-c1",
                "prompt": "prompt",
                "negative_prompt": "negative",
                "checkpoint": "wai",
                "loras": [],
                "seed": 42,
                "steps": 28,
                "cfg": 6.5,
                "width": 832,
                "height": 1216,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "status": "completed",
                "image_path": "images/gen-s1-c1.png",
                "created_at": "2026-04-02T00:00:00Z",
                "completed_at": "2026-04-02T00:00:05Z",
            }
        if url.endswith("/api/v1/generations/gen-s1-c1/ready"):
            return {"id": "gen-s1-c1", "publish_approved": 1, "curated_at": "2026-04-02T00:01:00Z"}
        if url.endswith("/api/v1/publishing/generations/gen-s1-c1/captions/generate"):
            return {
                "id": "caption-111",
                "generation_id": "gen-s1-c1",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "grok-vision",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#bathhouse",
                "approved": False,
                "created_at": "2026-04-02T00:02:00Z",
                "updated_at": "2026-04-02T00:02:00Z",
            }
        if url.endswith("/api/v1/publishing/captions/caption-111/approve"):
            return {
                "id": "caption-111",
                "generation_id": "gen-s1-c1",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "grok-vision",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#bathhouse",
                "approved": False,
                "created_at": "2026-04-02T00:02:00Z",
                "updated_at": "2026-04-02T00:03:00Z",
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        ["run_pilot_rerun_close_loop.py", "--base-url", "http://127.0.0.1:8000"],
        fake_request_json,
        sleep_fn=lambda seconds: None,
    )

    assert exit_code == 1
    assert "approval endpoint did not return approved=True" in stdout + stderr


def test_runner_fails_when_draft_publish_is_not_linked_to_approved_caption_variant() -> None:
    module = _load_module()

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if url.endswith("/api/v1/publishing/readiness"):
            return _readiness_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result()
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        if url.endswith("/api/v1/generations/gen-s1-c1/status"):
            return {"id": "gen-s1-c1", "status": "completed", "generation_time_sec": 5.2}
        if url.endswith("/api/v1/generations/gen-s1-c1"):
            return {
                "id": "gen-s1-c1",
                "prompt": "prompt",
                "negative_prompt": "negative",
                "checkpoint": "wai",
                "loras": [],
                "seed": 42,
                "steps": 28,
                "cfg": 6.5,
                "width": 832,
                "height": 1216,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "status": "completed",
                "image_path": "images/gen-s1-c1.png",
                "created_at": "2026-04-02T00:00:00Z",
                "completed_at": "2026-04-02T00:00:05Z",
            }
        if url.endswith("/api/v1/generations/gen-s1-c1/ready"):
            return {"id": "gen-s1-c1", "publish_approved": 1, "curated_at": "2026-04-02T00:01:00Z"}
        if url.endswith("/api/v1/publishing/generations/gen-s1-c1/captions/generate"):
            return {
                "id": "caption-111",
                "generation_id": "gen-s1-c1",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "grok-vision",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#bathhouse",
                "approved": False,
                "created_at": "2026-04-02T00:02:00Z",
                "updated_at": "2026-04-02T00:02:00Z",
            }
        if url.endswith("/api/v1/publishing/captions/caption-111/approve"):
            return {
                "id": "caption-111",
                "generation_id": "gen-s1-c1",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "grok-vision",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#bathhouse",
                "approved": True,
                "created_at": "2026-04-02T00:02:00Z",
                "updated_at": "2026-04-02T00:03:00Z",
            }
        if url.endswith("/api/v1/publishing/posts"):
            return {
                "id": "publish-job-111",
                "generation_id": "gen-s1-c1",
                "caption_variant_id": "caption-other",
                "platform": "pixiv",
                "status": "draft",
                "created_at": "2026-04-02T00:04:00Z",
                "updated_at": "2026-04-02T00:04:00Z",
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        ["run_pilot_rerun_close_loop.py", "--base-url", "http://127.0.0.1:8000"],
        fake_request_json,
        sleep_fn=lambda seconds: None,
    )

    assert exit_code == 1
    assert "publish job did not retain approved caption_variant_id" in stdout + stderr


def test_render_rerun_log_and_retro_include_selected_ids() -> None:
    module = _load_module()

    rendered_log = module._render_rerun_log(
        readiness_result={"degraded_mode": "full", "provider": "openrouter", "model": "grok-vision"},
        plan_result={"lane": "adult_nsfw", "policy_pack_id": "canon_adult_nsfw_v1"},
        queue_result={
            "requested_shot_count": 4,
            "queued_generation_count": 8,
            "queued_shots": [
                {"shot_no": 1, "generation_ids": ["gen-s1-c1", "gen-s1-c2"]},
                {"shot_no": 2, "generation_ids": ["gen-s2-c1", "gen-s2-c2"]},
            ],
        },
        selected_generation={"shot_no": 2, "candidate_no": 1, "generation_id": "gen-s2-c1"},
        ready_result={"publish_approved": 1, "curated_at": "2026-04-02T00:01:00Z"},
        caption_result={
            "id": "caption-222",
            "approved": False,
            "platform": "pixiv",
            "tone": "teaser",
            "channel": "social_short",
            "provider": "openrouter",
            "model": "grok-vision",
        },
        approval_result={
            "id": "caption-222",
            "approved": True,
            "provider": "openrouter",
            "model": "grok-vision",
        },
        publish_job_result={
            "id": "publish-job-222",
            "status": "draft",
            "caption_variant_id": "caption-222",
        },
    )
    rendered_retro = module._render_rerun_retro(
        readiness_result={"degraded_mode": "full"},
        queue_result={
            "queued_shots": [
                {"shot_no": 1, "generation_ids": ["gen-s1-c1", "gen-s1-c2"]},
                {"shot_no": 2, "generation_ids": ["gen-s2-c1", "gen-s2-c2"]},
            ],
        },
        selected_generation={"shot_no": 2, "candidate_no": 1, "generation_id": "gen-s2-c1"},
        ready_result={"publish_approved": 1, "curated_at": "2026-04-02T00:01:00Z"},
        approval_result={
            "id": "caption-222",
            "approved": True,
            "provider": "openrouter",
            "model": "grok-vision",
        },
        publish_job_result={
            "id": "publish-job-222",
            "status": "draft",
            "caption_variant_id": "caption-222",
        },
    )

    assert rendered_log.splitlines() == [
        "# HollowForge Pilot Rerun Close Loop",
        "",
        "## Close Loop Summary",
        "- readiness mode: full",
        "- plan lane: adult_nsfw",
        "- fixture summary: shot 2 candidate 1 selected for lane adult_nsfw on pixiv/social_short teaser draft flow",
        "- queued generations: 8",
        "- queued generation ids: gen-s1-c1, gen-s1-c2, gen-s2-c1, gen-s2-c2",
        "- selected shot: 2",
        "- selected candidate: 1",
        "- selected generation id: gen-s2-c1",
        "- ready publish_approved: 1",
        "- ready curated_at: 2026-04-02T00:01:00Z",
        "- caption variant id: caption-222",
        "- caption provider: openrouter",
        "- caption model: grok-vision",
        "- approval approved: True",
        "- approved caption id: caption-222",
        "- approved caption variant id: caption-222",
        "- draft publish job id: publish-job-222",
        "- draft publish status: draft",
        "- draft publish caption_variant_id: caption-222",
        "- outcome: closed-loop draft publish created with no manual UI intervention",
    ]
    assert rendered_retro.splitlines() == [
        "# HollowForge Pilot Rerun Retro",
        "",
        "## IDs",
        "- generation id: gen-s2-c1",
        "- caption variant id: caption-222",
        "- publish job id: publish-job-222",
        "",
        "## Queue",
        "- queued generation ids: gen-s1-c1, gen-s1-c2, gen-s2-c1, gen-s2-c2",
        "",
        "## Notes",
        "- ready evidence: publish_approved=1 curated_at=2026-04-02T00:01:00Z",
        "- caption evidence: provider=openrouter model=grok-vision",
        "- approval evidence: approved=True caption_variant_id=caption-222",
        "- approved caption id: caption-222",
        "- publish evidence: status=draft caption_variant_id=caption-222",
        "- closed-loop outcome: ready, caption, approve, and draft publish completed without manual UI intervention.",
        "- readiness mode at execution: full",
        "- Validate operator review of the drafted publish payload before external posting.",
    ]
