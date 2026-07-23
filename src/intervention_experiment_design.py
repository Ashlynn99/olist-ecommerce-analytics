"""Create an experiment design for validating risk-based operational interventions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reporting_utils import format_percent, markdown_table

ALPHA_TWO_SIDED_Z = 1.96
POWER_80_Z = 0.84
BASE_STRATEGY_COSTS = {"purchase_time": 3.0, "post_delivery": 12.0}


def stable_assignment(order_id: str, strategy: str) -> str:
    digest = hashlib.sha256(f"{strategy}:{order_id}".encode("utf-8")).hexdigest()
    return "treatment" if int(digest[:8], 16) % 2 == 0 else "control"


def load_inputs(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reports_dir = project_root / "reports"
    orders = pd.read_csv(
        project_root / "data" / "processed" / "orders_analysis_base.csv",
        usecols=["order_id", "review_score_mean", "is_low_review"],
    )
    recommendations = pd.read_csv(reports_dir / "intervention_strategy_recommendations.csv")
    purchase_predictions = pd.read_csv(
        reports_dir / "purchase_time_model_test_predictions.csv",
        parse_dates=["order_purchase_timestamp"],
    ).rename(columns={"purchase_time_low_review_probability": "risk_probability"})
    post_predictions = pd.read_csv(
        reports_dir / "model_low_review_test_predictions.csv",
        parse_dates=["order_purchase_timestamp"],
    ).rename(columns={"low_review_probability": "risk_probability"})
    purchase_predictions["strategy"] = "purchase_time"
    post_predictions["strategy"] = "post_delivery"
    predictions = pd.concat([purchase_predictions, post_predictions], ignore_index=True)
    predictions = predictions.merge(orders, on="order_id", how="left")
    return recommendations, predictions, orders


def z_sum() -> float:
    return ALPHA_TWO_SIDED_Z + POWER_80_Z


def minimum_detectable_effect(baseline_rate: float, n_per_group: int) -> float:
    if n_per_group <= 0:
        return np.nan
    return z_sum() * np.sqrt(2 * baseline_rate * (1 - baseline_rate) / n_per_group)


def required_sample_per_group(baseline_rate: float, relative_reduction: float) -> int:
    treatment_rate = baseline_rate * (1 - relative_reduction)
    pooled_rate = (baseline_rate + treatment_rate) / 2
    absolute_effect = baseline_rate - treatment_rate
    if absolute_effect <= 0:
        return 0
    return int(np.ceil(2 * pooled_rate * (1 - pooled_rate) * (z_sum() / absolute_effect) ** 2))


def build_candidate_frame(
    recommendations: pd.DataFrame,
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, recommendation in recommendations.iterrows():
        strategy = recommendation["strategy"]
        strategy_predictions = predictions[predictions["strategy"].eq(strategy)].copy()
        candidate_count = int(
            np.ceil(len(strategy_predictions) * recommendation["recommended_coverage_share"])
        )
        candidates = strategy_predictions.nlargest(candidate_count, "risk_probability").copy()
        candidates["recommended_coverage_share"] = recommendation["recommended_coverage_share"]
        candidates["assignment_group"] = candidates["order_id"].map(
            lambda order_id: stable_assignment(str(order_id), strategy)
        )
        candidates["experiment_unit"] = "order_id"
        candidates["primary_metric"] = "low_review_rate"
        candidates["contact_cost_brl"] = BASE_STRATEGY_COSTS[strategy]
        frames.append(candidates)
    return pd.concat(frames, ignore_index=True)


def summarize_experiment_frame(candidate_frame: pd.DataFrame) -> pd.DataFrame:
    summaries: list[dict[str, object]] = []
    for strategy, frame in candidate_frame.groupby("strategy"):
        control_n = int(frame["assignment_group"].eq("control").sum())
        treatment_n = int(frame["assignment_group"].eq("treatment").sum())
        n_per_group = min(control_n, treatment_n)
        baseline_rate = frame["target_low_review"].mean()
        mde_absolute = minimum_detectable_effect(baseline_rate, n_per_group)
        date_span_days = (
            frame["order_purchase_timestamp"].max() - frame["order_purchase_timestamp"].min()
        ).days + 1
        daily_candidate_rate = len(frame) / date_span_days
        summaries.append(
            {
                "strategy": strategy,
                "candidate_orders": len(frame),
                "control_orders": control_n,
                "treatment_orders": treatment_n,
                "baseline_low_review_rate": baseline_rate,
                "minimum_detectable_effect_abs": mde_absolute,
                "minimum_detectable_effect_relative": mde_absolute / baseline_rate,
                "required_n_per_group_10pct_relative_reduction": required_sample_per_group(
                    baseline_rate,
                    0.10,
                ),
                "required_n_per_group_15pct_relative_reduction": required_sample_per_group(
                    baseline_rate,
                    0.15,
                ),
                "required_n_per_group_20pct_relative_reduction": required_sample_per_group(
                    baseline_rate,
                    0.20,
                ),
                "estimated_daily_candidate_rate": daily_candidate_rate,
                "historical_candidate_window_days": date_span_days,
            }
        )
    return pd.DataFrame.from_records(summaries)


def build_metric_plan() -> pd.DataFrame:
    records = [
        {
            "metric_type": "primary",
            "metric_name": "low_review_rate",
            "definition": "Share of treated/control orders with review_score <= 2.",
            "decision_use": "Main success metric for customer-experience recovery.",
        },
        {
            "metric_type": "secondary",
            "metric_name": "average_review_score",
            "definition": "Mean review score among reviewed orders.",
            "decision_use": "Checks whether improvement is broad, not only at the low-score cutoff.",
        },
        {
            "metric_type": "secondary",
            "metric_name": "repeat_purchase_within_90d",
            "definition": "Observed repeat order within 90 days for eligible customers.",
            "decision_use": "Monitors whether intervention improves downstream customer behavior.",
        },
        {
            "metric_type": "guardrail",
            "metric_name": "cancellation_rate",
            "definition": "Share of orders canceled after intervention eligibility.",
            "decision_use": "Prevents operational actions from increasing cancellations.",
        },
        {
            "metric_type": "guardrail",
            "metric_name": "cost_per_successful_recovery",
            "definition": "Intervention cost divided by incremental low reviews avoided.",
            "decision_use": "Ensures the program remains economically viable.",
        },
    ]
    return pd.DataFrame.from_records(records)


def format_experiment_summary(summary: pd.DataFrame) -> pd.DataFrame:
    display = summary.copy()
    percent_columns = [
        "baseline_low_review_rate",
        "minimum_detectable_effect_abs",
        "minimum_detectable_effect_relative",
    ]
    for column in percent_columns:
        display[column] = display[column].map(format_percent)
    display["estimated_daily_candidate_rate"] = display["estimated_daily_candidate_rate"].map(
        lambda value: f"{value:.1f}"
    )
    display = display.rename(
        columns={
            "strategy": "Strategy",
            "candidate_orders": "Candidate Orders",
            "control_orders": "Control",
            "treatment_orders": "Treatment",
            "baseline_low_review_rate": "Baseline Low-Review Rate",
            "minimum_detectable_effect_abs": "MDE, Absolute",
            "minimum_detectable_effect_relative": "MDE, Relative",
            "required_n_per_group_10pct_relative_reduction": "N/Group for 10% Reduction",
            "required_n_per_group_15pct_relative_reduction": "N/Group for 15% Reduction",
            "required_n_per_group_20pct_relative_reduction": "N/Group for 20% Reduction",
            "estimated_daily_candidate_rate": "Daily Candidate Rate",
            "historical_candidate_window_days": "Historical Days",
        }
    )
    return display


def plot_sample_size(summary: pd.DataFrame, figures_dir: Path) -> None:
    plot_data = summary.set_index("strategy")[
        [
            "required_n_per_group_10pct_relative_reduction",
            "required_n_per_group_15pct_relative_reduction",
            "required_n_per_group_20pct_relative_reduction",
        ]
    ]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    plot_data.T.plot(kind="bar", ax=ax, color=["#3973a8", "#c84242"])
    ax.set_ylabel("Required orders per group")
    ax.set_title("Experiment Sample Size by Detectable Relative Reduction")
    ax.set_xticklabels(["10% reduction", "15% reduction", "20% reduction"], rotation=0)
    plt.tight_layout()
    plt.savefig(figures_dir / "experiment_sample_size_plan.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_assignment_balance(candidate_frame: pd.DataFrame, figures_dir: Path) -> None:
    balance = (
        candidate_frame.groupby(["strategy", "assignment_group"], as_index=False)
        .agg(orders=("order_id", "nunique"))
        .pivot(index="strategy", columns="assignment_group", values="orders")
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    balance.plot(kind="bar", ax=ax, color=["#6b7280", "#3e8b68"])
    ax.set_ylabel("Orders")
    ax.set_title("Deterministic Randomization Balance")
    ax.tick_params(axis="x", rotation=0)
    plt.tight_layout()
    plt.savefig(figures_dir / "experiment_assignment_balance.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_design_doc(
    summary: pd.DataFrame,
    metric_plan: pd.DataFrame,
    candidate_frame: pd.DataFrame,
    reports_dir: Path,
) -> None:
    summary_markdown = markdown_table(format_experiment_summary(summary))
    metric_markdown = markdown_table(metric_plan)
    purchase = summary[summary["strategy"].eq("purchase_time")].iloc[0]
    post = summary[summary["strategy"].eq("post_delivery")].iloc[0]
    purchase_orders = int(purchase["candidate_orders"])
    purchase_baseline = purchase["baseline_low_review_rate"]
    purchase_mde = purchase["minimum_detectable_effect_abs"]
    post_orders = int(post["candidate_orders"])
    post_baseline = post["baseline_low_review_rate"]
    post_mde = post["minimum_detectable_effect_abs"]

    design_doc = f"""# Intervention Experiment Design

## Objective

The ROI model is a scenario estimate. This experiment design defines how a marketplace team could
validate whether risk-based intervention actually reduces low-review outcomes and creates economic
value.

## Experiment Candidates

The candidate pool uses the model-recommended highest-risk 5% of test-period orders for each
strategy.

| Strategy | Candidate Orders | Baseline Low-Review Rate | Minimum Detectable Effect |
|---|---:|---:|---:|
| Purchase-time prevention | {purchase_orders:,} | {purchase_baseline:.1%} | {purchase_mde:.1%} |
| Post-delivery recovery | {post_orders:,} | {post_baseline:.1%} | {post_mde:.1%} |

## Design Summary

{summary_markdown}

## Metric Plan

{metric_markdown}

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
"""
    (reports_dir / "intervention_experiment_design.md").write_text(design_doc, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    recommendations, predictions, _ = load_inputs(PROJECT_ROOT)
    candidate_frame = build_candidate_frame(recommendations, predictions)
    summary = summarize_experiment_frame(candidate_frame)
    metric_plan = build_metric_plan()

    candidate_frame.to_csv(reports_dir / "intervention_experiment_candidate_frame.csv", index=False)
    summary.to_csv(reports_dir / "intervention_experiment_design_summary.csv", index=False)
    metric_plan.to_csv(reports_dir / "intervention_experiment_metric_plan.csv", index=False)
    plot_sample_size(summary, figures_dir)
    plot_assignment_balance(candidate_frame, figures_dir)
    write_design_doc(summary, metric_plan, candidate_frame, reports_dir)

    print("Intervention experiment design completed.")
    print(f"Candidate orders: {len(candidate_frame):,}")
    print(f"Summary: {reports_dir / 'intervention_experiment_design.md'}")


if __name__ == "__main__":
    main()
