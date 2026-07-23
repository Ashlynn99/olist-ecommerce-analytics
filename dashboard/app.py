"""Streamlit dashboard for the Olist analytics portfolio project."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"

COLORS = {
    "blue": "#3973a8",
    "red": "#c84242",
    "yellow": "#d9a62e",
    "green": "#3e8b68",
    "gray": "#6b7280",
}

st.set_page_config(
    page_title="Olist Operations Analytics",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {border-top: 2px solid #3973a8; padding-top: 0.7rem;}
    [data-testid="stMetricLabel"] {font-size: 0.85rem;}
    h1, h2, h3 {letter-spacing: 0;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, **kwargs)


@st.cache_data
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@st.cache_data
def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(path: Path) -> Path:
    if not path.exists():
        st.error(f"Missing generated file: `{path.relative_to(PROJECT_ROOT)}`")
        st.code("make analysis")
        st.stop()
    return path


def pct(value: float) -> str:
    return f"{value:.1%}"


def brl(value: float) -> str:
    return f"{value:,.0f} BRL"


def compact_brl(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M BRL"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}k BRL"
    return brl(value)


def style_figure(fig: go.Figure, height: int = 390) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=15, r=15, t=55, b=15),
        legend_title_text="",
        font=dict(size=13),
        hoverlabel=dict(namelength=-1),
    )
    return fig


def ai_operations_briefing() -> None:
    context = read_json(require_file(REPORTS_DIR / "ai_operations_context.json"))
    briefing = read_text(require_file(REPORTS_DIR / "ai_operations_briefing.md"))

    snapshot = context["snapshot"]
    counts = snapshot["counts"]
    rates = snapshot["rates"]
    queue = context["seller_action_queue"]
    mode_label = "Offline" if context.get("agent_mode") == "offline_deterministic" else "OpenAI"
    posture_label = str(snapshot["posture"]).split()[0].title()

    st.title("AI Operations Briefing")
    st.caption("Offline operations inspection agent for seller risk and intervention readiness")
    cols = st.columns(5)
    cols[0].metric("Agent Mode", mode_label)
    cols[1].metric("Month", str(snapshot["monitoring_month"]))
    cols[2].metric("Critical", f"{int(counts['critical']):,}")
    cols[3].metric("Watch", f"{int(counts['watch']):,}")
    cols[4].metric("Late Rate", pct(rates["late_rate"]))

    cols = st.columns(4)
    cols[0].metric("Operating Posture", posture_label)
    cols[1].metric("Seller Queue", f"{int(queue['totals']['sellers']):,}")
    cols[2].metric(
        "Queue Value at Risk", compact_brl(queue["totals"]["commercial_value_at_risk_brl"])
    )
    cols[3].metric("Alert Eligible", f"{int(counts['alert_eligible_sellers']):,}")

    left, right = st.columns([1, 1.05])
    with left:
        drivers = pd.DataFrame(context["top_alert_drivers"]).head(6)
        fig = px.bar(
            drivers.sort_values("sellers"),
            x="sellers",
            y="driver",
            orientation="h",
            title="Dominant Seller Alert Drivers",
            color_discrete_sequence=[COLORS["red"]],
        )
        fig.update_xaxes(title="Sellers")
        fig.update_yaxes(title="")
        st.plotly_chart(style_figure(fig, 360), width="stretch")
    with right:
        tier_summary = pd.DataFrame(queue["by_tier"])
        fig = px.bar(
            tier_summary,
            x="action_tier",
            y="sellers",
            color="owner",
            title="Seller Action Queue by Tier",
        )
        fig.update_xaxes(title="")
        fig.update_yaxes(title="Sellers")
        st.plotly_chart(style_figure(fig, 360), width="stretch")

    root_segments = pd.DataFrame(context["root_cause"]["top_priority_segments"]).head(8)
    if not root_segments.empty:
        fig = px.bar(
            root_segments.sort_values("share_of_low_reviews"),
            x="share_of_low_reviews",
            y="segment",
            orientation="h",
            color="segment_family",
            title="Root-Cause Segments Feeding the Briefing",
        )
        fig.update_xaxes(title="Share of all low reviews", tickformat=".0%")
        fig.update_yaxes(title="")
        st.plotly_chart(style_figure(fig, 430), width="stretch")

    st.subheader("Priority Action Queue")
    action_queue = pd.DataFrame(queue["top_actions"])
    display_cols = [
        "queue_rank",
        "seller_id",
        "action_tier",
        "owner",
        "sla_business_days",
        "seller_state",
        "priority_score",
        "first_action",
        "success_metric",
    ]
    st.dataframe(
        action_queue[display_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "priority_score": st.column_config.ProgressColumn(
                "Priority", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    st.subheader("Generated Briefing")
    st.markdown(briefing)

    with st.expander("Structured agent context"):
        st.json(context)


def executive_overview() -> None:
    orders = read_csv(
        require_file(DATA_DIR / "orders_analysis_base.csv"),
        parse_dates=["order_purchase_timestamp"],
    )
    orders["is_delivered"] = orders["is_delivered"].astype("boolean")
    orders["is_late"] = orders["is_late"].astype("boolean")
    orders["is_low_review"] = orders["is_low_review"].astype("boolean")

    total_orders = orders["order_id"].nunique()
    delivered = int((orders["is_delivered"].fillna(False) & orders["delivery_days"].notna()).sum())
    gross_payment = orders["payment_total"].sum()
    late_rate = orders.loc[orders["is_delivered"].fillna(False), "is_late"].mean()
    low_review_rate = orders.loc[orders["is_low_review"].notna(), "is_low_review"].mean()

    st.title("Executive KPI Overview")
    st.caption("Marketplace growth, payment volume, and customer-experience performance")
    cols = st.columns(5)
    cols[0].metric("Orders", f"{total_orders:,}")
    cols[1].metric("Delivered", f"{delivered:,}", pct(delivered / total_orders))
    cols[2].metric("Gross Payment Volume (BRL)", f"{gross_payment / 1_000_000:.1f}M")
    cols[3].metric("Late Delivery Rate", pct(late_rate))
    cols[4].metric("Low-Review Rate", pct(low_review_rate))

    monthly = (
        orders.assign(month=orders["order_purchase_timestamp"].dt.to_period("M").astype(str))
        .groupby("month", as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            gross_payment_volume=("payment_total", "sum"),
            late_rate=("is_late", "mean"),
            low_review_rate=("is_low_review", "mean"),
        )
    )
    monthly = monthly[monthly["orders"].ge(1_000)].copy()
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            monthly,
            x="month",
            y="gross_payment_volume",
            title="Monthly Gross Payment Volume",
            color_discrete_sequence=[COLORS["blue"]],
        )
        fig.update_yaxes(title="BRL")
        fig.update_xaxes(title="")
        st.plotly_chart(style_figure(fig), width="stretch")
    with right:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=monthly["month"],
                y=monthly["late_rate"],
                name="Late delivery rate",
                line=dict(color=COLORS["yellow"], width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=monthly["month"],
                y=monthly["low_review_rate"],
                name="Low-review rate",
                line=dict(color=COLORS["red"], width=2),
            )
        )
        fig.update_layout(title="Monthly Customer-Experience Risk")
        fig.update_yaxes(tickformat=".0%", title="")
        fig.update_xaxes(title="")
        st.plotly_chart(style_figure(fig), width="stretch")

    category = (
        orders.dropna(subset=["main_product_category"])
        .groupby("main_product_category", as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            payment_total=("payment_total", "sum"),
            low_review_rate=("is_low_review", "mean"),
        )
        .query("orders >= 500")
        .nlargest(12, "payment_total")
    )
    fig = px.scatter(
        category,
        x="payment_total",
        y="low_review_rate",
        size="orders",
        text="main_product_category",
        title="High-Value Categories: Payment Volume vs Low-Review Risk",
        color="low_review_rate",
        color_continuous_scale="RdYlGn_r",
    )
    fig.update_traces(textposition="top center")
    fig.update_xaxes(title="Gross Payment Volume, BRL")
    fig.update_yaxes(title="Low-Review Rate", tickformat=".0%")
    st.plotly_chart(style_figure(fig, 460), width="stretch")


def experience_root_cause() -> None:
    dimensions = read_csv(require_file(REPORTS_DIR / "root_cause_dimension_summary.csv"))
    segments = read_csv(require_file(REPORTS_DIR / "root_cause_priority_segments.csv"))

    severe_delay = dimensions[
        dimensions["dimension"].eq("delivery_delay_bucket")
        & dimensions["segment"].eq("15_plus_days_late")
    ].iloc[0]
    cross_state = dimensions[
        dimensions["dimension"].eq("route_type") & dimensions["segment"].eq("cross_state")
    ].iloc[0]
    top_segment = segments.iloc[0]

    st.title("Experience Root Cause")
    st.caption("Contribution-based decomposition of low-review outcomes")
    cols = st.columns(5)
    cols[0].metric("15+ Late Risk", pct(severe_delay["low_review_rate"]))
    cols[1].metric("15+ Late Share", pct(severe_delay["share_of_low_reviews"]))
    cols[2].metric("Cross-State Share", pct(cross_state["share_of_low_reviews"]))
    cols[3].metric("Top Segment", str(top_segment["segment"]))
    cols[4].metric("Top Share", pct(top_segment["share_of_low_reviews"]))

    family_options = ["All", *sorted(segments["segment_family"].dropna().unique())]
    selected_family = st.segmented_control("Segment view", family_options, default="All")
    filtered = segments.copy()
    if selected_family != "All":
        filtered = filtered[filtered["segment_family"].eq(selected_family)]
    filtered = filtered.sort_values("priority_score", ascending=False)

    left, right = st.columns([1.1, 1])
    with left:
        top = filtered.head(12).sort_values("share_of_low_reviews")
        fig = px.bar(
            top,
            x="share_of_low_reviews",
            y="segment",
            orientation="h",
            color="segment_family",
            title="Top Root-Cause Segments by Low-Review Contribution",
        )
        fig.update_xaxes(title="Share of all low reviews", tickformat=".0%")
        fig.update_yaxes(title="")
        st.plotly_chart(style_figure(fig, 460), width="stretch")
    with right:
        fig = px.scatter(
            filtered.head(40),
            x="orders",
            y="low_review_rate",
            size="share_of_low_reviews",
            color="segment_family",
            hover_data=["segment", "excess_low_reviews", "priority_score"],
            title="Risk vs Scale Priority Matrix",
        )
        fig.update_xaxes(title="Orders", type="log")
        fig.update_yaxes(title="Low-review rate", tickformat=".0%")
        st.plotly_chart(style_figure(fig, 460), width="stretch")

    st.subheader("Root-Cause Backlog")
    display_cols = [
        "segment_family",
        "segment",
        "orders",
        "low_review_orders",
        "low_review_rate",
        "share_of_low_reviews",
        "excess_low_reviews",
        "priority_score",
    ]
    st.dataframe(
        filtered[display_cols].head(30),
        width="stretch",
        hide_index=True,
        column_config={
            "low_review_rate": st.column_config.ProgressColumn(
                "Low-Review Rate", min_value=0, max_value=1, format="%.1%%"
            ),
            "share_of_low_reviews": st.column_config.ProgressColumn(
                "Share of Low Reviews", min_value=0, max_value=1, format="%.1%%"
            ),
            "priority_score": st.column_config.ProgressColumn(
                "Priority", min_value=0, max_value=120, format="%.1f"
            ),
            "excess_low_reviews": st.column_config.NumberColumn(
                "Excess Low Reviews", format="%.0f"
            ),
        },
    )


def seller_risk_monitoring() -> None:
    summary = read_csv(require_file(REPORTS_DIR / "seller_monthly_risk_summary.csv"))
    watchlist = read_csv(require_file(REPORTS_DIR / "seller_monthly_latest_watchlist.csv"))
    latest = summary.iloc[-1]

    st.title("Seller Risk Monitoring")
    st.caption(
        "Monthly seller alerts combining experience risk, deterioration, and commercial exposure"
    )
    cols = st.columns(5)
    cols[0].metric("Monitoring Month", str(latest["order_month"]))
    cols[1].metric("Active Sellers", f"{int(latest['active_sellers']):,}")
    cols[2].metric("Alert Eligible", f"{int(latest['alert_eligible_sellers']):,}")
    cols[3].metric("Critical", f"{int(latest['critical']):,}")
    cols[4].metric("Watch", f"{int(latest['watch']):,}")

    left, right = st.columns([1.15, 1])
    with left:
        status_long = summary.melt(
            id_vars=["order_month"],
            value_vars=["stable", "watch", "critical"],
            var_name="status",
            value_name="sellers",
        )
        fig = px.bar(
            status_long,
            x="order_month",
            y="sellers",
            color="status",
            title="Monthly Alert-Eligible Seller Status",
            color_discrete_map={
                "stable": COLORS["blue"],
                "watch": COLORS["yellow"],
                "critical": COLORS["red"],
            },
        )
        fig.update_xaxes(title="")
        st.plotly_chart(style_figure(fig), width="stretch")
    with right:
        fig = px.scatter(
            watchlist,
            x="seller_gmv",
            y="experience_risk_score",
            size="seller_orders",
            color="risk_status",
            hover_data=["seller_id", "priority_score", "alert_reason"],
            title="Latest Watchlist: Value vs Experience Risk",
            color_discrete_map={"watch": COLORS["yellow"], "critical": COLORS["red"]},
        )
        fig.update_xaxes(title="Monthly Seller Order Value, BRL", type="log")
        fig.update_yaxes(title="Experience Risk Score")
        st.plotly_chart(style_figure(fig), width="stretch")

    status_filter = st.segmented_control(
        "Risk status",
        options=["All", "critical", "watch"],
        default="All",
    )
    states = sorted(watchlist["seller_state"].dropna().unique())
    state_filter = st.multiselect("Seller state", states, placeholder="All states")
    filtered = watchlist.copy()
    if status_filter != "All":
        filtered = filtered[filtered["risk_status"].eq(status_filter)]
    if state_filter:
        filtered = filtered[filtered["seller_state"].isin(state_filter)]

    display_cols = [
        "seller_id",
        "seller_state",
        "risk_status",
        "risk_transition",
        "seller_orders",
        "seller_gmv",
        "priority_score",
        "alert_reason",
        "recommended_action",
    ]
    st.subheader("Operational Watchlist")
    st.dataframe(
        filtered[display_cols].sort_values("priority_score", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            "seller_gmv": st.column_config.NumberColumn("Seller Value", format="%.0f BRL"),
            "priority_score": st.column_config.ProgressColumn(
                "Priority", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )


def seller_action_queue() -> None:
    queue = read_csv(require_file(REPORTS_DIR / "seller_operations_queue.csv"))
    summary = read_csv(require_file(REPORTS_DIR / "seller_operations_queue_summary.csv"))
    action_matrix = read_csv(require_file(REPORTS_DIR / "seller_alert_action_matrix.csv"))

    st.title("Seller Action Queue")
    st.caption("Owner-assigned seller operations queue with SLA and diagnostic focus")

    p0_sellers = int(queue["action_tier"].eq("P0 Critical Escalation").sum())
    total_value = queue["seller_gmv"].sum()
    value_at_risk = queue["commercial_value_at_risk_brl"].sum()
    cols = st.columns(5)
    cols[0].metric("Sellers in Queue", f"{queue['seller_id'].nunique():,}")
    cols[1].metric("P0 Escalations", f"{p0_sellers:,}")
    cols[2].metric("Seller Orders", f"{int(queue['seller_orders'].sum()):,}")
    cols[3].metric("Seller Value", compact_brl(total_value))
    cols[4].metric("Value at Risk", compact_brl(value_at_risk))

    left, right = st.columns([1, 1.1])
    with left:
        fig = px.bar(
            summary.sort_values("sla_business_days"),
            x="action_tier",
            y="sellers",
            color="owner",
            title="Action Queue by Tier",
        )
        fig.update_xaxes(title="")
        fig.update_yaxes(title="Sellers")
        st.plotly_chart(style_figure(fig), width="stretch")
    with right:
        fig = px.bar(
            summary.sort_values("commercial_value_at_risk_brl"),
            x="commercial_value_at_risk_brl",
            y="action_tier",
            orientation="h",
            color="owner",
            title="Estimated Value at Risk by Tier",
        )
        fig.update_xaxes(title="BRL")
        fig.update_yaxes(title="")
        st.plotly_chart(style_figure(fig), width="stretch")

    tiers = list(summary.sort_values("sla_business_days")["action_tier"])
    selected_tiers = st.multiselect("Action tier", tiers, default=tiers[:2])
    owners = sorted(queue["owner"].dropna().unique())
    selected_owners = st.multiselect("Owner", owners, placeholder="All owners")
    filtered = queue.copy()
    if selected_tiers:
        filtered = filtered[filtered["action_tier"].isin(selected_tiers)]
    if selected_owners:
        filtered = filtered[filtered["owner"].isin(selected_owners)]

    st.subheader("Operational Queue")
    display_cols = [
        "queue_rank",
        "seller_id",
        "seller_state",
        "risk_status",
        "risk_transition",
        "action_tier",
        "owner",
        "sla_business_days",
        "seller_orders",
        "seller_gmv",
        "commercial_value_at_risk_brl",
        "priority_score",
        "diagnostic_focus",
        "first_action",
    ]
    st.dataframe(
        filtered[display_cols].sort_values("queue_rank"),
        width="stretch",
        hide_index=True,
        column_config={
            "seller_gmv": st.column_config.NumberColumn("Seller Value", format="%.0f BRL"),
            "commercial_value_at_risk_brl": st.column_config.NumberColumn(
                "Value at Risk", format="%.0f BRL"
            ),
            "priority_score": st.column_config.ProgressColumn(
                "Priority", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    with st.expander("Action matrix"):
        st.dataframe(action_matrix, width="stretch", hide_index=True)


def purchase_time_triage() -> None:
    metrics = read_csv(require_file(REPORTS_DIR / "purchase_time_model_metrics.csv"))
    lift = read_csv(require_file(REPORTS_DIR / "purchase_time_model_lift_table.csv"))
    model = metrics[metrics["model"].eq("purchase_time_logistic_regression")].iloc[0]
    top_10 = lift[np.isclose(lift["top_risk_share"], 0.10)].iloc[0]

    st.title("Purchase-Time Risk Triage")
    st.caption(
        "Leakage-controlled risk ranking using only information available at or before purchase"
    )
    cols = st.columns(5)
    cols[0].metric("ROC-AUC", f"{model['roc_auc']:.3f}")
    cols[1].metric("PR-AUC", f"{model['pr_auc']:.3f}")
    cols[2].metric("Top 10% Capture", pct(top_10["capture_rate"]))
    cols[3].metric("Top 10% Precision", pct(top_10["precision_in_segment"]))
    cols[4].metric("Top 10% Lift", f"{top_10['lift_vs_baseline']:.2f}x")

    left, right = st.columns(2)
    with left:
        fig = px.line(
            lift,
            x=lift["top_risk_share"] * 100,
            y=lift["capture_rate"],
            markers=True,
            title="Low Reviews Captured by Risk Coverage",
            color_discrete_sequence=[COLORS["blue"]],
        )
        fig.add_shape(type="line", x0=0, y0=0, x1=100, y1=1, line=dict(dash="dash", color="gray"))
        fig.update_xaxes(title="Highest-Risk Orders Reviewed", ticksuffix="%")
        fig.update_yaxes(title="Low Reviews Captured", tickformat=".0%")
        st.plotly_chart(style_figure(fig), width="stretch")
    with right:
        fig = px.bar(
            lift[lift["top_risk_share"].le(0.5)],
            x=lift.loc[lift["top_risk_share"].le(0.5), "top_risk_share"] * 100,
            y="lift_vs_baseline",
            title="Lift by Highest-Risk Segment",
            color_discrete_sequence=[COLORS["green"]],
        )
        fig.add_hline(y=1, line_dash="dash", line_color="gray")
        fig.update_xaxes(title="Highest-Risk Segment", ticksuffix="%")
        fig.update_yaxes(title="Lift vs Baseline")
        st.plotly_chart(style_figure(fig), width="stretch")

    predictions_path = REPORTS_DIR / "purchase_time_model_test_predictions.csv"
    if predictions_path.exists():
        predictions = read_csv(predictions_path)
        coverage = st.slider("Operational review capacity", 1, 30, 5, format="%d%%")
        count = int(np.ceil(len(predictions) * coverage / 100))
        top = predictions.nlargest(count, "purchase_time_low_review_probability")
        st.subheader(f"Top {coverage}% Risk Queue")
        st.dataframe(
            top[
                [
                    "order_id",
                    "order_purchase_timestamp",
                    "customer_state",
                    "main_product_category",
                    "payment_total",
                    "purchase_time_low_review_probability",
                ]
            ],
            width="stretch",
            hide_index=True,
            column_config={
                "payment_total": st.column_config.NumberColumn("Payment", format="%.2f BRL"),
                "purchase_time_low_review_probability": st.column_config.ProgressColumn(
                    "Risk Probability", min_value=0, max_value=1, format="%.1%%"
                ),
            },
        )
    else:
        st.info("Run `make analysis` to generate the order-level purchase-time risk queue.")


def intervention_roi_simulator() -> None:
    coverage = read_csv(require_file(REPORTS_DIR / "intervention_value_by_coverage.csv"))
    recommendations = read_csv(
        require_file(REPORTS_DIR / "intervention_strategy_recommendations.csv")
    )
    strategy_labels = {
        "purchase_time": "Purchase-Time Prevention",
        "post_delivery": "Post-Delivery Recovery",
    }

    st.title("Intervention ROI Simulator")
    st.caption(
        "Scenario tool for selecting intervention capacity under explicit cost and impact assumptions"
    )
    strategy = st.segmented_control(
        "Strategy",
        options=list(strategy_labels),
        format_func=lambda value: strategy_labels[value],
        default="post_delivery",
    )
    default = recommendations[recommendations["strategy"].eq(strategy)].iloc[0]
    base = coverage[coverage["strategy"].eq(strategy)].copy()

    a, b, c = st.columns(3)
    cost = a.number_input(
        "Cost per contact, BRL", 0.5, 50.0, float(base["cost_per_contact_brl"].iloc[0]), 0.5
    )
    effect_percent = b.slider(
        "Intervention effectiveness",
        min_value=1,
        max_value=80,
        value=int(round(base["assumed_intervention_effectiveness"].iloc[0] * 100)),
        step=1,
        format="%d%%",
    )
    effect = effect_percent / 100
    value = c.number_input(
        "Value per successful recovery, BRL",
        10.0,
        500.0,
        float(base["value_per_successful_recovery_brl"].iloc[0]),
        5.0,
    )

    base["intervention_cost_brl"] = base["orders_contacted"] * cost
    base["expected_benefit_brl"] = base["observed_low_reviews_in_segment"] * effect * value
    base["expected_net_value_brl"] = base["expected_benefit_brl"] - base["intervention_cost_brl"]
    base["expected_roi"] = base["expected_net_value_brl"] / base["intervention_cost_brl"]
    base["break_even_effectiveness"] = base["intervention_cost_brl"] / (
        base["observed_low_reviews_in_segment"] * value
    )
    best = base.loc[base["expected_net_value_brl"].idxmax()]

    cols = st.columns(5)
    cols[0].metric("Recommended Coverage", pct(best["coverage_share"]))
    cols[1].metric("Orders Contacted", f"{int(best['orders_contacted']):,}")
    cols[2].metric("Expected Net Value", compact_brl(best["expected_net_value_brl"]))
    cols[3].metric("Expected ROI", pct(best["expected_roi"]))
    cols[4].metric("Break-Even Effect", pct(best["break_even_effectiveness"]))

    fig = px.line(
        base,
        x=base["coverage_share"] * 100,
        y="expected_net_value_brl",
        markers=True,
        title=f"Expected Net Value by Coverage: {strategy_labels[strategy]}",
        color_discrete_sequence=[COLORS["red"] if strategy == "post_delivery" else COLORS["blue"]],
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_xaxes(title="Highest-Risk Orders Contacted", ticksuffix="%")
    fig.update_yaxes(title="Expected Net Value, BRL")
    st.plotly_chart(style_figure(fig, 440), width="stretch")

    with st.expander("How to interpret this scenario"):
        st.markdown(f"""
            The stored base recommendation for this strategy is **{default['recommended_coverage_share']:.0%}**
            coverage. This simulator recalculates the decision using your assumptions.

            The values are retrospective scenarios, not realized causal savings. A randomized pilot is
            required before production rollout.
            """)


def experiment_design() -> None:
    summary = read_csv(require_file(REPORTS_DIR / "intervention_experiment_design_summary.csv"))
    candidates = read_csv(require_file(REPORTS_DIR / "intervention_experiment_candidate_frame.csv"))
    metric_plan = read_csv(require_file(REPORTS_DIR / "intervention_experiment_metric_plan.csv"))
    strategy_labels = {
        "purchase_time": "Purchase-Time Prevention",
        "post_delivery": "Post-Delivery Recovery",
    }

    st.title("Experiment Design")
    st.caption("A/B test plan for validating risk-based intervention value")
    strategy = st.segmented_control(
        "Strategy",
        options=list(strategy_labels),
        format_func=lambda value: strategy_labels[value],
        default="post_delivery",
    )
    selected = summary[summary["strategy"].eq(strategy)].iloc[0]
    strategy_candidates = candidates[candidates["strategy"].eq(strategy)].copy()

    cols = st.columns(5)
    cols[0].metric("Candidate Orders", f"{int(selected['candidate_orders']):,}")
    cols[1].metric("Baseline Risk", pct(selected["baseline_low_review_rate"]))
    cols[2].metric("Abs. MDE", pct(selected["minimum_detectable_effect_abs"]))
    cols[3].metric("Treatment", f"{int(selected['treatment_orders']):,}")
    cols[4].metric("Control", f"{int(selected['control_orders']):,}")

    left, right = st.columns(2)
    with left:
        balance = (
            strategy_candidates.groupby("assignment_group", as_index=False)
            .agg(orders=("order_id", "nunique"))
            .sort_values("assignment_group")
        )
        fig = px.bar(
            balance,
            x="assignment_group",
            y="orders",
            color="assignment_group",
            title="Treatment-Control Assignment Balance",
            color_discrete_map={"control": COLORS["gray"], "treatment": COLORS["green"]},
        )
        fig.update_xaxes(title="")
        fig.update_yaxes(title="Orders")
        st.plotly_chart(style_figure(fig), width="stretch")
    with right:
        sample_size = pd.DataFrame(
            {
                "Relative Reduction": ["10%", "15%", "20%"],
                "Required Orders per Group": [
                    selected["required_n_per_group_10pct_relative_reduction"],
                    selected["required_n_per_group_15pct_relative_reduction"],
                    selected["required_n_per_group_20pct_relative_reduction"],
                ],
            }
        )
        fig = px.bar(
            sample_size,
            x="Relative Reduction",
            y="Required Orders per Group",
            title="Sample Size Planning",
            color_discrete_sequence=[COLORS["blue"]],
        )
        fig.add_hline(
            y=min(selected["treatment_orders"], selected["control_orders"]),
            line_dash="dash",
            line_color=COLORS["red"],
            annotation_text="available per group",
        )
        st.plotly_chart(style_figure(fig), width="stretch")

    st.subheader("Metric Governance")
    st.dataframe(metric_plan, width="stretch", hide_index=True)

    st.subheader("Experiment Candidate Sample")
    queue_columns = [
        "order_id",
        "assignment_group",
        "risk_probability",
        "customer_state",
        "main_product_category",
        "payment_total",
        "target_low_review",
    ]
    available_columns = [column for column in queue_columns if column in strategy_candidates]
    st.dataframe(
        strategy_candidates[available_columns].head(50),
        width="stretch",
        hide_index=True,
        column_config={
            "risk_probability": st.column_config.ProgressColumn(
                "Risk Probability", min_value=0, max_value=1, format="%.1%%"
            ),
            "payment_total": st.column_config.NumberColumn("Payment", format="%.2f BRL"),
        },
    )


PAGES = {
    "Executive KPI Overview": executive_overview,
    "AI Operations Briefing": ai_operations_briefing,
    "Experience Root Cause": experience_root_cause,
    "Seller Risk Monitoring": seller_risk_monitoring,
    "Seller Action Queue": seller_action_queue,
    "Purchase-Time Risk Triage": purchase_time_triage,
    "Intervention ROI Simulator": intervention_roi_simulator,
    "Experiment Design": experiment_design,
}

with st.sidebar:
    st.title("Olist Analytics")
    st.caption("Marketplace operations portfolio")
    selected_page = st.radio("View", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.caption("Brazilian e-commerce dataset · 2016–2018")
    st.link_button(
        "View Full Project Report",
        "https://github.com/Ashlynn99/olist-ecommerce-analytics/blob/main/reports/final_report.md",
        width="stretch",
    )

PAGES[selected_page]()
