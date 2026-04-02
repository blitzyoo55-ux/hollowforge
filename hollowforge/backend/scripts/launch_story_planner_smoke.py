"""Launch a Story Planner preview and queue anchor still candidates."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def _print_catalog_summary(catalog: dict[str, Any]) -> None:
    print("catalog_result:")
    print(f"characters: {len(catalog.get('characters') or [])}")
    print(f"locations: {len(catalog.get('locations') or [])}")
    print(f"policy_packs: {len(catalog.get('policy_packs') or [])}")


def _print_plan_summary(plan: dict[str, Any]) -> None:
    print("plan_result:")
    print(f"lane: {plan.get('lane')}")
    print(f"policy_pack_id: {plan.get('policy_pack_id')}")
    print(f"location: {(plan.get('location') or {}).get('name')}")
    print(f"shot_count: {len(plan.get('shots') or [])}")
    print("preview_success: true")


def _resolve_planner_recommendation(plan: dict[str, Any]) -> tuple[int, str]:
    raw_shot_no = plan.get("recommended_anchor_shot_no")
    try:
        shot_no = int(raw_shot_no)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Planner response did not include a valid recommended_anchor_shot_no: {raw_shot_no!r}"
        ) from exc
    if shot_no < 1:
        raise RuntimeError(
            f"Planner response did not include a valid recommended_anchor_shot_no: {raw_shot_no!r}"
        )

    reason = plan.get("recommended_anchor_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("Planner response did not include a valid recommended_anchor_reason")
    return shot_no, reason


def _resolve_recommended_shot_generations(
    queue_result: dict[str, Any],
    *,
    recommended_anchor_shot_no: int,
) -> list[Any]:
    queued_shots = queue_result.get("queued_shots")
    if not isinstance(queued_shots, list):
        raise RuntimeError("Queue response did not include queued_shots")

    for shot in queued_shots:
        if not isinstance(shot, dict):
            continue
        if shot.get("shot_no") != recommended_anchor_shot_no:
            continue
        generation_ids = shot.get("generation_ids")
        if not isinstance(generation_ids, list) or not generation_ids:
            raise RuntimeError(
                "Queue response did not include generation_ids for the recommended anchor shot"
            )
        return generation_ids

    raise RuntimeError("Queue response did not include queued shots for the recommended anchor shot")


def _print_planner_recommendation(
    *,
    recommended_anchor_shot_no: int,
    recommended_anchor_reason: str,
    queue_result: dict[str, Any],
) -> None:
    recommended_shot_generations = _resolve_recommended_shot_generations(
        queue_result,
        recommended_anchor_shot_no=recommended_anchor_shot_no,
    )

    print("planner_recommendation:")
    print(f"recommended_anchor_shot_no: {recommended_anchor_shot_no}")
    print(f"recommended_anchor_reason: {recommended_anchor_reason}")
    print("recommended_shot_generations:")
    print(
        f"shot_{recommended_anchor_shot_no:02d}: {recommended_shot_generations}"
    )


def _print_queue_summary(queue_result: dict[str, Any]) -> None:
    print("queue_result:")
    print(f"lane: {queue_result.get('lane')}")
    print(f"requested_shot_count: {queue_result.get('requested_shot_count')}")
    print(f"queued_generation_count: {queue_result.get('queued_generation_count')}")
    for shot in queue_result.get("queued_shots") or []:
        print(f"shot_{shot.get('shot_no'):02d}: {shot.get('generation_ids')}")


def _print_operator_links(*, ui_base_url: str) -> None:
    queue_url = f"{ui_base_url.rstrip('/')}/queue"
    gallery_url = f"{ui_base_url.rstrip('/')}/gallery"
    print("operator_links:")
    print(f"queue: {queue_url}")
    print(f"gallery: {gallery_url}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--story-prompt",
        default=(
            "Hana Seo compares notes with a quiet messenger in the "
            "Moonlit Bathhouse corridor after closing."
        ),
    )
    parser.add_argument("--lane", default="unrestricted")
    parser.add_argument("--candidate-count", type=int, default=2)
    parser.add_argument("--lead-character-id", default="hana_seo")
    parser.add_argument("--ui-base-url", default="http://localhost:5173")
    parser.add_argument("--support-description")
    args = parser.parse_args()

    try:
        base_url = args.base_url.rstrip("/")
        catalog = _request_json("GET", f"{base_url}/api/v1/tools/story-planner/catalog")
        _print_catalog_summary(catalog)

        cast = [
            {
                "role": "lead",
                "source_type": "registry",
                "character_id": args.lead_character_id,
            }
        ]
        if args.support_description is not None:
            cast.append(
                {
                    "role": "support",
                    "source_type": "freeform",
                    "freeform_description": args.support_description,
                }
            )

        plan = _request_json(
            "POST",
            f"{base_url}/api/v1/tools/story-planner/plan",
            {
                "story_prompt": args.story_prompt,
                "lane": args.lane,
                "cast": cast,
            },
        )
        _print_plan_summary(plan)
        recommended_anchor_shot_no, recommended_anchor_reason = _resolve_planner_recommendation(
            plan
        )

        queue_result = _request_json(
            "POST",
            f"{base_url}/api/v1/tools/story-planner/generate-anchors",
            {
                "approved_plan": plan,
                "candidate_count": args.candidate_count,
            },
        )
        _print_planner_recommendation(
            recommended_anchor_shot_no=recommended_anchor_shot_no,
            recommended_anchor_reason=recommended_anchor_reason,
            queue_result=queue_result,
        )
        _print_queue_summary(queue_result)
        _print_operator_links(ui_base_url=args.ui_base_url)
        return 0
    except (HTTPError, URLError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
