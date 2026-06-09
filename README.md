# Olist E-Commerce Operations Analytics

[![Quality checks](https://github.com/Ashlynn99/olist-ecommerce-analytics/actions/workflows/quality.yml/badge.svg)](https://github.com/Ashlynn99/olist-ecommerce-analytics/actions/workflows/quality.yml)

End-to-end marketplace analytics project combining business intelligence, leakage-aware risk
modeling, seller monitoring, customer lifecycle analysis, and intervention ROI simulation.

I built the project around a practical operating question: **how should an e-commerce marketplace
identify customer-experience risk early, prioritize limited operations capacity, and decide whether
intervention is economically justified?**

Data source: [Kaggle Olist Brazilian E-Commerce Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

## Executive Summary

- Built a reproducible Python, SQL, and Streamlit workflow across 9 relational source tables and
  99,441 orders.
- Identified delivery delay as the strongest operational issue: orders delivered 15+ days late had a
  78.9% low-review rate.
- Developed separate purchase-time and post-delivery risk models to distinguish prevention from
  service-recovery use cases.
- Converted a static seller scorecard into monthly risk monitoring with prioritized alerts, risk
  transitions, and recommended actions.
- Translated model rankings into cost, ROI, break-even, and sensitivity scenarios for operational
  decision-making.

## Core Business Questions

1. Where are marketplace value and customer-experience risks concentrated?
2. Which orders and sellers should operations teams prioritize under limited capacity?
3. Under what assumptions does risk-based intervention create positive expected value?

## Key Results

| Area | Result |
|---|---|
| Marketplace scale | 99,441 orders and 16.0M BRL gross payment volume |
| Delivery experience | 8.1% late-delivery rate; 78.9% low-review rate for orders 15+ days late |
| Post-delivery risk model | 0.763 ROC-AUC; top 10% captured 41.7% of low reviews |
| Purchase-time risk model | 0.640 ROC-AUC; top 10% captured 21.9% of low reviews without current-order delivery outcomes |
| Customer lifecycle | 2.3% observed 90-day repeat rate; median 29 days to second purchase |
| Seller monitoring | 34 critical and 49 watch sellers in the latest complete month; 44 sellers escalated |
| Intervention simulation | Highest-risk 5% maximized base-case expected value for both strategies |
| Model value vs random | +6,678 BRL purchase-time and +37,421 BRL post-delivery incremental scenario value |

## Selected Visuals

### Seller Monthly Risk Priority

![Seller Monthly Risk Priority](reports/figures/seller_monthly_priority_matrix.png)

### Purchase-Time Risk Model

![Purchase-Time Model Cumulative Gain](reports/figures/purchase_time_model_cumulative_gain.png)

### Intervention Expected Net Value

![Intervention Expected Net Value](reports/figures/intervention_net_value_by_coverage.png)

### Customer Cohort Activity

![Observed Cohort Repeat-Purchase Activity](reports/figures/cohort_repeat_activity_heatmap.png)

## Interactive Dashboard

The Streamlit dashboard turns the analysis into a four-view operating tool:

- Executive KPI Overview
- Seller Risk Monitoring
- Purchase-Time Risk Triage
- Intervention ROI Simulator

Run it locally after generating the analysis outputs:

```bash
make dashboard
```

## Technical Stack

`Python` · `pandas` · `scikit-learn` · `SQL` · `DuckDB` · `Streamlit` · `Plotly` · `Matplotlib`

Key modeling and analytical controls:

- Time-based train/test split
- Purchase-time feature leakage controls
- As-of seller history features
- Fixed 90-day repeat-purchase observation window
- Empirical-Bayes-style seller risk smoothing
- Random-selection value benchmark
- Conservative, base, and optimistic intervention scenarios

## Reproduce

```bash
git clone https://github.com/Ashlynn99/olist-ecommerce-analytics.git
cd olist-ecommerce-analytics

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Download the 9 Kaggle CSV files into data/raw/
make analysis
make check
make dashboard
```

Useful standalone commands:

```bash
make purchase-model
make cohort
make seller-monitor
make intervention-value
```

## Project Structure

```text
├── dashboard/
│   └── app.py                # Four-view Streamlit operations dashboard
├── notebooks/                # 10 ordered analysis notebooks
├── scripts/
│   ├── run_pipeline.py       # End-to-end notebook runner
│   └── quality_check.py      # Repository integrity and syntax checks
├── src/                      # Reusable modeling and monitoring modules
├── sql/                      # Reusable DuckDB business queries
├── reports/                  # Results, charts, summaries, and full report
└── data/                     # Raw and generated data instructions
```

Run `make check` to validate Python syntax, Markdown formatting, notebook JSON, Makefile targets,
critical file line structure, and required project paths.

## Detailed Documentation

- [Full analytical report](reports/final_report.md)
- [Purchase-time model summary](reports/purchase_time_model_summary.md)
- [Cohort and repeat analysis](reports/cohort_repeat_analysis_summary.md)
- [Seller monthly monitoring](reports/seller_monthly_monitoring_summary.md)
- [Intervention value simulation](reports/intervention_value_summary.md)
- [Data setup instructions](data/README.md)

## Decision Boundaries

- The historical dataset covers 2016–2018 and does not represent current Olist operations.
- The purchase-time model is designed for prevention; the post-delivery model is designed for
  service recovery.
- Seller alerts prioritize investigation and should not be used as automatic penalties.
- Intervention-value outputs are scenarios, not realized causal savings. A randomized pilot is
  required before rollout.
