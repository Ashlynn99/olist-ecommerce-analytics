"""Small formatting helpers for generated Markdown reports."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def markdown_table(frame: pd.DataFrame) -> str:
    """Render a small dataframe as a dependency-free Markdown table."""
    display = frame.copy().map(format_cell)
    headers = list(display.columns)
    separator = ["---"] * len(headers)
    rows = [headers, separator, *display.values.tolist()]
    return "\n".join("| " + " | ".join(str(value) for value in row) + " |" for row in rows)


def format_cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        if math.isclose(value, round(value), rel_tol=0, abs_tol=1e-9):
            return f"{value:,.0f}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value).replace("|", "\\|")


def format_percent(value: float) -> str:
    return f"{value:.1%}"


def format_brl(value: float) -> str:
    return f"{value:,.0f} BRL"
