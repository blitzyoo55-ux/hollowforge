# HollowForge Review Guide

Use this file with `AGENTS.md` when reviewing changes under HollowForge.

## Focus Areas

- frontend build and deploy completeness
- backend versus public exposure boundaries
- HollowForge to animation-worker contract stability
- operator claims around generation, quality scoring, or sequence pipeline state
- stale runtime docs or handoff notes that point to the wrong entrypoint

## Severity Guide

- `P0`
  - secrets exposure, Zero Trust bypass, wrong public service binding, or
    destructive execution against the wrong environment
- `P1`
  - missing required frontend build, broken backend or worker entrypoint,
    callback-contract regression, invalid smoke or preflight guidance, or
    operator-visible behavior regression
- `P2`
  - stale docs, weak verification evidence, or lower-risk maintainability issue

## Required Verification

Use the narrowest relevant command set and report what was actually run:

```bash
cd frontend && npm run lint && npm run test && npm run build
cd backend && .venv/bin/python scripts/check_local_animation_preflight.py
cd backend && .venv/bin/python scripts/launch_animation_preset_smoke.py --preset-id sdxl_ipadapter_microanim_v2 --generation-id <known-good-id>
```

For docs-only or non-runtime changes, verify the affected references directly
and state why runtime commands were skipped.

## Review Output Shape

- findings first
- severity on every finding
- exact file references
- verification run versus skipped
- remaining operator risks at the end
