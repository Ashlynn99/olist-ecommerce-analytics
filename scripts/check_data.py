"""Validate that the expected Kaggle raw data files are available."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

EXPECTED_RAW_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def main() -> None:
    missing_files = [name for name in EXPECTED_RAW_FILES if not (RAW_DATA_DIR / name).exists()]

    if missing_files:
        print("Missing raw data files under data/raw/:")
        for name in missing_files:
            print(f"- {name}")
        print("\nDownload the Olist dataset from Kaggle and place the 9 CSV files under data/raw/.")
        raise SystemExit(1)

    print("Raw data check passed.")
    print(f"Found {len(EXPECTED_RAW_FILES)} expected CSV files in {RAW_DATA_DIR.relative_to(PROJECT_ROOT)}.")


if __name__ == "__main__":
    main()
