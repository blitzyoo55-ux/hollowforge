"""Run a script-reproducible adult NSFW pilot rerun through draft publish."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_STORY_PROMPT = (
    "Hana Seo slips through the Moonlit Bathhouse corridor after closing, "
    "trading a charged look with a quiet attendant in a narrow, steam-bright passage."
)
DEFAULT_SUPPORT_DESCRIPTION = "quiet bathhouse attendant in a dark robe with damp hair"
_TERMINAL_NON_SUCCESS_STATUSES = {"failed", "cancelled", "canceled"}


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return parsed


def _wait_for_generation_completion(
    *,
    base_url: str,
    generation_id: str,
    poll_interval_sec: float = 2.0,
    timeout_sec: float = 300.0,
) -> dict[str, Any]:
    status_url = f"{base_url}/api/v1/generations/{generation_id}/status"
    elapsed = 0.0
    latest_status: dict[str, Any] | None = None
    while elapsed < timeout_sec:
        latest_status = _request_json("GET", status_url)
        status = str(latest_status.get("status"))
        if status == "completed":
            return latest_status
        if status in _TERMINAL_NON_SUCCESS_STATUSES:
            raise RuntimeError(
                f"Generation {generation_id} reached terminal non-success status: {status}"
            )
        time.sleep(poll_interval_sec)
        elapsed += poll_interval_sec
    detail = latest_status.get("status") if latest_status else "unknown"
    raise RuntimeError(
        f"Generation {generation_id} never reached completed within {int(timeout_sec)}s "
        f"(last_status={detail})"
    )


def _select_generation_id(
    queue_result: dict[str, Any],
    *,
    select_shot: int,
    select_candidate: int,
) -> str:
    queued_shots = queue_result.get("queued_shots") or []
    selected_shot = next(
        (shot for shot in queued_shots if int(shot.get("shot_no") or 0) == select_shot),
        None,
    )
    if selected_shot is None:
        raise RuntimeError(f"Shot {select_shot} was not queued")
    generation_ids = selected_shot.get("generation_ids") or []
    if select_candidate < 1 or select_candidate > len(generation_ids):
        raise RuntimeError(
            f"Candidate {select_candidate} is out of range for shot {select_shot}"
        )
    generation_id = generation_ids[select_candidate - 1]
    if not isinstance(generation_id, str) or not generation_id:
        raise RuntimeError(
            f"Shot {select_shot} candidate {select_candidate} did not return a generation id"
        )
    return generation_id


def _resolve_select_shot(
    plan_result: dict[str, Any],
    *,
    select_shot: int,
) -> tuple[int, str]:
    if select_shot > 0:
        return select_shot, "operator_override"
    recommended_anchor_shot_no = int(plan_result.get("recommended_anchor_shot_no") or 0)
    if recommended_anchor_shot_no < 1:
        raise RuntimeError("Plan did not provide a valid recommended_anchor_shot_no")
    return recommended_anchor_shot_no, "planner_recommendation"


def _print_section(label: str, payload: dict[str, Any], *, keys: list[str] | None = None) -> None:
    print(f"{label}:")
    selected_keys = keys or list(payload.keys())
    for key in selected_keys:
        print(f"{key}: {payload.get(key)}")


def _queued_generation_ids(queue_result: dict[str, Any]) -> list[str]:
    queued_ids: list[str] = []
    for shot in queue_result.get("queued_shots") or []:
        for generation_id in shot.get("generation_ids") or []:
            if isinstance(generation_id, str) and generation_id:
                queued_ids.append(generation_id)
    return queued_ids


def _render_rerun_log(
    *,
    readiness_result: dict[str, Any],
    plan_result: dict[str, Any],
    queue_result: dict[str, Any],
    selected_generation: dict[str, Any],
    ready_result: dict[str, Any],
    caption_result: dict[str, Any],
    approval_result: dict[str, Any],
    publish_job_result: dict[str, Any],
) -> str:
    queued_generation_ids = ", ".join(_queued_generation_ids(queue_result))
    fixture_summary = (
        f"shot {selected_generation.get('shot_no')} candidate {selected_generation.get('candidate_no')} "
        f"selected for lane {plan_result.get('lane')} on "
        f"{caption_result.get('platform')}/{caption_result.get('channel')} "
        f"{caption_result.get('tone')} {publish_job_result.get('status')} flow"
    )
    return "\n".join(
        [
            "# HollowForge Pilot Rerun Close Loop",
            "",
            "## Close Loop Summary",
            f"- readiness mode: {readiness_result.get('degraded_mode')}",
            f"- plan lane: {plan_result.get('lane')}",
            f"- fixture summary: {fixture_summary}",
            f"- queued generations: {queue_result.get('queued_generation_count')}",
            f"- queued generation ids: {queued_generation_ids}",
            f"- selected shot: {selected_generation.get('shot_no')}",
            f"- selected candidate: {selected_generation.get('candidate_no')}",
            f"- selected generation id: {selected_generation.get('generation_id')}",
            f"- ready publish_approved: {ready_result.get('publish_approved')}",
            f"- ready curated_at: {ready_result.get('curated_at')}",
            f"- caption variant id: {caption_result.get('id')}",
            f"- caption provider: {caption_result.get('provider')}",
            f"- caption model: {caption_result.get('model')}",
            f"- approval approved: {approval_result.get('approved')}",
            f"- approved caption id: {approval_result.get('id')}",
            f"- approved caption variant id: {approval_result.get('id')}",
            f"- draft publish job id: {publish_job_result.get('id')}",
            f"- draft publish status: {publish_job_result.get('status')}",
            f"- draft publish caption_variant_id: {publish_job_result.get('caption_variant_id')}",
            "- outcome: closed-loop draft publish created with no manual UI intervention",
        ]
    )


def _render_rerun_retro(
    *,
    readiness_result: dict[str, Any],
    queue_result: dict[str, Any],
    selected_generation: dict[str, Any],
    ready_result: dict[str, Any],
    approval_result: dict[str, Any],
    publish_job_result: dict[str, Any],
) -> str:
    queued_generation_ids = ", ".join(_queued_generation_ids(queue_result))
    return "\n".join(
        [
            "# HollowForge Pilot Rerun Retro",
            "",
            "## IDs",
            f"- generation id: {selected_generation.get('generation_id')}",
            f"- caption variant id: {approval_result.get('id')}",
            f"- publish job id: {publish_job_result.get('id')}",
            "",
            "## Queue",
            f"- queued generation ids: {queued_generation_ids}",
            "",
            "## Notes",
            (
                f"- ready evidence: publish_approved={ready_result.get('publish_approved')} "
                f"curated_at={ready_result.get('curated_at')}"
            ),
            (
                f"- caption evidence: provider={approval_result.get('provider')} "
                f"model={approval_result.get('model')}"
            ),
            (
                f"- approval evidence: approved={approval_result.get('approved')} "
                f"caption_variant_id={approval_result.get('id')}"
            ),
            f"- approved caption id: {approval_result.get('id')}",
            (
                f"- publish evidence: status={publish_job_result.get('status')} "
                f"caption_variant_id={publish_job_result.get('caption_variant_id')}"
            ),
            (
                "- closed-loop outcome: ready, caption, approve, and draft publish "
                "completed without manual UI intervention."
            ),
            f"- readiness mode at execution: {readiness_result.get('degraded_mode')}",
            "- Validate operator review of the drafted publish payload before external posting.",
        ]
    )


def _write_optional_output(path_value: str | None, rendered: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--ui-base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--lane", default="adult_nsfw")
    parser.add_argument("--candidate-count", type=int, default=2)
    parser.add_argument("--lead-character-id", default="hana_seo")
    parser.add_argument("--support-description", default=DEFAULT_SUPPORT_DESCRIPTION)
    parser.add_argument("--select-shot", type=int, default=0)
    parser.add_argument("--select-candidate", type=int, default=1)
    parser.add_argument("--platform", default="pixiv")
    parser.add_argument("--tone", default="teaser")
    parser.add_argument("--channel", default="social_short")
    parser.add_argument("--log-path")
    parser.add_argument("--retro-path")
    args = parser.parse_args()

    try:
        base_url = args.base_url.rstrip("/")
        _ = args.ui_base_url.rstrip("/")

        readiness_result = _request_json("GET", f"{base_url}/api/v1/publishing/readiness")
        _print_section(
            "readiness_result",
            readiness_result,
            keys=["degraded_mode", "provider", "model"],
        )
        if str(readiness_result.get("degraded_mode")) != "full":
            raise RuntimeError(
                f"Publishing readiness is not full: {readiness_result.get('degraded_mode')}"
            )

        plan_result = _request_json(
            "POST",
            f"{base_url}/api/v1/tools/story-planner/plan",
            {
                "story_prompt": args.story_prompt,
                "lane": args.lane,
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": args.lead_character_id,
                    },
                    {
                        "role": "support",
                        "source_type": "freeform",
                        "freeform_description": args.support_description,
                    },
                ],
            },
        )
        _print_section(
            "plan_result",
            plan_result,
            keys=["lane", "policy_pack_id", "story_prompt"],
        )
        recommended_anchor = {
            "recommended_anchor_shot_no": plan_result.get("recommended_anchor_shot_no"),
            "recommended_anchor_reason": plan_result.get("recommended_anchor_reason"),
        }
        _print_section(
            "recommended_anchor",
            recommended_anchor,
            keys=["recommended_anchor_shot_no", "recommended_anchor_reason"],
        )

        queue_result = _request_json(
            "POST",
            f"{base_url}/api/v1/tools/story-planner/generate-anchors",
            {
                "approved_plan": plan_result,
                "candidate_count": args.candidate_count,
            },
        )
        _print_section(
            "queue_result",
            queue_result,
            keys=["lane", "requested_shot_count", "queued_generation_count"],
        )

        selected_shot, selection_source = _resolve_select_shot(
            plan_result,
            select_shot=args.select_shot,
        )
        generation_id = _select_generation_id(
            queue_result,
            select_shot=selected_shot,
            select_candidate=args.select_candidate,
        )
        selected_generation = {
            "shot_no": selected_shot,
            "candidate_no": args.select_candidate,
            "generation_id": generation_id,
            "selection_source": selection_source,
        }
        _print_section(
            "selected_generation",
            selected_generation,
            keys=["shot_no", "candidate_no", "generation_id", "selection_source"],
        )

        _wait_for_generation_completion(base_url=base_url, generation_id=generation_id)

        generation_result = _request_json("GET", f"{base_url}/api/v1/generations/{generation_id}")
        image_path = generation_result.get("image_path")
        if not isinstance(image_path, str) or not image_path:
            raise RuntimeError(f"Generation {generation_id} has no source image path")
        selected_generation["image_path"] = image_path

        ready_result = _request_json(
            "POST",
            f"{base_url}/api/v1/generations/{generation_id}/ready",
        )
        _print_section(
            "ready_result",
            ready_result,
            keys=["id", "publish_approved", "curated_at"],
        )
        if int(ready_result.get("publish_approved") or 0) != 1:
            raise RuntimeError("ready endpoint did not set publish_approved=1")

        caption_result = _request_json(
            "POST",
            f"{base_url}/api/v1/publishing/generations/{generation_id}/captions/generate",
            {
                "platform": args.platform,
                "tone": args.tone,
                "channel": args.channel,
                "approved": False,
            },
        )
        _print_section(
            "caption_result",
            caption_result,
            keys=["id", "generation_id", "approved", "platform", "tone", "channel", "provider", "model"],
        )

        approval_result = _request_json(
            "POST",
            f"{base_url}/api/v1/publishing/captions/{caption_result['id']}/approve",
        )
        _print_section(
            "approval_result",
            approval_result,
            keys=["id", "generation_id", "approved", "platform", "tone", "channel"],
        )
        if approval_result.get("approved") is not True:
            raise RuntimeError("approval endpoint did not return approved=True")

        publish_job_result = _request_json(
            "POST",
            f"{base_url}/api/v1/publishing/posts",
            {
                "generation_id": generation_id,
                "caption_variant_id": approval_result["id"],
                "platform": args.platform,
                "status": "draft",
            },
        )
        _print_section(
            "publish_job_result",
            publish_job_result,
            keys=["id", "generation_id", "caption_variant_id", "platform", "status"],
        )
        if publish_job_result.get("caption_variant_id") != approval_result["id"]:
            raise RuntimeError("publish job did not retain approved caption_variant_id")

        rerun_log = _render_rerun_log(
            readiness_result=readiness_result,
            plan_result=plan_result,
            queue_result=queue_result,
            selected_generation=selected_generation,
            ready_result=ready_result,
            caption_result=caption_result,
            approval_result=approval_result,
            publish_job_result=publish_job_result,
        )
        rerun_retro = _render_rerun_retro(
            readiness_result=readiness_result,
            queue_result=queue_result,
            selected_generation=selected_generation,
            ready_result=ready_result,
            approval_result=approval_result,
            publish_job_result=publish_job_result,
        )
        _write_optional_output(args.log_path, rerun_log)
        _write_optional_output(args.retro_path, rerun_retro)
        return 0
    except (HTTPError, URLError, RuntimeError, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
