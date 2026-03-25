# Lab-451 Content Pipeline Plan

## Goal
- Build a repeatable end-to-end pipeline for:
  1. high-quality NSFW prompt generation
  2. CSV-based bulk image production
  3. curation / ready-to-go selection
  4. image-matched post text generation
  5. SNS publishing operations
  6. auto-detection of high-performing posts for AI animation follow-up

## Product Direction
- HollowForge remains the creative operations console.
- Generation, curation, captioning, and content packaging stay inside HollowForge.
- SNS posting credentials, scheduling, retries, and platform-specific delivery should eventually live in a separate publisher service.
- Local image generation remains the default production path.
- Animation should be remote-first unless local hardware comfortably sustains repeatable high-quality video inference.
- Lab-451 copy should be:
  - worldbuilding-heavy
  - suggestive and steamy
  - non-explicit
  - short enough for social reuse
  - easy to adapt per platform

## Compute / Tooling Assumption
- Images:
  - keep integrated in HollowForge + local ComfyUI
  - current local workflow already fits iteration-heavy prompt work
- Animation:
  - do not assume the same workstation can sustain production-grade video generation
  - treat animation as a separate execution concern with its own queue, budget, and provider strategy
- Decision:
  - HollowForge should orchestrate animation
  - the actual renderer should be pluggable and allowed to live outside HollowForge

## Animation Architecture Decision

### What stays integrated
- candidate discovery from engagement
- approval / rejection
- motion preset selection
- render profile selection
- result tracking back into gallery / publishing records

### What should be split out
- GPU-heavy animation execution
- remote job submission / polling
- provider-specific auth and retries
- cost controls
- render-node health checks

### Why split
- local image generation and remote animation have very different latency and hardware profiles
- managed animation APIs may become unavailable or policy-constrained
- a split execution layer keeps HollowForge stable even if the renderer changes from BytePlus to remote ComfyUI, Runpod-hosted workers, or another GPU executor

## Animation Provider Strategy

### Option A — Fully local
- Best for:
  - prototyping
  - short low-volume experiments
- Weakness:
  - likely bottlenecked by VRAM, throughput, and workstation availability
- Recommendation:
  - keep as fallback only

### Option B — Managed external API
- Best for:
  - compliant / non-explicit workloads
  - fastest initial integration
- Weakness:
  - policy volatility
  - less control over model stack and moderation outcomes
- Recommendation:
  - keep as optional adapter, not the core adult-content path

### Option C — Remote self-hosted worker on rented GPU
- Best for:
  - high-quality production animation
  - model freedom
  - stable orchestration across changing render backends
- Weakness:
  - requires worker deployment, storage, and job supervision
- Recommendation:
  - preferred production target

## Remote Animation Recommendation
- Preferred operating model:
  - HollowForge = orchestration + review + queue + analytics
  - external animation worker = execution
- Recommended worker shape:
  - queue consumer
  - provider/model adapters
  - output uploader
  - callback or polling API back to HollowForge
- Initial backend targets:
  - `local` for fallback tests
  - `remote_worker` for production
  - `managed_api` only for policy-safe/non-explicit use

## Current State
- Prompt CSV ingestion already exists via `Batch Import`.
- Bulk generation already exists.
- Quality filtering and `Ready to Go` selection already exist.
- Single-image caption generation already exists.
- Export packaging already exists.
- SNS publishing, engagement tracking, and animation escalation do not yet exist as first-class workflows.

## Target Pipeline

### Stage 1 — Prompt Factory
- Input:
  - theme / sub-world
  - character archetype
  - material stack
  - camera/framing
  - restraint/compliance mood
  - negative prompt profile
- Output:
  - normalized prompt rows
  - direct CSV export for batch generation
- Notes:
  - should support “recipe + variation matrix” generation
  - should emit tags/notes for downstream tracking

### Stage 2 — Bulk Generation
- Feed prompt CSV into existing generation queue.
- Keep source metadata attached to each generation:
  - prompt batch id
  - prompt row id
  - campaign / theme id
- Purpose:
  - measure which prompt families convert into usable images

### Stage 3 — Selection / Curation
- Existing `Quality AI` + manual review + `Ready to Go` becomes the formal gate.
- `publish_approved = 1` remains the publishing-ready switch.
- Recommended additions later:
  - curation reason tags
  - “why selected” notes
  - platform suitability flags

### Stage 4 — Caption Generation
- For ready images only, generate multiple caption variants:
  - `social_short`
  - `post_body`
  - `launch_copy`
- Each caption stores:
  - platform target
  - tone
  - model/provider
  - prompt version
  - approval state
- Lab-451 text principles:
  - high tension, low exposition
  - implication over explicitness
  - texture/protocol/compliance vocabulary
  - room for audience imagination

### Stage 5 — SNS Publishing
- HollowForge should prepare publish jobs.
- Separate publisher service should eventually execute:
  - account auth
  - scheduling
  - retries / rate limits
  - post URL / external ID tracking
- Initial HollowForge scope:
  - draft/queued/published/failed state
  - caption binding
  - platform tagging
  - export to publisher

### Stage 6 — High-Response → Animation
- Engagement snapshots are collected per publish job.
- A simple internal score suggests animation candidates.
- Candidate states:
  - `suggested`
  - `approved`
  - `queued`
  - `processing`
  - `completed`
  - `rejected`
- Recommended automation path:
  - V1: suggest candidate only
  - V2: manual approval selects target tool and executor backend
  - V3: queue candidate into a provider-agnostic animation job layer
  - V4: auto-submit only when motion templates and render profiles are standardized

## Architecture Recommendation

### Keep inside HollowForge
- prompt recipe management
- prompt CSV generation
- ready-to-go queue
- caption generation
- publish job planning
- engagement import / review
- animation candidate review
- animation job orchestration
- animation result registry

### Split into separate `lab451-publisher`
- SNS API credentials
- account/channel config
- scheduling workers
- posting retries
- posting webhooks / callback ingest
- compliance / audit logging

### Split into separate `lab451-animation-worker`
- GPU execution
- provider/model adapters
- remote storage staging
- job polling / retries
- render health monitoring
- cost-aware scheduling

## Phase Plan

### Phase A — Foundation
- Add DB tables for:
  - caption variants
  - publish jobs
  - engagement snapshots
  - animation candidates
- Add backend endpoints to manage them.
- Refactor caption generation into reusable service.

### Phase B — Ready Queue Ops
- Add `Ready to Go Ops` page:
  - list ready images
  - generate 3 caption variants
  - approve one caption
  - create publish jobs

### Phase C — Prompt Factory
- Add prompt recipe templates and CSV export UI.
- Track prompt family lineage into generation metadata.

### Phase D — Publisher Integration
- Build separate `lab451-publisher`.
- Support CSV/JSON intake from HollowForge.
- Push post results back into HollowForge.

### Phase E — Engagement Escalation
- Import engagement metrics.
- Suggest animation candidates automatically.
- Add manual approve/reject actions.

### Phase F — Animation Orchestration Layer
- Add provider-agnostic animation jobs.
- Separate executor mode from target tool.
- Track remote/local backend, external job ID, output path, and failures.

### Phase G — Remote Worker
- Build separate `lab451-animation-worker`.
- Support remote worker callbacks or polling.
- Add storage handoff for template videos, prompts, and outputs.

### Phase H — Animation Automation
- Bind candidate → render profile + target tool + executor backend.
- Add controlled dispatch from approved candidates into the animation queue.
- Keep managed API use optional and non-core.

## What Was Implemented In This Pass
- Added phase-A storage tables:
  - `caption_variants`
  - `publish_jobs`
  - `engagement_snapshots`
  - `animation_candidates`
- Added reusable caption generation service.
- Added publishing pipeline API for:
  - ready-item listing
  - caption generation + approval
  - publish job creation/update
  - engagement snapshot recording
  - animation candidate listing/update
- Added animation strategy revision:
  - remote-first animation recommendation
  - separate animation worker as the preferred production shape
- Added phase-F groundwork:
  - provider-agnostic `animation_jobs`
  - dispatch endpoint from HollowForge to external worker
  - callback endpoint from worker back to HollowForge
  - separate `lab451-animation-worker` scaffold with `stub` executor

## Recommended Next Build Step
- Replace the worker `stub` backend with a real executor adapter and add motion-template asset handoff.
