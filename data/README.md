# Data Instructions

Raw and processed data files are not committed to this repository.

## Raw Data

Download the dataset from Kaggle:

[Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

Place the following files under `data/raw/`:

```text
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

## Processed Data

Run:

```bash
make data
make analysis
```

or run the cleaning notebook directly:

```text
notebooks/02_data_cleaning.ipynb
```

This creates processed analytical tables under `data/processed/`, including:

```text
orders_analysis_base.csv
order_items_enriched.csv
order_payments_agg.csv
order_reviews_agg.csv
products_clean.csv
geolocation_clean.csv
```

The seller, logistics, and lift analysis notebook also creates:

```text
seller_order_base.csv
```

The purchase-time model and cohort analysis also create:

```text
purchase_time_seller_history_features.csv
customer_repeat_behavior_base.csv
```

## DuckDB Database

Run:

```bash
make sql
```

or run:

```text
notebooks/04_sql_business_analysis.ipynb
```

This creates:

```text
data/database/olist.duckdb
```
