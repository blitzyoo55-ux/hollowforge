"""Launch or monitor a HollowForge animation preset job."""

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


def _print_job_summary(job: dict[str, Any]) -> None:
    print(f"job_id: {job.get('id')}")
    print(f"status: {job.get('status')}")
    print(f"external_job_id: {job.get('external_job_id')}")
    print(f"external_job_url: {job.get('external_job_url')}")
    print(f"output_path: {job.get('output_path')}")
    print(f"error_message: {job.get('error_message')}")
    print(f"submitted_at: {job.get('submitted_at')}")
    print(f"completed_at: {job.get('completed_at')}")


def _load_request_overrides(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("--request-overrides-json must decode to a JSON object")
    return parsed


def _launch_job(
    *,
    base_url: str,
    preset_id: str,
    generation_id: str,
    request_overrides: dict[str, Any],
    dispatch_immediately: bool,
) -> str:
    payload = {
        "generation_id": generation_id,
        "dispatch_immediately": dispatch_immediately,
        "request_overrides": request_overrides,
    }
    response = _request_json(
        "POST",
        f"{base_url.rstrip('/')}/api/v1/animation/presets/{preset_id}/launch",
        payload,
    )
    preset = response.get("preset") or {}
    job = response.get("animation_job") or {}
    print("launch_result:")
    print(f"preset_id: {preset.get('id')}")
    _print_job_summary(job)
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        raise RuntimeError("Launch response did not include animation job id")
    return job_id


def _poll_job(*, base_url: str, job_id: str, poll_sec: float, timeout_sec: float) -> dict[str, Any]:
    start = time.time()
    last_status: str | None = None
    while True:
        job = _request_json(
            "GET",
            f"{base_url.rstrip('/')}/api/v1/animation/jobs/{job_id}",
        )
        status = str(job.get("status") or "")
        if status != last_status:
            print(f"[status] {status}")
            last_status = status
        if status in {"completed", "failed", "cancelled"}:
            return job
        if time.time() - start > timeout_sec:
            raise TimeoutError(f"Timed out waiting for animation job {job_id}")
        time.sleep(max(0.5, poll_sec))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--preset-id", default="sdxl_ipadapter_microanim_v2")
    parser.add_argument("--generation-id")
    parser.add_argument("--job-id")
    parser.add_argument("--poll-sec", type=float, default=5.0)
    parser.add_argument("--timeout-sec", type=float, default=1800.0)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--no-dispatch", action="store_true")
    parser.add_argument("--request-overrides-json")
    args = parser.parse_args()

    if not args.job_id and not args.generation_id:
        parser.error("Provide either --job-id or --generation-id")

    try:
        request_overrides = _load_request_overrides(args.request_overrides_json)
        job_id = args.job_id
        if not job_id:
            job_id = _launch_job(
                base_url=args.base_url,
                preset_id=args.preset_id,
                generation_id=args.generation_id,
                request_overrides=request_overrides,
                dispatch_immediately=not args.no_dispatch,
            )
        if args.no_wait:
            print(f"watch_job_id: {job_id}")
            return 0
        final_job = _poll_job(
            base_url=args.base_url,
            job_id=job_id,
            poll_sec=args.poll_sec,
            timeout_sec=args.timeout_sec,
        )
        print("final_result:")
        _print_job_summary(final_job)
        return 0 if str(final_job.get("status")) == "completed" else 1
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
