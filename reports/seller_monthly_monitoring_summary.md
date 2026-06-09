# Seller Monthly Risk Monitoring Summary

## Objective

I converted the static seller scorecard into a monthly monitoring system that identifies seller
deterioration, quantifies commercial exposure, and produces a prioritized operational watchlist.

The latest complete monitoring month is **2018-08**. The incomplete final month in the source data
is excluded.

## Latest Monitoring Results

- Active sellers: 1,278
- Sellers eligible for alerts: 343
- Critical sellers: 34
- Watch sellers: 49
- Sellers escalated from the previous month: 44
- Critical sellers' share of monthly seller-order value: 11.6%
- Critical sellers' share of monthly seller-orders: 14.3%
- Highest-priority seller: `c70c1b0d8ca86052f45a432a38b73958`, priority score 88.4, with 44
  seller-orders and 6,969 BRL in monthly order value
- Primary alert drivers: high low-review risk; high late-delivery risk; material deterioration vs
  seller history; high value exposure

## Monitoring Method

The unit of analysis is a seller-month. Each active seller is evaluated using:

1. Low-review risk
2. Late-delivery risk
3. Cancellation risk
4. Deterioration relative to the seller's own prior history
5. Monthly commercial exposure

Low-review, late-delivery, and cancellation rates use empirical-Bayes-style smoothing toward the
current marketplace rate with a prior strength of 20 orders. This reduces false alerts caused by
very small monthly samples.

The priority score combines 55% experience risk, 25% deterioration, and 20% seller value, then
applies a reliability adjustment based on monthly order volume. Sellers need at least 5 monthly
seller-orders and 3 reviewed orders to receive a watch or critical alert.

- Critical: top 10% of eligible sellers by priority score and experience risk score of at least 60
- Watch: top 25% of eligible sellers by priority score and experience risk score of at least 50

## Interpretation

This is an operational prioritization system, not a causal model or automatic seller penalty system.
A critical alert means that a seller combines relatively high customer-experience risk with
sufficient evidence and business exposure. The recommended next step is a seller-level investigation
using recent orders and complaint details.
