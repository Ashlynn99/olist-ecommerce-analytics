# Seller Operations Playbook

## Objective

This playbook converts the monthly seller risk monitor into an operating workflow. It defines alert
tiers, owners, service-level expectations, diagnostic focus, and success metrics.

## Current Queue Snapshot

| Metric | Value |
|---|---:|
| Sellers in action queue | 83 |
| P0 critical escalations | 23 |
| Seller-orders represented | 1,537 |
| Seller order value represented | 208,344 BRL |
| Estimated commercial value at risk | 33,212 BRL |
| Highest-priority seller | `c70c1b0d8ca86052f45a432a38b73958` |

## Alert Action Matrix

| action_tier | trigger | owner | sla_business_days | first_action | success_metric |
| --- | --- | --- | --- | --- | --- |
| P0 Critical Escalation | Critical status and escalated from previous month | Seller Operations Lead | 2 | Open seller-level incident review and inspect recent delayed orders. | Reduce late rate and low-review rate in next monitoring month. |
| P1 Critical Stabilization | Critical status with persistent high experience risk | Account Manager | 3 | Review fulfillment process and agree on corrective operating plan. | Move seller from critical to watch or stable within two months. |
| P2 Watch Deterioration | Watch status with deterioration or high priority score | Seller Operations Analyst | 5 | Diagnose alert driver and monitor next-cycle order experience. | Prevent escalation into critical status. |
| P3 Watch Monitoring | Watch status without immediate escalation signal | Operations Analyst | 7 | Add to weekly monitoring list and review repeated alert drivers. | Maintain stable status and avoid deterioration. |

## Queue Summary by Tier

| Action Tier | Owner | SLA Days | Sellers | Seller Orders | Seller Value | Value at Risk | Avg Priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 Critical Escalation | Seller Operations Lead | 2 | 23 | 744 | 90,425 BRL | 14,421 BRL | 76.2 |
| P1 Critical Stabilization | Account Manager | 3 | 11 | 193 | 26,301 BRL | 4,595 BRL | 75.7 |
| P2 Watch Deterioration | Seller Operations Analyst | 5 | 22 | 348 | 60,197 BRL | 9,562 BRL | 64.1 |
| P3 Watch Monitoring | Operations Analyst | 7 | 27 | 252 | 31,422 BRL | 4,633 BRL | 63.4 |

## Operating Workflow

1. Refresh monthly seller risk monitor after the complete month closes.
2. Assign each seller to an action tier using risk status, transition, and priority score.
3. Route P0 and P1 cases to owner review before lower-priority watch cases.
4. Diagnose the dominant alert driver: fulfillment delay, low review, cancellation, deterioration,
   or value exposure.
5. Track next-month status movement and measure whether critical/watch sellers return to stable.

## Operating Cadence

| Cadence | Review Question | Output |
|---|---|---|
| Daily during month close | Are any P0 sellers still unresolved after SLA? | Escalation note to Seller Operations Lead |
| Weekly | Which alert drivers repeat across the queue? | Root-cause backlog by delay, review, cancellation, and value exposure |
| Monthly | Which sellers improved, stayed risky, or deteriorated? | Status transition review and next-cycle queue |
| Quarterly | Are interventions reducing risk concentration? | Seller-policy and support-capacity recommendation |

## Governance Notes

- Alerts prioritize human review; they are not automatic seller penalties.
- SLA is counted in business days from the monthly monitoring refresh.
- Success should be evaluated by movement in late rate, low-review rate, cancellation rate,
  priority score, and seller status transition.

## Outputs

- `reports/seller_alert_action_matrix.csv`
- `reports/seller_operations_queue.csv`
- `reports/seller_operations_queue_summary.csv`
- `reports/figures/seller_operations_queue_by_tier.png`
- `reports/figures/seller_operations_value_at_risk.png`
