from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComicVerificationProfile:
    name: str
    execution_mode: str
    candidate_count: int
    render_poll_attempts: int
    render_poll_sec: float
    requires_materialized_asset: bool
    allow_synthetic_asset_fallback: bool


SMOKE_PROFILE = ComicVerificationProfile(
    name="smoke",
    execution_mode="local_preview",
    candidate_count=1,
    render_poll_attempts=12,
    render_poll_sec=0.5,
    requires_materialized_asset=False,
    allow_synthetic_asset_fallback=True,
)

FULL_PROFILE = ComicVerificationProfile(
    name="full",
    execution_mode="remote_worker",
    candidate_count=1,
    render_poll_attempts=240,
    render_poll_sec=2.0,
    requires_materialized_asset=True,
    allow_synthetic_asset_fallback=False,
)

_PROFILES = {
    SMOKE_PROFILE.name: SMOKE_PROFILE,
    FULL_PROFILE.name: FULL_PROFILE,
}


def get_profile(name: str) -> ComicVerificationProfile:
    normalized = str(name or "").strip().lower()
    if normalized not in _PROFILES:
        raise ValueError(f"Unknown comic verification profile: {name}")
    return _PROFILES[normalized]
