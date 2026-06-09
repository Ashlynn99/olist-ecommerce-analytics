"""Wrap Markdown prose while preserving tables, code blocks, and document structure."""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WIDTH = 100
LIST_PATTERN = re.compile(r"^(?P<indent>\s*)(?P<marker>(?:[-*+]|\d+\.)\s+)(?P<body>.*)$")


def wrap_text(
    text: str, width: int, initial_indent: str = "", subsequent_indent: str = ""
) -> list[str]:
    return textwrap.wrap(
        " ".join(text.split()),
        width=width,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        break_long_words=False,
        break_on_hyphens=False,
    )


def is_structural_line(line: str) -> bool:
    stripped = line.lstrip()
    return (
        not stripped
        or stripped.startswith(("#", "|", "![", "[![", ">", "---", "***", "<"))
        or ("](" in line and line.rstrip().endswith(")"))
        or stripped.startswith("```")
    )


def format_markdown(text: str, width: int = DEFAULT_WIDTH) -> str:
    output: list[str] = []
    paragraph: list[str] = []
    in_code_block = False

    def flush_paragraph() -> None:
        if not paragraph:
            return
        leading = re.match(r"^\s*", paragraph[0]).group(0)
        output.extend(
            wrap_text(" ".join(line.strip() for line in paragraph), width, leading, leading)
        )
        paragraph.clear()

    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```"):
            flush_paragraph()
            output.append(line.rstrip())
            in_code_block = not in_code_block
            continue

        if in_code_block:
            output.append(line.rstrip())
            continue

        list_match = LIST_PATTERN.match(line)
        if list_match:
            flush_paragraph()
            prefix = f"{list_match.group('indent')}{list_match.group('marker')}"
            continuation = " " * len(prefix)
            output.extend(wrap_text(list_match.group("body"), width, prefix, continuation))
            continue

        if is_structural_line(line):
            flush_paragraph()
            output.append(line.rstrip())
            continue

        paragraph.append(line)

    flush_paragraph()
    return "\n".join(output).rstrip() + "\n"


def markdown_files() -> list[Path]:
    return [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "data" / "README.md",
        *sorted((PROJECT_ROOT / "reports").glob("*.md")),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Fail if a Markdown file needs formatting."
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Target prose line width.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    changed: list[Path] = []

    for path in markdown_files():
        original = path.read_text(encoding="utf-8")
        formatted = format_markdown(original, width=args.width)
        if formatted == original:
            continue
        changed.append(path)
        if not args.check:
            path.write_text(formatted, encoding="utf-8")

    if args.check and changed:
        print("Markdown formatting required:")
        for path in changed:
            print(f"- {path.relative_to(PROJECT_ROOT)}")
        raise SystemExit(1)

    action = "checked" if args.check else "formatted"
    print(f"Markdown {action}: {len(markdown_files())} files; {len(changed)} changes.")


if __name__ == "__main__":
    main()
