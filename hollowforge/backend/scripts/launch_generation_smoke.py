"""Launch or monitor a HollowForge still-image generation job."""

from __future__ import annotations

import argparse
import json
import sys
import time
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


def _resolve_checkpoint(*, base_url: str, explicit_checkpoint: str | None) -> str:
    if explicit_checkpoint and explicit_checkpoint.strip():
        return explicit_checkpoint.strip()

    models = _request_json("GET", f"{base_url.rstrip('/')}/api/v1/system/models")
    checkpoints = models.get("checkpoints")
    if not isinstance(checkpoints, list):
        raise RuntimeError("System models response did not include a checkpoints list")
    for checkpoint in checkpoints:
        normalized = str(checkpoint or "").strip()
        if normalized:
            return normalized
    raise RuntimeError("System models response did not include any usable checkpoint")


def _build_generation_request(
    *,
    prompt: str,
    checkpoint: str,
    request_overrides: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "prompt": prompt,
        "checkpoint": checkpoint,
        "steps": 30,
        "cfg": 5.4,
        "width": 832,
        "height": 1216,
        "sampler": "euler_a",
        "scheduler": "normal",
        "tags": ["smoke", "still-image"],
        "notes": "still-image smoke test",
    }
    payload.update(request_overrides)
    return payload


def _print_generation_summary(generation: dict[str, Any]) -> None:
    print(f"generation_id: {generation.get('id')}")
    print(f"status: {generation.get('status')}")
    print(f"checkpoint: {generation.get('checkpoint')}")
    print(f"image_path: {generation.get('image_path')}")
    print(f"error_message: {generation.get('error_message')}")
    print(f"created_at: {generation.get('created_at')}")
    print(f"completed_at: {generation.get('completed_at')}")


def _load_request_overrides(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("--request-overrides-json must decode to a JSON object")
    return parsed


def _launch_generation(
    *,
    base_url: str,
    prompt: str,
    checkpoint: str,
    request_overrides: dict[str, Any],
) -> str:
    payload = _build_generation_request(
        prompt=prompt,
        checkpoint=checkpoint,
        request_overrides=request_overrides,
    )
    generation = _request_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v1/generations",
        payload,
    )
    print("launch_result:")
    _print_generation_summary(generation)
    generation_id = str(generation.get("id") or "").strip()
    if not generation_id:
        raise RuntimeError("Launch response did not include generation id")
    return generation_id


def _fetch_generation(*, base_url: str, generation_id: str) -> dict[str, Any]:
    return _request_json(
        "GET",
        f"{base_url.rstrip('/')}/api/v1/generations/{generation_id}",
    )


def _poll_generation(
    *,
    base_url: str,
    generation_id: str,
    poll_sec: float,
    timeout_sec: float,
) -> dict[str, Any]:
    start = time.time()
    last_status: str | None = None
    while True:
        status_payload = _request_json(
            "GET",
            f"{base_url.rstrip('/')}/api/v1/generations/{generation_id}/status",
        )
        status = str(status_payload.get("status") or "")
        if status != last_status:
            print(f"[status] {status}")
            last_status = status
        if status in {"completed", "failed", "cancelled"}:
            return _fetch_generation(base_url=base_url, generation_id=generation_id)
        if time.time() - start > timeout_sec:
            raise TimeoutError(f"Timed out waiting for generation {generation_id}")
        time.sleep(max(0.5, poll_sec))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--prompt",
        default=(
            "masterpiece, best quality, original character, adult woman, solo, "
            "studio portrait, calm expression, soft key light, clean composition"
        ),
    )
    parser.add_argument("--checkpoint")
    parser.add_argument("--generation-id")
    parser.add_argument("--poll-sec", type=float, default=5.0)
    parser.add_argument("--timeout-sec", type=float, default=1800.0)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--request-overrides-json")
    args = parser.parse_args()

    try:
        request_overrides = _load_request_overrides(args.request_overrides_json)
        generation_id = args.generation_id
        if not generation_id:
            checkpoint = _resolve_checkpoint(
                base_url=args.base_url,
                explicit_checkpoint=args.checkpoint,
            )
            generation_id = _launch_generation(
                base_url=args.base_url,
                prompt=args.prompt,
                checkpoint=checkpoint,
                request_overrides=request_overrides,
            )
        if args.no_wait:
            print(f"watch_generation_id: {generation_id}")
            return 0
        final_generation = _poll_generation(
            base_url=args.base_url,
            generation_id=generation_id,
            poll_sec=args.poll_sec,
            timeout_sec=args.timeout_sec,
        )
        print("final_result:")
        _print_generation_summary(final_generation)
        return 0 if str(final_generation.get("status")) == "completed" else 1
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
