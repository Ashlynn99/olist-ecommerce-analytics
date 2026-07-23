# AI Operations Briefing

Offline deterministic agent output. The briefing is generated from project report tables without
using paid API calls; an OpenAI layer can be enabled later for richer narration.

## Executive Snapshot

- Monitoring month: 2018-08
- Operating posture: elevated logistics pressure
- Active sellers: 1,278
- Alert-eligible sellers: 343
- Critical sellers: 34
- Watch sellers: 49
- Seller orders: 6,571
- Seller GMV: 1,003,308 BRL
- Late-delivery rate: 10.2%
- Low-review rate: 11.3%

The main signal is seller-side customer-experience pressure, led by high late-delivery risk. This
should trigger investigation and queue prioritization, not automatic seller penalties.

## What Changed

- Critical sellers changed by +3.
- Watch sellers changed by +11.
- Seller orders changed by +197.
- Late-delivery rate changed by +5.8 pp.
- Low-review rate changed by -0.0 pp.
- Cancellation rate changed by -0.2 pp.

## Recent Monitoring Trend

| Month | Orders | GMV | Late Rate | Low-Review Rate | Watch | Critical |
|---|---:|---:|---:|---:|---:|---:|
| 2018-03 | 7,281 | 1,155,127 BRL | 21.2% | 23.1% | 51 | 34 |
| 2018-04 | 7,069 | 1,159,698 BRL | 5.2% | 13.7% | 49 | 37 |
| 2018-05 | 6,967 | 1,149,782 BRL | 8.1% | 12.2% | 46 | 35 |
| 2018-06 | 6,274 | 1,022,677 BRL | 1.3% | 11.2% | 26 | 23 |
| 2018-07 | 6,374 | 1,058,728 BRL | 4.4% | 11.3% | 38 | 31 |
| 2018-08 | 6,571 | 1,003,308 BRL | 10.2% | 11.3% | 49 | 34 |

## Main Risk Drivers

- high late-delivery risk: 57 sellers
- high low-review risk: 53 sellers
- high value exposure: 53 sellers
- material deterioration vs seller history: 34 sellers
- high cancellation risk: 7 sellers

## Latest Risk Transitions

- Sellers with escalated or improved status: 81
- escalated: 44
- improved: 37

## Root-Cause Backlog

| Rank | Segment | Family | Orders | Low-Review Rate | Share of Low Reviews | Excess Low Reviews |
|---:|---|---|---:|---:|---:|---:|
| 1 | SP / cross_state | seller_state_route | 38,623 | 17.0% | 44.7% | 859 |
| 2 | on_or_before_estimate / cross_state | delay_route | 56,175 | 9.8% | 37.7% | -2,754 |
| 3 | SP / same_state | seller_state_route | 31,319 | 12.1% | 25.8% | -832 |
| 4 | on_or_before_estimate / same_state | delay_route | 32,474 | 8.3% | 18.5% | -2,063 |
| 5 | 8_14_days_late / cross_state | delay_route | 1,439 | 78.6% | 7.6% | 893 |
| 6 | 15_plus_days_late / cross_state | delay_route | 1,341 | 80.6% | 7.2% | 854 |

## Seller Action Queue

- Sellers in queue: 83
- Queue seller orders: 1,537
- Queue seller GMV: 208,344 BRL
- Estimated commercial value at risk: 33,212 BRL

| Rank | Seller | Tier | Owner | SLA | State | Priority | First Action |
|---:|---|---|---|---:|---|---:|---|
| 1 | `c70c1b0d8ca86052f45a432a38b73958` | P0 Critical Escalation | Seller Operations Lead | 2 days | SP | 88.4 | Open seller-level incident review and inspect recent delayed orders. |
| 2 | `e9bc59e7b60fc3063eb2290deda4cced` | P0 Critical Escalation | Seller Operations Lead | 2 days | PR | 87.7 | Open seller-level incident review and inspect recent delayed orders. |
| 3 | `16090f2ca825584b5a147ab24aa30c86` | P1 Critical Stabilization | Account Manager | 3 days | SP | 86.7 | Review fulfillment process and agree on corrective operating plan. |
| 4 | `c33847515fa6305ce6feb1e818569f13` | P0 Critical Escalation | Seller Operations Lead | 2 days | SC | 85.2 | Open seller-level incident review and inspect recent delayed orders. |
| 5 | `cab85505710c7cb9b720bceb52b01cee` | P0 Critical Escalation | Seller Operations Lead | 2 days | SP | 83.4 | Open seller-level incident review and inspect recent delayed orders. |
| 6 | `8b9d6eec4a7eb7d0f9d579ce0b38324d` | P1 Critical Stabilization | Account Manager | 3 days | RJ | 82.6 | Review fulfillment process and agree on corrective operating plan. |
| 7 | `87142160b41353c4e5fca2360caf6f92` | P0 Critical Escalation | Seller Operations Lead | 2 days | RS | 82.3 | Open seller-level incident review and inspect recent delayed orders. |
| 8 | `f46490624488d3ff7ce78613913a7711` | P0 Critical Escalation | Seller Operations Lead | 2 days | SP | 79.4 | Open seller-level incident review and inspect recent delayed orders. |

## Purchase-Time Triage

- ROC-AUC: 0.640
- PR-AUC: 0.240
- Top 10% capture rate: 21.9%
- Top 10% precision: 29.4%

Use purchase-time ranking for prevention capacity planning. It is weaker than post-delivery recovery
by design because it excludes current-order delivery outcomes.

## Intervention Recommendation

- Purchase-time prevention: recommend 5.0% coverage, 2,624 orders contacted, expected net value
  2,759 BRL, expected ROI 35.1%.
- Post-delivery recovery: recommend 5.0% coverage, 2,624 orders contacted, expected net value 15,158
  BRL, expected ROI 48.1%.

## Experiment Validation

- post_delivery: 2,624 candidate orders, baseline low-review rate 67.7%, 1,305 treatment and 1,319
  control orders.
- purchase_time: 2,624 candidate orders, baseline low-review rate 36.0%, 1,327 treatment and 1,297
  control orders.

## Recommended Operating Actions

- P0: Work the P0 Critical Escalation seller queue within the two-business-day SLA.
- P1: Investigate late-delivery and low-review overlaps before broad seller action.
- P2: Use the 5% intervention-coverage scenario as the first pilot capacity anchor.
- P3: Validate intervention value with the treatment/control experiment design.
- P4: Keep seller penalties, customer outreach, and compensation human-approved.

## Decision Boundaries

- Seller alerts are investigation priorities, not automatic penalties.
- Intervention value outputs are retrospective scenarios, not causal proof.
- The historical Olist dataset covers 2016-2018 and is not current operations data.
- Customer outreach, compensation, and seller enforcement remain human-approved actions.
