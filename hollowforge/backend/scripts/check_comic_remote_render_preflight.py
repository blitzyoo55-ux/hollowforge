"""Operational preflight checks for HollowForge comic remote still renders."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
READY_REMOTE_STATUSES = {"ok", "healthy", "ready"}
LOCAL_CALLBACK_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Literal["PASS", "FAIL", "SKIP"]
    detail: str


def _pass(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status="PASS", detail=detail)


def _fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status="FAIL", detail=detail)


def _skip(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status="SKIP", detail=detail)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _parse_http_url(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").strip().lower()
    hostname = (parsed.hostname or "").strip().lower()
    if scheme not in {"http", "https"} or not hostname:
        return None
    return scheme, hostname


def _is_local_http_url(url: str) -> bool:
    parsed = _parse_http_url(url)
    if parsed is None:
        return False
    _, hostname = parsed
    return hostname in LOCAL_CALLBACK_HOSTNAMES


def _fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    request = Request(url, headers=headers or {}, method="GET")
    with urlopen(request, timeout=5) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload or "{}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_stage_status(check: CheckResult, duration_sec: float) -> dict[str, Any]:
    status_map = {
        "PASS": "passed",
        "FAIL": "failed",
        "SKIP": "skipped",
    }
    stage_status: dict[str, Any] = {
        "status": status_map[check.status],
    }
    if duration_sec >= 0:
        stage_status["duration_sec"] = round(duration_sec, 3)
    if check.status == "FAIL":
        stage_status["error_summary"] = check.detail
    return stage_status


def _check_local_backend(base_url: str) -> CheckResult:
    if not _is_local_http_url(base_url):
        return _fail(
            "local_backend_health",
            "check_comic_remote_render_preflight only supports local backend URLs",
        )

    health_url = _join_url(base_url, "/api/v1/system/health")
    try:
        payload = _fetch_json(health_url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return _fail("local_backend_health", f"{health_url}: {exc}")

    status_value = str(payload.get("status") or "").strip().lower()
    db_ok = payload.get("db_ok")
    if status_value != "healthy" or db_ok is False:
        return _fail(
            "local_backend_health",
            f"{health_url} unhealthy status={payload.get('status')!r} db_ok={db_ok!r}",
        )
    return _pass(
        "local_backend_health",
        f"{health_url} status={status_value} db_ok={db_ok!r}",
    )


def _check_callback_base_url(*, worker_base_url: str) -> CheckResult:
    public_api_base_url = settings.PUBLIC_API_BASE_URL.strip()
    if not public_api_base_url:
        return _fail(
            "callback_base_url",
            "HOLLOWFORGE_PUBLIC_API_BASE_URL is not configured",
        )
    if _parse_http_url(public_api_base_url) is None:
        return _fail(
            "callback_base_url",
            "HOLLOWFORGE_PUBLIC_API_BASE_URL must be a valid http(s) URL",
        )

    worker_is_remote = _parse_http_url(worker_base_url) is not None and not _is_local_http_url(
        worker_base_url
    )
    if worker_is_remote and _is_local_http_url(public_api_base_url):
        return _fail(
            "callback_base_url",
            "HOLLOWFORGE_PUBLIC_API_BASE_URL must be worker-reachable for non-local remote workers; loopback is only valid for co-located workers",
        )

    health_url = _join_url(public_api_base_url, "/api/v1/system/health")
    try:
        payload = _fetch_json(health_url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return _fail("callback_base_url", f"{health_url}: {exc}")

    status_value = str(payload.get("status") or "").strip().lower()
    db_ok = payload.get("db_ok")
    if status_value != "healthy" or db_ok is False:
        return _fail(
            "callback_base_url",
            f"{health_url} unhealthy status={payload.get('status')!r} db_ok={db_ok!r}",
        )
    return _pass(
        "callback_base_url",
        f"{health_url} status={status_value} db_ok={db_ok!r}",
    )


def _detect_worker_auth_required(worker_base_url: str) -> bool | None:
    probe_url = _join_url(worker_base_url, "/api/v1/jobs")
    request = Request(probe_url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urlopen(request, timeout=5) as response:
            response.read()
        return False
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return True
        if exc.code in {404, 405}:
            return None
        raise RuntimeError(f"{probe_url} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"{probe_url}: {exc}") from exc


def _check_remote_worker(worker_base_url: str) -> CheckResult:
    if not worker_base_url:
        return _fail(
            "remote_worker_health",
            "HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL is not configured",
        )

    health_url = _join_url(worker_base_url, "/healthz")
    try:
        payload = _fetch_json(health_url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return _fail("remote_worker_health", f"{health_url}: {exc}")

    status_value = str(payload.get("status") or "").strip().lower()
    if status_value not in READY_REMOTE_STATUSES:
        return _fail(
            "remote_worker_health",
            f"{health_url} unhealthy status={payload.get('status')!r}",
        )
    executor_backend = str(payload.get("executor_backend") or "unknown")
    return _pass(
        "remote_worker_health",
        f"{health_url} status={status_value} executor_backend={executor_backend}",
    )


def _check_worker_api_token(*, auth_required: bool | None) -> CheckResult:
    if auth_required is None:
        return _skip("worker_api_token", "auth probe inconclusive")
    if not auth_required:
        return _skip("worker_api_token", "worker auth not required")

    token = settings.ANIMATION_WORKER_API_TOKEN.strip()
    if not token:
        return _fail(
            "worker_api_token",
            "HOLLOWFORGE_ANIMATION_WORKER_API_TOKEN is required when worker auth is enabled",
        )
    return _pass("worker_api_token", "configured for auth-enabled worker")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--worker-url", default=settings.ANIMATION_REMOTE_BASE_URL)
    args = parser.parse_args(argv)

    run_started_monotonic = time.monotonic()
    started_at = _utc_now_iso()
    checks: list[CheckResult] = []
    check_durations: dict[str, float] = {}

    check_start = time.monotonic()
    checks.append(_check_local_backend(args.backend_url))
    check_durations[checks[-1].name] = time.monotonic() - check_start

    check_start = time.monotonic()
    checks.append(_check_remote_worker(args.worker_url))
    check_durations[checks[-1].name] = time.monotonic() - check_start

    check_start = time.monotonic()
    checks.append(_check_callback_base_url(worker_base_url=args.worker_url))
    check_durations[checks[-1].name] = time.monotonic() - check_start

    auth_required: bool | None = False
    worker_ready = checks[1].status == "PASS"
    if worker_ready:
        check_start = time.monotonic()
        try:
            auth_required = _detect_worker_auth_required(args.worker_url)
        except RuntimeError as exc:
            checks.append(_fail("worker_api_token", str(exc)))
        else:
            checks.append(_check_worker_api_token(auth_required=auth_required))
        finally:
            check_durations[checks[-1].name] = time.monotonic() - check_start
    else:
        check_start = time.monotonic()
        checks.append(_skip("worker_api_token", "worker health failed, skipping auth probe"))
        check_durations[checks[-1].name] = time.monotonic() - check_start

    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}")

    overall_success = all(check.status != "FAIL" for check in checks)
    finished_at = _utc_now_iso()
    total_duration_sec = round(time.monotonic() - run_started_monotonic, 3)
    failure_check = next((check for check in checks if check.status == "FAIL"), None)
    payload: dict[str, Any] = {
        "run_mode": "preflight",
        "status": "completed" if overall_success else "failed",
        "overall_success": overall_success,
        "failure_stage": None if failure_check is None else failure_check.name,
        "error_summary": None if failure_check is None else failure_check.detail,
        "base_url": args.backend_url,
        "total_duration_sec": total_duration_sec,
        "started_at": started_at,
        "finished_at": finished_at,
        "stage_status": {
            check.name: _build_stage_status(check, check_durations.get(check.name, 0.0))
            for check in checks
        },
    }

    persistence_ok = False
    try:
        response = _post_json(
            _join_url(args.backend_url, "/api/v1/production/comic-verification/runs"),
            payload,
        )
    except Exception as exc:  # pragma: no cover - exercised in tests
        print("comic_verification_run_persisted: false")
        print(f"comic_verification_run_persist_error: {exc}")
    else:
        persistence_ok = True
        print("comic_verification_run_persisted: true")
        run_id = response.get("id")
        if run_id:
            print(f"comic_verification_run_id: {run_id}")

    return 0 if overall_success and persistence_ok else 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
