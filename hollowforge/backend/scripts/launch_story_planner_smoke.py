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
    parser.add_argument(
        "--support-description",
        default="quiet messenger in a dark coat",
    )
    args = parser.parse_args()

    try:
        base_url = args.base_url.rstrip("/")
        catalog = _request_json("GET", f"{base_url}/api/v1/tools/story-planner/catalog")
        _print_catalog_summary(catalog)

        plan = _request_json(
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
        _print_plan_summary(plan)

        queue_result = _request_json(
            "POST",
            f"{base_url}/api/v1/tools/story-planner/generate-anchors",
            {
                "approved_plan": plan,
                "candidate_count": args.candidate_count,
            },
        )
        _print_queue_summary(queue_result)
        _print_operator_links(ui_base_url=args.ui_base_url)
        return 0
    except (HTTPError, URLError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
