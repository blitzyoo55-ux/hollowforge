# HollowForge Pause Roadmap

Date: 2026-03-12
Status: Paused pending resume
Owner: Mori / Codex handoff

## Pause Point

HollowForge improvement work is intentionally paused here. The current state is no longer the older brief-in / prompt-out flow. Prompt Factory now has a controllable direction layer, stronger prompt-shaping controls, and a model-specific preference system. Resume from validation and operational hardening, not from foundational feature work.

## Completed In This Iteration

### Prompt Factory controls
- `tone` and `heat_level` now map to stronger generation rules instead of weak string hints.
- Default behavior was pushed toward stronger editorial output while keeping the system configurable.
- UI copy was updated so users can understand what each control actually does.

### Creative autonomy and direction pass
- Added `creative_autonomy` with `strict / hybrid / director`.
- Added `direction_pass_enabled` so the model can first propose scene direction before final prompt rows are written.
- Introduced `direction_pack` as a visible intermediate artifact instead of a hidden internal step.

### Human-in-the-loop editing
- Added `direction_pack_override` so edited direction data can be reused as binding input.
- Frontend now supports preview -> direction edit -> refreshed preview -> queue flow.
- Preview reuse and edited-preview state handling were added to reduce accidental regeneration.

### Checkpoint preference system
- Added per-checkpoint Prompt Factory preferences with modes such as `default / prefer / force / exclude`.
- Default behavior remains unchanged if no per-model preference is configured.
- Frontend settings support search, filtering, save, and reset for these preferences.

### Benchmark cue extraction
- Added favorite-derived cue pack extraction to better preserve benchmark visual language.
- Prompt generation now uses benchmark cue packs and applies safe reinforcement when prompts come back too weak.
- Frontend preview exposes the cue pack so the operator can inspect why a prompt was shaped a certain way.

### Recent operator workflow improvements
- Direction preview/editing is usable from the main Prompt Factory page.
- Queue handoff path was validated after prompt preview.
- A star-scout style exploration flow was started and should be evaluated before more feature work is added.

## Resume Order

1. Review recent scouting and Prompt Factory outputs for hit rate, repetition, and benchmark fidelity.
2. Identify which checkpoint preference profiles should become saved defaults for production use.
3. Tighten direction-pack editing UX where operators still need too many clicks or too much JSON awareness.
4. Add stronger queue observability for long creative batches: status, failures, reuse paths, and auditability.
5. Reassess benchmark cue extraction quality against actual top-performing outputs before adding more prompt logic.

## Recommended Next Tasks

### Product / UX
- Replace any remaining raw JSON editing surfaces with structured field editors where possible.
- Add compact operator views for comparing prompt preview, direction pack, and queued result side by side.
- Add clearer "using edited preview" vs "using fresh preview" indicators in the queue action area.

### Prompt / model quality
- Create checkpoint-specific defaults for autonomy mode, tone, and preferred cue emphasis.
- Add a lightweight review pass to detect weak or repetitive rows before queueing.
- Measure prompt diversity versus benchmark consistency across a fixed validation set.

### Operations
- Add a recent Prompt Factory runs panel with request settings, prompt density summary, and queue links.
- Add a failure bucket for provider response formatting issues and expose retries/recovery in UI.
- Add lightweight metrics for checkpoint usage, keep/drop rate, and preview-to-queue conversion.

## Guardrails For Resume

- Keep the current default behavior backward compatible when optional controls are unset.
- Preserve operator override ability; do not hide creative autonomy behind hardcoded system behavior.
- Validate with live preview before queue-facing changes.
- Treat checkpoint preference configuration as an additive layer, not a replacement for benchmark ranking.

## Definition Of A Good Resume

Work should resume only after the operator can do the following without friction:
- generate a preview,
- inspect and edit direction,
- understand why checkpoints were chosen,
- queue the intended version confidently,
- review results and iterate from observed output rather than guesswork.
