# Story Planner Support Anchoring Design

Date: 2026-04-02

## Goal

Improve HollowForge's `Story Planner` anchor path so freeform support characters stop
drifting into lead-like duplicates, and so operator evaluation follows the planner's
recommended anchor shot instead of accidentally treating the first completed establishing
frame as the representative result.

This branch is a quality branch. It does not change provider routing, checkpoint
selection, publishing behavior, or policy scope.

## Why This Branch Exists

The direct-input anchor branch improved planner recommendation and prompt compilation, but
the first fresh smoke result still looked weak:

- the reviewed image was a `shot_01` establishing frame, not the planner's recommended
  anchor shot
- `shot_01` is the least favorable cut for face detail and relationship clarity
- the support character was freeform and carried no identity metadata
- in a two-person wide shot, the model was free to mirror the lead's face and styling

This means the visible regression came from evaluation path drift and support identity
drift, not from a model or workflow regression.

## Current Failure Shape

Today the planner already returns enough data to choose a better anchor, and the rerun CLI
already respects planner recommendation when no operator override is provided. The gap is
elsewhere:

- `launch_story_planner_smoke.py` still injects a hardcoded freeform support description
  by default
- that hardcoded support can diverge from the actual story prompt
- freeform support entries keep `canonical_anchor`, `anti_drift`, `wardrobe_notes`, and
  `personality_notes` as `none`
- smoke evaluation is easy to misread because operators may look at the first completed
  batch item rather than the recommended shot path

So the system already knows how to recommend a better anchor, but it does not yet preserve
distinct support identity or make the recommended evaluation path obvious enough.

## Non-Goals

This branch will not:

- rewrite the full anchor render compiler
- change checkpoint, sampler, CFG, step count, or workflow lane defaults
- redesign publishing or caption generation
- add a new character database or persist freeform support as canonical registry entries
- introduce a separate evaluation UI

## Approaches Considered

### 1. Smoke-Only Fix

Only update `launch_story_planner_smoke.py` so it highlights the recommended shot and
stops hardcoding a mismatched support description.

Advantages:

- smallest diff
- fixes the immediate comparison mistake

Disadvantages:

- API/UI users still receive freeform support with no identity anchor
- two-person drift remains in actual product behavior

This is not enough.

### 2. Planner-Wide Support Anchoring + Smoke Alignment

Recommended approach.

Advantages:

- fixes the root cause for all product surfaces, not just the smoke script
- makes freeform support materially more stable in anchor batches
- makes evaluation logs and operator review align with planner recommendation

Disadvantages:

- touches planner service and smoke tooling together

This is the right balance between impact and scope.

### 3. Full Render-Compiler Rewrite

Rewrite support handling, shot phrasing, and prompt structure together.

Advantages:

- potentially strongest long-term quality gains

Disadvantages:

- much larger diff
- harder to isolate whether the immediate regression is solved

This is premature for the current problem.

## Recommendation

Use planner-wide support anchoring and align smoke evaluation with the planner's selected
path.

The immediate objective is:

- make freeform support visually distinct from the lead
- remove prompt/cast mismatch in smoke runs
- make recommended-shot evaluation the default comparison path

## Chosen Design

This branch introduces two coordinated changes:

1. `Story Planner` synthesizes a minimal identity pack for freeform support entries
2. `launch_story_planner_smoke.py` treats the planner's recommended shot as the primary
   evaluation path and stops forcing a mismatched default support description

## Scope

This branch will:

- synthesize `canonical_anchor`, `anti_drift`, `wardrobe_notes`, and `personality_notes`
  for freeform support entries
- keep the current API response schema unchanged
- preserve deterministic behavior for the same prompt and support input
- align smoke output around `recommended_anchor_shot_no`
- prefer prompt-derived support over a hardcoded support mismatch when support is not
  explicitly provided

This branch will not:

- introduce LLM-based character synthesis
- mutate registry character entries
- change queueing semantics or candidate counts
- add a new persistence layer for generated support identities

## Support Identity Synthesis

### Target

Only `source_type="freeform"` support entries are synthesized. Registry characters remain
authoritative. Lead behavior is unchanged.

### Inputs

Support identity synthesis uses:

- `freeform_description`
- `story_prompt`
- resolved `location`
- selected `lane`
- resolved lead identity, when present

### Output Fields

The planner fills the existing response fields:

- `canonical_anchor`
- `anti_drift`
- `wardrobe_notes`
- `personality_notes`

No schema change is needed because these fields already exist on
`StoryPlannerResolvedCastEntry`.

### Synthesis Rules

The synthesis stays deterministic and template-driven.

- `canonical_anchor`
  - summarize the freeform support description into a short adult character anchor that
    remains visually distinct from the lead
- `anti_drift`
  - explicitly separate support from the lead, including face, hairstyle, silhouette, and
    styling cues
- `wardrobe_notes`
  - preserve any concrete clothing, texture, or color hint in the support description
- `personality_notes`
  - summarize the support's role or attitude from the story prompt and location context

If the support description is too vague, the planner must still return a minimal distinct
secondary identity rather than leaving these fields blank.

### Lead/Support Separation Rule

The most important rule is preventing mirrored faces and styling. Every synthesized
freeform support entry must carry an anti-drift clause that keeps it visually distinct
from the lead whenever a lead is present.

This branch is not trying to make support richly authored. It is trying to prevent the
support from collapsing into the lead.

## Smoke Evaluation Alignment

### Support Input Behavior

`launch_story_planner_smoke.py` should no longer hardcode a support description that can
contradict the story prompt.

Rules:

- if `--support-description` is explicitly provided, use it
- otherwise do not inject a separate support string
- let the planner infer or merge support from the prompt itself

This keeps the smoke input closer to real operator usage and removes prompt/cast drift.

### Recommended-Shot Evaluation

The smoke command should print:

- `recommended_anchor_shot_no`
- `recommended_anchor_reason`
- the generation ids for the recommended shot in a dedicated section

The full queued shot list remains available, but it becomes secondary. Operators should no
longer treat the first completed batch item as the representative result by default.

### Logging Semantics

Smoke output should make the evaluation path explicit:

- planner recommendation
- any operator override
- which shot should be reviewed first

This keeps later comparisons honest and prevents misleading quality conclusions based on a
raw establishing frame.

## Error Handling

- if planner recommendation is missing or invalid, smoke should fail loudly rather than
  silently defaulting to `shot_01`
- if no support is inferred and none is provided, planner behavior remains valid; support
  synthesis simply does not run
- if freeform support synthesis has too little detail, it should fall back to a minimal
  distinct identity instead of blank metadata

## Testing Strategy

### Backend Planner Tests

Add failing tests first for:

- freeform support entries receive synthesized metadata
- synthesized support anti-drift explicitly separates support from the lead
- vague freeform support still returns non-empty identity metadata

### Smoke CLI Tests

Add failing tests first for:

- omitted `--support-description` no longer injects a mismatched hardcoded support
- output includes a dedicated recommended-shot section
- output clearly indicates the evaluation path to review first

### Verification

Target verification after implementation:

- planner backend test file(s) covering support synthesis
- smoke CLI test file(s)
- one live smoke run confirming the recommended-shot-first review path is legible

## Success Criteria

This branch is successful when all of the following are true:

- freeform support entries no longer return `none` for all identity fields
- two-person anchor prompts include enough support metadata to reduce twin-like drift
- smoke runs no longer inject a support description that contradicts the story prompt
- smoke output makes the planner-recommended review path obvious
- operators can compare quality using the intended anchor path instead of whichever shot
  finishes first
