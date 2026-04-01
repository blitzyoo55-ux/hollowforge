"""Smoke test publishing readiness and caption generation."""

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


def _print_readiness_summary(readiness: dict[str, Any]) -> None:
    print("readiness_result:")
    print(f"readiness_mode: {readiness.get('degraded_mode')}")
    print(f"provider: {readiness.get('provider')}")
    print(f"model: {readiness.get('model')}")


def _print_caption_summary(caption: dict[str, Any]) -> None:
    print("caption_result:")
    print(f"generation_id: {caption.get('generation_id')}")
    print(f"caption_id: {caption.get('id')}")
    print(f"approved: {str(bool(caption.get('approved'))).lower()}")
    print(f"provider: {caption.get('provider')}")
    print(f"model: {caption.get('model')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--generation-id", default="7056ca96-dc29-4421-996d-ca2fc47d7894")
    parser.add_argument("--platform", default="pixiv")
    parser.add_argument("--tone", default="teaser")
    parser.add_argument("--channel", default="social_short")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--readiness-only", action="store_true")
    args = parser.parse_args()

    try:
        base_url = args.base_url.rstrip("/")
        readiness = _request_json("GET", f"{base_url}/api/v1/publishing/readiness")
        _print_readiness_summary(readiness)

        if str(readiness.get("degraded_mode")) != "full":
            print(
                f"[ERROR] Publishing readiness is not full: {readiness.get('degraded_mode')}",
                file=sys.stderr,
            )
            return 1

        if args.readiness_only:
            return 0

        caption = _request_json(
            "POST",
            f"{base_url}/api/v1/publishing/generations/{args.generation_id}/captions/generate",
            {
                "platform": args.platform,
                "tone": args.tone,
                "channel": args.channel,
                "approved": bool(args.approved),
            },
        )
        _print_caption_summary(caption)
        return 0
    except (HTTPError, URLError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
