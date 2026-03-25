# HollowForge Sequence Animation Orchestration Design

Date: 2026-03-25
Status: Approved for planning
Branch: `codex/commit-slice-20260325`

## Summary

HollowForge will remain the single control plane for still generation, shot planning, sequence orchestration, animation dispatch, rough-cut assembly, scoring, and review. The system will add a sequence layer above the existing still-generation and animation-job stack so it can automatically build 30-second-plus narrative clips from multiple shots.

Stage 1 is intentionally narrow:

- Single character
- Single fixed location
- No dialogue or lip-sync
- Emotion and action beats only
- Fixed beat grammar
- Per-shot anchor stills
- Straight-cut rough-cut output
- Human approval only at the rough-cut stage

The local Mac mini remains heavily used for still generation and selection. Remote workers are introduced primarily for repeated image-to-video execution across many shots.

## Context

Current HollowForge already supports:

- Character-oriented still generation and curation
- Prompt-factory based prompt generation
- Animation dispatch to a remote worker
- Local animation smoke-testing paths
- Backend callback-driven animation result updates

Observed local environment on 2026-03-25:

- Host: Apple Mac mini, M4, 24 GB unified memory
- Backend reachable
- ComfyUI reachable
- Required LTXV and IPAdapter models present
- Local animation worker not currently up

Implication:

- Local still generation is viable and should stay central
- Local full-sequence video production is technically possible but operationally weak
- Repeated multi-shot image-to-video is the right place to use remote workers

## Goals

- Generate 30-40 second rough-cut sequence candidates automatically
- Preserve strong character identity continuity across shots
- Preserve fixed-location continuity across shots
- Reuse HollowForge still-generation strengths instead of replacing them
- Support both `all_ages` and `adult_nsfw` production lanes without duplicating the product
- Keep the product unified while allowing execution, policy, and provider lanes to diverge
- Maximize use of the local Mac mini for still generation and selection

## Non-Goals

- Final publish-ready editing with music, titles, and transitions
- Multi-character cinematic scenes in Stage 1
- Loose story generation with unconstrained shot structures in Stage 1
- Cross-lane fallback between `all_ages` and `adult_nsfw`
- Creating a separate Phase 2 product for sequence generation

## Product Boundary

HollowForge remains the main product.

HollowForge owns:

- Character canon
- Location canon
- Prompt generation
- Sequence planning
- Still batch generation
- Anchor scoring and selection
- Animation dispatch
- Rough-cut assembly
- Review and scoring

HollowForge does not own all heavy execution locally forever. It delegates runtime-heavy work to pluggable lanes.

Recommended product shape:

- One HollowForge control plane
- Multiple runtime lanes
- Multiple prompt-provider profiles
- Multiple animation executor profiles

This keeps sequence assets, review workflows, and canon systems unified while isolating policy-sensitive and compute-heavy execution paths.

## Stage 1 Scope

Stage 1 sequence contract:

- `6-8` shots
- `4-6` seconds per shot target
- `30-40` seconds total
- Single character
- Single fixed location
- No dialogue
- No lip-sync
- Fixed beat grammar
- Per-shot anchor stills
- Straight-cut rough-cut output

Stage 1 priority order:

1. Character continuity
2. Story beat clarity
3. Throughput

## Architecture

The existing `generation -> animation_job -> worker -> callback` pipeline stays in place. A new sequence layer is added above it.

Core sequence entities:

- `SequenceBlueprint`
  - Reusable sequence template
  - Locks character, location, beat grammar, tone, target duration, shot count, and executor policy
- `SequenceRun`
  - One automated attempt to produce a narrative sequence from a blueprint
  - Holds execution mode, scoring summary, selected rough cut, and failure summary
- `SequenceShot`
  - One planned shot inside a sequence
  - Holds beat type, camera intent, emotion intent, action intent, continuity rules, and target duration
- `ShotAnchor`
  - The selected still used as the visual basis for one shot
- `ShotClip`
  - The generated video clip for one shot
- `RoughCut`
  - The ordered assembly of shot clips into a straight-cut preview video

Logical flow:

`SequenceBlueprint -> SequenceRun -> SequenceShot -> ShotAnchor -> AnimationJob -> ShotClip -> RoughCut`

## Content Lanes and Policy Split

The system must support two hard-separated content modes:

- `all_ages`
- `adult_nsfw`

Every sequence-layer entity should include `content_mode` and `policy_profile_id`.

Minimum entities requiring lane tagging:

- `sequence_blueprints`
- `sequence_runs`
- `sequence_shots`
- `shot_anchor_candidates`
- `shot_clips`
- `rough_cuts`

Lane separation rules:

- No shared reference pools between lanes
- No shared model or LoRA whitelists by default
- No shared publish destinations
- No cross-lane prompt fallback
- No cross-lane animation executor fallback
- No cross-lane callback token reuse

Recommended operating model:

- Unified HollowForge control plane
- `safe` lane
- `adult` lane

The product stays unified. The policies and execution paths do not.

## Prompt Provider Strategy

Prompt generation is provider-profile driven rather than globally fixed.

Recommended provider split:

- `all_ages`
  - Hosted provider primary
  - Example profiles: `xai_direct`, `openrouter_xai_primary`
- `adult_nsfw`
  - Local LLM primary
  - Hosted providers optional only as explicit secondary options

Rationale:

- Hosted providers are convenient for safe-mode prompt generation
- Adult prompt generation is more likely to hit provider policy instability
- Prompt and shot-plan generation is far lighter than video inference, so local LLM use is realistic even when local full video production is not ideal

Provider requirements:

- Return structured JSON for beat plans and shot prompts
- Be selected per `SequenceRun`
- Be constrained by `content_mode`
- Be constrained by `policy_profile_id`

Suggested future provider-profile examples:

- `safe_hosted_grok`
- `safe_openrouter_fallback`
- `adult_local_llm`
- `adult_local_llm_strict_json`

## Runtime Topology

HollowForge should use a hybrid execution topology.

Control plane:

- HollowForge backend
- Database
- Canon assets
- Review state
- Sequence orchestration
- Rough-cut assembly

Execution lanes:

- `safe_local_preview`
- `safe_remote_prod`
- `adult_local_preview`
- `adult_remote_prod`

Local remains important, but not for the entire sequence-production burden.

## Local Compute Strategy

The Mac mini should be treated as a `still-first engine`.

Local responsibilities:

- Prompt generation
- Sequence beat expansion
- Shot prompt packet creation
- Still batch generation
- Quality scoring
- Identity scoring
- Continuity scoring
- Anchor selection
- Rough-cut assembly
- Preview rendering
- Single-shot animation smoke tests

Remote responsibilities:

- High-volume shot clip generation
- Shot retry batches
- Multi-candidate rough-cut clip production

Operating rule:

- Remote workers should be called only after anchor stills are selected
- Remote workers are clip executors, not idea explorers

This maximizes use of the Mac mini where it already performs well and limits remote costs to clips that survived local selection.

## Automatic Generation Pipeline

Stage 1 generation flow:

1. Create a `SequenceRun` from a selected `SequenceBlueprint`
2. Expand the fixed beat grammar into `6-8` `SequenceShot` records
3. Build a `shot prompt packet` for each shot from:
   - character canon
   - fixed location canon
   - prior-shot continuity state
   - beat grammar constraints
4. Generate `8-20` still candidates per shot locally
5. Score candidates per shot using:
   - `identity_score`
   - `location_lock_score`
   - `beat_fit_score`
   - `quality_score`
6. Select:
   - `1` primary anchor
   - `1-2` backup anchors
7. Dispatch the selected anchor as an animation job
8. Capture the resulting clip as a `ShotClip`
9. Assemble ordered `ShotClip` outputs into a `RoughCut`
10. Score `2-4` candidate rough cuts and select a default winner

Human review point:

- Only after rough-cut candidates are available

This keeps the system automation-first while preserving a deterministic place for human selection.

## Data Model

New tables recommended for Stage 1:

- `sequence_blueprints`
  - `id`
  - `content_mode`
  - `policy_profile_id`
  - `character_id`
  - `location_id`
  - `beat_grammar_id`
  - `target_duration_sec`
  - `shot_count`
  - `tone`
  - `executor_policy`
- `sequence_runs`
  - `id`
  - `sequence_blueprint_id`
  - `content_mode`
  - `policy_profile_id`
  - `prompt_provider_profile_id`
  - `execution_mode`
  - `status`
  - `selected_rough_cut_id`
  - `total_score`
  - `error_summary`
- `sequence_shots`
  - `id`
  - `sequence_run_id`
  - `shot_no`
  - `beat_type`
  - `camera_intent`
  - `emotion_intent`
  - `action_intent`
  - `target_duration_sec`
  - `continuity_rules`
- `shot_anchor_candidates`
  - `id`
  - `sequence_shot_id`
  - `generation_id`
  - `identity_score`
  - `location_lock_score`
  - `beat_fit_score`
  - `quality_score`
  - `is_selected_primary`
  - `is_selected_backup`
- `shot_clips`
  - `id`
  - `sequence_shot_id`
  - `selected_animation_job_id`
  - `clip_path`
  - `clip_duration_sec`
  - `clip_score`
  - `retry_count`
  - `is_degraded`
- `rough_cuts`
  - `id`
  - `sequence_run_id`
  - `output_path`
  - `timeline_json`
  - `total_duration_sec`
  - `continuity_score`
  - `story_score`
  - `overall_score`

Existing entities remain relevant:

- `generations` remain the still asset layer
- `animation_jobs` remain the shot execution layer

## Failure Handling

Failure should be handled at the shot level before escalating to full-run failure.

Shot failure order:

1. Retry with a backup anchor
2. Retry with a lower-motion preset in the same lane
3. Mark the shot degraded and continue run assembly

Provider failure order:

- Prompt provider failure -> retry with a same-lane fallback provider
- Animation executor failure -> retry with a same-lane fallback executor
- Cross-lane fallback -> forbidden

Operational protections:

- If local memory pressure rises, reduce still-batch size before sacrificing sequence structure
- Keep incomplete runs if enough clips exist to compare narrative candidates
- Surface degraded shots clearly in review

## Review and Scoring

Stage 1 review target is the rough cut, not individual shots.

Minimum run-level scores:

- `identity_continuity_score`
- `location_continuity_score`
- `beat_coverage_score`
- `motion_stability_score`
- `clip_success_rate`

Minimum operational KPIs:

- Anchor selection success rate per shot
- Shot clip success rate
- Rough-cut completion rate
- Average run time by lane
- Remote retry rate by lane

Selection behavior:

- Produce `2-4` rough-cut candidates per run when possible
- Automatically choose a default best candidate
- Let the operator review and override at the rough-cut stage

## Testing Strategy

Implementation should include verification at four layers.

Control-plane verification:

- Blueprint creation and validation
- Sequence-run lifecycle transitions
- Shot expansion from fixed beat grammar
- Same-lane retry and fallback behavior
- Cross-lane isolation enforcement

Still pipeline verification:

- Still candidate generation for each shot
- Anchor scoring and ranking stability
- Identity and location continuity scoring behavior
- Backup-anchor selection behavior

Animation pipeline verification:

- Animation-job dispatch from selected anchors
- Worker callback handling
- Same-lane executor fallback
- Degraded-shot marking when retries fail

Assembly verification:

- Rough-cut timeline assembly
- Ordered clip concatenation
- Duration accounting
- Rough-cut scoring and default-candidate selection

Operational smoke tests should exist for both lanes:

- `all_ages` local preview
- `adult_nsfw` local preview
- `all_ages` remote execution
- `adult_nsfw` remote execution

## Rollout Plan

### Stage 1

- Unified HollowForge control plane
- Local still generation and scoring stay primary
- Local prompt generation and shot planning stay primary
- Remote workers handle most multi-shot image-to-video execution
- Output ends at straight-cut rough-cut preview

### Stage 2

- Stabilize lane-specific remote workers
- Add queue priority, retries, health checks, and cost tracking
- Improve storage separation and execution observability

### Stage 3

- Expand beyond single fixed location
- Support more flexible beat grammars
- Add longer sequences and higher-complexity edits
- Optionally swap in video-native executors later without changing the control plane

## Acceptance Criteria

Stage 1 is considered successful when HollowForge can:

- Create automated rough-cut candidates from a sequence blueprint
- Produce `30-40` second outputs with `6-8` shots
- Keep one character visually coherent across the full sequence
- Keep one fixed location visually coherent across the full sequence
- Separate `all_ages` and `adult_nsfw` execution and policy lanes
- Use the local Mac mini heavily for still generation and selection
- Use remote workers primarily for repeated shot-level image-to-video
- Present candidate rough cuts for human selection without requiring shot-by-shot approval

## Open Follow-On Work

This design intentionally stops before implementation details. The next step should be an implementation plan covering:

- Schema migrations
- Backend orchestration services
- Worker contract extensions
- Rough-cut assembly pipeline
- Prompt-provider profile abstraction
- Executor-profile abstraction
- Review UI changes
- Operational health and retry instrumentation
