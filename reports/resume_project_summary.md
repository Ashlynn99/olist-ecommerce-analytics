# Resume Project Summary

## Project Name

Olist E-Commerce Operations Analytics and AI Operations Briefing Agent

## One-Line Resume Version

Built an end-to-end e-commerce operations analytics system using Python, SQL, machine learning, and
Streamlit, then added an offline AI Operations Briefing Agent to convert seller-risk, root-cause,
ROI, and experiment-design outputs into an executive operations briefing.

## Resume Bullets

- Built a reproducible marketplace analytics workflow across 9 relational Olist tables and 99,441
  orders using Python, pandas, DuckDB SQL, scikit-learn, and Streamlit.
- Developed leakage-controlled low-review risk models for purchase-time prevention and
  post-delivery recovery, with the post-delivery model reaching 0.763 ROC-AUC and the purchase-time
  model capturing 21.9% of low reviews in the top 10% highest-risk orders.
- Designed a seller monitoring system that identified 34 critical sellers, 49 watch sellers, and 44
  newly escalated sellers in the latest complete monitoring month.
- Built a seller operations queue with alert tiers, owners, SLA targets, diagnostic focus, first
  actions, and success metrics, prioritizing 83 sellers and 33,212 BRL estimated commercial value at
  risk.
- Performed root-cause decomposition showing that SP cross-state seller routes contributed 44.7% of
  all low reviews, while severe delivery delays had low-review rates above 78%.
- Simulated risk-based intervention ROI and found that the highest-risk 5% segment maximized
  base-case expected net value for both prevention and recovery strategies.
- Added an offline-first AI Operations Briefing Agent that reads generated report tables, creates a
  structured operations context, and produces a no-API Markdown briefing for dashboard and portfolio
  presentation.
- Integrated the briefing agent into a Streamlit dashboard as an AI Operations Briefing page, while
  preserving an optional OpenAI API layer for future natural-language enhancement.

## Short Portfolio Description

This project answers a practical marketplace operations question: how should an e-commerce platform
identify low-review risk early, prioritize limited operations capacity, and decide whether an
intervention is economically justified?

I built a full analytics workflow using Python, SQL, machine learning, and Streamlit. The system
combines executive KPIs, root-cause decomposition, seller monthly monitoring, purchase-time risk
triage, intervention ROI simulation, and A/B experiment design. I then extended the project with an
offline AI Operations Briefing Agent that turns deterministic report outputs into an executive
operations brief. The agent is designed with a reproducible analytics layer first and an optional
OpenAI API rewrite layer second, which keeps the no-cost baseline stable while making the system
ready for LLM enhancement.

## AI Agent Architecture

```text
Olist source tables and generated reports
-> pandas/DuckDB/scikit-learn analytics pipeline
-> seller risk, root-cause, ROI, and experiment report tables
-> offline deterministic agent tools
-> structured operations context JSON
-> AI Operations Briefing Markdown
-> Streamlit AI Operations Briefing page
```

## Why The Agent Is Designed Offline First

The offline-first design makes the agent reproducible, inspectable, and safe for a portfolio or
business-operations workflow. Python performs deterministic metric extraction and prioritization,
while the optional OpenAI layer is reserved for richer narration. This avoids relying on an API key
for the core product demo and reduces the risk of hallucinated metrics.

## Interview Talking Points

- I separated deterministic analytics from AI narration so that the agent always has a reliable
  data foundation.
- I used seller-month monitoring with smoothed rates to reduce false alerts from small sample sizes.
- I treated seller alerts as investigation priorities rather than automatic enforcement decisions.
- I connected risk prediction to operational capacity and ROI so the project goes beyond model
  accuracy.
- I added an experiment-design layer because retrospective ROI simulation is not causal proof.
- I made the OpenAI layer optional so the product is functional without paid API usage, but still
  ready for LLM-powered summarization later.

## Technical Stack

Python, pandas, NumPy, scikit-learn, DuckDB SQL, Streamlit, Plotly, Matplotlib, Makefile automation,
Markdown reporting, optional OpenAI Responses API integration.

## ChatGPT Prompt For Resume Tailoring

Use the project summary below to create resume-ready bullets for a data analyst, business analyst,
analytics engineer, or AI product analyst role. Keep the bullets quantified, action-oriented, and
ATS-friendly. Emphasize Python, SQL, machine learning, Streamlit dashboarding, operations analytics,
seller risk monitoring, ROI simulation, experiment design, and the offline AI Operations Briefing
Agent.

```text
Project: Olist E-Commerce Operations Analytics and AI Operations Briefing Agent

Built an end-to-end e-commerce operations analytics system across 9 relational Olist tables and
99,441 orders. The workflow uses Python, pandas, DuckDB SQL, scikit-learn, Streamlit, Plotly, and
Makefile automation. It includes executive KPI analysis, delivery-risk analysis, root-cause
decomposition, purchase-time and post-delivery low-review risk models, seller monthly monitoring,
seller action queue, intervention ROI simulation, and A/B experiment design.

Key results include: 0.763 ROC-AUC for the post-delivery low-review risk model; 0.640 ROC-AUC for
the purchase-time prevention model; top 10% purchase-time risk segment captured 21.9% of low
reviews; 34 critical sellers and 49 watch sellers in the latest complete month; 44 sellers
escalated; 83 sellers prioritized in the action queue; 33,212 BRL estimated value at risk; SP
cross-state seller routes contributed 44.7% of all low reviews; highest-risk 5% intervention
coverage maximized expected net value in base-case scenarios.

Added an offline-first AI Operations Briefing Agent. The agent reads generated report tables,
creates a structured operations context JSON, generates a no-API Markdown executive briefing, and
surfaces the output in a Streamlit AI Operations Briefing dashboard page. The architecture separates
deterministic analytics from optional OpenAI API narration, keeping the product reproducible and
safe while making it LLM-ready.
```
