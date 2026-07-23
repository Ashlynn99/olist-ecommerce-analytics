# Intervention Experiment Design

## Objective

The ROI model is a scenario estimate. This experiment design defines how a marketplace team could
validate whether risk-based intervention actually reduces low-review outcomes and creates economic
value.

## Experiment Candidates

The candidate pool uses the model-recommended highest-risk 5% of test-period orders for each
strategy.

| Strategy | Candidate Orders | Baseline Low-Review Rate | Minimum Detectable Effect |
|---|---:|---:|---:|
| Purchase-time prevention | 2,624 | 36.0% | 5.3% |
| Post-delivery recovery | 2,624 | 67.7% | 5.1% |

## Design Summary

| Strategy | Candidate Orders | Control | Treatment | Baseline Low-Review Rate | MDE, Absolute | MDE, Relative | N/Group for 10% Reduction | N/Group for 15% Reduction | N/Group for 20% Reduction | Daily Candidate Rate | Historical Days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| post_delivery | 2,624 | 1,319 | 1,305 | 67.7% | 5.1% | 7.6% | 785 | 356 | 204 | 10.9 | 240 |
| purchase_time | 2,624 | 1,297 | 1,327 | 36.0% | 5.3% | 14.7% | 2,722 | 1,194 | 663 | 10.9 | 241 |

## Metric Plan

| metric_type | metric_name | definition | decision_use |
| --- | --- | --- | --- |
| primary | low_review_rate | Share of treated/control orders with review_score <= 2. | Main success metric for customer-experience recovery. |
| secondary | average_review_score | Mean review score among reviewed orders. | Checks whether improvement is broad, not only at the low-score cutoff. |
| secondary | repeat_purchase_within_90d | Observed repeat order within 90 days for eligible customers. | Monitors whether intervention improves downstream customer behavior. |
| guardrail | cancellation_rate | Share of orders canceled after intervention eligibility. | Prevents operational actions from increasing cancellations. |
| guardrail | cost_per_successful_recovery | Intervention cost divided by incremental low reviews avoided. | Ensures the program remains economically viable. |

## Recommended Test Design

- Unit of randomization: `order_id`.
- Assignment: deterministic 50/50 split into treatment and control using a stable hash of strategy
  and order id.
- Purchase-time prevention treatment: proactive message or operational escalation after purchase.
- Post-delivery recovery treatment: human support or service-recovery action after delivery.
- Primary decision metric: low-review rate.
- Guardrail metrics: cancellation rate and cost per successful recovery.

## Implementation Plan

| Step | Standard |
|---|---|
| Eligibility logging | Save every eligible order with strategy, score, timestamp, and assignment group. |
| Treatment logging | Record whether the intended message, support action, or escalation was actually delivered. |
| Holdout discipline | Keep control orders free from the test intervention unless a safety or compliance issue appears. |
| Outcome window | Evaluate low-review outcomes after the review window has closed for both groups. |
| Readout | Report effect size, confidence interval, guardrail movement, cost, and operational learnings. |

## Decision Rules

1. Launch only if treatment reduces low-review rate without worsening guardrail metrics.
2. Compare incremental benefit with actual intervention cost, not only model-ranked risk.
3. Roll out gradually by capacity tier if the pilot is positive.
4. Keep seller-penalty decisions separate from this order-level customer intervention test.

## Limitations

- The historical dataset cannot observe actual intervention effects.
- The sample-size numbers are planning approximations using normal two-proportion assumptions.
- A production system would need live eligibility rules, treatment logging, and post-treatment
  outcome tracking.

## Outputs

- `reports/intervention_experiment_design_summary.csv`
- `reports/intervention_experiment_metric_plan.csv`
- `reports/intervention_experiment_candidate_frame.csv`
- `reports/figures/experiment_sample_size_plan.png`
- `reports/figures/experiment_assignment_balance.png`
