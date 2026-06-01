# Low Review Risk Modeling Summary

## Objective

Predict whether a delivered order is likely to receive a low review score (`review_score <= 2`).

## Data Split

- Training period: orders before 2018-01-01
- Test period: orders on or after 2018-01-01
- Training rows: 43,363
- Test rows: 52,468
- Test low-review rate: 13.4%

## Leakage Control

The model excludes review text, review score, review count, and any field derived directly from the review outcome.

## Model Performance

| Model | Threshold | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Dummy prior | 0.500 | 0.500 | 0.134 | 0.000 | 0.000 | 0.000 |
| Logistic tuned | 0.682 | 0.763 | 0.446 | 0.506 | 0.465 | 0.485 |

## Interpretation

I treat the model as a risk-ranking tool rather than an automated decision system. It can help prioritize orders for customer support follow-up or operational review.

A useful next improvement would be to compare two versions of the model: one available at purchase time and one available after delivery. That would separate prevention use cases from post-delivery recovery use cases.
