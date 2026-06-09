from pathlib import Path

import duckdb


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    processed_dir = project_root / "data" / "processed"
    database_dir = project_root / "data" / "database"
    database_dir.mkdir(parents=True, exist_ok=True)

    database_path = database_dir / "olist.duckdb"
    orders_path = processed_dir / "orders_analysis_base.csv"
    items_path = processed_dir / "order_items_enriched.csv"
    products_path = processed_dir / "products_clean.csv"
    quality_path = processed_dir / "data_quality_summary.csv"

    required_files = [orders_path, items_path, products_path, quality_path]
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        missing = "\n".join(str(path) for path in missing_files)
        raise FileNotFoundError(
            f"Missing processed files. Run 02_data_cleaning.ipynb first:\n{missing}"
        )

    with duckdb.connect(database_path) as con:
        con.execute("DROP VIEW IF EXISTS v_monthly_kpis;")
        con.execute("DROP VIEW IF EXISTS v_category_summary;")
        con.execute("DROP VIEW IF EXISTS v_state_summary;")
        con.execute("DROP TABLE IF EXISTS orders_analysis_base;")
        con.execute("DROP TABLE IF EXISTS order_items_enriched;")
        con.execute("DROP TABLE IF EXISTS products_clean;")
        con.execute("DROP TABLE IF EXISTS data_quality_summary;")

        con.execute(
            """
            CREATE TABLE orders_analysis_base AS
            SELECT *
            FROM read_csv_auto(?, HEADER = TRUE);
            """,
            [str(orders_path)],
        )
        con.execute(
            """
            CREATE TABLE order_items_enriched AS
            SELECT *
            FROM read_csv_auto(?, HEADER = TRUE);
            """,
            [str(items_path)],
        )
        con.execute(
            """
            CREATE TABLE products_clean AS
            SELECT *
            FROM read_csv_auto(?, HEADER = TRUE);
            """,
            [str(products_path)],
        )
        con.execute(
            """
            CREATE TABLE data_quality_summary AS
            SELECT *
            FROM read_csv_auto(?, HEADER = TRUE);
            """,
            [str(quality_path)],
        )

        con.execute("""
            CREATE VIEW v_monthly_kpis AS
            SELECT
                purchase_month,
                COUNT(*) AS orders,
                SUM(payment_total) AS gross_payment_volume,
                AVG(payment_total) AS avg_payment_value,
                SUM(product_total) AS product_total,
                SUM(freight_total) AS freight_total,
                AVG(review_score_mean) AS avg_review_score,
                AVG(CASE WHEN is_delivered THEN delivery_days END) AS avg_delivery_days,
                AVG(CASE WHEN is_delivered THEN CAST(is_late AS INTEGER) END) AS late_rate
            FROM orders_analysis_base
            WHERE payment_total IS NOT NULL
            GROUP BY purchase_month;
            """)

        con.execute("""
            CREATE VIEW v_category_summary AS
            SELECT
                main_product_category,
                COUNT(*) AS orders,
                SUM(payment_total) AS gross_payment_volume,
                AVG(payment_total) AS avg_payment_value,
                SUM(freight_total) / NULLIF(SUM(payment_total), 0) AS freight_share,
                AVG(review_score_mean) AS avg_review_score,
                AVG(CAST(is_low_review AS INTEGER)) AS low_review_rate,
                AVG(CASE WHEN is_delivered THEN CAST(is_late AS INTEGER) END) AS late_rate,
                AVG(CASE WHEN is_delivered THEN delivery_days END) AS avg_delivery_days
            FROM orders_analysis_base
            WHERE main_product_category IS NOT NULL
            GROUP BY main_product_category;
            """)

        con.execute("""
            CREATE VIEW v_state_summary AS
            SELECT
                customer_state,
                COUNT(*) AS orders,
                SUM(payment_total) AS gross_payment_volume,
                AVG(payment_total) AS avg_payment_value,
                AVG(review_score_mean) AS avg_review_score,
                AVG(CAST(is_low_review AS INTEGER)) AS low_review_rate,
                AVG(CASE WHEN is_delivered THEN CAST(is_late AS INTEGER) END) AS late_rate,
                AVG(CASE WHEN is_delivered THEN delivery_days END) AS avg_delivery_days
            FROM orders_analysis_base
            WHERE customer_state IS NOT NULL
            GROUP BY customer_state;
            """)

        row_counts = con.execute("""
            SELECT 'orders_analysis_base' AS table_name, COUNT(*) AS rows FROM orders_analysis_base
            UNION ALL
            SELECT 'order_items_enriched', COUNT(*) FROM order_items_enriched
            UNION ALL
            SELECT 'products_clean', COUNT(*) FROM products_clean
            UNION ALL
            SELECT 'data_quality_summary', COUNT(*) FROM data_quality_summary;
            """).fetchdf()

    print(f"Created DuckDB database: {database_path}")
    print(row_counts.to_string(index=False))


if __name__ == "__main__":
    main()
