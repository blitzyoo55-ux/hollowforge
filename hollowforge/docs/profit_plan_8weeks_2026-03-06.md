# HollowForge 8-Week Profit Plan (2026-03-06)

## 1) Objective
- Raise monthly net profit from about `$2,289` (baseline scenario) to `>= $5,000` within 8 weeks.
- Primary monetization focus: personal content production and distribution.
- Secondary monetization focus: lightweight BYO-compute licensing pilot (optional, after Week 6).

## 2) Baseline Snapshot (fixed on 2026-03-06, KST)
- Source: `hollowforge/data/hollowforge.db` (live production DB).
- Total jobs: `2,532`
- Completed: `2,182`
- Failed: `179`
- Queued/Running: `166 / 1`
- AI analyzed coverage on completed: `99.82%` (`2,178/2,182`)
- Avg generation runtime: `206.24 sec`
- Current queue drain estimate: `9.57 hours`
- Calendar-day throughput: `145.47 completed/day` (~`4,364/month`)
- Publish approved rate: `0.92%`

## 3) Target Economics and KPI Math
### Profit equation
`Monthly Net = Monthly Volume x Monetizable Rate x Realized Revenue Per Asset x (1 - Variable Cost Rate)`

### Fixed throughput assumption
- Monthly volume cap (current): `4,364 assets/month`

### Week-8 target economics (minimum to cross $5,000 net)
- Monetizable rate: `>= 4.5%`
- Realized revenue per monetized asset: `>= $38`
- Variable cost rate: `<= 28%`
- Expected:
  - Gross: `4,364 x 0.045 x 38 = $7,462`
  - Net: `$7,462 x 0.72 = $5,372`

## 4) Weekly KPI Ladder (8 weeks)
| Week | Monetizable Rate Target | Revenue/Asset Target | Variable Cost Cap | Net Run-Rate Target |
|---|---:|---:|---:|---:|
| W1 | 1.2% | $28 | 32% | $1,000 |
| W2 | 1.6% | $30 | 32% | $1,400 |
| W3 | 2.1% | $31 | 31% | $1,950 |
| W4 | 2.8% | $33 | 31% | $2,800 |
| W5 | 3.4% | $35 | 30% | $3,700 |
| W6 | 3.9% | $36 | 29% | $4,400 |
| W7 | 4.3% | $37 | 28% | $4,950 |
| W8 | 4.5%+ | $38+ | 28% | $5,000+ |

## 5) 8-Week Execution Plan
## W1 - Measurement lock and funnel definition
- Create one weekly dashboard from DB (single source of truth).
- Define monetizable criteria:
  - `quality_ai_score >= 90`
  - `finger_anomaly = 0`
  - manual review pass
- Track three funnel stages:
  - `candidate` -> `approved` -> `published/sold`
- Deliverables:
  - KPI sheet updated daily
  - Top 5 reject reasons documented

## W2 - Prompt and model curation for conversion
- Stop low-yield model/prompt combinations.
- Focus generation budget on top conversion checkpoints/samplers only.
- Build 3 product lanes:
  - premium set (high polish)
  - volume set (high output)
  - niche set (specific audience tag)
- Deliverables:
  - Reject-rate reduction by at least 20% from W1
  - Monetizable rate >= 1.6%

## W3 - Offer architecture and pricing test
- Productize output into sellable units:
  - pack size A: 10 assets
  - pack size B: 25 assets
  - premium bundle: curated + edited
- Run price A/B test for each lane.
- Introduce minimum quality gate before publish.
- Deliverables:
  - Revenue/asset >= $31
  - 2 repeat-buy signals from existing buyers/users

## W4 - Channel execution and cadence
- Fix posting cadence per channel (daily and weekly schedule).
- Separate channel roles:
  - acquisition channel
  - conversion channel
  - retention channel
- Build simple release calendar (2 weeks rolling).
- Deliverables:
  - Monetizable rate >= 2.8%
  - Consistent weekly launch cadence (no skipped week)

## W5 - Scale what converts, kill what does not
- Cut bottom 30% SKUs/channels by ROI.
- Reallocate output budget to top 20% performers.
- Introduce faster review flow:
  - auto filter -> manual final approval
- Deliverables:
  - Monetizable rate >= 3.4%
  - Revenue/asset >= $35

## W6 - Retention and upsell
- Add subscription-like continuity offer (monthly drops, tiered access).
- Upsell from volume set to premium bundle.
- Add feedback loop: buyer comments -> prompt updates in 48h.
- Deliverables:
  - Monetizable rate >= 3.9%
  - Variable cost <= 29%

## W7 - Automation and SLA hardening
- Automate repetitive curation/reporting steps.
- Reduce queue spillover by scheduling generation windows.
- Optional BYO-compute pilot for 3 to 5 testers (license-style access).
- Deliverables:
  - Monetizable rate >= 4.3%
  - Net run-rate >= $4,950

## W8 - Stabilize and decide next quarter
- Lock best-performing portfolio.
- Freeze pricing tiers with final evidence.
- Decide expansion path:
  - keep personal content scale-up
  - add BYO-compute micro-SaaS layer
- Deliverables:
  - Net >= $5,000/month run-rate
  - 90-day operating plan approved

## 6) Hard Guardrails (Go/No-Go Rules)
- If W4 monetizable rate < `2.0%`: pause scaling, return to W2 optimization.
- If W6 revenue/asset < `$33`: rework packaging and pricing before further volume.
- If variable cost > `35%` for 2 consecutive weeks: cut low-margin channels immediately.
- If queue drain > `12h` for 3+ days/week: reduce batch pressure and rebalance schedule.

## 7) Weekly Operating Checklist
- Monday:
  - lock prior-week KPI
  - choose top 3 experiments
- Mid-week:
  - kill/continue decision per experiment
- Friday:
  - publish weekly P&L and funnel report
  - update next-week allocation

## 8) SQL KPI Snippets (DB: `data/hollowforge.db`)
```sql
-- Core status snapshot
SELECT
  datetime('now') AS ts_utc,
  COUNT(*) AS total,
  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed,
  SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
  SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS queued,
  SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
FROM generations;
```

```sql
-- Analyze coverage and quality distribution
SELECT
  ROUND(100.0 * SUM(CASE WHEN status='completed' AND quality_ai_score IS NOT NULL THEN 1 ELSE 0 END)
    / NULLIF(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END),0), 2) AS analyzed_coverage_pct,
  ROUND(AVG(quality_ai_score),2) AS avg_ai_score,
  ROUND(100.0 * SUM(CASE WHEN quality_ai_score>=90 THEN 1 ELSE 0 END) / COUNT(*), 2) AS g90_pct
FROM generations
WHERE status='completed' AND quality_ai_score IS NOT NULL;
```

```sql
-- End-to-end latency (request to completed)
SELECT ROUND(AVG((julianday(completed_at)-julianday(created_at))*86400),2) AS e2e_avg_sec
FROM generations
WHERE status='completed' AND completed_at IS NOT NULL;
```

```sql
-- Daily completed throughput
SELECT substr(created_at,1,10) AS day,
       SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed
FROM generations
GROUP BY day
ORDER BY day DESC;
```

## 9) Decision at Week 8
- If net run-rate is `>= $5,000` and stable for 2 straight weeks:
  - continue scale-up and add controlled channel expansion.
- If net run-rate is `< $5,000`:
  - do not increase volume.
  - fix monetizable rate and revenue/asset first, then re-test for 2 more weeks.
