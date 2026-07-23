"""Decompose low-review and late-delivery issues into business root-cause segments."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reporting_utils import format_brl, format_percent, markdown_table

MIN_SEGMENT_ORDERS = 250
TOP_N = 12


def load_inputs(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    processed_dir = project_root / "data" / "processed"
    orders = pd.read_csv(
        processed_dir / "orders_analysis_base.csv",
        parse_dates=["order_purchase_timestamp"],
    )
    seller_orders = pd.read_csv(
        processed_dir / "seller_order_base.csv",
        parse_dates=["order_purchase_timestamp"],
    )
    return orders, seller_orders


def delivery_delay_bucket(delta_days: pd.Series) -> pd.Series:
    bins = [-np.inf, 0, 3, 7, 14, np.inf]
    labels = [
        "on_or_before_estimate",
        "1_3_days_late",
        "4_7_days_late",
        "8_14_days_late",
        "15_plus_days_late",
    ]
    return pd.cut(delta_days, bins=bins, labels=labels).astype("object").fillna("unknown")


def freight_burden_bucket(freight_share: pd.Series) -> pd.Series:
    bins = [-np.inf, 0.10, 0.20, 0.35, np.inf]
    labels = [
        "low_freight_share",
        "medium_freight_share",
        "high_freight_share",
        "very_high_freight_share",
    ]
    return pd.cut(freight_share, bins=bins, labels=labels).astype("object").fillna("unknown")


def payment_value_band(payment_total: pd.Series) -> pd.Series:
    bins = [-np.inf, 50, 150, 300, np.inf]
    labels = ["under_50_brl", "50_150_brl", "150_300_brl", "300_plus_brl"]
    return pd.cut(payment_total, bins=bins, labels=labels).astype("object").fillna("unknown")


def prepare_order_base(orders: pd.DataFrame, seller_orders: pd.DataFrame) -> pd.DataFrame:
    route_by_order = (
        seller_orders.groupby("order_id", as_index=False)
        .agg(
            route_type=(
                "is_cross_state",
                lambda values: "cross_state" if values.fillna(False).any() else "same_state",
            ),
            avg_customer_seller_distance_km=("customer_seller_distance_km", "mean"),
        )
        .copy()
    )
    base = orders.merge(route_by_order, on="order_id", how="left")
    base["route_type"] = base["route_type"].fillna("unknown")
    base["main_product_category"] = base["main_product_category"].fillna("unknown")
    base["main_seller_state"] = base["main_seller_state"].fillna("unknown")
    base["customer_state"] = base["customer_state"].fillna("unknown")
    base["primary_payment_type"] = base["primary_payment_type"].fillna("unknown")
    base["delivery_delay_bucket"] = delivery_delay_bucket(base["delivery_delta_days"])
    base["freight_burden_bucket"] = freight_burden_bucket(base["freight_share_of_payment"])
    base["payment_value_band"] = payment_value_band(base["payment_total"])
    base["is_delivered"] = base["is_delivered"].fillna(False).astype(bool)
    base["is_late"] = base["is_late"].fillna(False).astype(bool)
    base["is_low_review"] = base["is_low_review"].fillna(False).astype(bool)
    return base


def contribution_by_dimension(base: pd.DataFrame, dimension: str) -> pd.DataFrame:
    overall_low_review_rate = base.loc[base["has_review"].fillna(False), "is_low_review"].mean()
    overall_late_rate = base.loc[base["is_delivered"], "is_late"].mean()
    grouped = (
        base.groupby(dimension, dropna=False)
        .agg(
            orders=("order_id", "nunique"),
            delivered_orders=("is_delivered", "sum"),
            reviewed_orders=("has_review", "sum"),
            low_review_orders=("is_low_review", "sum"),
            late_orders=("is_late", "sum"),
            gross_payment_volume=("payment_total", "sum"),
        )
        .reset_index()
        .rename(columns={dimension: "segment"})
    )
    grouped["dimension"] = dimension
    grouped["low_review_rate"] = grouped["low_review_orders"] / grouped["reviewed_orders"]
    grouped["late_rate"] = grouped["late_orders"] / grouped["delivered_orders"]
    grouped["share_of_orders"] = grouped["orders"] / grouped["orders"].sum()
    grouped["share_of_low_reviews"] = (
        grouped["low_review_orders"] / grouped["low_review_orders"].sum()
    )
    grouped["share_of_late_orders"] = grouped["late_orders"] / grouped["late_orders"].sum()
    grouped["share_of_payment"] = (
        grouped["gross_payment_volume"] / grouped["gross_payment_volume"].sum()
    )
    grouped["low_review_contribution_index"] = (
        grouped["share_of_low_reviews"] / grouped["share_of_orders"]
    )
    grouped["late_contribution_index"] = (
        grouped["share_of_late_orders"] / grouped["share_of_orders"]
    )
    grouped["expected_low_reviews_at_average"] = (
        grouped["reviewed_orders"] * overall_low_review_rate
    )
    grouped["excess_low_reviews"] = (
        grouped["low_review_orders"] - grouped["expected_low_reviews_at_average"]
    )
    grouped["expected_late_orders_at_average"] = grouped["delivered_orders"] * overall_late_rate
    grouped["excess_late_orders"] = (
        grouped["late_orders"] - grouped["expected_late_orders_at_average"]
    )
    return grouped.replace([np.inf, -np.inf], np.nan)


def build_dimension_summary(base: pd.DataFrame) -> pd.DataFrame:
    dimensions = [
        "delivery_delay_bucket",
        "route_type",
        "customer_state",
        "main_seller_state",
        "main_product_category",
        "primary_payment_type",
        "freight_burden_bucket",
        "payment_value_band",
    ]
    return pd.concat(
        [contribution_by_dimension(base, dimension) for dimension in dimensions],
        ignore_index=True,
    )


def build_priority_segments(base: pd.DataFrame) -> pd.DataFrame:
    segment_specs = [
        ("category_state", ["main_product_category", "customer_state"]),
        ("category_route", ["main_product_category", "route_type"]),
        ("seller_state_route", ["main_seller_state", "route_type"]),
        ("delay_route", ["delivery_delay_bucket", "route_type"]),
    ]
    frames: list[pd.DataFrame] = []
    total_low_reviews = base["is_low_review"].sum()
    total_orders = base["order_id"].nunique()
    overall_rate = base.loc[base["has_review"].fillna(False), "is_low_review"].mean()

    for segment_family, columns in segment_specs:
        frame = (
            base.groupby(columns, dropna=False)
            .agg(
                orders=("order_id", "nunique"),
                delivered_orders=("is_delivered", "sum"),
                reviewed_orders=("has_review", "sum"),
                low_review_orders=("is_low_review", "sum"),
                late_orders=("is_late", "sum"),
                gross_payment_volume=("payment_total", "sum"),
            )
            .reset_index()
        )
        frame["segment_family"] = segment_family
        frame["segment"] = frame[columns].astype(str).agg(" / ".join, axis=1)
        frame["low_review_rate"] = frame["low_review_orders"] / frame["reviewed_orders"]
        frame["late_rate"] = frame["late_orders"] / frame["delivered_orders"]
        frame["share_of_low_reviews"] = frame["low_review_orders"] / total_low_reviews
        frame["share_of_orders"] = frame["orders"] / total_orders
        frame["expected_low_reviews_at_average"] = frame["reviewed_orders"] * overall_rate
        frame["excess_low_reviews"] = (
            frame["low_review_orders"] - frame["expected_low_reviews_at_average"]
        )
        frame["priority_score"] = (
            100
            * frame["share_of_low_reviews"].fillna(0) ** 0.55
            * np.maximum(frame["low_review_rate"].fillna(0) / overall_rate, 0) ** 0.35
            * np.maximum(frame["orders"].fillna(0) / MIN_SEGMENT_ORDERS, 0) ** 0.10
        )
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[combined["orders"].ge(MIN_SEGMENT_ORDERS)].copy()
    return combined.sort_values("priority_score", ascending=False)


def format_priority_backlog(priority_segments: pd.DataFrame) -> pd.DataFrame:
    display = priority_segments.head(8)[
        [
            "segment_family",
            "segment",
            "orders",
            "low_review_rate",
            "share_of_low_reviews",
            "excess_low_reviews",
            "priority_score",
        ]
    ].copy()
    display["low_review_rate"] = display["low_review_rate"].map(format_percent)
    display["share_of_low_reviews"] = display["share_of_low_reviews"].map(format_percent)
    display["excess_low_reviews"] = display["excess_low_reviews"].map(lambda value: f"{value:,.0f}")
    display["priority_score"] = display["priority_score"].map(lambda value: f"{value:.1f}")
    return display.rename(
        columns={
            "segment_family": "Segment View",
            "segment": "Segment",
            "orders": "Orders",
            "low_review_rate": "Low-Review Rate",
            "share_of_low_reviews": "Share of Low Reviews",
            "excess_low_reviews": "Excess Low Reviews",
            "priority_score": "Priority",
        }
    )


def format_top_contributors(dimension_summary: pd.DataFrame) -> pd.DataFrame:
    key_dimensions = [
        "delivery_delay_bucket",
        "route_type",
        "customer_state",
        "main_product_category",
    ]
    rows = []
    for dimension in key_dimensions:
        segment = (
            dimension_summary[
                dimension_summary["dimension"].eq(dimension)
                & dimension_summary["orders"].ge(MIN_SEGMENT_ORDERS)
            ]
            .sort_values("share_of_low_reviews", ascending=False)
            .iloc[0]
        )
        rows.append(
            {
                "Root-Cause Layer": dimension,
                "Largest Contributor": segment["segment"],
                "Orders": f"{int(segment['orders']):,}",
                "Low-Review Rate": format_percent(segment["low_review_rate"]),
                "Share of Low Reviews": format_percent(segment["share_of_low_reviews"]),
                "Payment Volume": format_brl(segment["gross_payment_volume"]),
            }
        )
    return pd.DataFrame.from_records(rows)


def save_outputs(
    dimension_summary: pd.DataFrame,
    priority_segments: pd.DataFrame,
    reports_dir: Path,
) -> None:
    dimension_summary.to_csv(reports_dir / "root_cause_dimension_summary.csv", index=False)
    top_contributors = (
        dimension_summary[dimension_summary["orders"].ge(MIN_SEGMENT_ORDERS)]
        .sort_values(["dimension", "share_of_low_reviews"], ascending=[True, False])
        .groupby("dimension", group_keys=False)
        .head(8)
    )
    top_contributors.to_csv(reports_dir / "root_cause_top_contributors.csv", index=False)
    priority_segments.head(50).to_csv(
        reports_dir / "root_cause_priority_segments.csv",
        index=False,
    )


def plot_low_review_pareto(priority_segments: pd.DataFrame, figures_dir: Path) -> None:
    top = priority_segments.head(TOP_N).copy().sort_values("share_of_low_reviews")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(top["segment"], top["share_of_low_reviews"], color="#3973a8")
    ax.set_xlabel("Share of all low-review orders")
    ax.set_title("Root-Cause Pareto: Highest-Contribution Experience Segments")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    plt.tight_layout()
    plt.savefig(figures_dir / "root_cause_low_review_pareto.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_delay_bucket_impact(dimension_summary: pd.DataFrame, figures_dir: Path) -> None:
    buckets = dimension_summary[
        dimension_summary["dimension"].eq("delivery_delay_bucket")
        & dimension_summary["segment"].ne("unknown")
    ].copy()
    order = [
        "on_or_before_estimate",
        "1_3_days_late",
        "4_7_days_late",
        "8_14_days_late",
        "15_plus_days_late",
    ]
    buckets["segment"] = pd.Categorical(buckets["segment"], categories=order, ordered=True)
    buckets = buckets.sort_values("segment")
    fig, ax1 = plt.subplots(figsize=(10, 5.5))
    ax2 = ax1.twinx()
    ax1.bar(buckets["segment"].astype(str), buckets["orders"], color="#3973a8", alpha=0.75)
    ax2.plot(
        buckets["segment"].astype(str),
        buckets["low_review_rate"],
        color="#c84242",
        marker="o",
        linewidth=2,
    )
    ax1.set_ylabel("Orders")
    ax2.set_ylabel("Low-review rate")
    ax2.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax1.set_title("Delivery Delay Bucket: Volume and Low-Review Risk")
    ax1.tick_params(axis="x", rotation=35)
    plt.tight_layout()
    plt.savefig(figures_dir / "root_cause_delay_bucket_impact.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_category_state_heatmap(priority_segments: pd.DataFrame, figures_dir: Path) -> None:
    category_state = priority_segments[priority_segments["segment_family"].eq("category_state")]
    top_categories = (
        category_state.groupby("main_product_category")["low_review_orders"].sum().nlargest(8).index
    )
    top_states = (
        category_state.groupby("customer_state")["low_review_orders"].sum().nlargest(8).index
    )
    heatmap = (
        category_state[
            category_state["main_product_category"].isin(top_categories)
            & category_state["customer_state"].isin(top_states)
        ]
        .pivot_table(
            index="main_product_category",
            columns="customer_state",
            values="share_of_low_reviews",
            aggfunc="sum",
            fill_value=0,
        )
        .loc[top_categories, top_states]
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    image = ax.imshow(heatmap.values, cmap="Reds", aspect="auto")
    ax.set_xticks(range(len(heatmap.columns)), labels=heatmap.columns)
    ax.set_yticks(range(len(heatmap.index)), labels=heatmap.index)
    ax.set_title("Low-Review Contribution Heatmap: Category by Customer State")
    cbar = fig.colorbar(image, ax=ax)
    cbar.ax.yaxis.set_major_formatter(lambda value, _: f"{value:.1%}")
    plt.tight_layout()
    plt.savefig(figures_dir / "root_cause_category_state_heatmap.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_priority_matrix(priority_segments: pd.DataFrame, figures_dir: Path) -> None:
    top = priority_segments.head(25).copy()
    fig, ax = plt.subplots(figsize=(9, 6))
    sizes = np.clip(top["share_of_low_reviews"] * 8000, 40, 900)
    scatter = ax.scatter(
        top["orders"],
        top["low_review_rate"],
        s=sizes,
        c=top["priority_score"],
        cmap="viridis",
        alpha=0.75,
        edgecolor="white",
        linewidth=0.8,
    )
    for _, row in top.head(8).iterrows():
        ax.annotate(
            str(row["segment"])[:35],
            (row["orders"], row["low_review_rate"]),
            fontsize=8,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.set_xscale("log")
    ax.set_xlabel("Orders, log scale")
    ax.set_ylabel("Low-review rate")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.set_title("Root-Cause Priority Matrix")
    fig.colorbar(scatter, ax=ax, label="Priority score")
    plt.tight_layout()
    plt.savefig(
        figures_dir / "root_cause_segment_priority_matrix.png", dpi=160, bbox_inches="tight"
    )
    plt.close(fig)


def write_summary(
    dimension_summary: pd.DataFrame,
    priority_segments: pd.DataFrame,
    reports_dir: Path,
) -> None:
    delay = dimension_summary[
        dimension_summary["dimension"].eq("delivery_delay_bucket")
        & dimension_summary["segment"].eq("15_plus_days_late")
    ].iloc[0]
    route = dimension_summary[
        dimension_summary["dimension"].eq("route_type")
        & dimension_summary["segment"].eq("cross_state")
    ].iloc[0]
    top_category = (
        dimension_summary[dimension_summary["dimension"].eq("main_product_category")]
        .sort_values("share_of_low_reviews", ascending=False)
        .iloc[0]
    )
    top_segment = priority_segments.iloc[0]
    contributor_table = markdown_table(format_top_contributors(dimension_summary))
    backlog_table = markdown_table(format_priority_backlog(priority_segments))

    summary = f"""# Root-Cause Decomposition Summary

## Objective

I decomposed low-review and late-delivery issues by contribution, not only by rate. This separates
small high-risk pockets from large operational drivers that create the most customer-experience
damage.

## Main Findings

| Root-Cause View | Key Result |
|---|---:|
| 15+ days late segment | {delay['share_of_low_reviews']:.1%} of all low reviews |
| 15+ days late low-review rate | {delay['low_review_rate']:.1%} |
| Cross-state routes | {route['share_of_low_reviews']:.1%} of all low reviews |
| Top category contributor | {top_category['segment']} |
| Top cross-dimensional segment | {top_segment['segment']} |
| Top segment low-review rate | {top_segment['low_review_rate']:.1%} |
| Top segment share of low reviews | {top_segment['share_of_low_reviews']:.1%} |

## Contribution View

{contributor_table}

## Root-Cause Backlog

{backlog_table}

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
"""
    (reports_dir / "root_cause_analysis_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    orders, seller_orders = load_inputs(PROJECT_ROOT)
    base = prepare_order_base(orders, seller_orders)
    dimension_summary = build_dimension_summary(base)
    priority_segments = build_priority_segments(base)
    save_outputs(dimension_summary, priority_segments, reports_dir)

    plot_low_review_pareto(priority_segments, figures_dir)
    plot_delay_bucket_impact(dimension_summary, figures_dir)
    plot_category_state_heatmap(priority_segments, figures_dir)
    plot_priority_matrix(priority_segments, figures_dir)
    write_summary(dimension_summary, priority_segments, reports_dir)

    print("Root-cause decomposition completed.")
    print(f"Dimension rows: {len(dimension_summary):,}")
    print(f"Priority segments: {len(priority_segments):,}")
    print(f"Summary: {reports_dir / 'root_cause_analysis_summary.md'}")


if __name__ == "__main__":
    main()
