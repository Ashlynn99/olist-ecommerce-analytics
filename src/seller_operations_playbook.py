"""Build an operational playbook and action queue for seller risk monitoring."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt
import pandas as pd

from reporting_utils import format_brl, markdown_table


def load_watchlist(project_root: Path) -> pd.DataFrame:
    return pd.read_csv(project_root / "reports" / "seller_monthly_latest_watchlist.csv")


def classify_action_tier(row: pd.Series) -> str:
    if row["risk_status"] == "critical" and row["risk_transition"] == "escalated":
        return "P0 Critical Escalation"
    if row["risk_status"] == "critical":
        return "P1 Critical Stabilization"
    if row["risk_transition"] == "escalated" or row["priority_score"] >= 70:
        return "P2 Watch Deterioration"
    return "P3 Watch Monitoring"


def diagnostic_focus(alert_reason: str) -> str:
    reason = str(alert_reason)
    focuses: list[str] = []
    if "late-delivery" in reason:
        focuses.append("fulfillment delay")
    if "low-review" in reason:
        focuses.append("customer dissatisfaction")
    if "cancellation" in reason:
        focuses.append("cancellation control")
    if "value exposure" in reason:
        focuses.append("commercial exposure")
    if "deterioration" in reason:
        focuses.append("recent performance deterioration")
    return "; ".join(focuses) if focuses else "general seller performance"


def build_action_matrix() -> pd.DataFrame:
    records = [
        {
            "action_tier": "P0 Critical Escalation",
            "trigger": "Critical status and escalated from previous month",
            "owner": "Seller Operations Lead",
            "sla_business_days": 2,
            "first_action": "Open seller-level incident review and inspect recent delayed orders.",
            "success_metric": "Reduce late rate and low-review rate in next monitoring month.",
        },
        {
            "action_tier": "P1 Critical Stabilization",
            "trigger": "Critical status with persistent high experience risk",
            "owner": "Account Manager",
            "sla_business_days": 3,
            "first_action": "Review fulfillment process and agree on corrective operating plan.",
            "success_metric": "Move seller from critical to watch or stable within two months.",
        },
        {
            "action_tier": "P2 Watch Deterioration",
            "trigger": "Watch status with deterioration or high priority score",
            "owner": "Seller Operations Analyst",
            "sla_business_days": 5,
            "first_action": "Diagnose alert driver and monitor next-cycle order experience.",
            "success_metric": "Prevent escalation into critical status.",
        },
        {
            "action_tier": "P3 Watch Monitoring",
            "trigger": "Watch status without immediate escalation signal",
            "owner": "Operations Analyst",
            "sla_business_days": 7,
            "first_action": "Add to weekly monitoring list and review repeated alert drivers.",
            "success_metric": "Maintain stable status and avoid deterioration.",
        },
    ]
    return pd.DataFrame.from_records(records)


def build_action_queue(watchlist: pd.DataFrame, action_matrix: pd.DataFrame) -> pd.DataFrame:
    queue = watchlist.copy()
    queue["action_tier"] = queue.apply(classify_action_tier, axis=1)
    queue["diagnostic_focus"] = queue["alert_reason"].map(diagnostic_focus)
    queue = queue.merge(action_matrix, on="action_tier", how="left")
    queue["queue_rank"] = queue["priority_score"].rank(method="first", ascending=False).astype(int)
    queue["commercial_value_at_risk_brl"] = queue["seller_gmv"] * queue["smoothed_low_review_rate"]
    ordered_columns = [
        "queue_rank",
        "order_month",
        "seller_id",
        "seller_state",
        "seller_city",
        "risk_status",
        "risk_transition",
        "action_tier",
        "owner",
        "sla_business_days",
        "seller_orders",
        "seller_gmv",
        "commercial_value_at_risk_brl",
        "priority_score",
        "experience_risk_score",
        "diagnostic_focus",
        "first_action",
        "success_metric",
        "alert_reason",
    ]
    return queue[ordered_columns].sort_values("queue_rank")


def summarize_queue(queue: pd.DataFrame) -> pd.DataFrame:
    return (
        queue.groupby(["action_tier", "owner", "sla_business_days"], as_index=False)
        .agg(
            sellers=("seller_id", "nunique"),
            seller_orders=("seller_orders", "sum"),
            seller_gmv=("seller_gmv", "sum"),
            commercial_value_at_risk_brl=("commercial_value_at_risk_brl", "sum"),
            avg_priority_score=("priority_score", "mean"),
        )
        .sort_values("sla_business_days")
    )


def format_queue_summary(summary: pd.DataFrame) -> pd.DataFrame:
    display = summary.copy()
    display["seller_gmv"] = display["seller_gmv"].map(format_brl)
    display["commercial_value_at_risk_brl"] = display["commercial_value_at_risk_brl"].map(
        format_brl
    )
    display["avg_priority_score"] = display["avg_priority_score"].map(lambda value: f"{value:.1f}")
    display = display.rename(
        columns={
            "action_tier": "Action Tier",
            "owner": "Owner",
            "sla_business_days": "SLA Days",
            "sellers": "Sellers",
            "seller_orders": "Seller Orders",
            "seller_gmv": "Seller Value",
            "commercial_value_at_risk_brl": "Value at Risk",
            "avg_priority_score": "Avg Priority",
        }
    )
    return display


def plot_queue_by_tier(summary: pd.DataFrame, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(summary["action_tier"], summary["sellers"], color="#3973a8")
    ax.set_xlabel("Sellers")
    ax.set_title("Seller Operations Queue by Action Tier")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_operations_queue_by_tier.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_value_at_risk(summary: pd.DataFrame, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.bar(
        summary["action_tier"],
        summary["commercial_value_at_risk_brl"],
        color="#c84242",
    )
    ax.set_ylabel("Commercial value at risk, BRL")
    ax.set_title("Estimated Seller Value at Risk by Action Tier")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(figures_dir / "seller_operations_value_at_risk.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_playbook(
    action_matrix: pd.DataFrame,
    queue: pd.DataFrame,
    summary: pd.DataFrame,
    reports_dir: Path,
) -> None:
    p0 = summary[summary["action_tier"].eq("P0 Critical Escalation")]
    p0_sellers = int(p0["sellers"].iloc[0]) if len(p0) else 0
    total_value_at_risk = queue["commercial_value_at_risk_brl"].sum()
    top_seller = queue.iloc[0]
    matrix_markdown = markdown_table(action_matrix)
    summary_markdown = markdown_table(format_queue_summary(summary))

    playbook = f"""# Seller Operations Playbook

## Objective

This playbook converts the monthly seller risk monitor into an operating workflow. It defines alert
tiers, owners, service-level expectations, diagnostic focus, and success metrics.

## Current Queue Snapshot

| Metric | Value |
|---|---:|
| Sellers in action queue | {queue['seller_id'].nunique():,} |
| P0 critical escalations | {p0_sellers:,} |
| Seller-orders represented | {int(queue['seller_orders'].sum()):,} |
| Seller order value represented | {queue['seller_gmv'].sum():,.0f} BRL |
| Estimated commercial value at risk | {total_value_at_risk:,.0f} BRL |
| Highest-priority seller | `{top_seller['seller_id']}` |

## Alert Action Matrix

{matrix_markdown}

## Queue Summary by Tier

{summary_markdown}

## Operating Workflow

1. Refresh monthly seller risk monitor after the complete month closes.
2. Assign each seller to an action tier using risk status, transition, and priority score.
3. Route P0 and P1 cases to owner review before lower-priority watch cases.
4. Diagnose the dominant alert driver: fulfillment delay, low review, cancellation, deterioration,
   or value exposure.
5. Track next-month status movement and measure whether critical/watch sellers return to stable.

## Operating Cadence

| Cadence | Review Question | Output |
|---|---|---|
| Daily during month close | Are any P0 sellers still unresolved after SLA? | Escalation note to Seller Operations Lead |
| Weekly | Which alert drivers repeat across the queue? | Root-cause backlog by delay, review, cancellation, and value exposure |
| Monthly | Which sellers improved, stayed risky, or deteriorated? | Status transition review and next-cycle queue |
| Quarterly | Are interventions reducing risk concentration? | Seller-policy and support-capacity recommendation |

## Governance Notes

- Alerts prioritize human review; they are not automatic seller penalties.
- SLA is counted in business days from the monthly monitoring refresh.
- Success should be evaluated by movement in late rate, low-review rate, cancellation rate,
  priority score, and seller status transition.

## Outputs

- `reports/seller_alert_action_matrix.csv`
- `reports/seller_operations_queue.csv`
- `reports/seller_operations_queue_summary.csv`
- `reports/figures/seller_operations_queue_by_tier.png`
- `reports/figures/seller_operations_value_at_risk.png`
"""
    (reports_dir / "seller_operations_playbook.md").write_text(playbook, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    watchlist = load_watchlist(PROJECT_ROOT)
    action_matrix = build_action_matrix()
    queue = build_action_queue(watchlist, action_matrix)
    summary = summarize_queue(queue)

    action_matrix.to_csv(reports_dir / "seller_alert_action_matrix.csv", index=False)
    queue.to_csv(reports_dir / "seller_operations_queue.csv", index=False)
    summary.to_csv(reports_dir / "seller_operations_queue_summary.csv", index=False)
    plot_queue_by_tier(summary, figures_dir)
    plot_value_at_risk(summary, figures_dir)
    write_playbook(action_matrix, queue, summary, reports_dir)

    print("Seller operations playbook completed.")
    print(f"Queue sellers: {queue['seller_id'].nunique():,}")
    print(f"Summary: {reports_dir / 'seller_operations_playbook.md'}")


if __name__ == "__main__":
    main()
