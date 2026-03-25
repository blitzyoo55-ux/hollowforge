# HollowForge Weekly Ops Template (8-Week Sprint)

## Usage
- Use one copy of this template per week (W1~W8).
- Keep all numeric values tied to DB query outputs when possible.
- Every Friday, lock this sheet and do next-week allocation from the results.

---

## Week Header
- Week: `W__`
- Date range: `YYYY-MM-DD ~ YYYY-MM-DD`
- Owner: ``
- Goal of the week (one line): ``

## 1) KPI Scoreboard
| KPI | Target | Actual | Gap | Status (G/Y/R) |
|---|---:|---:|---:|---|
| Monetizable rate (%) |  |  |  |  |
| Revenue per asset ($) |  |  |  |  |
| Variable cost rate (%) |  |  |  |  |
| Net run-rate ($/month) |  |  |  |  |
| Queue drain (hours) |  |  |  |  |
| Analyze coverage (%) |  |  |  |  |

## 2) Funnel Tracking
| Funnel Stage | Count | Conversion (%) |
|---|---:|---:|
| Generated |  | - |
| Candidate |  |  |
| Approved |  |  |
| Published |  |  |
| Sold / Monetized |  |  |

- Top reject reason #1:
- Top reject reason #2:
- Top reject reason #3:

## 3) Channel & SKU Performance
| Channel/SKU | Volume | Revenue | Conversion | Notes |
|---|---:|---:|---:|---|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

- Keep (Top 20%): ``
- Cut (Bottom 30%): ``
- Reallocate budget to: ``

## 4) Experiments (max 3)
| Experiment | Hypothesis | Metric | Result | Decision (Kill/Continue/Scale) |
|---|---|---|---|---|
| Exp-1 |  |  |  |  |
| Exp-2 |  |  |  |  |
| Exp-3 |  |  |  |  |

## 5) Go/No-Go Guardrails Check
- W4 rule (`monetizable < 2.0%`): `Pass / Fail / N/A`
- W6 rule (`revenue/asset < $33`): `Pass / Fail / N/A`
- Cost rule (`variable cost > 35% for 2 weeks`): `Pass / Fail`
- Queue rule (`drain > 12h, 3+ days/week`): `Pass / Fail`

If any `Fail`:
- Immediate action this week:
- Owner:
- Due date:

## 6) Weekly P&L Snapshot
- Gross revenue: `$`
- Variable cost: `$`
- Contribution margin: `$`
- Fixed cost (if any): `$`
- Net profit (week): `$`
- Monthly net run-rate estimate: `$`

## 7) Next Week Plan
- Primary KPI to improve: ``
- Stop doing: ``
- Start doing: ``
- Continue doing: ``

---

## Appendix A) Daily Log (Optional)
| Date | Key Action | KPI Change | Blocker | Next Action |
|---|---|---|---|---|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## Appendix B) SQL Paste Area
```sql
-- Paste weekly SQL queries and outputs here
```
