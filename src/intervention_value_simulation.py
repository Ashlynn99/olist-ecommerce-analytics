"""Intervention cost and expected-value scenarios for low-review risk models."""

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


COVERAGE_LEVELS = [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.00]
VALUE_PER_SUCCESSFUL_RECOVERY = 75.0
BASE_STRATEGIES = {
    "purchase_time": {
        "display_name": "Purchase-time prevention",
        "score_column": "purchase_time_low_review_probability",
        "cost_per_contact": 3.0,
        "intervention_effectiveness": 0.15,
        "description": "Automated proactive communication or operational escalation after purchase",
    },
    "post_delivery": {
        "display_name": "Post-delivery recovery",
        "score_column": "low_review_probability",
        "cost_per_contact": 12.0,
        "intervention_effectiveness": 0.35,
        "description": "Human support outreach or service-recovery action immediately after delivery",
    },
}


def load_predictions(reports_dir: Path) -> dict[str, pd.DataFrame]:
    paths = {
        "purchase_time": reports_dir / "purchase_time_model_test_predictions.csv",
        "post_delivery": reports_dir / "model_low_review_test_predictions.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Prediction files are missing. Run `make analysis` first. Missing: "
            + ", ".join(missing)
        )

    predictions = {name: pd.read_csv(path) for name, path in paths.items()}
    purchase = predictions["purchase_time"]
    post = predictions["post_delivery"]

    if len(purchase) != len(post):
        raise ValueError("Purchase-time and post-delivery prediction files have different row counts.")

    comparison = purchase[["order_id", "target_low_review"]].merge(
        post[["order_id", "target_low_review"]],
        on="order_id",
        how="outer",
        suffixes=("_purchase", "_post"),
        indicator=True,
    )
    if not comparison["_merge"].eq("both").all():
        raise ValueError("The two prediction files do not cover the same orders.")
    if not comparison["target_low_review_purchase"].eq(
        comparison["target_low_review_post"]
    ).all():
        raise ValueError("Target labels differ between prediction files.")

    return predictions


def simulate_strategy(
    predictions: pd.DataFrame,
    strategy_name: str,
    score_column: str,
    cost_per_contact: float,
    intervention_effectiveness: float,
    value_per_successful_recovery: float,
    coverage_levels: list[float] = COVERAGE_LEVELS,
) -> pd.DataFrame:
    ranked = predictions.sort_values(score_column, ascending=False).reset_index(drop=True)
    total_low_reviews = int(ranked["target_low_review"].sum())
    baseline_rate = float(ranked["target_low_review"].mean())
    rows = []

    for coverage in coverage_levels:
        contacts = max(1, int(np.ceil(len(ranked) * coverage)))
        selected = ranked.iloc[:contacts]
        observed_low_reviews = int(selected["target_low_review"].sum())
        segment_low_review_rate = float(selected["target_low_review"].mean())
        expected_successful_recoveries = observed_low_reviews * intervention_effectiveness
        intervention_cost = contacts * cost_per_contact
        expected_benefit = expected_successful_recoveries * value_per_successful_recovery
        expected_net_value = expected_benefit - intervention_cost
        expected_roi = expected_net_value / intervention_cost if intervention_cost else np.nan
        random_expected_low_reviews = contacts * baseline_rate
        random_expected_net_value = (
            random_expected_low_reviews
            * intervention_effectiveness
            * value_per_successful_recovery
            - intervention_cost
        )
        break_even_effectiveness = (
            intervention_cost / (observed_low_reviews * value_per_successful_recovery)
            if observed_low_reviews
            else np.nan
        )

        rows.append(
            {
                "strategy": strategy_name,
                "coverage_share": coverage,
                "orders_contacted": contacts,
                "observed_low_reviews_in_segment": observed_low_reviews,
                "low_reviews_captured_share": observed_low_reviews / total_low_reviews,
                "segment_low_review_rate": segment_low_review_rate,
                "lift_vs_baseline": segment_low_review_rate / baseline_rate,
                "cost_per_contact_brl": cost_per_contact,
                "assumed_intervention_effectiveness": intervention_effectiveness,
                "value_per_successful_recovery_brl": value_per_successful_recovery,
                "expected_successful_recoveries": expected_successful_recoveries,
                "intervention_cost_brl": intervention_cost,
                "expected_benefit_brl": expected_benefit,
                "expected_net_value_brl": expected_net_value,
                "expected_roi": expected_roi,
                "random_selection_expected_net_value_brl": random_expected_net_value,
                "incremental_net_value_vs_random_brl": expected_net_value
                - random_expected_net_value,
                "break_even_effectiveness": break_even_effectiveness,
            }
        )

    return pd.DataFrame(rows)


def create_base_simulation(predictions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for name, config in BASE_STRATEGIES.items():
        frames.append(
            simulate_strategy(
                predictions=predictions[name],
                strategy_name=name,
                score_column=config["score_column"],
                cost_per_contact=config["cost_per_contact"],
                intervention_effectiveness=config["intervention_effectiveness"],
                value_per_successful_recovery=VALUE_PER_SUCCESSFUL_RECOVERY,
            )
        )
    return pd.concat(frames, ignore_index=True)


def create_scenario_simulation(predictions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    scenario_multipliers = {
        "conservative": {"cost": 1.25, "effectiveness": 0.65, "value": 0.75},
        "base": {"cost": 1.00, "effectiveness": 1.00, "value": 1.00},
        "optimistic": {"cost": 0.80, "effectiveness": 1.35, "value": 1.25},
    }
    frames = []
    for name, config in BASE_STRATEGIES.items():
        for scenario, multiplier in scenario_multipliers.items():
            simulated = simulate_strategy(
                predictions=predictions[name],
                strategy_name=name,
                score_column=config["score_column"],
                cost_per_contact=config["cost_per_contact"] * multiplier["cost"],
                intervention_effectiveness=min(
                    1.0, config["intervention_effectiveness"] * multiplier["effectiveness"]
                ),
                value_per_successful_recovery=VALUE_PER_SUCCESSFUL_RECOVERY
                * multiplier["value"],
            )
            simulated.insert(1, "scenario", scenario)
            frames.append(simulated)
    return pd.concat(frames, ignore_index=True)


def create_sensitivity_table(
    predictions: dict[str, pd.DataFrame], base_simulation: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for strategy, config in BASE_STRATEGIES.items():
        recommended = (
            base_simulation[base_simulation["strategy"].eq(strategy)]
            .sort_values("expected_net_value_brl", ascending=False)
            .iloc[0]
        )
        coverage = float(recommended["coverage_share"])
        ranked = predictions[strategy].sort_values(config["score_column"], ascending=False)
        contacts = max(1, int(np.ceil(len(ranked) * coverage)))
        observed_low_reviews = int(ranked.iloc[:contacts]["target_low_review"].sum())

        for cost_per_contact in [2.0, 5.0, 10.0, 15.0, 20.0]:
            for effectiveness in [0.10, 0.20, 0.30, 0.40, 0.50]:
                cost = contacts * cost_per_contact
                benefit = (
                    observed_low_reviews * effectiveness * VALUE_PER_SUCCESSFUL_RECOVERY
                )
                net_value = benefit - cost
                rows.append(
                    {
                        "strategy": strategy,
                        "recommended_coverage_share": coverage,
                        "orders_contacted": contacts,
                        "observed_low_reviews_in_segment": observed_low_reviews,
                        "cost_per_contact_brl": cost_per_contact,
                        "assumed_intervention_effectiveness": effectiveness,
                        "value_per_successful_recovery_brl": VALUE_PER_SUCCESSFUL_RECOVERY,
                        "expected_net_value_brl": net_value,
                        "expected_roi": net_value / cost,
                    }
                )
    return pd.DataFrame(rows)


def create_recommendations(
    base_simulation: pd.DataFrame, scenario_simulation: pd.DataFrame
) -> pd.DataFrame:
    rows = []
    for strategy, config in BASE_STRATEGIES.items():
        strategy_base = base_simulation[base_simulation["strategy"].eq(strategy)]
        recommended = strategy_base.sort_values("expected_net_value_brl", ascending=False).iloc[0]
        base_at_recommended = scenario_simulation[
            scenario_simulation["strategy"].eq(strategy)
            & scenario_simulation["coverage_share"].eq(recommended["coverage_share"])
        ].copy()
        scenario_net = dict(
            zip(base_at_recommended["scenario"], base_at_recommended["expected_net_value_brl"])
        )
        rows.append(
            {
                "strategy": strategy,
                "display_name": config["display_name"],
                "recommended_coverage_share": recommended["coverage_share"],
                "orders_contacted": int(recommended["orders_contacted"]),
                "observed_low_reviews_in_segment": int(
                    recommended["observed_low_reviews_in_segment"]
                ),
                "low_reviews_captured_share": recommended["low_reviews_captured_share"],
                "base_expected_successful_recoveries": recommended[
                    "expected_successful_recoveries"
                ],
                "base_expected_net_value_brl": recommended["expected_net_value_brl"],
                "base_expected_roi": recommended["expected_roi"],
                "incremental_net_value_vs_random_brl": recommended[
                    "incremental_net_value_vs_random_brl"
                ],
                "break_even_effectiveness": recommended["break_even_effectiveness"],
                "conservative_net_value_brl": scenario_net["conservative"],
                "optimistic_net_value_brl": scenario_net["optimistic"],
                "operating_description": config["description"],
            }
        )
    return pd.DataFrame(rows)


def create_figures(
    base_simulation: pd.DataFrame,
    scenario_simulation: pd.DataFrame,
    sensitivity: pd.DataFrame,
    recommendations: pd.DataFrame,
    figures_dir: Path,
) -> None:
    plt.style.use("default")
    colors = {"purchase_time": "#4c78a8", "post_delivery": "#d62728"}
    labels = {
        "purchase_time": "Purchase-time prevention",
        "post_delivery": "Post-delivery recovery",
    }

    fig, ax = plt.subplots(figsize=(11, 6))
    coverage_positions = np.arange(len(COVERAGE_LEVELS))
    for strategy in BASE_STRATEGIES:
        plot = (
            base_simulation[base_simulation["strategy"].eq(strategy)]
            .set_index("coverage_share")
            .reindex(COVERAGE_LEVELS)
        )
        ax.plot(
            coverage_positions,
            plot["expected_net_value_brl"],
            marker="o",
            linewidth=2,
            color=colors[strategy],
            label=labels[strategy],
        )
    ax.axhline(0, color="black", linestyle="--", linewidth=1)
    ax.set_title("Expected Net Value by Intervention Coverage")
    ax.set_xlabel("Highest-Risk Orders Contacted")
    ax.set_ylabel("Expected Net Value, BRL")
    ax.set_xticks(coverage_positions)
    ax.set_xticklabels(["1%", "2%", "5%", "10%", "20%", "30%", "50%", "100%"])
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "intervention_net_value_by_coverage.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    scenario_best = scenario_simulation.loc[
        scenario_simulation.groupby(["strategy", "scenario"])["expected_net_value_brl"].idxmax()
    ].copy()
    scenarios = ["conservative", "base", "optimistic"]
    x = np.arange(len(scenarios))
    width = 0.34
    fig, ax = plt.subplots(figsize=(11, 6))
    for offset, strategy in zip([-width / 2, width / 2], BASE_STRATEGIES):
        plot = (
            scenario_best[scenario_best["strategy"].eq(strategy)]
            .set_index("scenario")
            .reindex(scenarios)
        )
        ax.bar(
            x + offset,
            plot["expected_net_value_brl"],
            width=width,
            color=colors[strategy],
            label=labels[strategy],
        )
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels([value.title() for value in scenarios])
    ax.set_title("Best Expected Net Value Across Scenarios")
    ax.set_ylabel("Expected Net Value, BRL")
    ax.legend()
    plt.tight_layout()
    plt.savefig(figures_dir / "intervention_scenario_comparison.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, strategy in zip(axes, BASE_STRATEGIES):
        table = sensitivity[sensitivity["strategy"].eq(strategy)].pivot(
            index="assumed_intervention_effectiveness",
            columns="cost_per_contact_brl",
            values="expected_net_value_brl",
        )
        vmax = np.nanmax(np.abs(table.to_numpy()))
        image = ax.imshow(
            table.to_numpy(),
            cmap="RdYlGn",
            aspect="auto",
            vmin=-vmax,
            vmax=vmax,
        )
        ax.set_xticks(np.arange(len(table.columns)))
        ax.set_xticklabels([f"{value:.0f}" for value in table.columns])
        ax.set_yticks(np.arange(len(table.index)))
        ax.set_yticklabels([f"{value:.0%}" for value in table.index])
        ax.set_title(labels[strategy])
        ax.set_xlabel("Cost per Contact, BRL")
        for row in range(len(table.index)):
            for col in range(len(table.columns)):
                ax.text(
                    col,
                    row,
                    f"{table.iloc[row, col] / 1000:.1f}k",
                    ha="center",
                    va="center",
                    fontsize=8,
                )
    axes[0].set_ylabel("Assumed Intervention Effectiveness")
    fig.suptitle("Expected Net Value Sensitivity at Recommended Coverage")
    fig.colorbar(image, ax=axes, label="Expected Net Value, BRL", shrink=0.82)
    plt.savefig(figures_dir / "intervention_value_sensitivity.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    comparison = recommendations.copy()
    x = np.arange(len(comparison))
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    ax1.bar(
        x,
        comparison["base_expected_net_value_brl"],
        color=[colors[value] for value in comparison["strategy"]],
        alpha=0.82,
        label="Expected net value",
    )
    ax2.plot(
        x,
        comparison["low_reviews_captured_share"],
        color="#333333",
        marker="o",
        linewidth=2,
        label="Low reviews captured",
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels(comparison["display_name"])
    ax1.set_ylabel("Expected Net Value, BRL")
    ax2.set_ylabel("Share of Low Reviews Captured")
    ax2.set_ylim(0, max(0.5, comparison["low_reviews_captured_share"].max() * 1.25))
    ax1.set_title("Recommended Base-Case Intervention Strategies")
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")
    plt.tight_layout()
    plt.savefig(figures_dir / "intervention_recommended_strategies.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_summary(
    recommendations: pd.DataFrame,
    reports_dir: Path,
) -> None:
    purchase = recommendations[recommendations["strategy"].eq("purchase_time")].iloc[0]
    post = recommendations[recommendations["strategy"].eq("post_delivery")].iloc[0]

    summary = f"""# Intervention Cost and Expected-Value Simulation

## Objective

I translated the purchase-time and post-delivery low-review risk rankings into intervention-capacity and value scenarios.

This is a retrospective scenario simulation, not a measured causal impact study. The model identifies historical low-review risk, while intervention effectiveness and recovery value are explicit assumptions that should be validated through a controlled experiment.

## Base-Case Assumptions

| Strategy | Cost per Contact | Assumed Effectiveness | Value per Successful Recovery |
|---|---:|---:|---:|
| Purchase-time prevention | {BASE_STRATEGIES['purchase_time']['cost_per_contact']:.0f} BRL | {BASE_STRATEGIES['purchase_time']['intervention_effectiveness']:.0%} | {VALUE_PER_SUCCESSFUL_RECOVERY:.0f} BRL |
| Post-delivery recovery | {BASE_STRATEGIES['post_delivery']['cost_per_contact']:.0f} BRL | {BASE_STRATEGIES['post_delivery']['intervention_effectiveness']:.0%} | {VALUE_PER_SUCCESSFUL_RECOVERY:.0f} BRL |

The purchase-time action represents a lower-cost automated communication or operational escalation. The post-delivery action represents a higher-cost human support or service-recovery workflow.

## Recommended Base-Case Strategies

| Strategy | Risk Coverage | Orders Contacted | Low Reviews Captured | Expected Net Value | Incremental Value vs Random | ROI | Break-Even Effectiveness |
|---|---:|---:|---:|---:|---:|---:|---:|
| Purchase-time prevention | {purchase['recommended_coverage_share']:.0%} | {int(purchase['orders_contacted']):,} | {purchase['low_reviews_captured_share']:.1%} | {purchase['base_expected_net_value_brl']:,.0f} BRL | {purchase['incremental_net_value_vs_random_brl']:,.0f} BRL | {purchase['base_expected_roi']:.1%} | {purchase['break_even_effectiveness']:.1%} |
| Post-delivery recovery | {post['recommended_coverage_share']:.0%} | {int(post['orders_contacted']):,} | {post['low_reviews_captured_share']:.1%} | {post['base_expected_net_value_brl']:,.0f} BRL | {post['incremental_net_value_vs_random_brl']:,.0f} BRL | {post['base_expected_roi']:.1%} | {post['break_even_effectiveness']:.1%} |

## Interpretation

- The recommended coverage is the tested risk segment with the highest expected net value under the base assumptions.
- Incremental value versus random isolates the benefit of using the model ranking instead of contacting the same number of randomly selected orders.
- Purchase-time prevention is cheaper and can act earlier, but the model's lower precision limits the economically attractive coverage range.
- Post-delivery recovery is more expensive per order, but its stronger risk concentration supports higher expected net value.
- The sensitivity analysis shows when either strategy becomes unprofitable as cost rises or effectiveness falls.
- Under the conservative assumptions, neither tested strategy produces positive net value; the economically appropriate decision would be not to launch until assumptions improve or a pilot demonstrates stronger effects.

## Decision Boundary

These values should not be presented as realized savings. A production decision should begin with a randomized pilot that measures actual intervention effectiveness, customer response, cost per contact, and longer-term customer value. The scenario model can then be updated with experimentally observed parameters.
"""
    (reports_dir / "intervention_value_summary.md").write_text(summary, encoding="utf-8")


def main() -> None:
    reports_dir = PROJECT_ROOT / "reports"
    figures_dir = reports_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    predictions = load_predictions(reports_dir)
    base_simulation = create_base_simulation(predictions)
    scenario_simulation = create_scenario_simulation(predictions)
    sensitivity = create_sensitivity_table(predictions, base_simulation)
    recommendations = create_recommendations(base_simulation, scenario_simulation)

    base_simulation.to_csv(reports_dir / "intervention_value_by_coverage.csv", index=False)
    scenario_simulation.to_csv(reports_dir / "intervention_value_scenarios.csv", index=False)
    sensitivity.to_csv(reports_dir / "intervention_value_sensitivity.csv", index=False)
    recommendations.to_csv(reports_dir / "intervention_strategy_recommendations.csv", index=False)

    create_figures(
        base_simulation, scenario_simulation, sensitivity, recommendations, figures_dir
    )
    write_summary(recommendations, reports_dir)

    print("Intervention cost and expected-value simulation completed.")
    print(
        recommendations[
            [
                "display_name",
                "recommended_coverage_share",
                "orders_contacted",
                "low_reviews_captured_share",
                "base_expected_net_value_brl",
                "base_expected_roi",
                "incremental_net_value_vs_random_brl",
                "break_even_effectiveness",
            ]
        ].to_string(index=False)
    )
    print(f"Summary: {reports_dir / 'intervention_value_summary.md'}")


if __name__ == "__main__":
    main()
