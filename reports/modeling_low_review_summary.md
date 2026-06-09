# Post-Delivery Low Review Risk Modeling Summary

## Objective

Rank delivered orders by the probability of receiving a low review score (`review_score <= 2`).

## Data Split

- Training period: orders before 2018-01-01
- Test period: orders on or after 2018-01-01
- Training rows: 43,363
- Test rows: 52,468
- Test low-review rate: 13.4%

## Leakage Control

The model excludes review text, review score, review count, and any field derived directly from the
review outcome. It does include post-delivery operational fields such as actual delivery days and
late-delivery status, so it is designed for service recovery and operational review after delivery.

## Model Performance

| Model | Threshold | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Dummy prior | 0.500 | 0.500 | 0.134 | 0.000 | 0.000 | 0.000 |
| Logistic tuned | 0.682 | 0.763 | 0.446 | 0.506 | 0.465 | 0.485 |

## Interpretation

I treat the model as a post-delivery risk-ranking tool rather than an automated decision system. It
can help prioritize delivered orders for customer support follow-up or operational review.

The project also includes a separate purchase-time model that excludes current-order delivery
outcomes. Comparing the two models separates prevention use cases from post-delivery recovery use
cases and makes the cost of earlier prediction explicit.
