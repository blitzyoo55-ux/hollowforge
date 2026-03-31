# HollowForge Grok Prompt Factory — 2026-03-11

## Goal

Use Grok as a text-generation provider for two automation tasks:

1. Generate large HollowForge prompt batches in CSV form for local image generation.
2. Generate short X post copy for selected images.

This design does **not** use Grok to generate images. HollowForge remains the image-generation runtime.

---

## What was added

Backend prompt-factory endpoints:

- `GET /api/v1/tools/prompt-factory/capabilities`
- `POST /api/v1/tools/prompt-factory/generate`
- `POST /api/v1/tools/prompt-factory/generate.csv`
- `POST /api/v1/tools/prompt-factory/generate-and-queue`

These endpoints:

- use an OpenAI-compatible provider client
- support `openrouter` and direct `xai`
- read the current favorite-image benchmark from the HollowForge DB
- generate prompt rows in chunks for 100+ batch use cases
- export CSV in the same pipe-delimited format used by `frontend/src/pages/BatchImportPage.tsx`
- queue generated rows directly into HollowForge without a CSV round-trip

---

## Provider decision

### Short answer

For automation, a consumer Grok/X subscription is not enough.

You need one of:

- `OPENROUTER_API_KEY`
- `XAI_API_KEY`

### Recommended path

1. **Pilot with OpenRouter first**
   - HollowForge already uses OpenRouter for image-conditioned captioning.
   - Lowest integration risk.
   - Good for refusal-rate and JSON-validity testing.

2. **Move to direct xAI if Grok becomes core infrastructure**
   - Cleaner ownership of provider behavior and billing.
   - Better long-term if Grok is the primary prompt engine.

3. **Keep OpenRouter as fallback**
   - Useful if xAI rate limits or model availability change.

### Billing note

As checked on 2026-03-11 from official xAI docs:

- Grok account and xAI API account can be shared.
- Billing for the consumer product and API usage is separate.

Reference URLs:

- `https://docs.x.ai/developers/quickstart`
- `https://docs.x.ai/docs/resources/faq-api/accounts`
- `https://docs.x.ai/console/billing`

---

## Current benchmark source

Prompt-factory defaults are not invented from scratch.

They are derived from the current favorite-image pool in the local HollowForge DB:

- top checkpoints
- top LoRAs
- average LoRA strengths
- dominant CFG values
- dominant step counts
- dominant sampler / scheduler
- dominant resolution
- recurring Lab-451 keywords
- dominant negative prompt

Fallback defaults still match the latest favorites analysis if the DB has no favorite rows.

---

## Why this structure is better

Do **not** let the LLM freely choose every sampler, checkpoint, and strength.

That creates avoidable variance and lower reproducibility.

Instead:

- benchmarked model settings come from favorites
- Grok expands scene design, lore, pose, framing, material emphasis, and series variety
- lane selection stays internal; HollowForge applies the correct lane automatically from the chosen checkpoint

This keeps output creative without losing the Lab-451 production baseline.

---

## CSV format

The CSV export uses the existing HollowForge batch import schema:

`Set_No|Checkpoint|LoRA_1|Strength_1|LoRA_2|Strength_2|LoRA_3|Strength_3|LoRA_4|Strength_4|Sampler|Steps|CFG|Clip_Skip|Resolution|Positive_Prompt|Negative_Prompt`

That means prompt batches can be generated and then imported into HollowForge without a format-conversion step.

---

## What still needs a real API pilot

The code path is ready, but one operational question cannot be answered purely from docs:

- how often Grok refuses or weakens high-heat adult prompt requests in practice

That must be measured with a small live API pilot.

Recommended pilot:

- `count=24`
- `chunk_size=8`
- compare `openrouter` vs `xai`
- record:
  - refusal rate
  - malformed JSON rate
  - duplicate rate
  - lore consistency
  - import-ready row rate

If Grok is stable there, scale to `count=120`.

---

## Example request

```json
{
  "concept_brief": "Lab-451 specimen intake campaign focused on latex drones, sealed hoods, compliance frames, and clinical seduction.",
  "creative_brief": "Expand locations, restraint devices, lensing, and hierarchy cues while preserving the favorite benchmark settings.",
  "count": 120,
  "chunk_size": 20,
  "provider": "openrouter",
  "tone": "campaign",
  "heat_level": "steamy",
  "target_lora_count": 2,
  "checkpoint_pool_size": 3,
  "include_negative_prompt": true,
  "dedupe": true,
  "forbidden_elements": ["school setting", "casual selfie vibe"],
  "expansion_axes": ["camera distance", "lighting mood", "mask design", "location", "restraint device", "story beat"]
}
```

---

## Next recommended step

Run a small live provider pilot first.

Do not jump straight to `count=100+` until:

- JSON structure is stable
- refusal rate is known
- HollowForge import rows stay consistent

Once that is confirmed, this prompt-factory path is suitable for high-volume batch generation.

## Adult Lane Default Split

Prompt Factory adult defaults now use OpenRouter/Grok through:

- `HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE`
- `HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL`

This only changes the prompt-factory lane. Sequence runtime adult defaults remain `adult_local_llm`, so the Stage 1 sequence path keeps its existing local-first behavior unless `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE` is changed separately.
