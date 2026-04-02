# HollowForge Ops Pilot Log

## Baseline
- backend tests: PASS - 62 passed in 7.97s
- frontend tests: PASS - Duration 5.14s (transform 1.77s, setup 2.78s, collect 10.71s, tests 7.45s, environment 8.24s, prepare 1.79s)
- adult provider resolution: PASS - prompt=adult_openrouter_grok runtime=adult_local_llm
- publishing readiness: PASS - mode=full provider=openrouter model=x-ai/grok-4-fast
- story planner smoke: PASS - lane=unrestricted policy=canon_unrestricted_v1 queued=8

## Episode Runs
- episode:
  - premise: Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing, both wrapped in damp silk layers and carrying a sealed towel bundle that neither wants to explain.
  - lane: adult_nsfw
  - plan approved: yes
  - queued generation ids: 7056ca96-dc29-4421-996d-ca2fc47d7894, 18d4353a-ace2-4105-9fc1-eb05eb0476e0, 3139b314-3313-43f1-bf57-aedf6c0a3113, 2c9ddf10-9f4a-4e67-84a1-230485d39399, 44b60998-c18e-4240-81a4-3461f084cb1f, f5d1071f-cc14-42a8-b85c-bcc48bc28bbc, 2d4f8897-09d0-4f64-8926-ae49f8aa0886, 0d7a1a25-aad2-4672-8282-84c6911fc385

## Ready Queue
- selected generation ids: 7056ca96-dc29-4421-996d-ca2fc47d7894
- ready count: 1

## Publishing Pilot
- generation id: 7056ca96-dc29-4421-996d-ca2fc47d7894
  - publishing readiness: full
  - caption variants created: 1
  - caption variant id: cfd7cca0-1e34-4abe-b16f-47bd48625fd2
  - caption provider/model: openrouter / x-ai/grok-4-fast
  - approved caption id: none
  - draft publish job id: cae30b47-4831-4c55-957e-16e75d34481d
