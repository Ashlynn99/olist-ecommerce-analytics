"""Deterministic data tools for the Olist operations inspection agent.

This module is the no-API layer of the agent. It reads generated report tables,
turns them into compact Python dictionaries, and renders a complete operations
briefing without requiring an LLM call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"


def read_report(name: str, reports_dir: Path = REPORTS_DIR) -> pd.DataFrame:
    """Read a required CSV report from the generated reports directory."""
    path = reports_dir / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing report file: {path.relative_to(PROJECT_ROOT)}. " "Run `make analysis` first."
        )
    return pd.read_csv(path)


def read_optional_report(name: str, reports_dir: Path = REPORTS_DIR) -> pd.DataFrame:
    """Read an optional report, returning an empty frame when it is absent."""
    path = reports_dir / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def clean_value(value: Any) -> Any:
    """Convert pandas and numpy scalar values into JSON-friendly Python values."""
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and np.isnan(value):
        return None
    if pd.isna(value):
        return None
    return value


def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: clean_value(value) for key, value in record.items()}


def format_percent(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.1%}"


def format_rate_change(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if float(value) >= 0 else ""
    return f"{sign}{float(value) * 100:.1f} pp"


def format_brl(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.0f} BRL"


def format_signed_number(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+,.0f}"


def latest_monitoring_snapshot(summary: pd.DataFrame) -> dict[str, Any]:
    """Summarize the latest seller monthly monitoring row."""
    summary = summary.sort_values("order_month").reset_index(drop=True)
    latest = summary.iloc[-1]
    previous = summary.iloc[-2] if len(summary) > 1 else None

    count_columns = [
        "active_sellers",
        "alert_eligible_sellers",
        "seller_orders",
        "delivered_orders",
        "reviewed_orders",
        "low_review_orders",
        "late_orders",
        "canceled_orders",
        "watch",
        "critical",
    ]
    rate_columns = ["late_rate", "low_review_rate", "cancellation_rate"]

    snapshot: dict[str, Any] = {
        "monitoring_month": str(latest["order_month"]),
        "counts": {
            column: int(latest[column])
            for column in count_columns
            if column in summary.columns and pd.notna(latest[column])
        },
        "rates": {
            column: float(latest[column])
            for column in rate_columns
            if column in summary.columns and pd.notna(latest[column])
        },
        "month_over_month": {},
        "posture": "normal",
    }

    if previous is not None:
        for column in count_columns + rate_columns:
            if column in summary.columns:
                snapshot["month_over_month"][column] = clean_value(
                    latest[column] - previous[column]
                )

    late_change = snapshot["month_over_month"].get("late_rate") or 0
    critical_change = snapshot["month_over_month"].get("critical") or 0
    watch_change = snapshot["month_over_month"].get("watch") or 0
    if late_change >= 0.03 and critical_change > 0:
        snapshot["posture"] = "elevated logistics pressure"
    elif critical_change > 0 or watch_change > 0:
        snapshot["posture"] = "rising seller watchlist pressure"
    elif late_change < -0.03 and critical_change <= 0:
        snapshot["posture"] = "improving operating pressure"

    return snapshot


def monthly_trend(summary: pd.DataFrame, periods: int = 6) -> list[dict[str, Any]]:
    """Return a compact recent trend table for the briefing."""
    columns = [
        "order_month",
        "seller_orders",
        "seller_gmv",
        "late_rate",
        "low_review_rate",
        "cancellation_rate",
        "watch",
        "critical",
    ]
    available_columns = [column for column in columns if column in summary.columns]
    trend = summary.sort_values("order_month").tail(periods)[available_columns]
    return [clean_record(record) for record in trend.to_dict(orient="records")]


def alert_driver_summary(watchlist: pd.DataFrame) -> list[dict[str, Any]]:
    """Count repeated alert reasons across the latest seller watchlist."""
    if watchlist.empty or "alert_reason" not in watchlist.columns:
        return []

    driver_counts: dict[str, int] = {}
    for reason_text in watchlist["alert_reason"].dropna():
        for reason in str(reason_text).split(";"):
            normalized = reason.strip()
            if normalized:
                driver_counts[normalized] = driver_counts.get(normalized, 0) + 1

    return [
        {"driver": driver, "sellers": sellers}
        for driver, sellers in sorted(driver_counts.items(), key=lambda item: item[1], reverse=True)
    ]


def top_seller_alerts(watchlist: pd.DataFrame, limit: int = 10) -> list[dict[str, Any]]:
    """Return the highest-priority latest seller alerts."""
    if watchlist.empty:
        return []

    columns = [
        "seller_id",
        "seller_state",
        "seller_city",
        "risk_status",
        "previous_risk_status",
        "risk_transition",
        "seller_orders",
        "seller_gmv",
        "low_review_rate",
        "late_rate",
        "cancellation_rate",
        "experience_risk_score",
        "deterioration_score",
        "priority_score",
        "alert_reason",
        "recommended_action",
    ]
    available_columns = [column for column in columns if column in watchlist.columns]
    top = watchlist.sort_values("priority_score", ascending=False).head(limit)
    return [clean_record(record) for record in top[available_columns].to_dict(orient="records")]


def transition_summary(transitions: pd.DataFrame) -> dict[str, Any]:
    """Summarize seller risk-status movement in the latest monitoring period."""
    if transitions.empty:
        return {"total_transitioned_sellers": 0, "by_transition": {}}

    if "risk_transition" in transitions.columns:
        counts = transitions["risk_transition"].value_counts().to_dict()
        return {
            "total_transitioned_sellers": int(len(transitions)),
            "by_transition": {key: int(value) for key, value in counts.items()},
        }

    if {"previous_risk_status", "risk_status", "sellers"}.issubset(transitions.columns):
        records = [clean_record(record) for record in transitions.to_dict(orient="records")]
        return {
            "total_transitioned_sellers": int(transitions["sellers"].sum()),
            "status_matrix": records,
        }

    return {"total_transitioned_sellers": int(len(transitions)), "by_transition": {}}


def root_cause_summary(
    dimension_summary: pd.DataFrame, priority_segments: pd.DataFrame, limit: int = 8
) -> dict[str, Any]:
    """Summarize low-review root-cause contributors."""
    result: dict[str, Any] = {
        "top_priority_segments": [],
        "dimension_highlights": [],
    }

    if not priority_segments.empty:
        columns = [
            "segment_family",
            "segment",
            "orders",
            "low_review_orders",
            "low_review_rate",
            "late_rate",
            "share_of_low_reviews",
            "excess_low_reviews",
            "priority_score",
        ]
        available_columns = [column for column in columns if column in priority_segments.columns]
        top_segments = priority_segments.sort_values("priority_score", ascending=False).head(limit)
        result["top_priority_segments"] = [
            clean_record(record)
            for record in top_segments[available_columns].to_dict(orient="records")
        ]

    if not dimension_summary.empty and "dimension" in dimension_summary.columns:
        for dimension, group in dimension_summary.groupby("dimension"):
            candidates = group.copy()
            if "unknown" in candidates["segment"].astype(str).values and len(candidates) > 1:
                candidates = candidates[~candidates["segment"].astype(str).eq("unknown")]
            sort_column = (
                "share_of_low_reviews"
                if "share_of_low_reviews" in candidates.columns
                else "low_review_orders"
            )
            highlight = candidates.sort_values(sort_column, ascending=False).head(1)
            if not highlight.empty:
                record = clean_record(highlight.iloc[0].to_dict())
                result["dimension_highlights"].append(record)

    return result


def seller_action_queue_summary(
    queue: pd.DataFrame, queue_summary: pd.DataFrame, limit: int = 10
) -> dict[str, Any]:
    """Summarize owner, SLA, and action-tier backlog for seller operations."""
    result: dict[str, Any] = {
        "totals": {
            "sellers": 0,
            "seller_orders": 0,
            "seller_gmv": 0.0,
            "commercial_value_at_risk_brl": 0.0,
        },
        "by_tier": [],
        "top_actions": [],
    }

    if not queue.empty:
        result["totals"] = {
            "sellers": int(queue["seller_id"].nunique()),
            "seller_orders": int(queue["seller_orders"].sum()),
            "seller_gmv": float(queue["seller_gmv"].sum()),
            "commercial_value_at_risk_brl": float(queue["commercial_value_at_risk_brl"].sum()),
        }
        action_columns = [
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
            "success_metric",
        ]
        available_columns = [column for column in action_columns if column in queue.columns]
        top = queue.sort_values("queue_rank").head(limit)
        result["top_actions"] = [
            clean_record(record) for record in top[available_columns].to_dict(orient="records")
        ]

    if not queue_summary.empty:
        result["by_tier"] = [
            clean_record(record) for record in queue_summary.to_dict(orient="records")
        ]

    return result


def purchase_time_model_summary(metrics: pd.DataFrame, lift: pd.DataFrame) -> dict[str, Any]:
    """Summarize purchase-time model quality and top-risk segment performance."""
    if metrics.empty:
        return {}

    model = metrics.iloc[0]
    if (
        "model" in metrics.columns
        and metrics["model"].eq("purchase_time_logistic_regression").any()
    ):
        model = metrics[metrics["model"].eq("purchase_time_logistic_regression")].iloc[0]

    top_10 = None
    if not lift.empty and "top_risk_share" in lift.columns:
        top_10_index = (lift["top_risk_share"] - 0.10).abs().idxmin()
        top_10 = clean_record(lift.loc[top_10_index].to_dict())

    return {
        "model": clean_record(model.to_dict()),
        "top_10_percent_segment": top_10,
    }


def intervention_roi_summary(recommendations: pd.DataFrame) -> list[dict[str, Any]]:
    """Summarize recommended intervention coverage by strategy."""
    if recommendations.empty:
        return []

    columns = [
        "strategy",
        "display_name",
        "recommended_coverage_share",
        "orders_contacted",
        "observed_low_reviews_in_segment",
        "low_reviews_captured_share",
        "base_expected_net_value_brl",
        "base_expected_roi",
        "incremental_net_value_vs_random_brl",
        "break_even_effectiveness",
        "operating_description",
    ]
    available_columns = [column for column in columns if column in recommendations.columns]
    return [
        clean_record(record)
        for record in recommendations[available_columns].to_dict(orient="records")
    ]


def experiment_design_summary(summary: pd.DataFrame, metric_plan: pd.DataFrame) -> dict[str, Any]:
    """Summarize the intervention validation plan."""
    result: dict[str, Any] = {"strategies": [], "metrics": []}
    if not summary.empty:
        result["strategies"] = [
            clean_record(record) for record in summary.to_dict(orient="records")
        ]
    if not metric_plan.empty:
        result["metrics"] = [
            clean_record(record) for record in metric_plan.to_dict(orient="records")
        ]
    return result


def build_operations_context(reports_dir: Path = REPORTS_DIR, top_n: int = 10) -> dict[str, Any]:
    """Build the compact context packet that an API-backed agent can later consume."""
    seller_summary = read_report("seller_monthly_risk_summary.csv", reports_dir)
    watchlist = read_report("seller_monthly_latest_watchlist.csv", reports_dir)
    latest_transitions = read_report("seller_monthly_latest_transitions.csv", reports_dir)
    model_metrics = read_report("purchase_time_model_metrics.csv", reports_dir)
    lift_table = read_report("purchase_time_model_lift_table.csv", reports_dir)
    recommendations = read_report("intervention_strategy_recommendations.csv", reports_dir)
    root_dimensions = read_optional_report("root_cause_dimension_summary.csv", reports_dir)
    root_segments = read_optional_report("root_cause_priority_segments.csv", reports_dir)
    seller_queue = read_optional_report("seller_operations_queue.csv", reports_dir)
    seller_queue_summary = read_optional_report("seller_operations_queue_summary.csv", reports_dir)
    experiment_summary = read_optional_report(
        "intervention_experiment_design_summary.csv", reports_dir
    )
    experiment_metrics = read_optional_report(
        "intervention_experiment_metric_plan.csv", reports_dir
    )

    return {
        "agent_mode": "offline_deterministic",
        "snapshot": latest_monitoring_snapshot(seller_summary),
        "recent_monthly_trend": monthly_trend(seller_summary),
        "top_alert_drivers": alert_driver_summary(watchlist),
        "top_seller_alerts": top_seller_alerts(watchlist, limit=top_n),
        "latest_transition_summary": transition_summary(latest_transitions),
        "root_cause": root_cause_summary(root_dimensions, root_segments),
        "seller_action_queue": seller_action_queue_summary(
            seller_queue, seller_queue_summary, limit=top_n
        ),
        "purchase_time_model": purchase_time_model_summary(model_metrics, lift_table),
        "intervention_roi": intervention_roi_summary(recommendations),
        "experiment_design": experiment_design_summary(experiment_summary, experiment_metrics),
        "decision_boundaries": [
            "Seller alerts are investigation priorities, not automatic penalties.",
            "Intervention value outputs are retrospective scenarios, not causal proof.",
            "The historical Olist dataset covers 2016-2018 and is not current operations data.",
            "Customer outreach, compensation, and seller enforcement remain human-approved actions.",
        ],
    }


def render_metric_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Month | Orders | GMV | Late Rate | Low-Review Rate | Watch | Critical |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{row.get('order_month')} | "
            f"{int(row.get('seller_orders') or 0):,} | "
            f"{format_brl(row.get('seller_gmv'))} | "
            f"{format_percent(row.get('late_rate'))} | "
            f"{format_percent(row.get('low_review_rate'))} | "
            f"{int(row.get('watch') or 0):,} | "
            f"{int(row.get('critical') or 0):,} |"
        )
    return lines


def render_markdown_briefing(context: dict[str, Any]) -> str:
    """Render a complete readable operations briefing without calling an LLM."""
    snapshot = context["snapshot"]
    counts = snapshot["counts"]
    rates = snapshot["rates"]
    month_over_month = snapshot["month_over_month"]
    drivers = context["top_alert_drivers"][:5]
    transitions = context["latest_transition_summary"]
    root_segments = context["root_cause"]["top_priority_segments"][:6]
    queue = context["seller_action_queue"]
    queue_totals = queue["totals"]
    queue_actions = queue["top_actions"][:8]
    purchase_model = context["purchase_time_model"]
    roi_rows = context["intervention_roi"]
    experiment = context["experiment_design"]
    top_10_segment = purchase_model.get("top_10_percent_segment") or {}

    late_change = month_over_month.get("late_rate")
    critical_change = month_over_month.get("critical")
    watch_change = month_over_month.get("watch")
    dominant_driver = drivers[0]["driver"] if drivers else "no dominant alert driver"

    lines = [
        "# AI Operations Briefing",
        "",
        "Offline deterministic agent output. The briefing is generated from project report tables",
        "without using paid API calls; an OpenAI layer can be enabled later for richer narration.",
        "",
        "## Executive Snapshot",
        "",
        f"- Monitoring month: {snapshot['monitoring_month']}",
        f"- Operating posture: {snapshot['posture']}",
        f"- Active sellers: {counts.get('active_sellers', 0):,}",
        f"- Alert-eligible sellers: {counts.get('alert_eligible_sellers', 0):,}",
        f"- Critical sellers: {counts.get('critical', 0):,}",
        f"- Watch sellers: {counts.get('watch', 0):,}",
        f"- Seller orders: {counts.get('seller_orders', 0):,}",
        f"- Seller GMV: {format_brl(context['recent_monthly_trend'][-1].get('seller_gmv'))}",
        f"- Late-delivery rate: {format_percent(rates.get('late_rate'))}",
        f"- Low-review rate: {format_percent(rates.get('low_review_rate'))}",
        "",
        "The main signal is seller-side customer-experience pressure, led by "
        f"{dominant_driver}. This should trigger investigation and queue prioritization, "
        "not automatic seller penalties.",
        "",
        "## What Changed",
        "",
        f"- Critical sellers changed by {format_signed_number(critical_change)}.",
        f"- Watch sellers changed by {format_signed_number(watch_change)}.",
        f"- Seller orders changed by {format_signed_number(month_over_month.get('seller_orders'))}.",
        f"- Late-delivery rate changed by {format_rate_change(late_change)}.",
        f"- Low-review rate changed by {format_rate_change(month_over_month.get('low_review_rate'))}.",
        f"- Cancellation rate changed by {format_rate_change(month_over_month.get('cancellation_rate'))}.",
        "",
        "## Recent Monitoring Trend",
        "",
    ]
    lines.extend(render_metric_table(context["recent_monthly_trend"]))

    lines.extend(
        [
            "",
            "## Main Risk Drivers",
            "",
        ]
    )
    if drivers:
        lines.extend([f"- {item['driver']}: {item['sellers']} sellers" for item in drivers])
    else:
        lines.append("- No watchlist alert drivers found.")

    lines.extend(
        [
            "",
            "## Latest Risk Transitions",
            "",
            f"- Sellers with escalated or improved status: "
            f"{transitions.get('total_transitioned_sellers', 0):,}",
        ]
    )
    for name, value in transitions.get("by_transition", {}).items():
        lines.append(f"- {name}: {value:,}")

    lines.extend(
        [
            "",
            "## Root-Cause Backlog",
            "",
            "| Rank | Segment | Family | Orders | Low-Review Rate | Share of Low Reviews | Excess Low Reviews |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    for index, segment in enumerate(root_segments, start=1):
        lines.append(
            "| "
            f"{index} | "
            f"{segment.get('segment', '')} | "
            f"{segment.get('segment_family', '')} | "
            f"{int(segment.get('orders') or 0):,} | "
            f"{format_percent(segment.get('low_review_rate'))} | "
            f"{format_percent(segment.get('share_of_low_reviews'))} | "
            f"{float(segment.get('excess_low_reviews') or 0):,.0f} |"
        )

    lines.extend(
        [
            "",
            "## Seller Action Queue",
            "",
            f"- Sellers in queue: {queue_totals.get('sellers', 0):,}",
            f"- Queue seller orders: {queue_totals.get('seller_orders', 0):,}",
            f"- Queue seller GMV: {format_brl(queue_totals.get('seller_gmv'))}",
            f"- Estimated commercial value at risk: "
            f"{format_brl(queue_totals.get('commercial_value_at_risk_brl'))}",
            "",
            "| Rank | Seller | Tier | Owner | SLA | State | Priority | First Action |",
            "|---:|---|---|---|---:|---|---:|---|",
        ]
    )
    for action in queue_actions:
        lines.append(
            "| "
            f"{int(action.get('queue_rank') or 0)} | "
            f"`{action.get('seller_id', '')}` | "
            f"{action.get('action_tier', '')} | "
            f"{action.get('owner', '')} | "
            f"{int(action.get('sla_business_days') or 0)} days | "
            f"{action.get('seller_state', '')} | "
            f"{float(action.get('priority_score') or 0):.1f} | "
            f"{action.get('first_action', '')} |"
        )

    lines.extend(
        [
            "",
            "## Purchase-Time Triage",
            "",
            f"- ROC-AUC: {purchase_model.get('model', {}).get('roc_auc', 0):.3f}",
            f"- PR-AUC: {purchase_model.get('model', {}).get('pr_auc', 0):.3f}",
            f"- Top 10% capture rate: {format_percent(top_10_segment.get('capture_rate'))}",
            f"- Top 10% precision: {format_percent(top_10_segment.get('precision_in_segment'))}",
            "",
            "Use purchase-time ranking for prevention capacity planning. It is weaker than",
            "post-delivery recovery by design because it excludes current-order delivery outcomes.",
            "",
            "## Intervention Recommendation",
            "",
        ]
    )
    for row in roi_rows:
        lines.append(
            f"- {row.get('display_name', row.get('strategy'))}: recommend "
            f"{format_percent(row.get('recommended_coverage_share'))} coverage, "
            f"{int(row.get('orders_contacted') or 0):,} orders contacted, expected net value "
            f"{format_brl(row.get('base_expected_net_value_brl'))}, expected ROI "
            f"{format_percent(row.get('base_expected_roi'))}."
        )

    lines.extend(
        [
            "",
            "## Experiment Validation",
            "",
        ]
    )
    if experiment["strategies"]:
        for row in experiment["strategies"]:
            lines.append(
                f"- {row.get('strategy')}: {int(row.get('candidate_orders') or 0):,} candidate "
                f"orders, baseline low-review rate {format_percent(row.get('baseline_low_review_rate'))}, "
                f"{int(row.get('treatment_orders') or 0):,} treatment and "
                f"{int(row.get('control_orders') or 0):,} control orders."
            )
    else:
        lines.append("- No experiment design summary found.")

    lines.extend(
        [
            "",
            "## Recommended Operating Actions",
            "",
            "- P0: Work the P0 Critical Escalation seller queue within the two-business-day SLA.",
            "- P1: Investigate late-delivery and low-review overlaps before broad seller action.",
            "- P2: Use the 5% intervention-coverage scenario as the first pilot capacity anchor.",
            "- P3: Validate intervention value with the treatment/control experiment design.",
            "- P4: Keep seller penalties, customer outreach, and compensation human-approved.",
            "",
            "## Decision Boundaries",
            "",
        ]
    )
    lines.extend([f"- {boundary}" for boundary in context["decision_boundaries"]])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    context = build_operations_context()
    context_path = REPORTS_DIR / "ai_operations_context.json"

    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")

    print("AI operations context generated.")
    print(f"Context: {context_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
