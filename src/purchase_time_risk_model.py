"""Build a leakage-controlled purchase-time low-review risk model."""

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

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TEST_START_DATE = pd.Timestamp("2018-01-01")


def coerce_bool(series: pd.Series) -> pd.Series:
    return series.replace({"True": True, "False": False, "true": True, "false": False}).astype(
        "boolean"
    )


def load_inputs(project_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    processed_dir = project_root / "data" / "processed"
    raw_dir = project_root / "data" / "raw"

    orders = pd.read_csv(processed_dir / "orders_analysis_base.csv")
    seller_orders = pd.read_csv(processed_dir / "seller_order_base.csv")
    reviews = pd.read_csv(
        raw_dir / "olist_order_reviews_dataset.csv",
        usecols=["order_id", "review_answer_timestamp"],
    )

    datetime_cols = [
        "order_purchase_timestamp",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]
    for col in datetime_cols:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    seller_orders["order_purchase_timestamp"] = pd.to_datetime(
        seller_orders["order_purchase_timestamp"], errors="coerce"
    )
    reviews["review_answer_timestamp"] = pd.to_datetime(
        reviews["review_answer_timestamp"], errors="coerce"
    )

    for frame in [orders, seller_orders]:
        for col in ["is_delivered", "is_late", "is_low_review"]:
            if col in frame.columns:
                frame[col] = coerce_bool(frame[col])

    return orders, seller_orders, reviews


def cumulative_event_table(
    events: pd.DataFrame,
    timestamp_col: str,
    value_aggregations: dict[str, tuple[str, str]],
) -> pd.DataFrame:
    grouped = events.groupby(["seller_id", timestamp_col], as_index=False).agg(**value_aggregations)
    grouped = grouped.sort_values(["seller_id", timestamp_col])

    value_cols = list(value_aggregations)
    grouped[value_cols] = grouped.groupby("seller_id")[value_cols].cumsum()
    return grouped


def merge_prior_events(
    base: pd.DataFrame,
    events: pd.DataFrame,
    event_timestamp_col: str,
) -> pd.DataFrame:
    left = base.sort_values(["order_purchase_timestamp", "seller_id"]).copy()
    right = events.sort_values([event_timestamp_col, "seller_id"]).copy()
    return pd.merge_asof(
        left,
        right,
        left_on="order_purchase_timestamp",
        right_on=event_timestamp_col,
        by="seller_id",
        direction="backward",
        allow_exact_matches=False,
    )


def build_seller_history_features(
    orders: pd.DataFrame,
    seller_orders: pd.DataFrame,
    reviews: pd.DataFrame,
) -> pd.DataFrame:
    order_outcomes = orders[
        [
            "order_id",
            "order_delivered_customer_date",
            "delivery_days",
            "is_late",
            "is_low_review",
        ]
    ].copy()
    review_events = reviews.groupby("order_id", as_index=False).agg(
        review_event_timestamp=("review_answer_timestamp", "max")
    )

    base = seller_orders.merge(order_outcomes, on="order_id", how="left", suffixes=("", "_order"))
    base = base.merge(review_events, on="order_id", how="left")
    base["is_late_value"] = base["is_late_order"].astype("Int64")
    base["is_low_review_value"] = base["is_low_review_order"].astype("Int64")

    seller_order_base = base[
        [
            "seller_id",
            "order_id",
            "order_purchase_timestamp",
            "seller_item_total",
            "avg_product_weight_g",
            "avg_product_volume_cm3",
            "customer_seller_distance_km",
            "is_cross_state",
        ]
    ].copy()
    seller_order_base["is_cross_state"] = coerce_bool(seller_order_base["is_cross_state"])

    purchase_events = cumulative_event_table(
        seller_order_base.dropna(subset=["order_purchase_timestamp"]),
        "order_purchase_timestamp",
        {
            "seller_prior_orders": ("order_id", "count"),
            "seller_prior_order_value": ("seller_item_total", "sum"),
        },
    )
    purchase_history = merge_prior_events(
        seller_order_base,
        purchase_events,
        "order_purchase_timestamp",
    )

    delivery_event_base = base.dropna(
        subset=["order_delivered_customer_date", "is_late_value"]
    ).copy()
    delivery_events = cumulative_event_table(
        delivery_event_base,
        "order_delivered_customer_date",
        {
            "seller_prior_deliveries": ("order_id", "count"),
            "seller_prior_late_orders": ("is_late_value", "sum"),
            "seller_prior_delivery_days_total": ("delivery_days", "sum"),
        },
    )
    delivery_history = merge_prior_events(
        seller_order_base,
        delivery_events,
        "order_delivered_customer_date",
    )

    review_event_base = base.dropna(subset=["review_event_timestamp", "is_low_review_value"]).copy()
    review_events_cumulative = cumulative_event_table(
        review_event_base,
        "review_event_timestamp",
        {
            "seller_prior_reviews": ("order_id", "count"),
            "seller_prior_low_reviews": ("is_low_review_value", "sum"),
        },
    )
    review_history = merge_prior_events(
        seller_order_base,
        review_events_cumulative,
        "review_event_timestamp",
    )

    seller_history = purchase_history[
        [
            "seller_id",
            "order_id",
            "seller_prior_orders",
            "seller_prior_order_value",
            "avg_product_weight_g",
            "avg_product_volume_cm3",
            "customer_seller_distance_km",
            "is_cross_state",
        ]
    ].copy()
    seller_history = seller_history.merge(
        delivery_history[
            [
                "seller_id",
                "order_id",
                "seller_prior_deliveries",
                "seller_prior_late_orders",
                "seller_prior_delivery_days_total",
            ]
        ],
        on=["seller_id", "order_id"],
        how="left",
    )
    seller_history = seller_history.merge(
        review_history[
            [
                "seller_id",
                "order_id",
                "seller_prior_reviews",
                "seller_prior_low_reviews",
            ]
        ],
        on=["seller_id", "order_id"],
        how="left",
    )

    count_cols = [
        "seller_prior_orders",
        "seller_prior_order_value",
        "seller_prior_deliveries",
        "seller_prior_late_orders",
        "seller_prior_delivery_days_total",
        "seller_prior_reviews",
        "seller_prior_low_reviews",
    ]
    seller_history[count_cols] = seller_history[count_cols].fillna(0)
    seller_history["seller_prior_late_rate"] = seller_history[
        "seller_prior_late_orders"
    ] / seller_history["seller_prior_deliveries"].replace(0, np.nan)
    seller_history["seller_prior_avg_delivery_days"] = seller_history[
        "seller_prior_delivery_days_total"
    ] / seller_history["seller_prior_deliveries"].replace(0, np.nan)
    seller_history["seller_prior_low_review_rate"] = seller_history[
        "seller_prior_low_reviews"
    ] / seller_history["seller_prior_reviews"].replace(0, np.nan)

    seller_history["is_cross_state_num"] = seller_history["is_cross_state"].astype("Int64")
    order_seller_features = seller_history.groupby("order_id", as_index=False).agg(
        seller_history_rows=("seller_id", "count"),
        seller_prior_orders_mean=("seller_prior_orders", "mean"),
        seller_prior_orders_min=("seller_prior_orders", "min"),
        seller_prior_orders_max=("seller_prior_orders", "max"),
        seller_prior_order_value_mean=("seller_prior_order_value", "mean"),
        seller_prior_deliveries_mean=("seller_prior_deliveries", "mean"),
        seller_prior_late_rate_mean=("seller_prior_late_rate", "mean"),
        seller_prior_late_rate_max=("seller_prior_late_rate", "max"),
        seller_prior_avg_delivery_days_mean=("seller_prior_avg_delivery_days", "mean"),
        seller_prior_reviews_mean=("seller_prior_reviews", "mean"),
        seller_prior_low_review_rate_mean=("seller_prior_low_review_rate", "mean"),
        seller_prior_low_review_rate_max=("seller_prior_low_review_rate", "max"),
        avg_product_weight_g=("avg_product_weight_g", "mean"),
        avg_product_volume_cm3=("avg_product_volume_cm3", "mean"),
        avg_customer_seller_distance_km=("customer_seller_distance_km", "mean"),
        any_cross_state=("is_cross_state_num", "max"),
    )
    order_seller_features["new_seller_order"] = (
        order_seller_features["seller_prior_orders_max"].fillna(0).eq(0).astype(int)
    )
    return order_seller_features


def build_model_data(orders: pd.DataFrame, seller_features: pd.DataFrame) -> pd.DataFrame:
    model_data = orders.merge(seller_features, on="order_id", how="left")
    model_data = model_data[
        model_data["is_delivered"].fillna(False)
        & model_data["is_low_review"].notna()
        & model_data["order_purchase_timestamp"].notna()
    ].copy()
    model_data["target_low_review"] = model_data["is_low_review"].astype(int)
    model_data["any_cross_state"] = model_data["any_cross_state"].fillna(0).astype(int)
    model_data["new_seller_order"] = model_data["new_seller_order"].fillna(1).astype(int)
    return model_data


def model_feature_lists() -> tuple[list[str], list[str]]:
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
        "estimated_delivery_days",
        "seller_prior_orders_mean",
        "seller_prior_orders_min",
        "seller_prior_orders_max",
        "seller_prior_order_value_mean",
        "seller_prior_deliveries_mean",
        "seller_prior_late_rate_mean",
        "seller_prior_late_rate_max",
        "seller_prior_avg_delivery_days_mean",
        "seller_prior_reviews_mean",
        "seller_prior_low_review_rate_mean",
        "seller_prior_low_review_rate_max",
        "avg_product_weight_g",
        "avg_product_volume_cm3",
        "avg_customer_seller_distance_km",
        "any_cross_state",
        "new_seller_order",
    ]
    categorical_features = [
        "purchase_month",
        "purchase_dayofweek",
        "customer_state",
        "main_product_category",
        "main_seller_state",
        "primary_payment_type",
    ]
    return numeric_features, categorical_features


def evaluate_scores(
    y_true: pd.Series, scores: np.ndarray, threshold: float = 0.5
) -> dict[str, float]:
    predictions = scores >= threshold
    return {
        "threshold": threshold,
        "roc_auc": roc_auc_score(y_true, scores),
        "pr_auc": average_precision_score(y_true, scores),
        "precision": precision_score(y_true, predictions, zero_division=0),
        "recall": recall_score(y_true, predictions, zero_division=0),
        "f1": f1_score(y_true, predictions, zero_division=0),
    }


def build_lift_table(y_true: pd.Series, scores: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked = pd.DataFrame({"target_low_review": y_true.to_numpy(), "score": scores})
    ranked = ranked.sort_values("score", ascending=False).reset_index(drop=True)
    total_low_reviews = ranked["target_low_review"].sum()
    baseline_rate = ranked["target_low_review"].mean()

    rows = []
    for share in [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00]:
        n = max(1, int(np.ceil(len(ranked) * share)))
        segment = ranked.iloc[:n]
        captured = segment["target_low_review"].sum()
        rows.append(
            {
                "top_risk_share": share,
                "orders_reviewed": n,
                "low_reviews_captured": int(captured),
                "capture_rate": captured / total_low_reviews,
                "precision_in_segment": segment["target_low_review"].mean(),
                "lift_vs_baseline": segment["target_low_review"].mean() / baseline_rate,
            }
        )

    cumulative = ranked.copy()
    cumulative["orders_share"] = (np.arange(len(cumulative)) + 1) / len(cumulative)
    cumulative["capture_rate"] = cumulative["target_low_review"].cumsum() / total_low_reviews
    return pd.DataFrame(rows), cumulative


def train_purchase_time_model(
    model_data: pd.DataFrame,
    reports_dir: Path,
    figures_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    numeric_features, categorical_features = model_feature_lists()
    feature_cols = numeric_features + categorical_features

    train_df = model_data[model_data["order_purchase_timestamp"] < TEST_START_DATE].copy()
    test_df = model_data[model_data["order_purchase_timestamp"] >= TEST_START_DATE].copy()

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
    model = Pipeline(
        steps=[
            (
                "preprocessor",
                ColumnTransformer(
                    transformers=[
                        ("num", numeric_transformer, numeric_features),
                        ("cat", categorical_transformer, categorical_features),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42),
            ),
        ]
    )
    model.fit(X_train, y_train)

    baseline_scores = np.repeat(y_train.mean(), len(y_test))
    model_scores = model.predict_proba(X_test)[:, 1]
    metrics = pd.DataFrame(
        [
            {
                "model": "prior_baseline",
                **evaluate_scores(y_test, baseline_scores),
                "train_rows": len(train_df),
                "test_rows": len(test_df),
                "test_low_review_rate": y_test.mean(),
            },
            {
                "model": "purchase_time_logistic_regression",
                **evaluate_scores(y_test, model_scores),
                "train_rows": len(train_df),
                "test_rows": len(test_df),
                "test_low_review_rate": y_test.mean(),
            },
        ]
    )

    lift_table, cumulative = build_lift_table(y_test, model_scores)
    test_predictions = test_df[
        [
            "order_id",
            "order_purchase_timestamp",
            "customer_state",
            "main_product_category",
            "payment_total",
            "target_low_review",
        ]
    ].copy()
    test_predictions["purchase_time_low_review_probability"] = model_scores

    feature_names = model.named_steps["preprocessor"].get_feature_names_out()
    coefficients = model.named_steps["classifier"].coef_[0]
    feature_importance = pd.DataFrame(
        {
            "feature": feature_names,
            "coefficient": coefficients,
            "absolute_coefficient": np.abs(coefficients),
        }
    ).sort_values("absolute_coefficient", ascending=False)

    metrics.to_csv(reports_dir / "purchase_time_model_metrics.csv", index=False)
    lift_table.to_csv(reports_dir / "purchase_time_model_lift_table.csv", index=False)
    feature_importance.to_csv(
        reports_dir / "purchase_time_model_feature_importance.csv", index=False
    )
    test_predictions.to_csv(reports_dir / "purchase_time_model_test_predictions.csv", index=False)

    fpr, tpr, _ = roc_curve(y_test, model_scores)
    precision, recall, _ = precision_recall_curve(y_test, model_scores)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(fpr, tpr, color="#4c78a8", linewidth=2)
    axes[0].plot([0, 1], [0, 1], linestyle="--", color="#7f7f7f")
    axes[0].set_title("Purchase-Time Model ROC Curve")
    axes[0].set_xlabel("False Positive Rate")
    axes[0].set_ylabel("True Positive Rate")
    axes[1].plot(recall, precision, color="#e45756", linewidth=2)
    axes[1].axhline(y_test.mean(), linestyle="--", color="#7f7f7f")
    axes[1].set_title("Purchase-Time Model Precision-Recall Curve")
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    plt.tight_layout()
    plt.savefig(figures_dir / "purchase_time_model_roc_pr.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(cumulative["orders_share"], cumulative["capture_rate"], color="#d62728", linewidth=2)
    ax.plot([0, 1], [0, 1], linestyle="--", color="#7f7f7f")
    ax.set_title("Purchase-Time Model Cumulative Gain")
    ax.set_xlabel("Share of Orders Reviewed")
    ax.set_ylabel("Share of Low Reviews Captured")
    plt.tight_layout()
    plt.savefig(
        figures_dir / "purchase_time_model_cumulative_gain.png", dpi=160, bbox_inches="tight"
    )
    plt.close(fig)

    top_features = (
        feature_importance.loc[
            ~feature_importance["feature"].str.contains("infrequent_sklearn", regex=False)
        ]
        .head(20)
        .sort_values("coefficient")
    )
    colors = np.where(top_features["coefficient"] >= 0, "#e45756", "#4c78a8")
    fig, ax = plt.subplots(figsize=(11, 8))
    ax.barh(top_features["feature"], top_features["coefficient"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Purchase-Time Model: Largest Logistic Coefficients")
    ax.set_xlabel("Standardized Logistic Coefficient")
    plt.tight_layout()
    plt.savefig(
        figures_dir / "purchase_time_model_feature_coefficients.png", dpi=160, bbox_inches="tight"
    )
    plt.close(fig)

    return metrics, lift_table, feature_importance


def write_summary(
    reports_dir: Path,
    metrics: pd.DataFrame,
    lift_table: pd.DataFrame,
    feature_importance: pd.DataFrame,
) -> None:
    model_metrics = metrics.loc[metrics["model"].eq("purchase_time_logistic_regression")].iloc[0]
    top_10 = lift_table.loc[lift_table["top_risk_share"].eq(0.10)].iloc[0]
    readable_features = feature_importance.loc[
        ~feature_importance["feature"].str.contains("infrequent_sklearn", regex=False),
        "feature",
    ].head(5)
    top_features = ", ".join(
        readable_features.str.replace("num__", "", regex=False)
        .str.replace("cat__", "", regex=False)
        .str.replace("_", " ", regex=False)
    )

    summary = f"""# Purchase-Time Low-Review Risk Model

## Objective

I built this model to rank low-review risk using only information available at or before purchase
time.

The feature set excludes actual delivery outcomes and current-order review information.
Seller-history features are calculated as-of each order timestamp and only use seller delivery or
review events that occurred before the current purchase.

## Time Split

- Train: orders before {TEST_START_DATE.date()}
- Test: orders on or after {TEST_START_DATE.date()}
- Train rows: {int(model_metrics['train_rows']):,}
- Test rows: {int(model_metrics['test_rows']):,}
- Test low-review rate: {model_metrics['test_low_review_rate']:.1%}

## Performance

| Metric | Value |
|---|---:|
| ROC-AUC | {model_metrics['roc_auc']:.3f} |
| PR-AUC | {model_metrics['pr_auc']:.3f} |
| Precision at 0.50 threshold | {model_metrics['precision']:.3f} |
| Recall at 0.50 threshold | {model_metrics['recall']:.3f} |
| F1 at 0.50 threshold | {model_metrics['f1']:.3f} |
| Top 10% low reviews captured | {top_10['capture_rate']:.1%} |
| Top 10% precision | {top_10['precision_in_segment']:.1%} |
| Top 10% lift vs baseline | {top_10['lift_vs_baseline']:.2f}x |

## Interpretation

This model is designed for early risk triage after an order is placed. It is expected to perform
below the post-delivery model because it deliberately excludes the strongest delivery-outcome
variables.

The largest absolute coefficients include: {top_features}.

Seller-history features are leakage-controlled, but the analysis remains observational. The model
should support prioritization and monitoring rather than automated customer or seller decisions.
"""
    (reports_dir / "purchase_time_model_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    processed_dir = PROJECT_ROOT / "data" / "processed"
    figures_dir.mkdir(parents=True, exist_ok=True)

    orders, seller_orders, reviews = load_inputs(PROJECT_ROOT)
    seller_features = build_seller_history_features(orders, seller_orders, reviews)
    seller_features.to_csv(processed_dir / "purchase_time_seller_history_features.csv", index=False)

    model_data = build_model_data(orders, seller_features)
    metrics, lift_table, feature_importance = train_purchase_time_model(
        model_data,
        reports_dir,
        figures_dir,
    )
    write_summary(reports_dir, metrics, lift_table, feature_importance)

    print("Purchase-time risk model completed.")
    print(metrics.to_string(index=False))
    print(f"Summary: {reports_dir / 'purchase_time_model_summary.md'}")


if __name__ == "__main__":
    main()
