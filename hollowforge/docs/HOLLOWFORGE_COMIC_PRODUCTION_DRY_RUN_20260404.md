# HollowForge Comic Production Dry Run Runbook

Date: 2026-04-04

This runbook covers the production dry-run helper for comic handoff validation. It is meant for operator validation of a real episode/export path, not for smoke-fallback flow testing.

## Canonical Operator Order

1. Confirm the episode already exists and points at the intended character version.
2. Confirm the intended layout template and manuscript profile ids.
3. Confirm every panel has a selected render asset and no placeholder smoke asset paths are present.
4. Run the dry-run helper.
5. Inspect the emitted report JSON and the handoff ZIP.
6. Open the result in CLIP STUDIO EX for manual finishing.

Recommended command:

```bash
cd backend
./.venv/bin/python scripts/launch_comic_production_dry_run.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id <episode_id> \
  --layout-template-id jp_2x2_v1 \
  --manuscript-profile-id jp_manga_rightbound_v1
```

## What Must Be Selected Before Handoff

- Every comic panel must have a selected render asset.
- The selected render asset for each panel must point at a production image path, not `comics/previews/smoke_assets/...`.
- The episode must already be assembled into pages for the target layout and manuscript profile.
- The export ZIP must exist and must contain the final handoff payload, not a synthetic fallback.

The dry-run helper will refuse placeholder smoke asset paths. That is intentional and should be treated as a validation failure, not a warning.

## What To Inspect Inside The ZIP

Verify that the ZIP includes the expected production handoff artifacts:

- the dialogue manifest
- the panel asset manifest
- the page assembly manifest
- the teaser handoff manifest
- the manuscript profile manifest
- the handoff readme
- the production checklist
- the page preview PNGs
- the selected panel asset files

Also verify that:

- no entry path contains `comics/previews/smoke_assets`
- page previews match the intended layout template
- selected assets correspond to the intended panels in order

## What To Do Next In CLIP STUDIO EX

1. Import the exported page previews or open the exported assets in the manuscript workspace.
2. Apply the Japanese right-bound manuscript settings from the selected manuscript profile.
3. Check trim, bleed, and safe-area alignment before drawing on the pages.
4. Place dialogue, captions, and sound effects with right-to-left reading order in mind.
5. Finish line work, tone, and print-ready cleanup.
6. Export the final manuscript from CLIP STUDIO EX using the production naming pattern from the manuscript profile.

If the dry-run helper reports any placeholder asset path, stop before CLIP STUDIO EX and regenerate the selected render assets from production sources first.
