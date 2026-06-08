"""Monthly seller risk monitoring with volume-aware alerts and risk transitions."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATPLOTLIB_CACHE_DIR = PROJECT_ROOT / ".matplotlib_cache"
MATPLOTLIB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CACHE_DIR))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PRIOR_STRENGTH = 20
MIN_MONTHLY_ORDERS = 5
MIN_MONTHLY_REVIEWS = 3
STATUS_ORDER = ["insufficient_volume", "stable", "watch", "critical"]


def coerce_bool(series: pd.Series) -> pd.Series:
    return series.replace(
        {"True": True, "False": False, "true": True, "false": False, 1: True, 0: False}
    ).astype("boolean")


def load_seller_order_base(project_root: Path) -> pd.DataFrame:
    processed_dir = project_root / "data" / "processed"
    seller_order_path = processed_dir / "seller_order_base.csv"

    if not seller_order_path.exists():
        from seller_logistics_lift_analysis import build_seller_order_base, load_inputs

        orders, items, geolocation = load_inputs(project_root)
        seller_order = build_seller_order_base(orders, items, geolocation)
        seller_order.to_csv(seller_order_path, index=False)
    else:
        seller_order = pd.read_csv(seller_order_path)

    seller_order["order_purchase_timestamp"] = pd.to_datetime(
        seller_order["order_purchase_timestamp"], errors="coerce"
    )
    for column in ["is_delivered", "is_late", "is_low_review", "is_cross_state"]:
        seller_order[column] = coerce_bool(seller_order[column])

    return seller_order


def determine_monitoring_window(seller_order: pd.DataFrame) -> tuple[pd.Period, pd.Period]:
    purchase_month = seller_order["order_purchase_timestamp"].dt.to_period("M")
    last_observed_month = purchase_month.max()
    last_complete_month = last_observed_month - 1

    monthly_orders = seller_order.groupby(purchase_month)["order_id"].nunique()
    meaningful_months = monthly_orders[monthly_orders.ge(1000)]
    first_monitoring_month = meaningful_months.index.min()

    return first_monitoring_month, last_complete_month


def prepare_monitoring_orders(
    seller_order: pd.DataFrame, first_month: pd.Period, last_month: pd.Period
) -> pd.DataFrame:
    monitor = seller_order.copy()
    monitor["order_month"] = monitor["order_purchase_timestamp"].dt.to_period("M")
    monitor = monitor[monitor["order_month"].between(first_month, last_month)].copy()

    monitor["delivered_num"] = monitor["is_delivered"].fillna(False).astype(int)
    monitor["late_num"] = (
        monitor["is_late"].fillna(False) & monitor["is_delivered"].fillna(False)
    ).astype(int)
    monitor["reviewed_num"] = monitor["review_score_mean"].notna().astype(int)
    monitor["low_review_num"] = (
        monitor["is_low_review"].fillna(False) & monitor["review_score_mean"].notna()
    ).astype(int)
    monitor["canceled_num"] = monitor["order_status"].eq("canceled").astype(int)
    monitor["cross_state_num"] = monitor["is_cross_state"].fillna(False).astype(int)
    return monitor


def aggregate_seller_months(monitor: pd.DataFrame) -> pd.DataFrame:
    seller_month = (
        monitor.groupby(["seller_id", "order_month"], as_index=False)
        .agg(
            seller_orders=("order_id", "nunique"),
            seller_gmv=("seller_item_total", "sum"),
            product_revenue=("seller_product_total", "sum"),
            freight_revenue=("seller_freight_total", "sum"),
            delivered_orders=("delivered_num", "sum"),
            late_orders=("late_num", "sum"),
            reviewed_orders=("reviewed_num", "sum"),
            low_review_orders=("low_review_num", "sum"),
            canceled_orders=("canceled_num", "sum"),
            cross_state_orders=("cross_state_num", "sum"),
            avg_delivery_days=("delivery_days", "mean"),
            avg_review_score=("review_score_mean", "mean"),
            seller_state=("seller_state", "first"),
            seller_city=("seller_city", "first"),
        )
        .sort_values(["seller_id", "order_month"])
        .reset_index(drop=True)
    )

    seller_month["late_rate"] = seller_month["late_orders"] / seller_month[
        "delivered_orders"
    ].replace(0, np.nan)
    seller_month["low_review_rate"] = seller_month["low_review_orders"] / seller_month[
        "reviewed_orders"
    ].replace(0, np.nan)
    seller_month["cancellation_rate"] = seller_month["canceled_orders"] / seller_month[
        "seller_orders"
    ].replace(0, np.nan)
    seller_month["review_coverage"] = seller_month["reviewed_orders"] / seller_month[
        "seller_orders"
    ].replace(0, np.nan)
    seller_month["cross_state_rate"] = seller_month["cross_state_orders"] / seller_month[
        "seller_orders"
    ].replace(0, np.nan)
    return seller_month


def add_marketplace_benchmarks(seller_month: pd.DataFrame) -> pd.DataFrame:
    marketplace = (
        seller_month.groupby("order_month", as_index=False)
        .agg(
            market_seller_orders=("seller_orders", "sum"),
            market_seller_gmv=("seller_gmv", "sum"),
            market_delivered_orders=("delivered_orders", "sum"),
            market_late_orders=("late_orders", "sum"),
            market_reviewed_orders=("reviewed_orders", "sum"),
            market_low_review_orders=("low_review_orders", "sum"),
            market_canceled_orders=("canceled_orders", "sum"),
        )
    )
    marketplace["market_late_rate"] = marketplace["market_late_orders"] / marketplace[
        "market_delivered_orders"
    ].replace(0, np.nan)
    marketplace["market_low_review_rate"] = marketplace[
        "market_low_review_orders"
    ] / marketplace["market_reviewed_orders"].replace(0, np.nan)
    marketplace["market_cancellation_rate"] = marketplace[
        "market_canceled_orders"
    ] / marketplace["market_seller_orders"].replace(0, np.nan)

    return seller_month.merge(marketplace, on="order_month", how="left")


def add_smoothed_rates_and_history(seller_month: pd.DataFrame) -> pd.DataFrame:
    rate_specs = [
        ("low_review", "low_review_orders", "reviewed_orders", "market_low_review_rate"),
        ("late", "late_orders", "delivered_orders", "market_late_rate"),
        ("cancellation", "canceled_orders", "seller_orders", "market_cancellation_rate"),
    ]

    for label, bad_col, denominator_col, market_col in rate_specs:
        seller_month[f"smoothed_{label}_rate"] = (
            seller_month[bad_col] + PRIOR_STRENGTH * seller_month[market_col]
        ) / (seller_month[denominator_col] + PRIOR_STRENGTH)

        group = seller_month.groupby("seller_id", sort=False)
        seller_month[f"prior_{bad_col}"] = group[bad_col].cumsum() - seller_month[bad_col]
        seller_month[f"prior_{denominator_col}"] = (
            group[denominator_col].cumsum() - seller_month[denominator_col]
        )
        seller_month[f"historical_{label}_rate"] = (
            seller_month[f"prior_{bad_col}"] + PRIOR_STRENGTH * seller_month[market_col]
        ) / (seller_month[f"prior_{denominator_col}"] + PRIOR_STRENGTH)
        seller_month[f"{label}_rate_deterioration"] = (
            seller_month[f"smoothed_{label}_rate"]
            - seller_month[f"historical_{label}_rate"]
        ).clip(lower=0)

    return seller_month


def percentile_by_month(series: pd.Series) -> pd.Series:
    return series.rank(method="average", pct=True)


def add_risk_scores(seller_month: pd.DataFrame) -> pd.DataFrame:
    percentile_columns = {
        "smoothed_low_review_rate": "low_review_risk_percentile",
        "smoothed_late_rate": "late_risk_percentile",
        "smoothed_cancellation_rate": "cancellation_risk_percentile",
        "low_review_rate_deterioration": "low_review_deterioration_percentile",
        "late_rate_deterioration": "late_deterioration_percentile",
        "cancellation_rate_deterioration": "cancellation_deterioration_percentile",
        "seller_gmv": "gmv_percentile",
        "seller_orders": "order_volume_percentile",
    }
    for source, target in percentile_columns.items():
        seller_month[target] = seller_month.groupby("order_month")[source].transform(
            percentile_by_month
        )

    seller_month["experience_risk_score"] = 100 * (
        0.50 * seller_month["low_review_risk_percentile"]
        + 0.35 * seller_month["late_risk_percentile"]
        + 0.15 * seller_month["cancellation_risk_percentile"]
    )
    seller_month["deterioration_score"] = 100 * (
        0.50 * seller_month["low_review_deterioration_percentile"]
        + 0.35 * seller_month["late_deterioration_percentile"]
        + 0.15 * seller_month["cancellation_deterioration_percentile"]
    )
    seller_month["reliability_score"] = np.minimum(
        1.0, np.sqrt(seller_month["seller_orders"] / 20)
    )
    seller_month["priority_score"] = (
        0.55 * seller_month["experience_risk_score"]
        + 0.25 * seller_month["deterioration_score"]
        + 20 * seller_month["gmv_percentile"]
    ) * (0.65 + 0.35 * seller_month["reliability_score"])

    seller_month["eligible_for_alert"] = (
        seller_month["seller_orders"].ge(MIN_MONTHLY_ORDERS)
        & seller_month["reviewed_orders"].ge(MIN_MONTHLY_REVIEWS)
    )
    seller_month["priority_percentile"] = np.nan
    eligible = seller_month["eligible_for_alert"]
    seller_month.loc[eligible, "priority_percentile"] = seller_month.loc[eligible].groupby(
        "order_month"
    )["priority_score"].transform(percentile_by_month)

    seller_month["risk_status"] = "stable"
    seller_month.loc[~eligible, "risk_status"] = "insufficient_volume"
    seller_month.loc[
        eligible
        & seller_month["priority_percentile"].ge(0.75)
        & seller_month["experience_risk_score"].ge(50),
        "risk_status",
    ] = "watch"
    seller_month.loc[
        eligible
        & seller_month["priority_percentile"].ge(0.90)
        & seller_month["experience_risk_score"].ge(60),
        "risk_status",
    ] = "critical"
    return seller_month


def alert_reason(row: pd.Series) -> str:
    reasons = []
    if row["low_review_risk_percentile"] >= 0.80:
        reasons.append("high low-review risk")
    if row["late_risk_percentile"] >= 0.80:
        reasons.append("high late-delivery risk")
    if row["cancellation_risk_percentile"] >= 0.80:
        reasons.append("high cancellation risk")
    if row["deterioration_score"] >= 80:
        reasons.append("material deterioration vs seller history")
    if row["gmv_percentile"] >= 0.80:
        reasons.append("high value exposure")
    return "; ".join(reasons) if reasons else "combined moderate risk signals"


def recommended_action(row: pd.Series) -> str:
    if row["late_risk_percentile"] >= 0.80 and row["low_review_risk_percentile"] >= 0.80:
        return "Investigate fulfillment delays and review recent complaints"
    if row["cancellation_risk_percentile"] >= 0.80:
        return "Review inventory availability and order acceptance process"
    if row["low_review_risk_percentile"] >= 0.80:
        return "Audit recent low-review orders and product-service issues"
    if row["deterioration_score"] >= 80:
        return "Contact seller to review the recent performance decline"
    return "Monitor next month and review the highest-risk orders"


def add_alerts_and_transitions(seller_month: pd.DataFrame) -> pd.DataFrame:
    seller_month["alert_reason"] = seller_month.apply(alert_reason, axis=1)
    seller_month["recommended_action"] = seller_month.apply(recommended_action, axis=1)

    previous = seller_month.groupby("seller_id", sort=False).shift(1)
    previous_month_is_adjacent = previous["order_month"].eq(seller_month["order_month"] - 1)
    seller_month["previous_risk_status"] = previous["risk_status"].where(previous_month_is_adjacent)

    status_rank = {"stable": 0, "watch": 1, "critical": 2}
    current_rank = seller_month["risk_status"].map(status_rank)
    previous_rank = seller_month["previous_risk_status"].map(status_rank)
    has_previous = seller_month["previous_risk_status"].notna()
    both_insufficient = seller_month["previous_risk_status"].eq(
        "insufficient_volume"
    ) & seller_month["risk_status"].eq("insufficient_volume")
    became_eligible = seller_month["previous_risk_status"].eq(
        "insufficient_volume"
    ) & seller_month["risk_status"].ne("insufficient_volume")
    lost_eligibility = seller_month["previous_risk_status"].ne(
        "insufficient_volume"
    ) & seller_month["risk_status"].eq("insufficient_volume") & has_previous
    seller_month["risk_transition"] = "new_or_returning"
    seller_month.loc[both_insufficient, "risk_transition"] = "unchanged"
    seller_month.loc[became_eligible, "risk_transition"] = "became_eligible"
    seller_month.loc[lost_eligibility, "risk_transition"] = "insufficient_evidence"
    seller_month.loc[previous_rank.eq(current_rank), "risk_transition"] = "unchanged"
    seller_month.loc[previous_rank.lt(current_rank), "risk_transition"] = "escalated"
    seller_month.loc[previous_rank.gt(current_rank), "risk_transition"] = "improved"
    return seller_month


def create_report_tables(
    seller_month: pd.DataFrame, reports_dir: Path, processed_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    latest_month = seller_month["order_month"].max()
    latest = seller_month[seller_month["order_month"].eq(latest_month)].copy()
    watchlist = latest[latest["risk_status"].isin(["watch", "critical"])].sort_values(
        ["risk_status", "priority_score", "seller_gmv"],
        ascending=[True, False, False],
    )

    monthly_summary = (
        seller_month.groupby("order_month", as_index=False)
        .agg(
            active_sellers=("seller_id", "nunique"),
            alert_eligible_sellers=("eligible_for_alert", "sum"),
            seller_orders=("seller_orders", "sum"),
            seller_gmv=("seller_gmv", "sum"),
            delivered_orders=("delivered_orders", "sum"),
            late_orders=("late_orders", "sum"),
            reviewed_orders=("reviewed_orders", "sum"),
            low_review_orders=("low_review_orders", "sum"),
            canceled_orders=("canceled_orders", "sum"),
        )
    )
    status_counts = (
        seller_month.pivot_table(
            index="order_month",
            columns="risk_status",
            values="seller_id",
            aggfunc="count",
            fill_value=0,
        )
        .reindex(columns=STATUS_ORDER, fill_value=0)
        .reset_index()
    )
    monthly_summary = monthly_summary.merge(status_counts, on="order_month", how="left")
    monthly_summary["late_rate"] = monthly_summary["late_orders"] / monthly_summary[
        "delivered_orders"
    ].replace(0, np.nan)
    monthly_summary["low_review_rate"] = monthly_summary[
        "low_review_orders"
    ] / monthly_summary["reviewed_orders"].replace(0, np.nan)
    monthly_summary["cancellation_rate"] = monthly_summary[
        "canceled_orders"
    ] / monthly_summary["seller_orders"].replace(0, np.nan)

    transition_summary = (
        latest.groupby(["previous_risk_status", "risk_status"], dropna=False)
        .size()
        .rename("sellers")
        .reset_index()
        .sort_values("sellers", ascending=False)
    )
    latest_transitions = latest[latest["risk_transition"].isin(["escalated", "improved"])].sort_values(
        ["risk_transition", "priority_score"], ascending=[True, False]
    )
    operational_columns = [
        "order_month",
        "seller_id",
        "seller_state",
        "seller_city",
        "risk_status",
        "previous_risk_status",
        "risk_transition",
        "seller_orders",
        "seller_gmv",
        "delivered_orders",
        "reviewed_orders",
        "low_review_orders",
        "low_review_rate",
        "smoothed_low_review_rate",
        "late_orders",
        "late_rate",
        "smoothed_late_rate",
        "canceled_orders",
        "cancellation_rate",
        "smoothed_cancellation_rate",
        "experience_risk_score",
        "deterioration_score",
        "reliability_score",
        "priority_score",
        "alert_reason",
        "recommended_action",
    ]
    watchlist = watchlist[operational_columns].copy()
    latest_transitions = latest_transitions[operational_columns].copy()

    export = seller_month.copy()
    export["order_month"] = export["order_month"].astype(str)
    export.to_csv(processed_dir / "seller_monthly_risk_monitor.csv", index=False)

    for table in [watchlist, monthly_summary, transition_summary, latest_transitions]:
        if "order_month" in table:
            table["order_month"] = table["order_month"].astype(str)

    watchlist.to_csv(reports_dir / "seller_monthly_latest_watchlist.csv", index=False)
    monthly_summary.to_csv(reports_dir / "seller_monthly_risk_summary.csv", index=False)
    transition_summary.to_csv(reports_dir / "seller_risk_transition_summary.csv", index=False)
    latest_transitions.to_csv(reports_dir / "seller_monthly_latest_transitions.csv", index=False)
    return latest, watchlist, monthly_summary, transition_summary


def create_figures(
    seller_month: pd.DataFrame,
    latest: pd.DataFrame,
    watchlist: pd.DataFrame,
    monthly_summary: pd.DataFrame,
    transition_summary: pd.DataFrame,
    figures_dir: Path,
) -> None:
    summary_plot = monthly_summary.tail(18).copy()
    x = np.arange(len(summary_plot))
    fig, ax = plt.subplots(figsize=(13, 6))
    bottom = np.zeros(len(summary_plot))
    colors = {"stable": "#4c78a8", "watch": "#f2cf5b", "critical": "#d62728"}
    for status in ["stable", "watch", "critical"]:
        values = summary_plot[status].to_numpy()
        ax.bar(x, values, bottom=bottom, label=status.replace("_", " ").title(), color=colors[status])
        bottom += values
    ax.set_xticks(x)
    ax.set_xticklabels(summary_plot["order_month"].astype(str), rotation=45, ha="right")
    ax.set_title("Monthly Seller Monitoring Status")
    ax.set_ylabel("Alert-Eligible Sellers")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_monthly_risk_status.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    eligible_latest = latest[latest["eligible_for_alert"]].copy()
    status_colors = {"stable": "#4c78a8", "watch": "#f2cf5b", "critical": "#d62728"}
    bubble_size = 30 + 250 * eligible_latest["order_volume_percentile"]
    fig, ax = plt.subplots(figsize=(11, 7))
    for status in ["stable", "watch", "critical"]:
        subset = eligible_latest[eligible_latest["risk_status"].eq(status)]
        ax.scatter(
            subset["seller_gmv"],
            subset["experience_risk_score"],
            s=bubble_size.loc[subset.index],
            c=status_colors[status],
            alpha=0.72,
            edgecolor="white",
            linewidth=0.5,
            label=status.title(),
        )
    ax.set_xscale("log")
    ax.set_title(f"Seller Risk Priority Matrix, {latest['order_month'].iloc[0]}")
    ax.set_xlabel("Monthly Seller Order Value, log scale")
    ax.set_ylabel("Experience Risk Score")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_monthly_priority_matrix.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    top_watchlist = watchlist.head(15).sort_values("priority_score")
    fig, ax = plt.subplots(figsize=(12, 7))
    labels = top_watchlist["seller_id"].str.slice(0, 8) + " (" + top_watchlist["seller_state"].fillna("NA") + ")"
    bar_colors = top_watchlist["risk_status"].map(status_colors)
    ax.barh(labels, top_watchlist["priority_score"], color=bar_colors)
    ax.set_title(f"Highest-Priority Seller Alerts, {latest['order_month'].iloc[0]}")
    ax.set_xlabel("Priority Score")
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_monthly_top_alerts.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    transition_matrix = (
        transition_summary.dropna(subset=["previous_risk_status"])
        .pivot(index="previous_risk_status", columns="risk_status", values="sellers")
        .reindex(index=STATUS_ORDER, columns=STATUS_ORDER, fill_value=0)
        .fillna(0)
    )
    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(transition_matrix.to_numpy(), cmap="Blues", aspect="auto")
    ax.set_xticks(np.arange(len(transition_matrix.columns)))
    ax.set_xticklabels([value.replace("_", " ").title() for value in transition_matrix.columns], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(transition_matrix.index)))
    ax.set_yticklabels([value.replace("_", " ").title() for value in transition_matrix.index])
    ax.set_xlabel("Current Month Status")
    ax.set_ylabel("Previous Month Status")
    ax.set_title("Latest Seller Risk Status Transitions")
    for row in range(len(transition_matrix.index)):
        for col in range(len(transition_matrix.columns)):
            ax.text(col, row, int(transition_matrix.iloc[row, col]), ha="center", va="center")
    fig.colorbar(image, ax=ax, label="Sellers")
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_risk_transition_matrix.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_summary(
    seller_month: pd.DataFrame,
    latest: pd.DataFrame,
    watchlist: pd.DataFrame,
    reports_dir: Path,
) -> None:
    latest_month = str(latest["order_month"].iloc[0])
    critical = latest[latest["risk_status"].eq("critical")]
    watch = latest[latest["risk_status"].eq("watch")]
    escalated = latest[latest["risk_transition"].eq("escalated")]
    top = watchlist.iloc[0] if len(watchlist) else None
    critical_gmv_share = critical["seller_gmv"].sum() / latest["seller_gmv"].sum()
    critical_order_share = critical["seller_orders"].sum() / latest["seller_orders"].sum()

    top_text = (
        f"- Highest-priority seller: `{top['seller_id']}`, priority score {top['priority_score']:.1f}, "
        f"with {top['seller_orders']:,} seller-orders and {top['seller_gmv']:,.0f} BRL in monthly order value\n"
        f"- Primary alert drivers: {top['alert_reason']}"
        if top is not None
        else "- No seller met the watch or critical alert criteria."
    )

    summary = f"""# Seller Monthly Risk Monitoring Summary

## Objective

I converted the static seller scorecard into a monthly monitoring system that identifies seller deterioration, quantifies commercial exposure, and produces a prioritized operational watchlist.

The latest complete monitoring month is **{latest_month}**. The incomplete final month in the source data is excluded.

## Latest Monitoring Results

- Active sellers: {latest['seller_id'].nunique():,}
- Sellers eligible for alerts: {int(latest['eligible_for_alert'].sum()):,}
- Critical sellers: {len(critical):,}
- Watch sellers: {len(watch):,}
- Sellers escalated from the previous month: {len(escalated):,}
- Critical sellers' share of monthly seller-order value: {critical_gmv_share:.1%}
- Critical sellers' share of monthly seller-orders: {critical_order_share:.1%}
{top_text}

## Monitoring Method

The unit of analysis is a seller-month. Each active seller is evaluated using:

1. Low-review risk
2. Late-delivery risk
3. Cancellation risk
4. Deterioration relative to the seller's own prior history
5. Monthly commercial exposure

Low-review, late-delivery, and cancellation rates use empirical-Bayes-style smoothing toward the current marketplace rate with a prior strength of {PRIOR_STRENGTH} orders. This reduces false alerts caused by very small monthly samples.

The priority score combines 55% experience risk, 25% deterioration, and 20% seller value, then applies a reliability adjustment based on monthly order volume. Sellers need at least {MIN_MONTHLY_ORDERS} monthly seller-orders and {MIN_MONTHLY_REVIEWS} reviewed orders to receive a watch or critical alert.

- Critical: top 10% of eligible sellers by priority score and experience risk score of at least 60
- Watch: top 25% of eligible sellers by priority score and experience risk score of at least 50

## Interpretation

This is an operational prioritization system, not a causal model or automatic seller penalty system. A critical alert means that a seller combines relatively high customer-experience risk with sufficient evidence and business exposure. The recommended next step is a seller-level investigation using recent orders and complaint details.
"""
    (reports_dir / "seller_monthly_monitoring_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    seller_order = load_seller_order_base(PROJECT_ROOT)
    first_month, last_month = determine_monitoring_window(seller_order)
    monitor_orders = prepare_monitoring_orders(seller_order, first_month, last_month)
    seller_month = aggregate_seller_months(monitor_orders)
    seller_month = add_marketplace_benchmarks(seller_month)
    seller_month = add_smoothed_rates_and_history(seller_month)
    seller_month = add_risk_scores(seller_month)
    seller_month = add_alerts_and_transitions(seller_month)
    latest, watchlist, monthly_summary, transition_summary = create_report_tables(
        seller_month, reports_dir, processed_dir
    )
    create_figures(
        seller_month, latest, watchlist, monthly_summary, transition_summary, figures_dir
    )
    write_summary(seller_month, latest, watchlist, reports_dir)

    print("Seller monthly risk monitoring completed.")
    print(
        pd.DataFrame(
            [
                {
                    "latest_complete_month": str(latest["order_month"].iloc[0]),
                    "active_sellers": latest["seller_id"].nunique(),
                    "alert_eligible_sellers": int(latest["eligible_for_alert"].sum()),
                    "critical_sellers": int(latest["risk_status"].eq("critical").sum()),
                    "watch_sellers": int(latest["risk_status"].eq("watch").sum()),
                    "escalated_sellers": int(latest["risk_transition"].eq("escalated").sum()),
                }
            ]
        ).to_string(index=False)
    )
    print(f"Summary: {reports_dir / 'seller_monthly_monitoring_summary.md'}")


if __name__ == "__main__":
    main()
