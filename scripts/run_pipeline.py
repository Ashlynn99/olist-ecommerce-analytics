"""Run the project notebooks in a reproducible order."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import warnings
from pathlib import Path

import nbformat

warnings.filterwarnings("ignore", message="FigureCanvasAgg is non-interactive.*")
warnings.filterwarnings("ignore", message="More than 20 figures have been opened.*")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATPLOTLIB_CACHE_DIR = PROJECT_ROOT / ".matplotlib_cache"
MATPLOTLIB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CACHE_DIR))

NOTEBOOKS = [
    "notebooks/01_data_understanding.ipynb",
    "notebooks/02_data_cleaning.ipynb",
    "notebooks/03_eda_business_analysis.ipynb",
    "notebooks/04_sql_business_analysis.ipynb",
    "notebooks/05_modeling_low_review_risk.ipynb",
    "notebooks/06_seller_logistics_lift_analysis.ipynb",
    "notebooks/07_purchase_time_risk_model.ipynb",
    "notebooks/08_cohort_repeat_analysis.ipynb",
    "notebooks/09_seller_monthly_risk_monitor.ipynb",
]


def display(*objects: object) -> None:
    for obj in objects:
        print(obj)


def run_command(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def execute_notebook_direct(notebook_path: Path) -> None:
    notebook = nbformat.read(notebook_path, as_version=4)
    namespace = {"__name__": "__main__", "display": display}

    print(f"Executing {notebook_path}")
    for cell_index, cell in enumerate(notebook.cells, start=1):
        if cell.get("cell_type") != "code":
            continue

        source = cell.get("source", "")
        if not str(source).strip():
            continue

        try:
            exec(compile(str(source), str(notebook_path), "exec"), namespace)
        except Exception as exc:
            print(f"Notebook execution failed: {notebook_path}, cell {cell_index}")
            raise exc

    try:
        import matplotlib.pyplot as plt

        plt.close("all")
    except ImportError:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute the Olist analytics workflow.")
    parser.add_argument(
        "--skip-data-understanding",
        action="store_true",
        help="Skip the exploratory data-understanding notebook.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the notebook execution order without running notebooks.",
    )
    parser.add_argument(
        "--executor",
        choices=["direct", "nbconvert"],
        default="direct",
        help="Execution backend. The direct backend runs code cells without requiring a Jupyter kernel.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.chdir(PROJECT_ROOT)
    notebooks = NOTEBOOKS[1:] if args.skip_data_understanding else NOTEBOOKS

    run_command([sys.executable, "scripts/check_data.py"])

    if args.dry_run:
        print("Notebook execution order:")
        for notebook in notebooks:
            print(f"- {notebook}")
        return

    for notebook in notebooks:
        notebook_path = PROJECT_ROOT / notebook
        if args.executor == "direct":
            execute_notebook_direct(notebook_path)
        else:
            run_command(
                [
                    sys.executable,
                    "-m",
                    "jupyter",
                    "nbconvert",
                    "--to",
                    "notebook",
                    "--execute",
                    "--inplace",
                    "--ExecutePreprocessor.timeout=900",
                    notebook,
                ]
            )


if __name__ == "__main__":
    main()
