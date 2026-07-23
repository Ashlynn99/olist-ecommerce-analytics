# Olist E-Commerce Analytics Report

## Executive Summary

I analyzed Olist's Brazilian e-commerce marketplace data from 2016 to 2018 to understand growth,
delivery performance, customer satisfaction, observed repeat-purchase behavior, seller risk, and
low-review risk across the order lifecycle. The project combines Python data cleaning, business EDA,
SQL analysis, customer cohort analysis, monthly seller monitoring, two leakage-aware machine
learning use cases, and intervention-value simulation.

The main finding is that customer experience is closely related to delivery performance. Orders
delivered more than 15 days late have a low-review rate of 78.9%, while the overall low-review rate
is 14.7%. This makes delivery delay the clearest operational issue in the analysis.

## Data Scope

The raw dataset contains 9 CSV files covering:

- Orders
- Customers
- Order items
- Payments
- Reviews
- Products
- Sellers
- Geolocation
- Product category translation

The final analytical base table contains 99,441 order-level records and 53 columns.

## Data Preparation

I kept the raw data unchanged and created a processed layer for analysis.

Key preparation steps:

- Converted order timestamps into datetime fields
- Created delivery metrics such as delivery days, estimated delivery days, delivery delta, and late
  delivery flag
- Aggregated payment records to order level
- Aggregated review records to order level
- Enriched order items with product, category, and seller information
- Aggregated item-level data to order level
- Collapsed geolocation records by zip code prefix to avoid row duplication during joins

This produced the main analytical table:

```text
data/processed/orders_analysis_base.csv
```

## Business KPI Summary

| Metric | Value |
|---|---:|
| Total orders | 99,441 |
| Delivered orders | 96,470 |
| Delivery rate | 97.0% |
| Gross payment volume, based on `payment_total` including freight | 16,008,872 BRL |
| Average payment value per order | 161 BRL |
| Freight share of payment total | 14.1% |
| Average delivery time | 12.6 days |
| Late delivery rate | 8.1% |
| Average review score | 4.09 |
| Low-review rate | 14.7% |

`payment_total` includes product value and freight, so I treat this measure as gross payment volume
rather than merchandise-only GMV. Product revenue and freight value are tracked separately in the
analytical table.

## Growth Analysis

The strongest gross payment volume month was 2017-11, with 1,194,883 BRL and 7,544 orders. Monthly
order and payment trends show clear growth across most of the observed period, with seasonal peaks
and later-period volatility.

Relevant figure:

![Monthly Orders and Gross Payment Volume](figures/monthly_orders_gmv.png)

## Delivery and Customer Experience

Delivery performance is the clearest customer experience driver in this project.

Key finding:

- Orders delivered 15+ days late had a low-review rate of 78.9%.
- Overall low-review rate was 14.7%.

This means extreme delivery delays are associated with a much higher probability of customer
dissatisfaction.

Relevant figure:

![Delivery Delay and Low Review Rate](figures/delivery_delay_low_review_rate.png)

## Category Analysis

The top category by revenue was `health_beauty`, generating 1,442,254 BRL across 8,802 orders.

Category analysis should not be based on revenue alone. A more useful management view combines:

- Revenue
- Order volume
- Freight share
- Average delivery time
- Late delivery rate
- Average review score
- Low-review rate

This helps identify categories that are both commercially important and experience-sensitive.

Relevant figure:

![Category Experience Map](figures/category_experience_map.png)

## Geographic Analysis

The top customer state by gross payment volume was SP, with 5,998,227 BRL and 41,746 orders.

State-level analysis helps identify where revenue is concentrated and where delivery experience
differs. This can support logistics planning, regional seller development, and customer support
prioritization.

Relevant figure:

![State Revenue and Delivery Experience](figures/state_revenue_delivery_experience.png)

## SQL Analytics Layer

I used DuckDB as a local embedded database. The SQL layer makes the business logic auditable and
reusable.

The project includes SQL files for:

- Executive KPIs
- Monthly growth
- Delivery experience
- Category and region performance
- Low-review risk segmentation

This mirrors a realistic analytics workflow where Python handles cleaning and modeling, while SQL
handles repeatable business queries.

## Post-Delivery Low-Review Risk Model

The machine learning task ranks delivered orders by the probability of receiving a low review score,
defined as:

```text
review_score <= 2
```

The model excludes review-derived fields to avoid leakage. It uses a time-based split:

- Train: orders before 2018-01-01
- Test: orders on or after 2018-01-01

Model results:

| Model | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Dummy baseline | 0.500 | 0.134 | 0.000 | 0.000 | 0.000 |
| Logistic regression, tuned threshold | 0.763 | 0.446 | 0.506 | 0.465 | 0.485 |

The model is best used as a post-delivery risk-ranking tool. It can help prioritize delivered orders
for customer support follow-up or operational review, but it should not be treated as an automated
decision system.

Important boundary: the model uses post-delivery features such as actual delivery days, estimated
delivery days, delivery delay, and late-delivery status. These variables are only known after
delivery, so this is not a pure purchase-time prediction system.

Relevant figures:

![Model ROC Curve](figures/model_low_review_roc_curve.png)

![Model Precision Recall Curve](figures/model_low_review_precision_recall_curve.png)

## Purchase-Time Low-Review Risk Model

I built a second model for early risk triage using only information available at or before purchase
time.

Current-order delivery outcomes and review information are excluded. Seller-history features are
calculated as-of each purchase timestamp and only use seller delivery or review events observed
before the current order.

Model comparison:

| Model | ROC-AUC | PR-AUC | Top 10% Capture | Top 10% Lift |
|---|---:|---:|---:|---:|
| Purchase-time logistic regression | 0.640 | 0.240 | 21.9% | 2.19x |
| Post-delivery logistic regression | 0.763 | 0.446 | 41.7% | 4.17x |

The purchase-time model provides weaker ranking performance, but it supports preventive monitoring
before delivery outcomes are known. This makes the two models complementary rather than
interchangeable.

Relevant figures:

![Purchase-Time Model ROC and PR Curves](figures/purchase_time_model_roc_pr.png)

![Purchase-Time Model Cumulative Gain](figures/purchase_time_model_cumulative_gain.png)

## Cohort and Observed Repeat-Purchase Analysis

I used `customer_unique_id` and delivered orders to examine customer lifecycle behavior.

Key results:

| Metric | Value |
|---|---:|
| Customers with delivered orders | 93,358 |
| Observed repeat customers | 2,801 |
| Observed repeat-customer rate | 3.0% |
| Customers eligible for 90-day analysis | 75,320 |
| 90-day repeat rate | 2.3% |
| Median days to second delivered order | 29 |

The dataset covers a limited historical window, so these figures represent observed repeat behavior
rather than true long-term retention. The primary 90-day comparison reduces right-censoring by
excluding customers without sufficient follow-up time.

First-order experience comparisons were descriptive rather than causal. The 90-day repeat rate was
2.3% after an on-time first order and 2.1% after a late first order. Customers with a first-order
low review did not show a simple lower 90-day repeat rate, highlighting the importance of avoiding
unsupported causal claims.

Relevant figures:

![Observed Cohort Repeat-Purchase Activity](figures/cohort_repeat_activity_heatmap.png)

![Monthly New vs Repeat Orders](figures/monthly_new_vs_repeat_orders.png)

## Additional Analysis

I added four focused extensions to make the project more practical without making the workflow
unnecessarily complex.

### Seller Performance Scorecard

The seller scorecard evaluates sellers across commercial value and customer experience risk.

Key outputs:

- High-value high-risk sellers: 35
- Orders associated with high-value high-risk sellers: 9,890

This segment is important because these sellers contribute meaningful marketplace value while also
creating elevated customer dissatisfaction risk. In a marketplace setting, this type of segmentation
can support seller monitoring, account management, and targeted operational follow-up.

Relevant figure:

![Seller Scorecard Value Risk](figures/seller_scorecard_value_risk.png)

### Seller Monthly Risk Monitoring

I converted the static seller scorecard into a recurring seller-month monitoring workflow. The
system combines customer-experience risk, deterioration relative to each seller's own history,
monthly commercial exposure, and minimum evidence requirements.

Low-review, late-delivery, and cancellation rates are smoothed toward the monthly marketplace rate.
This reduces false alerts from sellers with very small monthly samples.

The priority score combines 55% experience risk, 25% deterioration, and 20% seller value, followed
by a monthly-volume reliability adjustment. Critical alerts represent the top 10% of eligible
sellers by priority score with an experience risk score of at least 60.

Latest complete monitoring month, 2018-08:

| Metric | Value |
|---|---:|
| Active sellers | 1,278 |
| Sellers eligible for alerts | 343 |
| Critical sellers | 34 |
| Watch sellers | 49 |
| Sellers escalated from stable or watch | 44 |
| Critical sellers' share of monthly seller-order value | 11.6% |
| Critical sellers' share of monthly seller-orders | 14.3% |

The monitor outputs a prioritized seller watchlist, specific alert drivers, suggested operational
actions, and month-over-month status transitions. It should support seller investigation and account
management rather than automatic penalties.

Relevant figures:

![Seller Monthly Risk Priority Matrix](figures/seller_monthly_priority_matrix.png)

![Seller Risk Status Transitions](figures/seller_risk_transition_matrix.png)

## Intervention Cost and Expected-Value Simulation

I translated the purchase-time and post-delivery risk rankings into intervention-capacity and value
scenarios. The simulation uses historical low-review outcomes together with explicit assumptions for
contact cost, intervention effectiveness, and the value of a successful recovery.

Base-case results:

| Strategy | Risk Coverage | Orders Contacted | Low Reviews Captured | Expected Net Value | Incremental Value vs Random | ROI |
|---|---:|---:|---:|---:|---:|---:|
| Purchase-time prevention | 5% | 2,624 | 13.4% | 2,759 BRL | 6,678 BRL | 35.1% |
| Post-delivery recovery | 5% | 2,624 | 25.3% | 15,158 BRL | 37,421 BRL | 48.1% |

The purchase-time scenario assumes a 3 BRL automated action with 15% effectiveness. The
post-delivery scenario assumes a 12 BRL service-recovery action with 35% effectiveness. Both use 75
BRL as the assumed value of a successful recovery.

The incremental-value comparison isolates the contribution of model ranking relative to randomly
contacting the same number of orders. Conservative assumptions make both strategies unprofitable, so
these values should guide pilot design rather than be presented as realized savings.

Relevant figures:

![Intervention Expected Net Value](figures/intervention_net_value_by_coverage.png)

![Intervention Value Sensitivity](figures/intervention_value_sensitivity.png)

### Logistics Distance and Cross-State Delivery

I estimated customer-seller distance using zip-code prefix geolocation and compared same-state
versus cross-state routes.

Key results:

| Route Type | Seller-Orders | Avg Distance KM | Avg Delivery Days | Late Rate | Low-Review Rate |
|---|---:|---:|---:|---:|---:|
| Same-state | 34,907 | 153.8 | 7.91 | 5.9% | 10.9% |
| Cross-state | 61,767 | 851.9 | 15.03 | 9.0% | 14.7% |

This adds more context to the delivery-delay finding. Cross-state routes are longer, slower, and
associated with higher low-review risk.

Relevant figure:

![Logistics Distance Delivery Review](figures/logistics_distance_delivery_review.png)

### Model Lift and Business Simulation

I translated the low-review model into a practical prioritization question:

> If the support team can only review the highest-risk orders, how many low reviews could it cover?

Key results:

| Highest-Risk Segment | Orders Reviewed | Low Reviews Captured | Capture Rate | Segment Precision | Lift |
|---|---:|---:|---:|---:|---:|
| Top 5% | 2,624 | 1,777 | 25.3% | 67.7% | 5.06x |
| Top 10% | 5,247 | 2,927 | 41.7% | 55.8% | 4.17x |
| Top 20% | 10,494 | 3,973 | 56.5% | 37.9% | 2.83x |

This makes the machine learning component easier to apply. The model is not just a classifier; it
becomes a way to prioritize limited customer support capacity.

Relevant figure:

![Low Review Cumulative Gain](figures/model_low_review_cumulative_gain.png)

### Root-Cause Decomposition

I decomposed low-review outcomes by contribution, not only by rate. This is important because a
small segment can have a high low-review rate but limited business impact, while a larger segment
can create more total customer-experience damage even at a lower rate.

Key results:

| Root-Cause View | Result |
|---|---:|
| 15+ days late low-review rate | 78.9% |
| 15+ days late share of all low reviews | 8.2% |
| Cross-state route share of all low reviews | 67.4% |
| Top category contributor | bed_bath_table |
| Top cross-dimensional segment | SP / cross_state |
| Top segment share of all low reviews | 44.7% |

The root-cause backlog ranks segments by contribution and risk together. In the current dataset,
cross-state logistics and seller-state route combinations create the largest concentration of
low-review outcomes, while severe delivery-delay buckets remain the clearest diagnostic signal for
individual order dissatisfaction.

Relevant figures:

![Root-Cause Pareto](figures/root_cause_low_review_pareto.png)

![Root-Cause Priority Matrix](figures/root_cause_segment_priority_matrix.png)

### Seller Operations Playbook

I converted the monthly seller monitor into a more operational playbook. The goal is to make seller
risk actionable for a marketplace operations team, not only descriptive for a report.

Latest action queue:

| Metric | Value |
|---|---:|
| Sellers in action queue | 83 |
| P0 critical escalations | 23 |
| Seller-orders represented | 1,537 |
| Seller order value represented | 208,344 BRL |
| Estimated commercial value at risk | 33,212 BRL |

The playbook assigns each seller to an action tier:

| Tier | Owner | SLA | Operating Meaning |
|---|---|---:|---|
| P0 Critical Escalation | Seller Operations Lead | 2 business days | Critical and newly escalated sellers |
| P1 Critical Stabilization | Account Manager | 3 business days | Critical sellers needing corrective plans |
| P2 Watch Deterioration | Seller Operations Analyst | 5 business days | Watch sellers with deterioration or high priority |
| P3 Watch Monitoring | Operations Analyst | 7 business days | Watch sellers requiring routine monitoring |

This makes the seller risk monitor closer to a real operating workflow: assign owner, diagnose alert
driver, act within SLA, and evaluate next-month status movement.

Relevant figures:

![Seller Operations Queue by Tier](figures/seller_operations_queue_by_tier.png)

![Seller Value at Risk by Action Tier](figures/seller_operations_value_at_risk.png)

### Intervention Experiment Design

The intervention-value model is a scenario estimate, so I added an experiment design to define how
the marketplace team could validate actual impact before scaling.

Experiment plan:

| Strategy | Candidate Orders | Baseline Low-Review Rate | Minimum Detectable Effect |
|---|---:|---:|---:|
| Purchase-time prevention | 2,624 | 36.0% | 5.3% |
| Post-delivery recovery | 2,624 | 67.7% | 5.1% |

The design uses deterministic 50/50 treatment-control assignment at the `order_id` level. The
primary metric is low-review rate, with average review score, observed 90-day repeat behavior,
cancellation rate, and cost per successful recovery tracked as secondary or guardrail metrics.

This completes the decision loop: model ranking identifies likely risk, ROI simulation estimates
economic value, and experiment design defines how to measure whether the intervention truly works.

Relevant figures:

![Experiment Sample Size Plan](figures/experiment_sample_size_plan.png)

![Experiment Assignment Balance](figures/experiment_assignment_balance.png)

## Operational Dashboard

I packaged the main analytical outputs into a Streamlit dashboard so that the project can be used as
an operating tool rather than only read as a report:

- **Executive KPI Overview:** marketplace scale, payment volume, delivery performance, and
  customer-experience risk.
- **Experience Root Cause:** contribution-based root-cause backlog across delay, route, geography,
  and category segments.
- **Seller Risk Monitoring:** monthly alert volumes, risk transitions, and a prioritized seller
  watchlist.
- **Seller Action Queue:** P0–P3 seller operating queue with owners, SLA, diagnostic focus, and
  estimated value at risk.
- **Purchase-Time Risk Triage:** leakage-controlled model performance and an order-level risk queue
  for preventive action.
- **Intervention ROI Simulator:** adjustable contact cost, effectiveness, recovery value, and
  coverage assumptions.
- **Experiment Design:** treatment/control assignment, sample-size planning, and metric governance.

Run the dashboard after generating the analysis outputs:

```bash
make dashboard
```

## Business Recommendations

1. Prioritize extreme delivery delay prevention.

   Orders delivered more than 15 days late show a very high low-review risk. Olist could monitor
   these orders and trigger proactive communication or recovery offers.

2. Use category-level experience monitoring.

   Revenue-heavy categories should be monitored together with delay rate, freight share, and
   low-review rate. High-revenue categories with weak experience metrics deserve closer review.

3. Build a low-review risk workflow.

   The model can rank delivered orders by dissatisfaction risk. Customer support teams could use
   this ranking to prioritize post-delivery outreach or operational review.

4. Use seller scorecards and monthly alerts for seller performance monitoring.

   High-value high-risk sellers should be reviewed first. Monthly risk transitions can distinguish
   persistent risk from newly deteriorating sellers and direct account-management attention.

5. Convert seller alerts into an operating cadence.

   P0 and P1 sellers should receive owner-assigned review with explicit SLA tracking. Weekly and
   monthly reviews should track whether sellers move back to stable, stay risky, or deteriorate.

6. Separate purchase-time and post-delivery models.

   Use the purchase-time model for preventive monitoring and the post-delivery model for
   service-recovery prioritization. Their different performance levels reflect different information
   availability.

7. Track customer lifecycle metrics with fixed observation windows.

   Use the 90-day observed repeat rate as a consistent monitoring metric and compare it across
   cohorts, categories, and first-order experiences.

8. Pilot interventions before scaling.

   Start with the highest-risk 5% of orders and use randomized treatment and control groups to
   estimate actual incremental recovery, cost per contact, and downstream customer value.

## Limitations

- The dataset is historical and does not reflect current Olist operations.
- The analysis is observational and does not prove causality.
- Some features are only available after delivery, so the current model is not a pure purchase-time
  prediction system.
- The purchase-time model uses leakage-controlled historical seller outcomes, but data availability
  in a production system would need to be confirmed.
- Repeat-purchase metrics are affected by the limited observation period and do not represent true
  long-term retention.
- Seller monitoring alerts use relative thresholds and smoothed historical evidence; they support
  investigation rather than proving seller fault.
- Intervention-value estimates depend on assumed effectiveness and recovery value; they are
  scenarios rather than realized causal impact.
- `payment_total` includes freight, so gross payment volume should not be interpreted as
  merchandise-only GMV.
- The dataset does not include customer demographics, marketing acquisition channels, or full seller
  operational history.

## Conclusion

This project shows a complete but focused analytics workflow: raw data understanding, cleaning,
business analysis, SQL querying, predictive modeling, customer lifecycle analysis, and seller
monitoring. I extended the analysis into root-cause decomposition, seller operations playbook, and
experiment design so the final project reads less like a one-time notebook analysis and more like a
repeatable operating system for marketplace experience management.

The main business takeaway is that logistics performance is closely tied to customer satisfaction,
and that order, seller, and route risk can be structured into practical prioritization workflows.
The strongest next step in a real company setting would be a controlled pilot that tests whether
risk-based outreach reduces low-review outcomes without increasing cost, cancellations, or seller
friction.
