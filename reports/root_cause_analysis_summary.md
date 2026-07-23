# Root-Cause Decomposition Summary

## Objective

I decomposed low-review and late-delivery issues by contribution, not only by rate. This separates
small high-risk pockets from large operational drivers that create the most customer-experience
damage.

## Main Findings

| Root-Cause View | Key Result |
|---|---:|
| 15+ days late segment | 8.2% of all low reviews |
| 15+ days late low-review rate | 78.9% |
| Cross-state routes | 67.4% of all low reviews |
| Top category contributor | bed_bath_table |
| Top cross-dimensional segment | SP / cross_state |
| Top segment low-review rate | 17.0% |
| Top segment share of low reviews | 44.7% |

## Contribution View

| Root-Cause Layer | Largest Contributor | Orders | Low-Review Rate | Share of Low Reviews | Payment Volume |
| --- | --- | --- | --- | --- | --- |
| delivery_delay_bucket | on_or_before_estimate | 88,649 | 9.3% | 56.2% | 14,070,141 BRL |
| route_type | cross_state | 63,313 | 15.6% | 67.4% | 11,078,350 BRL |
| customer_state | SP | 41,746 | 12.7% | 36.1% | 5,998,227 BRL |
| main_product_category | bed_bath_table | 9,350 | 16.7% | 10.6% | 1,249,807 BRL |

## Root-Cause Backlog

| Segment View | Segment | Orders | Low-Review Rate | Share of Low Reviews | Excess Low Reviews | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| seller_state_route | SP / cross_state | 38,623 | 17.0% | 44.7% | 859 | 111.7 |
| delay_route | on_or_before_estimate / cross_state | 56,175 | 9.8% | 37.7% | -2,754 | 87.1 |
| seller_state_route | SP / same_state | 31,319 | 12.1% | 25.8% | -832 | 71.7 |
| delay_route | on_or_before_estimate / same_state | 32,474 | 8.3% | 18.5% | -2,063 | 52.8 |
| delay_route | 8_14_days_late / cross_state | 1,439 | 78.6% | 7.6% | 893 | 51.7 |
| delay_route | 15_plus_days_late / cross_state | 1,341 | 80.6% | 7.2% | 854 | 50.4 |
| delay_route | unknown / cross_state | 1,414 | 77.2% | 7.1% | 840 | 49.7 |
| delay_route | 4_7_days_late / cross_state | 1,289 | 63.2% | 5.4% | 607 | 39.6 |

## Business Interpretation

- Delivery delay remains the clearest root-cause signal because the severe-delay bucket combines
  very high dissatisfaction risk with meaningful low-review contribution.
- Cross-state logistics should be treated as an operating-risk layer, not just a geographic
  descriptor. It helps explain why some categories and customer states produce more experience
  pressure.
- The best operational queue should rank segments by contribution and risk together. A segment with
  high risk but limited volume is useful for diagnosis; a segment with high contribution and high
  risk is a better first action area.

## Recommended Follow-Up

1. Treat severe delivery delay as the primary operating defect because it has the highest
   dissatisfaction rate.
2. Use cross-state route monitoring as a logistics control layer because it carries most
   low-review volume.
3. Prioritize seller-state and category-state combinations when allocating seller operations,
   logistics, and customer support capacity.

## Outputs

- `reports/root_cause_dimension_summary.csv`
- `reports/root_cause_top_contributors.csv`
- `reports/root_cause_priority_segments.csv`
- `reports/figures/root_cause_low_review_pareto.png`
- `reports/figures/root_cause_delay_bucket_impact.png`
- `reports/figures/root_cause_category_state_heatmap.png`
- `reports/figures/root_cause_segment_priority_matrix.png`
