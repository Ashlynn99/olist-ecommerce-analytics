# Purchase-Time Low-Review Risk Model

## Objective

I built this model to rank low-review risk using only information available at or before purchase
time.

The feature set excludes actual delivery outcomes and current-order review information.
Seller-history features are calculated as-of each order timestamp and only use seller delivery or
review events that occurred before the current purchase.

## Time Split

- Train: orders before 2018-01-01
- Test: orders on or after 2018-01-01
- Train rows: 43,364
- Test rows: 52,468
- Test low-review rate: 13.4%

## Performance

| Metric | Value |
|---|---:|
| ROC-AUC | 0.640 |
| PR-AUC | 0.240 |
| Precision at 0.50 threshold | 0.201 |
| Recall at 0.50 threshold | 0.526 |
| F1 at 0.50 threshold | 0.291 |
| Top 10% low reviews captured | 21.9% |
| Top 10% precision | 29.4% |
| Top 10% lift vs baseline | 2.19x |

## Interpretation

This model is designed for early risk triage after an order is placed. It is expected to perform
below the post-delivery model because it deliberately excludes the strongest delivery-outcome
variables.

The largest absolute coefficients include: main product category food drink, main product category
fashion male clothing, seller prior deliveries mean, main seller state MT, main product category
audio.

Seller-history features are leakage-controlled, but the analysis remains observational. The model
should support prioritization and monitoring rather than automated customer or seller decisions.
