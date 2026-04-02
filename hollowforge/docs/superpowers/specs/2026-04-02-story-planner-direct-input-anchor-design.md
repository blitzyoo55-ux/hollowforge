# Story Planner Direct Input Anchor Design

Date: 2026-04-02

## Goal

Improve HollowForge so a user can enter one natural-language episode idea directly in
`Story Planner`, have the system interpret it reliably, and produce a stronger
anchor-ready render prompt and generation path without requiring an operator to handhold
shot selection or prompt cleanup.

This branch has two product goals:

- make direct authoring through `Story Planner` the primary human input surface
- improve anchor selection and prompt compilation so `adult_nsfw` runs no longer default
  to generic establishing shots when a later shot would better represent the intended
  scene

This is a quality and usability branch, not a policy-relaxation branch.

## Why This Branch Exists

The recent pilot rerun proved the operational loop can close from:

- story plan
- anchor generation
- ready
- caption generation
- caption approval
- draft publish creation

However, the actual image selected by the rerun looked closer to an all-ages or general
scene setup than to the adult-targeted mood the lane implied. The reason was not a
runtime failure. It was a product-shape problem:

- the rerun script defaulted to `shot 1 / candidate 1`
- `shot 1` is always an establishing shot
- the planner builds the same four-shot scaffold regardless of lane
- the anchor prompt is still closer to a story memo than to a strong render intent

So the next meaningful improvement is not more publishing work. It is making the input
surface and anchor path interpret natural-language intent better.

## Current System Fit

The existing architecture already has the right seams:

- the web UI already exposes `Story Planner` as a dedicated mode inside
  `Prompt Factory`
- the backend already accepts a compact authoring contract:
  - `story_prompt`
  - `lane`
  - optional `cast`
- the planner already resolves:
  - cast
  - location
  - episode brief
  - four-shot plan
- the queue step already turns an approved plan into deterministic anchor generations
- the rerun CLI already exercises the same routes the UI uses

This means the branch should improve the existing path, not introduce a parallel input
system.

## Non-Goals

This branch will not do the following:

- redesign the full `Prompt Factory` advanced mode
- introduce a separate authoring application
- change publishing or external posting behavior
- change caption provider routing or platform readiness rules
- redesign the character/episode schema
- expand the system into a separate sequence-orchestration rewrite

## Approaches Considered

### 1. Selection-First Only

Only change the default selected shot for adult reruns so the system stops picking the
establishing frame.

Advantages:

- smallest diff
- very fast to validate

Disadvantages:

- planner output quality stays mostly unchanged
- direct web input still feels underpowered
- prompt quality still depends too much on raw story wording

This would help, but it would not solve the actual product problem.

### 2. Compiler-First Only

Keep planner output unchanged and add a render-intent compiler layer before queueing
generation.

Advantages:

- better render prompts from the same story text
- preserves current UI

Disadvantages:

- shot selection remains weak
- anchor recommendation still defaults to operator taste or CLI overrides

This improves prompts but leaves the input-to-shot path too passive.

### 3. Hybrid: Direct Input UX + Lane-Aware Shot Selection + Thin Compiler

Recommended approach.

Advantages:

- improves direct authoring without inventing a new tool
- fixes the most visible cause of weak results: default selection behavior
- makes planner output more informative by returning a recommended anchor shot
- keeps the implementation bounded to the `Story Planner` anchor path

Disadvantages:

- touches backend models, planner logic, rerun CLI, and the web UI together

This is the right tradeoff. The problem is not isolated to one layer.

## Recommendation

Use the hybrid approach, but keep the scope bounded to:

- `Story Planner` web UI
- planner request/response contract
- shot-building logic
- anchor prompt compilation
- rerun CLI default selection behavior

Do not redesign unrelated authoring or publishing surfaces in this branch.

## Chosen Design

The branch will introduce four coordinated changes:

1. keep `Story Planner` as the primary direct-input surface, centered around one large
   natural-language prompt field
2. expand the planner request and response so it can accept optional guidance and return
   a recommended anchor shot
3. make shot construction lane-aware so the adult lane produces stronger anchor-ready
   later shots while preserving a stable establishing frame
4. add a thin deterministic anchor compiler that translates planner output into more
   render-friendly prompt structure

## Scope

This branch will do the following:

- preserve the current one-field authoring experience
- add optional guidance controls in the web UI
- extend the planner contract with optional location and anchor-beat preferences
- return planner-side anchor recommendations
- use planner recommendation as the default selection in rerun automation
- improve later-shot output quality for `adult_nsfw`
- improve how anchor prompts are assembled from planner data

This branch will not:

- add a new LLM layer to compile prompts
- create a separate prompt-editing product
- replace manual override capability
- remove the existing CLI or API paths

## Input UX Design

### Primary Direct Input Surface

The main authoring surface remains `Story Planner` in the existing web UI. This is the
recommended operator path for direct use without going through an assistant.

The authoring model stays:

- one large `Story Prompt` field for natural-language input
- optional controls that sharpen, rather than replace, freeform writing

This preserves the current product shape while making it more useful.

### Optional Guidance Controls

The right-side panel should continue to hold optional guidance. This branch adds four
operator-facing controls:

- `Lead lock`
  - keep using registry lead selection when the user wants character continuity
- `Support lock`
  - allow registry or freeform support lock, instead of leaving support fully implicit
- `Location lock`
  - allow the operator to pin a location from the planner catalog when they do not want
    location inference to drift
- `Preferred anchor beat`
  - enum:
    - `auto`
    - `exchange`
    - `reveal`
    - `decision`

These controls are optional. The happy path must still work from the prompt alone.

## Direct Input Path Recommendation

Users should not have to go through an assistant to use this flow. The recommended
direct usage model is:

1. `Story Planner` web UI for normal authoring
2. CLI for reproducible batch or operator reruns
3. API for future external integrations

This keeps one contract across all entry points instead of inventing separate
interfaces.

## Backend Contract Changes

### Request

Extend `StoryPlannerPlanRequest` with optional fields:

- `location_id: string | null`
- `preferred_anchor_beat: "auto" | "exchange" | "reveal" | "decision"`

Existing fields stay unchanged:

- `story_prompt`
- `lane`
- `cast`

All existing clients that omit the new fields must keep working.

### Response

Extend `StoryPlannerPlanResponse` with:

- `recommended_anchor_shot_no: int`
- `recommended_anchor_reason: string`

This turns the planner from “four shots and figure it out yourself” into “four shots
plus a recommended default anchor.”

## Lane-Aware Shot Builder

### Current Problem

The current planner always emits the same four-shot ladder:

1. establish scene
2. introduce exchange
3. reveal key detail
4. close on decision

That structure is useful, but today it does not react to lane. So the adult lane and a
general lane can feel too similar at the shot-deck level.

### New Behavior

Keep the four-shot scaffold, but make later shots lane-aware.

For `all_ages`:

- keep the existing structure nearly unchanged

For `adult_nsfw`:

- keep `shot 1` as an establishing frame
- strengthen `shot 2`, `shot 3`, and `shot 4` as anchor-friendly frames by emphasizing:
  - relationship signal
  - readable tension
  - private-space framing
  - expressive body language
  - continuity-preserving emotional escalation

This should not rely on operator guesswork after the plan is returned.

## Planner Recommendation Logic

The planner should compute a recommended anchor shot after the four-shot deck is built.

### Recommendation Rules

If `preferred_anchor_beat` is explicit:

- `exchange` maps to the shot that best represents the relational beat
- `reveal` maps to the detail-reveal shot
- `decision` maps to the commitment/closing shot

If `preferred_anchor_beat=auto`:

- for `adult_nsfw`, prefer a later shot by default
- prefer the shot whose framing best preserves both:
  - scene readability
  - relational signal
- fall back to `shot 1` only if the later shots are missing or invalid

The planner should also return a one-line reason, for example:

- `shot 2 keeps the exchange readable while preserving location continuity`

## Default Selection Behavior

The rerun CLI and any UI default selection should stop assuming `shot 1` is the best
anchor.

### New Default Rule

- if the operator explicitly provides a shot override, use it
- otherwise, use `recommended_anchor_shot_no`

This keeps manual control intact while improving the default path.

## Thin Anchor Prompt Compiler

### Current Problem

The current anchor prompt is mostly a structured story note:

- story prompt
- episode premise
- cast continuity
- location details
- shot card

That is useful for debugging, but not strong enough as a rendering layer.

### New Compiler Layer

Introduce a deterministic prompt-compilation step inside the anchor path. This is not a
new model call. It is a new prompt-assembly function.

The compiler should convert planner output into render-intent sections such as:

- subject focus
- relationship signal
- location and atmosphere signal
- framing and camera signal
- mood and emotion signal
- continuity guard

The compiler still uses existing planner data:

- `story_prompt`
- `episode_brief`
- `resolved_cast`
- `location`
- `shot`

But it should assemble them as a render instruction, not as a plain story memo.

## Rendering Behavior After Change

After this branch:

- the operator can continue using one freeform story prompt
- the planner resolves cast and location as before
- the planner now returns a recommended anchor shot
- the adult lane defaults to a stronger later-shot anchor path
- the anchor prompt becomes more render-oriented and less memo-like
- the rerun CLI follows the planner recommendation unless explicitly overridden

## Frontend Changes

### Story Planner Input Panel

Modify the existing `Story Planner` input panel to add:

- optional location lock selector
- optional preferred anchor beat selector
- existing registry lead/support controls remain

No second authoring mode is introduced.

### Plan Review Surface

The plan review UI should surface:

- `recommended_anchor_shot_no`
- `recommended_anchor_reason`

So the operator understands what the planner wants to use and why.

### Direct Input Guidance

Improve helper copy to encourage one-line structured freeform input such as:

- character
- place
- tension
- immediate scene goal

But do not require multi-field structured authoring.

## CLI And API Behavior

### CLI

Update the rerun CLI to:

- accept planner recommendation by default
- keep `--select-shot` as an explicit override
- optionally accept the new planner preference fields over time

### API

The planner routes remain the same:

- `POST /api/v1/tools/story-planner/plan`
- `POST /api/v1/tools/story-planner/generate-anchors`

Only the payload and response shape expand.

## Testing Strategy

### Backend

Add or update targeted tests for:

- request validation with optional `location_id`
- request validation with optional `preferred_anchor_beat`
- planner recommendation behavior for `adult_nsfw`
- recommendation override behavior
- lane-aware shot content for later adult shots
- thin compiler output shape
- rerun CLI defaulting to the planner recommendation

### Frontend

Add or update targeted tests for:

- new optional controls rendering
- plan payload including `location_id` and `preferred_anchor_beat`
- freeform-only submission still working
- planner recommendation rendering in review UI
- default selected shot following planner recommendation

### Live Verification

Minimum live verification should cover:

1. one direct `Story Planner` preview using freeform prompt only
2. one preview using optional guidance fields
3. one anchor queue result where the recommended shot is a later shot in the adult lane
4. one workflow prompt inspection showing more render-oriented structure

Full close-loop rerun is useful but optional for this branch.

## Risks And Mitigations

### Risk: Too Much Hidden Logic

If the planner starts recommending shots without clear explanation, the operator may
stop trusting the system.

Mitigation:

- always return `recommended_anchor_reason`
- keep manual override intact

### Risk: Compiler Becomes Another Opaque Layer

If the compiler is too magical, debugging prompt quality gets harder.

Mitigation:

- keep it deterministic
- build from existing planner fields only
- expose the compiled structure in stored prompt text or debug output

### Risk: UI Complexity Creep

If too many structured controls are added, the direct-input flow becomes slower than
the current freeform experience.

Mitigation:

- keep all new controls optional
- maintain one-prompt happy path

## File Impact

Likely files in scope:

- `backend/app/models.py`
- `backend/app/services/story_planner_service.py`
- `backend/scripts/run_pilot_rerun_close_loop.py`
- `backend/tests/test_story_planner_service.py`
- `backend/tests/test_story_planner_routes.py`
- `backend/tests/test_run_pilot_rerun_close_loop.py`
- `frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx`
- `frontend/src/components/tools/story-planner/StoryPlannerMode.tsx`
- `frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx`
- any plan review / anchor results component that must surface recommendation metadata

## Success Criteria

This branch is successful when:

- a user can author directly through `Story Planner` with one natural-language prompt
- optional guidance fields improve control without being required
- adult-lane previews no longer default to `shot 1` when a later shot is the better
  anchor
- anchor prompts become more render-oriented than story-memo-oriented
- the rerun CLI and UI both follow planner recommendation by default
- existing freeform planner usage keeps working without migration pain
