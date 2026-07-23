"""AI-powered operations briefing generator for the Olist analytics project.

Run this after the analytical reports have been generated:

    python src/operations_inspection_agent.py

By default this script runs in offline deterministic mode and does not call a
paid API. Pass --use-openai when you explicitly want to use the OpenAI layer.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from ops_agent_tools import (
    PROJECT_ROOT,
    REPORTS_DIR,
    build_operations_context,
    render_markdown_briefing,
)

DEFAULT_MODEL = "gpt-5.6-luna"
OUTPUT_PATH = REPORTS_DIR / "ai_operations_briefing.md"


SYSTEM_PROMPT = """You are the Olist Operations Inspection Agent.

Your job is to turn structured marketplace analytics outputs into a concise
operations briefing for an e-commerce operations team.

Rules:
- Use only the provided context. Do not invent metrics, causes, current events,
  or operational outcomes.
- Seller alerts are investigation priorities, not automatic penalties.
- Intervention ROI is a retrospective scenario signal, not causal proof.
- Prioritize concrete operating actions over generic analytics language.
- Write in English because the project reports and dashboard are in English.
- Keep the briefing executive-friendly but evidence-based.
"""


USER_PROMPT_TEMPLATE = """Create the final AI Operations Briefing from this context.

Required structure:

# AI Operations Briefing

## Executive Snapshot
Summarize the current monitoring month and the most important risk signal.

## What Changed
Explain the month-over-month changes that matter operationally.

## Main Risk Drivers
Rank the dominant alert drivers and explain why they matter.

## Root-Cause Backlog
Explain the top root-cause segments.

## Seller Action Queue
Provide a short action plan for the highest-priority seller queue.

## Purchase-Time Triage
Interpret the purchase-time model in practical terms for prevention workflow.

## Intervention Recommendation
Explain which intervention coverage looks like the starting point for a pilot
and why.

## Experiment Validation
Summarize the treatment/control validation plan.

## Decision Boundaries
State the limitations and human-approval boundaries.

Context JSON:
{context_json}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the AI operations briefing from Olist report outputs."
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_AGENT_MODEL", DEFAULT_MODEL),
        help="OpenAI model to use when API generation is enabled.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Markdown output path.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Write the deterministic briefing. This is the default behavior.",
    )
    parser.add_argument(
        "--use-openai",
        action="store_true",
        help="Call OpenAI to rewrite the deterministic context into a richer briefing.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of seller alerts to include in the context packet.",
    )
    return parser.parse_args()


def response_text(response: Any) -> str:
    """Extract text from a Responses API result across SDK versions."""
    direct_text = getattr(response, "output_text", None)
    if direct_text:
        return str(direct_text)

    output_items = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output_items:
        content_items = getattr(item, "content", None) or []
        for content in content_items:
            text = getattr(content, "text", None)
            if text:
                chunks.append(str(text))

    return "\n".join(chunks).strip()


def generate_with_openai(context: dict[str, Any], model: str) -> str:
    """Generate the briefing with the OpenAI Responses API."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI SDK is not installed. Run `pip install -r requirements.txt` "
            "inside the project virtual environment."
        ) from exc

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it in your terminal before running "
            "the AI briefing."
        )

    client = OpenAI()
    context_json = json.dumps(context, ensure_ascii=False, indent=2)
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=USER_PROMPT_TEMPLATE.format(context_json=context_json),
    )

    briefing = response_text(response)
    if not briefing:
        raise RuntimeError("The OpenAI response did not include output text.")
    return briefing


def write_briefing(path: Path, briefing: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(briefing.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    context = build_operations_context(top_n=args.top_n)
    context_path = REPORTS_DIR / "ai_operations_context.json"
    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")

    mode = "offline"
    try:
        if args.use_openai and not args.offline:
            briefing = generate_with_openai(context, args.model)
            mode = f"openai:{args.model}"
        else:
            briefing = render_markdown_briefing(context)
    except Exception as exc:
        briefing = render_markdown_briefing(context)
        briefing += (
            "\n## AI Generation Status\n\n"
            f"- OpenAI generation was skipped: {exc}\n"
            "- This file currently contains the deterministic fallback briefing.\n"
        )
        mode = "fallback"

    write_briefing(output_path, briefing)
    print("Operations inspection briefing generated.")
    print(f"Mode: {mode}")
    print(f"Context: {context_path.relative_to(PROJECT_ROOT)}")
    print(f"Output: {output_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
