"""Seller scorecard, logistics distance, and model lift analysis."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
matplotlib_cache_dir = PROJECT_ROOT / ".matplotlib_cache"
matplotlib_cache_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache_dir))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def coerce_bool(series: pd.Series) -> pd.Series:
    return series.replace({"True": True, "False": False, "true": True, "false": False}).astype("boolean")


def haversine_km(lat1, lng1, lat2, lng2):
    radius_km = 6371.0
    lat1 = np.radians(lat1)
    lng1 = np.radians(lng1)
    lat2 = np.radians(lat2)
    lng2 = np.radians(lng2)

    dlat = lat2 - lat1
    dlng = lng2 - lng1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlng / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))
    return radius_km * c


def min_max_scale(series: pd.Series, lower: float, upper: float) -> pd.Series:
    value_range = series.max() - series.min()
    if pd.isna(value_range) or value_range == 0:
        return pd.Series((lower + upper) / 2, index=series.index)
    return lower + (series - series.min()) / value_range * (upper - lower)


def load_inputs(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    processed_dir = project_root / "data" / "processed"
    orders = pd.read_csv(processed_dir / "orders_analysis_base.csv")
    items = pd.read_csv(processed_dir / "order_items_enriched.csv")
    geolocation = pd.read_csv(processed_dir / "geolocation_clean.csv")

    orders["order_purchase_timestamp"] = pd.to_datetime(orders["order_purchase_timestamp"], errors="coerce")
    for col in ["is_delivered", "is_late", "is_low_review"]:
        if col in orders.columns:
            orders[col] = coerce_bool(orders[col])

    return orders, items, geolocation


def build_seller_order_base(orders: pd.DataFrame, items: pd.DataFrame, geolocation: pd.DataFrame) -> pd.DataFrame:
    items_with_volume = items.copy()
    items_with_volume["product_volume_cm3"] = (
        items_with_volume["product_length_cm"]
        * items_with_volume["product_height_cm"]
        * items_with_volume["product_width_cm"]
    )

    seller_order = (
        items_with_volume.groupby(["seller_id", "order_id"], as_index=False)
        .agg(
            seller_order_items=("order_item_id", "count"),
            seller_product_total=("price", "sum"),
            seller_freight_total=("freight_value", "sum"),
            seller_item_total=("item_total", "sum"),
            avg_product_weight_g=("product_weight_g", "mean"),
            avg_product_volume_cm3=("product_volume_cm3", "mean"),
            seller_zip_code_prefix=("seller_zip_code_prefix", "first"),
            seller_city=("seller_city", "first"),
            seller_state=("seller_state", "first"),
        )
    )

    order_cols = [
        "order_id",
        "order_status",
        "order_purchase_timestamp",
        "purchase_month",
        "is_delivered",
        "delivery_days",
        "estimated_delivery_days",
        "delivery_delta_days",
        "is_late",
        "customer_state",
        "customer_city",
        "customer_zip_code_prefix",
        "customer_geolocation_lat",
        "customer_geolocation_lng",
        "payment_total",
        "review_score_mean",
        "is_low_review",
    ]
    seller_order = seller_order.merge(orders[order_cols], on="order_id", how="left")

    seller_geo = geolocation.rename(
        columns={
            "geolocation_zip_code_prefix": "seller_zip_code_prefix",
            "geolocation_lat": "seller_geolocation_lat",
            "geolocation_lng": "seller_geolocation_lng",
            "geolocation_city": "seller_geolocation_city",
            "geolocation_state": "seller_geolocation_state",
            "geolocation_records": "seller_geolocation_records",
        }
    )
    seller_order = seller_order.merge(seller_geo, on="seller_zip_code_prefix", how="left")

    has_geo = (
        seller_order["customer_geolocation_lat"].notna()
        & seller_order["customer_geolocation_lng"].notna()
        & seller_order["seller_geolocation_lat"].notna()
        & seller_order["seller_geolocation_lng"].notna()
    )
    seller_order["customer_seller_distance_km"] = np.nan
    seller_order.loc[has_geo, "customer_seller_distance_km"] = haversine_km(
        seller_order.loc[has_geo, "customer_geolocation_lat"],
        seller_order.loc[has_geo, "customer_geolocation_lng"],
        seller_order.loc[has_geo, "seller_geolocation_lat"],
        seller_order.loc[has_geo, "seller_geolocation_lng"],
    )

    seller_order["is_cross_state"] = (
        seller_order["customer_state"].ne(seller_order["seller_state"]).astype("boolean")
    )
    missing_state = seller_order["customer_state"].isna() | seller_order["seller_state"].isna()
    seller_order.loc[missing_state, "is_cross_state"] = pd.NA
    seller_order["seller_freight_share"] = seller_order["seller_freight_total"] / seller_order[
        "seller_item_total"
    ].replace(0, np.nan)

    return seller_order


def create_seller_scorecard(
    seller_order: pd.DataFrame, reports_dir: Path, figures_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scored_orders = seller_order[seller_order["review_score_mean"].notna()].copy()

    seller_scorecard = (
        scored_orders.groupby("seller_id", as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            seller_gmv=("seller_item_total", "sum"),
            product_revenue=("seller_product_total", "sum"),
            freight_revenue=("seller_freight_total", "sum"),
            avg_order_value=("seller_item_total", "mean"),
            avg_delivery_days=("delivery_days", "mean"),
            late_rate=("is_late", lambda s: pd.Series(s).astype("boolean").mean()),
            avg_review_score=("review_score_mean", "mean"),
            low_review_rate=("is_low_review", lambda s: pd.Series(s).astype("boolean").mean()),
            cross_state_rate=("is_cross_state", "mean"),
            avg_distance_km=("customer_seller_distance_km", "mean"),
            avg_freight_share=("seller_freight_share", "mean"),
            seller_state=("seller_state", "first"),
            seller_city=("seller_city", "first"),
        )
    )

    min_orders = 30
    eligible = seller_scorecard["orders"] >= min_orders
    gmv_cutoff = seller_scorecard.loc[eligible, "seller_gmv"].quantile(0.75)
    risk_cutoff = seller_scorecard.loc[eligible, "low_review_rate"].quantile(0.75)

    seller_scorecard["value_tier"] = np.where(seller_scorecard["seller_gmv"] >= gmv_cutoff, "high_value", "standard_value")
    seller_scorecard["risk_tier"] = np.where(
        seller_scorecard["low_review_rate"] >= risk_cutoff, "high_risk", "standard_risk"
    )
    seller_scorecard.loc[~eligible, "value_tier"] = "low_volume"
    seller_scorecard.loc[~eligible, "risk_tier"] = "low_volume"
    seller_scorecard["seller_segment"] = seller_scorecard["value_tier"] + "__" + seller_scorecard["risk_tier"]

    seller_segment_summary = (
        seller_scorecard.groupby("seller_segment", as_index=False)
        .agg(
            sellers=("seller_id", "count"),
            orders=("orders", "sum"),
            seller_gmv=("seller_gmv", "sum"),
            avg_low_review_rate=("low_review_rate", "mean"),
            avg_late_rate=("late_rate", "mean"),
            avg_review_score=("avg_review_score", "mean"),
        )
        .sort_values("seller_gmv", ascending=False)
    )

    seller_scorecard.to_csv(reports_dir / "seller_scorecard.csv", index=False)
    seller_segment_summary.to_csv(reports_dir / "seller_segment_summary.csv", index=False)

    plot_data = seller_scorecard[seller_scorecard["orders"] >= min_orders].copy()
    plot_data["bubble_size"] = min_max_scale(plot_data["orders"], 40, 600)
    color_map = {
        "high_value__high_risk": "#d62728",
        "high_value__standard_risk": "#2ca02c",
        "standard_value__high_risk": "#ff7f0e",
        "standard_value__standard_risk": "#4c78a8",
    }
    colors = plot_data["seller_segment"].map(color_map).fillna("#7f7f7f")

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(
        plot_data["seller_gmv"],
        plot_data["low_review_rate"],
        s=plot_data["bubble_size"],
        c=colors,
        alpha=0.72,
        edgecolor="white",
        linewidth=0.6,
    )
    ax.axvline(gmv_cutoff, color="black", linestyle="--", linewidth=1)
    ax.axhline(risk_cutoff, color="black", linestyle="--", linewidth=1)
    ax.set_xscale("log")
    ax.set_title("Seller Scorecard: Value vs Low Review Risk")
    ax.set_xlabel("Seller GMV, log scale")
    ax.set_ylabel("Low Review Rate")
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_scorecard_value_risk.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    top_risky = (
        seller_scorecard[seller_scorecard["orders"] >= min_orders]
        .sort_values(["low_review_rate", "seller_gmv"], ascending=[False, False])
        .head(15)
        .sort_values("low_review_rate", ascending=True)
    )
    fig, ax = plt.subplots(figsize=(12, 7))
    labels = top_risky["seller_id"].str.slice(0, 8) + " (" + top_risky["seller_state"].fillna("NA") + ")"
    ax.barh(labels, top_risky["low_review_rate"], color="#d62728")
    ax.set_title("Highest Low-Review Sellers Among Sellers With 30+ Orders")
    ax.set_xlabel("Low Review Rate")
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_top_low_review_risk.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    return seller_scorecard, seller_segment_summary


def create_logistics_distance_analysis(
    seller_order: pd.DataFrame, reports_dir: Path, figures_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    logistics = seller_order[
        seller_order["is_delivered"].fillna(False)
        & seller_order["review_score_mean"].notna()
        & seller_order["customer_seller_distance_km"].notna()
        & seller_order["is_cross_state"].notna()
    ].copy()

    distance_bins = [0, 100, 300, 600, 1000, 1500, 2500, np.inf]
    distance_labels = ["0-100", "100-300", "300-600", "600-1000", "1000-1500", "1500-2500", "2500+"]
    logistics["distance_bucket_km"] = pd.cut(
        logistics["customer_seller_distance_km"],
        bins=distance_bins,
        labels=distance_labels,
        include_lowest=True,
    )
    logistics["route_type"] = np.where(logistics["is_cross_state"], "cross_state", "same_state")

    distance_summary = (
        logistics.groupby("distance_bucket_km", observed=True)
        .agg(
            seller_orders=("order_id", "count"),
            avg_distance_km=("customer_seller_distance_km", "mean"),
            avg_delivery_days=("delivery_days", "mean"),
            late_rate=("is_late", lambda s: pd.Series(s).astype("boolean").mean()),
            avg_review_score=("review_score_mean", "mean"),
            low_review_rate=("is_low_review", lambda s: pd.Series(s).astype("boolean").mean()),
            avg_freight_share=("seller_freight_share", "mean"),
        )
        .reset_index()
    )

    route_summary = (
        logistics.groupby("route_type", as_index=False)
        .agg(
            seller_orders=("order_id", "count"),
            avg_distance_km=("customer_seller_distance_km", "mean"),
            avg_delivery_days=("delivery_days", "mean"),
            late_rate=("is_late", lambda s: pd.Series(s).astype("boolean").mean()),
            avg_review_score=("review_score_mean", "mean"),
            low_review_rate=("is_low_review", lambda s: pd.Series(s).astype("boolean").mean()),
            avg_freight_share=("seller_freight_share", "mean"),
        )
    )

    state_lane_summary = (
        logistics.groupby(["seller_state", "customer_state"], as_index=False)
        .agg(
            seller_orders=("order_id", "count"),
            seller_gmv=("seller_item_total", "sum"),
            avg_distance_km=("customer_seller_distance_km", "mean"),
            avg_delivery_days=("delivery_days", "mean"),
            late_rate=("is_late", lambda s: pd.Series(s).astype("boolean").mean()),
            low_review_rate=("is_low_review", lambda s: pd.Series(s).astype("boolean").mean()),
        )
        .query("seller_orders >= 100")
        .sort_values(["low_review_rate", "seller_gmv"], ascending=[False, False])
    )

    logistics.to_csv(reports_dir / "seller_order_distance_base.csv", index=False)
    distance_summary.to_csv(reports_dir / "logistics_distance_summary.csv", index=False)
    route_summary.to_csv(reports_dir / "logistics_route_summary.csv", index=False)
    state_lane_summary.to_csv(reports_dir / "logistics_state_lane_summary.csv", index=False)

    x = np.arange(len(distance_summary))
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax2 = ax1.twinx()
    ax1.bar(x, distance_summary["seller_orders"], color="#bab0ac", label="Seller-orders")
    ax2.plot(x, distance_summary["avg_delivery_days"], marker="o", color="#1f77b4", label="Avg delivery days")
    ax2.plot(x, distance_summary["low_review_rate"], marker="o", color="#d62728", label="Low review rate")
    ax1.set_xticks(x)
    ax1.set_xticklabels(distance_summary["distance_bucket_km"].astype(str), rotation=25)
    ax1.set_title("Distance Buckets: Delivery Time and Low Review Risk")
    ax1.set_xlabel("Customer-Seller Distance Bucket, km")
    ax1.set_ylabel("Seller-orders")
    ax2.set_ylabel("Days / Rate")
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")
    plt.tight_layout()
    plt.savefig(figures_dir / "logistics_distance_delivery_review.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    route_plot = route_summary.sort_values("route_type")
    x = np.arange(len(route_plot))
    fig, ax = plt.subplots(figsize=(9, 6))
    width = 0.25
    ax.bar(x - width, route_plot["avg_delivery_days"], width=width, label="Avg delivery days", color="#1f77b4")
    ax.bar(x, route_plot["late_rate"], width=width, label="Late rate", color="#ff7f0e")
    ax.bar(x + width, route_plot["low_review_rate"], width=width, label="Low review rate", color="#d62728")
    ax.set_xticks(x)
    ax.set_xticklabels(route_plot["route_type"])
    ax.set_title("Same-State vs Cross-State Delivery Experience")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "logistics_cross_state_comparison.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    return distance_summary, route_summary, state_lane_summary


def create_model_lift_analysis(orders: pd.DataFrame, reports_dir: Path, figures_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_data = orders[
        orders["is_delivered"].fillna(False)
        & orders["is_low_review"].notna()
        & orders["payment_total"].notna()
        & orders["order_purchase_timestamp"].notna()
    ].copy()
    model_data["target_low_review"] = model_data["is_low_review"].astype(int)
    model_data["is_late_num"] = model_data["is_late"].fillna(False).astype(int)

    numeric_features = [
        "payment_total",
        "product_total",
        "freight_total",
        "freight_share_of_payment",
        "item_count",
        "product_count",
        "seller_count",
        "product_category_count",
        "avg_item_price",
        "avg_freight_ratio",
        "payment_count",
        "payment_type_count",
        "max_payment_installments",
        "approval_time_hours",
        "delivery_days",
        "estimated_delivery_days",
        "delivery_delta_days",
        "is_late_num",
    ]
    categorical_features = [
        "purchase_month",
        "purchase_dayofweek",
        "customer_state",
        "main_product_category",
        "main_seller_state",
        "primary_payment_type",
    ]
    feature_cols = numeric_features + categorical_features

    cutoff_date = pd.Timestamp("2018-01-01")
    train_df = model_data[model_data["order_purchase_timestamp"] < cutoff_date].copy()
    test_df = model_data[model_data["order_purchase_timestamp"] >= cutoff_date].copy()

    X_train = train_df[feature_cols]
    y_train = train_df["target_low_review"]
    X_test = test_df[feature_cols]
    y_test = test_df["target_low_review"]

    numeric_transformer = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=50)),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)),
        ]
    )
    model.fit(X_train, y_train)
    y_score = model.predict_proba(X_test)[:, 1]

    precision, recall, thresholds = precision_recall_curve(y_test, y_score)
    f1_values = np.divide(
        2 * precision[:-1] * recall[:-1],
        precision[:-1] + recall[:-1],
        out=np.zeros_like(precision[:-1]),
        where=(precision[:-1] + recall[:-1]) != 0,
    )
    best_threshold = float(thresholds[int(np.nanargmax(f1_values))])

    predictions = test_df[
        [
            "order_id",
            "order_purchase_timestamp",
            "customer_state",
            "main_product_category",
            "payment_total",
            "delivery_days",
            "delivery_delta_days",
            "is_late",
            "target_low_review",
        ]
    ].copy()
    predictions["low_review_probability"] = y_score
    predictions["risk_rank"] = predictions["low_review_probability"].rank(method="first", ascending=False).astype(int)
    predictions["risk_percentile"] = predictions["risk_rank"] / len(predictions)
    predictions["predicted_at_best_threshold"] = predictions["low_review_probability"] >= best_threshold

    sorted_pred = predictions.sort_values("low_review_probability", ascending=False).reset_index(drop=True)
    total_low_reviews = sorted_pred["target_low_review"].sum()
    baseline_rate = sorted_pred["target_low_review"].mean()

    rows = []
    for top_share in [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00]:
        n = max(1, int(np.ceil(len(sorted_pred) * top_share)))
        top = sorted_pred.iloc[:n]
        captured = top["target_low_review"].sum()
        rows.append(
            {
                "top_risk_share": top_share,
                "orders_reviewed": n,
                "low_reviews_captured": int(captured),
                "capture_rate": captured / total_low_reviews,
                "precision_in_segment": top["target_low_review"].mean(),
                "lift_vs_baseline": top["target_low_review"].mean() / baseline_rate,
            }
        )
    lift_table = pd.DataFrame(rows)

    cumulative = sorted_pred[["target_low_review", "low_review_probability"]].copy()
    cumulative["orders_seen"] = np.arange(1, len(cumulative) + 1)
    cumulative["orders_share"] = cumulative["orders_seen"] / len(cumulative)
    cumulative["low_reviews_captured"] = cumulative["target_low_review"].cumsum()
    cumulative["capture_rate"] = cumulative["low_reviews_captured"] / total_low_reviews

    predictions.to_csv(reports_dir / "model_low_review_test_predictions.csv", index=False)
    lift_table.to_csv(reports_dir / "model_low_review_lift_table.csv", index=False)
    cumulative.to_csv(reports_dir / "model_low_review_cumulative_gain.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(cumulative["orders_share"], cumulative["capture_rate"], color="#d62728", linewidth=2, label="Model")
    ax.plot([0, 1], [0, 1], color="#7f7f7f", linestyle="--", label="Random")
    ax.set_title("Cumulative Gain: Low Reviews Captured by Risk Ranking")
    ax.set_xlabel("Share of Orders Reviewed")
    ax.set_ylabel("Share of Low Reviews Captured")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "model_low_review_cumulative_gain.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 6))
    lift_plot = lift_table[lift_table["top_risk_share"] <= 0.5].copy()
    ax.bar(
        (lift_plot["top_risk_share"] * 100).astype(str) + "%",
        lift_plot["lift_vs_baseline"],
        color="#4c78a8",
    )
    ax.axhline(1, color="black", linestyle="--", linewidth=1)
    ax.set_title("Lift by Highest-Risk Order Segment")
    ax.set_xlabel("Top Risk Segment")
    ax.set_ylabel("Lift vs Baseline Low-Review Rate")
    plt.tight_layout()
    plt.savefig(figures_dir / "model_low_review_lift_by_segment.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    metrics = pd.DataFrame(
        [
            {
                "roc_auc": roc_auc_score(y_test, y_score),
                "pr_auc": average_precision_score(y_test, y_score),
                "best_threshold": best_threshold,
                "test_rows": len(test_df),
                "test_low_review_rate": baseline_rate,
            }
        ]
    )
    metrics.to_csv(reports_dir / "model_low_review_lift_metrics.csv", index=False)

    return lift_table, metrics


def write_summary(
    reports_dir: Path,
    seller_segment_summary: pd.DataFrame,
    distance_summary: pd.DataFrame,
    route_summary: pd.DataFrame,
    lift_table: pd.DataFrame,
    lift_metrics: pd.DataFrame,
) -> None:
    high_value_high_risk = seller_segment_summary[
        seller_segment_summary["seller_segment"].eq("high_value__high_risk")
    ]
    high_value_high_risk_sellers = (
        int(high_value_high_risk["sellers"].iloc[0]) if len(high_value_high_risk) else 0
    )
    high_value_high_risk_orders = (
        int(high_value_high_risk["orders"].iloc[0]) if len(high_value_high_risk) else 0
    )

    farthest_bucket = distance_summary.sort_values("avg_distance_km", ascending=False).iloc[0]
    cross_state = route_summary[route_summary["route_type"].eq("cross_state")].iloc[0]
    same_state = route_summary[route_summary["route_type"].eq("same_state")].iloc[0]
    top_10 = lift_table[lift_table["top_risk_share"].eq(0.10)].iloc[0]
    top_20 = lift_table[lift_table["top_risk_share"].eq(0.20)].iloc[0]
    metrics = lift_metrics.iloc[0]

    summary = f"""# Additional Analysis Summary

## 1. Seller Performance Scorecard

I built a seller scorecard to compare marketplace value with customer experience risk.

- High-value high-risk sellers: {high_value_high_risk_sellers:,}
- Orders associated with high-value high-risk sellers: {high_value_high_risk_orders:,}

This segment is useful for marketplace operations because it highlights sellers that contribute meaningful order volume while also creating higher customer dissatisfaction risk.

## 2. Logistics Distance and Cross-State Delivery

I estimated customer-seller distance using zip-code-level geolocation and compared same-state and cross-state routes.

- Same-state seller-orders: {int(same_state['seller_orders']):,}
- Cross-state seller-orders: {int(cross_state['seller_orders']):,}
- Same-state average delivery days: {same_state['avg_delivery_days']:.2f}
- Cross-state average delivery days: {cross_state['avg_delivery_days']:.2f}
- Same-state low-review rate: {same_state['low_review_rate']:.1%}
- Cross-state low-review rate: {cross_state['low_review_rate']:.1%}
- Longest distance bucket analyzed: {farthest_bucket['distance_bucket_km']} km, with average delivery days of {farthest_bucket['avg_delivery_days']:.2f}

This adds context to the delivery-delay finding: longer and cross-state routes are slower and carry higher review risk.

## 3. Model Lift and Business Simulation

I converted the low-review model into a prioritization view for a limited customer support team.

- Test ROC-AUC: {metrics['roc_auc']:.3f}
- Test PR-AUC: {metrics['pr_auc']:.3f}
- Top 10% highest-risk orders capture {top_10['capture_rate']:.1%} of low reviews
- Top 10% segment precision: {top_10['precision_in_segment']:.1%}
- Top 10% lift vs baseline: {top_10['lift_vs_baseline']:.2f}x
- Top 20% highest-risk orders capture {top_20['capture_rate']:.1%} of low reviews

This makes the model easier to discuss in business terms: it shows how much low-review risk can be covered if the team only reviews the riskiest orders.

## Project Positioning

These additions keep the project focused while adding practical business depth:

1. Marketplace growth and revenue analysis
2. Seller performance monitoring
3. Logistics network performance
4. Customer satisfaction risk modeling
5. Operational prioritization through lift analysis
"""
    (reports_dir / "additional_analysis_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    reports_dir = project_root / "reports"
    figures_dir = reports_dir / "figures"
    processed_dir = project_root / "data" / "processed"
    figures_dir.mkdir(parents=True, exist_ok=True)

    orders, items, geolocation = load_inputs(project_root)
    seller_order = build_seller_order_base(orders, items, geolocation)
    seller_order.to_csv(processed_dir / "seller_order_base.csv", index=False)

    seller_scorecard, seller_segment_summary = create_seller_scorecard(seller_order, reports_dir, figures_dir)
    distance_summary, route_summary, state_lane_summary = create_logistics_distance_analysis(
        seller_order, reports_dir, figures_dir
    )
    lift_table, lift_metrics = create_model_lift_analysis(orders, reports_dir, figures_dir)

    write_summary(reports_dir, seller_segment_summary, distance_summary, route_summary, lift_table, lift_metrics)

    print("Additional seller, logistics, and lift analysis completed.")
    print(f"Seller scorecard rows: {len(seller_scorecard):,}")
    print(f"Distance summary rows: {len(distance_summary):,}")
    print(f"Lift table rows: {len(lift_table):,}")
    print(f"Summary: {reports_dir / 'additional_analysis_summary.md'}")


if __name__ == "__main__":
    main()
