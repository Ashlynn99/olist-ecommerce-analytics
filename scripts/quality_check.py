"""Run lightweight repository checks that do not require the raw Kaggle data."""

from __future__ import annotations

import json
import py_compile
import subprocess
from pathlib import Path

from format_markdown import markdown_files

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ["dashboard", "scripts", "sql", "src"]
MINIMUM_LINE_COUNTS = {
    "dashboard/app.py": 100,
    "scripts/run_pipeline.py": 50,
    "src/purchase_time_risk_model.py": 100,
    "Makefile": 20,
    "reports/final_report.md": 100,
}
REQUIRED_PATHS = [
    ".gitattributes",
    ".github/workflows/quality.yml",
    ".streamlit/config.toml",
    "dashboard/app.py",
    "requirements-dev.txt",
    "reports/final_report.md",
    "reports/root_cause_analysis_summary.md",
    "reports/seller_operations_playbook.md",
    "reports/intervention_experiment_design.md",
    "scripts/run_pipeline.py",
]
MAKE_TARGETS = [
    "setup",
    "data",
    "analysis",
    "sql",
    "purchase-model",
    "cohort",
    "seller-monitor",
    "intervention-value",
    "root-cause",
    "seller-playbook",
    "experiment-design",
    "dashboard",
    "report",
    "all",
    "clean",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def check_required_paths() -> None:
    missing = [path for path in REQUIRED_PATHS if not (PROJECT_ROOT / path).exists()]
    if missing:
        fail(f"Missing required project paths: {', '.join(missing)}")


def check_critical_file_shape() -> None:
    for relative_path, minimum_lines in MINIMUM_LINE_COUNTS.items():
        path = PROJECT_ROOT / relative_path
        text = path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        if line_count < minimum_lines:
            fail(f"{relative_path} has only {line_count} lines; expected at least {minimum_lines}.")
        if "\r" in text:
            fail(f"{relative_path} contains non-LF line endings.")


def python_files() -> list[Path]:
    files: list[Path] = []
    for directory in SOURCE_DIRS:
        files.extend(
            path
            for path in (PROJECT_ROOT / directory).rglob("*.py")
            if "__pycache__" not in path.parts
        )
    return sorted(files)


def check_python() -> None:
    for path in python_files():
        py_compile.compile(path, doraise=True)


def check_source_line_length() -> None:
    for path in python_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if len(line) > 160:
                fail(
                    f"{path.relative_to(PROJECT_ROOT)}:{line_number} has "
                    f"{len(line)} characters; refactor the source line."
                )


def check_notebooks() -> None:
    notebooks = sorted((PROJECT_ROOT / "notebooks").glob("*.ipynb"))
    if len(notebooks) != 13:
        fail(f"Expected 13 notebooks; found {len(notebooks)}.")
    for path in notebooks:
        with path.open(encoding="utf-8") as handle:
            json.load(handle)


def check_makefile() -> None:
    subprocess.run(
        ["make", "--dry-run", *MAKE_TARGETS],
        cwd=PROJECT_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def check_readme_structure() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    for expected in ["dashboard/", "app.py", "scripts/", "src/", "reports/"]:
        if expected not in readme:
            fail(f"README project structure is missing {expected}.")


def check_markdown_line_length() -> None:
    for path in markdown_files():
        in_code_block = False
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block or stripped.startswith(("|", "![", "[![", "http")):
                continue
            if len(line) > 160:
                fail(
                    f"{path.relative_to(PROJECT_ROOT)}:{line_number} has "
                    f"{len(line)} characters; wrap Markdown prose."
                )


def main() -> None:
    checks = [
        check_required_paths,
        check_critical_file_shape,
        check_python,
        check_source_line_length,
        check_notebooks,
        check_makefile,
        check_readme_structure,
        check_markdown_line_length,
    ]
    for check in checks:
        check()
        print(f"PASS {check.__name__}")

    print(
        f"Repository quality checks passed: {len(python_files())} Python files, "
        f"13 notebooks, and {len(markdown_files())} Markdown files."
    )


if __name__ == "__main__":
    main()
