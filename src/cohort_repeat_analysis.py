"""Analyze customer cohorts and observed repeat-purchase behavior."""

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

REPEAT_WINDOW_DAYS = 90


def coerce_bool(series: pd.Series) -> pd.Series:
    return series.replace({"True": True, "False": False, "true": True, "false": False}).astype(
        "boolean"
    )


def load_orders(project_root: Path) -> pd.DataFrame:
    orders = pd.read_csv(project_root / "data" / "processed" / "orders_analysis_base.csv")
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )
    for col in ["is_delivered", "is_late", "is_low_review"]:
        orders[col] = coerce_bool(orders[col])
    return orders


def prepare_delivered_orders(orders: pd.DataFrame) -> pd.DataFrame:
    delivered = orders[
        orders["is_delivered"].fillna(False)
        & orders["customer_unique_id"].notna()
        & orders["order_purchase_timestamp"].notna()
    ].copy()
    delivered = delivered.sort_values(
        ["customer_unique_id", "order_purchase_timestamp", "order_id"]
    )
    delivered["customer_order_number"] = delivered.groupby("customer_unique_id").cumcount() + 1
    delivered["is_repeat_order"] = delivered["customer_order_number"].gt(1)
    delivered["order_month_period"] = delivered["order_purchase_timestamp"].dt.to_period("M")
    delivered["order_month"] = delivered["order_month_period"].astype(str)
    return delivered


def build_customer_summary(delivered: pd.DataFrame) -> pd.DataFrame:
    first_orders = delivered.drop_duplicates("customer_unique_id", keep="first").copy()
    first_orders = first_orders[
        [
            "customer_unique_id",
            "order_id",
            "order_purchase_timestamp",
            "customer_state",
            "main_product_category",
            "is_late",
            "is_low_review",
            "review_score_mean",
        ]
    ].rename(
        columns={
            "order_id": "first_order_id",
            "order_purchase_timestamp": "first_purchase_timestamp",
            "customer_state": "first_customer_state",
            "main_product_category": "first_product_category",
            "is_late": "first_order_is_late",
            "is_low_review": "first_order_is_low_review",
            "review_score_mean": "first_order_review_score",
        }
    )

    second_orders = delivered.loc[
        delivered["customer_order_number"].eq(2),
        [
            "customer_unique_id",
            "order_purchase_timestamp",
        ],
    ].rename(columns={"order_purchase_timestamp": "second_purchase_timestamp"})

    customer_summary = (
        delivered.groupby("customer_unique_id", as_index=False)
        .agg(
            delivered_orders=("order_id", "nunique"),
            gross_payment_volume=("payment_total", "sum"),
            last_purchase_timestamp=("order_purchase_timestamp", "max"),
        )
        .merge(first_orders, on="customer_unique_id", how="left")
        .merge(second_orders, on="customer_unique_id", how="left")
    )
    customer_summary["observed_repeat_customer"] = customer_summary["delivered_orders"].ge(2)
    customer_summary["days_to_second_purchase"] = (
        customer_summary["second_purchase_timestamp"] - customer_summary["first_purchase_timestamp"]
    ).dt.total_seconds() / 86400

    observation_end = delivered["order_purchase_timestamp"].max()
    eligibility_cutoff = observation_end - pd.Timedelta(days=REPEAT_WINDOW_DAYS)
    customer_summary["eligible_for_90d_repeat"] = (
        customer_summary["first_purchase_timestamp"] <= eligibility_cutoff
    )
    customer_summary["repeat_within_90d"] = customer_summary[
        "second_purchase_timestamp"
    ].notna() & (
        customer_summary["second_purchase_timestamp"]
        <= customer_summary["first_purchase_timestamp"] + pd.Timedelta(days=REPEAT_WINDOW_DAYS)
    )
    return customer_summary


def build_cohort_matrix(delivered: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    first_month = delivered.groupby("customer_unique_id")["order_month_period"].min()
    cohort_orders = delivered.copy()
    cohort_orders["cohort_month_period"] = cohort_orders["customer_unique_id"].map(first_month)
    cohort_orders["months_since_first"] = (
        (cohort_orders["order_month_period"].dt.year - cohort_orders["cohort_month_period"].dt.year)
        * 12
        + cohort_orders["order_month_period"].dt.month
        - cohort_orders["cohort_month_period"].dt.month
    )

    active = (
        cohort_orders.groupby(["cohort_month_period", "months_since_first"])["customer_unique_id"]
        .nunique()
        .rename("active_customers")
        .reset_index()
    )
    cohort_size = (
        cohort_orders.loc[cohort_orders["months_since_first"].eq(0)]
        .groupby("cohort_month_period")["customer_unique_id"]
        .nunique()
        .rename("cohort_size")
    )
    active = active.merge(cohort_size, on="cohort_month_period", how="left")
    active["active_customer_share"] = active["active_customers"] / active["cohort_size"]
    matrix = active.pivot(
        index="cohort_month_period",
        columns="months_since_first",
        values="active_customer_share",
    )
    matrix.index = matrix.index.astype(str)
    cohort_sizes = cohort_size.reset_index()
    cohort_sizes["cohort_month"] = cohort_sizes["cohort_month_period"].astype(str)
    cohort_sizes = cohort_sizes.drop(columns=["cohort_month_period"])
    return matrix, cohort_sizes


def build_repeat_summaries(
    delivered: pd.DataFrame,
    customer_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly = (
        delivered.groupby(["order_month", "is_repeat_order"])
        .agg(orders=("order_id", "nunique"), gross_payment_volume=("payment_total", "sum"))
        .reset_index()
    )
    monthly["order_type"] = np.where(
        monthly["is_repeat_order"], "repeat_order", "new_customer_order"
    )

    eligible = customer_summary[customer_summary["eligible_for_90d_repeat"]].copy()
    overall = pd.DataFrame(
        [
            {
                "customers": len(customer_summary),
                "observed_repeat_customers": int(
                    customer_summary["observed_repeat_customer"].sum()
                ),
                "observed_repeat_customer_rate": customer_summary[
                    "observed_repeat_customer"
                ].mean(),
                "eligible_customers_90d": len(eligible),
                "repeat_customers_within_90d": int(eligible["repeat_within_90d"].sum()),
                "repeat_rate_within_90d": eligible["repeat_within_90d"].mean(),
                "median_days_to_second_purchase": customer_summary[
                    "days_to_second_purchase"
                ].median(),
            }
        ]
    )

    experience_rows = []
    for feature, label in [
        ("first_order_is_late", "First order late"),
        ("first_order_is_low_review", "First order low review"),
    ]:
        subset = eligible[eligible[feature].notna()].copy()
        summary = (
            subset.groupby(feature)
            .agg(
                eligible_customers_90d=("customer_unique_id", "count"),
                repeat_customers_within_90d=("repeat_within_90d", "sum"),
                repeat_rate_within_90d=("repeat_within_90d", "mean"),
                observed_repeat_rate=("observed_repeat_customer", "mean"),
            )
            .reset_index()
        )
        summary["experience_dimension"] = label
        summary["experience_group"] = np.where(summary[feature], "Yes", "No")
        experience_rows.append(summary.drop(columns=[feature]))
    experience_summary = pd.concat(experience_rows, ignore_index=True)

    category_summary = (
        eligible.groupby("first_product_category", dropna=False)
        .agg(
            eligible_customers_90d=("customer_unique_id", "count"),
            repeat_customers_within_90d=("repeat_within_90d", "sum"),
            repeat_rate_within_90d=("repeat_within_90d", "mean"),
            observed_repeat_rate=("observed_repeat_customer", "mean"),
        )
        .reset_index()
        .query("eligible_customers_90d >= 300")
        .sort_values(["repeat_rate_within_90d", "eligible_customers_90d"], ascending=[False, False])
    )
    return monthly, overall, experience_summary, category_summary


def create_figures(
    cohort_matrix: pd.DataFrame,
    cohort_sizes: pd.DataFrame,
    monthly: pd.DataFrame,
    customer_summary: pd.DataFrame,
    experience_summary: pd.DataFrame,
    figures_dir: Path,
) -> None:
    eligible_cohorts = cohort_sizes.loc[cohort_sizes["cohort_size"].ge(100), "cohort_month"]
    heatmap = cohort_matrix.loc[cohort_matrix.index.isin(eligible_cohorts)].iloc[:, 1:13]
    heatmap_values = heatmap.to_numpy()
    color_upper_bound = max(0.01, float(np.nanquantile(heatmap_values, 0.98)))
    fig, ax = plt.subplots(figsize=(13, 8))
    image = ax.imshow(
        heatmap_values,
        aspect="auto",
        cmap="Blues",
        vmin=0,
        vmax=color_upper_bound,
    )
    ax.set_title("Observed Cohort Repeat-Purchase Activity")
    ax.set_xlabel("Months Since First Delivered Order")
    ax.set_ylabel("First Purchase Cohort")
    ax.set_xticks(np.arange(len(heatmap.columns)))
    ax.set_xticklabels(heatmap.columns)
    ax.set_yticks(np.arange(len(heatmap.index)))
    ax.set_yticklabels(heatmap.index)
    fig.colorbar(image, ax=ax, label="Share of Cohort Active Again")
    plt.tight_layout()
    plt.savefig(figures_dir / "cohort_repeat_activity_heatmap.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    monthly_pivot = monthly.pivot(
        index="order_month", columns="order_type", values="orders"
    ).fillna(0)
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.bar(
        monthly_pivot.index,
        monthly_pivot.get("new_customer_order", 0),
        label="New-customer orders",
        color="#4c78a8",
    )
    ax.bar(
        monthly_pivot.index,
        monthly_pivot.get("repeat_order", 0),
        bottom=monthly_pivot.get("new_customer_order", 0),
        label="Repeat orders",
        color="#f58518",
    )
    ax.set_title("Monthly Delivered Orders: New vs Repeat Customers")
    ax.set_xlabel("Purchase Month")
    ax.set_ylabel("Orders")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "monthly_new_vs_repeat_orders.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    plot_data = experience_summary.copy()
    plot_data["label"] = plot_data["experience_dimension"] + ": " + plot_data["experience_group"]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(
        plot_data["label"], plot_data["repeat_rate_within_90d"], color=["#4c78a8", "#e45756"] * 2
    )
    ax.set_title("90-Day Repeat Rate by First-Order Experience")
    ax.set_xlabel("Observed Repeat Rate Within 90 Days")
    plt.tight_layout()
    plt.savefig(
        figures_dir / "repeat_rate_by_first_order_experience.png", dpi=160, bbox_inches="tight"
    )
    plt.close(fig)

    days = customer_summary["days_to_second_purchase"].dropna()
    days = days[days <= 365]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(days, bins=np.arange(0, 371, 15), color="#72b7b2", edgecolor="white")
    ax.axvline(
        days.median(), color="#d62728", linestyle="--", label=f"Median: {days.median():.0f} days"
    )
    ax.set_title("Days to Second Delivered Order")
    ax.set_xlabel("Days")
    ax.set_ylabel("Customers")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "days_to_second_purchase.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_summary(
    reports_dir: Path,
    overall: pd.DataFrame,
    experience_summary: pd.DataFrame,
    category_summary: pd.DataFrame,
) -> None:
    metrics = overall.iloc[0]
    late = experience_summary.loc[experience_summary["experience_dimension"].eq("First order late")]
    low_review = experience_summary.loc[
        experience_summary["experience_dimension"].eq("First order low review")
    ]

    def group_rate(frame: pd.DataFrame, group: str) -> float:
        return float(
            frame.loc[frame["experience_group"].eq(group), "repeat_rate_within_90d"].iloc[0]
        )

    top_category = category_summary.iloc[0]
    summary = f"""# Cohort and Observed Repeat-Purchase Analysis

## Scope

I analyzed delivered orders using `customer_unique_id` to measure observed repeat-purchase
behavior.

The dataset covers a limited historical window, so these metrics should not be interpreted as true
long-term retention. To reduce right-censoring, the primary comparison uses a fixed
{REPEAT_WINDOW_DAYS}-day repeat window and only includes customers whose first purchase occurred at
least {REPEAT_WINDOW_DAYS} days before the final observed order date.

## Main Results

| Metric | Value |
|---|---:|
| Customers with delivered orders | {int(metrics['customers']):,} |
| Observed repeat customers | {int(metrics['observed_repeat_customers']):,} |
| Observed repeat-customer rate | {metrics['observed_repeat_customer_rate']:.1%} |
| Customers eligible for {REPEAT_WINDOW_DAYS}-day analysis | {int(metrics['eligible_customers_90d']):,} |
| {REPEAT_WINDOW_DAYS}-day repeat rate | {metrics['repeat_rate_within_90d']:.1%} |
| Median days to second delivered order | {metrics['median_days_to_second_purchase']:.0f} |

## First-Order Experience and Repeat Behavior

- First order on time: {group_rate(late, 'No'):.1%} repeated within {REPEAT_WINDOW_DAYS} days
- First order late: {group_rate(late, 'Yes'):.1%} repeated within {REPEAT_WINDOW_DAYS} days
- First order without a low review: {group_rate(low_review, 'No'):.1%} repeated within {REPEAT_WINDOW_DAYS} days
- First order with a low review: {group_rate(low_review, 'Yes'):.1%} repeated within {REPEAT_WINDOW_DAYS} days

These comparisons are descriptive and do not establish causality. Customer intent, category
purchase cycles, and other unobserved factors may affect both first-order experience and repeat
behavior.

Among first-order categories with at least 300 eligible customers, the highest observed
{REPEAT_WINDOW_DAYS}-day repeat rate was `{top_category['first_product_category']}` at
{top_category['repeat_rate_within_90d']:.1%}.

## Business Use

This analysis adds a customer-lifecycle view to the project. It can support onboarding-quality
monitoring, category-specific repeat-purchase strategy, and evaluation of whether poor first-order
experiences are associated with weaker observed repeat behavior.
"""
    (reports_dir / "cohort_repeat_analysis_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    figures_dir.mkdir(parents=True, exist_ok=True)

    orders = load_orders(PROJECT_ROOT)
    delivered = prepare_delivered_orders(orders)
    customer_summary = build_customer_summary(delivered)
    cohort_matrix, cohort_sizes = build_cohort_matrix(delivered)
    monthly, overall, experience_summary, category_summary = build_repeat_summaries(
        delivered,
        customer_summary,
    )

    customer_summary.to_csv(processed_dir / "customer_repeat_behavior_base.csv", index=False)
    cohort_matrix.to_csv(reports_dir / "cohort_repeat_activity_matrix.csv")
    cohort_sizes.to_csv(reports_dir / "cohort_sizes.csv", index=False)
    monthly.to_csv(reports_dir / "monthly_new_repeat_orders.csv", index=False)
    overall.to_csv(reports_dir / "repeat_behavior_metrics.csv", index=False)
    experience_summary.to_csv(reports_dir / "repeat_by_first_order_experience.csv", index=False)
    category_summary.to_csv(reports_dir / "repeat_by_first_category.csv", index=False)

    create_figures(
        cohort_matrix,
        cohort_sizes,
        monthly,
        customer_summary,
        experience_summary,
        figures_dir,
    )
    write_summary(reports_dir, overall, experience_summary, category_summary)

    print("Cohort and repeat-purchase analysis completed.")
    print(overall.to_string(index=False))
    print(f"Summary: {reports_dir / 'cohort_repeat_analysis_summary.md'}")


if __name__ == "__main__":
    main()
