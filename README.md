# Olist E-Commerce Analytics and Post-Delivery Low-Review Risk Ranking

## Project Overview

I built this project to analyze the Brazilian Olist e-commerce marketplace dataset from a business and operations perspective. The goal was to understand marketplace growth, delivery performance, customer satisfaction, and whether delivered orders can be ranked by low-review risk for service recovery and operational review.

The project covers the full analytics workflow:

1. Data understanding across 9 raw CSV tables
2. Data cleaning and order-level analytical table creation
3. Business EDA with KPI and experience analysis
4. SQL analytics using DuckDB
5. Post-delivery low-review risk modeling
6. Seller, logistics, and model lift analysis

Data source: [Olist Brazilian E-Commerce Public Dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

## Business Questions

- How did Olist's orders, gross payment volume, and average payment value evolve over time?
- Which product categories, customer states, and payment methods drive revenue?
- How does delivery performance relate to customer review scores?
- Which order segments have the highest risk of receiving low reviews?
- After delivery, can a simple machine learning model rank orders by low-review risk?

## Key Findings

- Total orders analyzed: 99,441
- Delivered orders: 96,470, equal to 97.0% of orders
- Gross payment volume based on `payment_total`, including freight: 16,008,872 BRL
- Average payment value per order: 161 BRL
- Average delivery time: 12.6 days
- Late delivery rate among delivered orders: 8.1%
- Average review score: 4.09
- Low-review rate, defined as review score <= 2: 14.7%
- Highest gross payment volume month: 2017-11, with 1,194,883 BRL and 7,544 orders
- Top category by revenue: health_beauty
- Top customer state by gross payment volume: SP
- Orders delivered 15+ days late had a low-review rate of 78.9%
- Cross-state seller-orders averaged 15.0 delivery days versus 7.9 days for same-state seller-orders
- The top 10% highest-risk orders identified by the model captured 41.7% of all low reviews in the test period
- 35 sellers were classified as high-value / high-risk, covering 9,890 associated orders

## Selected Visuals

### Monthly Orders and Gross Payment Volume

![Monthly Orders and Gross Payment Volume](reports/figures/monthly_orders_gmv.png)

### Delivery Delay and Low Review Rate

![Delivery Delay and Low Review Rate](reports/figures/delivery_delay_low_review_rate.png)

### Category Experience Map

![Category Experience Map](reports/figures/category_experience_map.png)

### Low Review Risk Ranking ROC Curve

![Low Review Model ROC Curve](reports/figures/model_low_review_roc_curve.png)

## Additional Analysis

I added three focused analyses to make the project more useful for marketplace operations.

### 1. Seller Performance Scorecard

I segmented sellers by marketplace value and customer experience risk. This helps identify sellers that are commercially important but may need operational follow-up.

![Seller Scorecard Value Risk](reports/figures/seller_scorecard_value_risk.png)

### 2. Logistics Distance and Cross-State Analysis

I used customer and seller zip-code prefix geolocation to estimate customer-seller distance and compare same-state versus cross-state routes.

Key result:

- Same-state seller-orders: 34,907
- Cross-state seller-orders: 61,767
- Same-state average delivery days: 7.9
- Cross-state average delivery days: 15.0
- Same-state low-review rate: 10.9%
- Cross-state low-review rate: 14.7%

![Logistics Distance Delivery Review](reports/figures/logistics_distance_delivery_review.png)

### 3. Model Lift and Gain Simulation

I translated the low-review model into a customer support prioritization view.

Key result:

- Top 10% highest-risk orders captured 41.7% of low reviews
- Top 10% segment precision was 55.8%
- Top 10% lift versus baseline was 4.17x

![Low Review Cumulative Gain](reports/figures/model_low_review_cumulative_gain.png)

## Post-Delivery Risk Ranking Model

The modeling task ranks delivered orders by the probability of receiving a low review score, defined as `review_score <= 2`.

The model excludes review-derived fields to avoid data leakage. It uses a time-based split:

- Train: orders before 2018-01-01
- Test: orders on or after 2018-01-01

| Model | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| Dummy baseline | 0.500 | 0.134 | 0.000 | 0.000 | 0.000 |
| Logistic regression, tuned threshold | 0.763 | 0.446 | 0.506 | 0.465 | 0.485 |

The model is best interpreted as a post-delivery risk-ranking tool for customer support prioritization and operational review. I would not use it as an automated decision system.

Important boundary: the feature set includes post-delivery information such as actual delivery days, delivery delay, and late-delivery status. This makes the current model useful for service recovery after delivery, not for pure purchase-time prediction.

The lift analysis makes the model easier to discuss in business terms: reviewing only the top 10% highest-risk orders would cover 41.7% of low reviews in the test set.

## Repository Structure

```text
.
├── data/
│   ├── README.md
│   ├── raw/                 # raw Kaggle CSV files, not committed
│   ├── processed/           # generated cleaned files, not committed
│   └── database/            # generated DuckDB database, not committed
├── notebooks/
│   ├── 01_data_understanding.ipynb
│   ├── 02_data_cleaning.ipynb
│   ├── 03_eda_business_analysis.ipynb
│   ├── 04_sql_business_analysis.ipynb
│   ├── 05_modeling_low_review_risk.ipynb
│   └── 06_seller_logistics_lift_analysis.ipynb
├── reports/
│   ├── final_report.md
│   ├── eda_key_findings.md
│   ├── modeling_low_review_summary.md
│   ├── model_low_review_metrics.csv
│   ├── model_low_review_feature_importance.csv
│   ├── additional_analysis_summary.md
│   ├── seller_segment_summary.csv
│   ├── logistics_distance_summary.csv
│   ├── logistics_route_summary.csv
│   ├── model_low_review_lift_table.csv
│   └── figures/
├── scripts/
│   ├── check_data.py
│   └── run_pipeline.py
├── sql/
│   ├── 00_create_database.py
│   ├── 01_business_kpis.sql
│   ├── 02_growth_analysis.sql
│   ├── 03_delivery_experience.sql
│   ├── 04_category_region_analysis.sql
│   └── 05_customer_review_risk.sql
├── requirements.txt
├── Makefile
├── LICENSE
├── src/
│   └── seller_logistics_lift_analysis.py
└── README.md
```

## How to Reproduce

### 1. Clone the repository

```bash
git clone https://github.com/Ashlynn99/olist-ecommerce-analytics.git
cd olist-ecommerce-analytics
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Download the data

Download the dataset from Kaggle:

[Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)

Place the 9 raw CSV files under:

```text
data/raw/
```

Expected files:

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

### 4. Run the reproducible workflow

The project includes a small Makefile so the main workflow can be checked and executed from the command line:

```bash
make setup
make data
make analysis
make report
```

`make data` checks whether the expected raw Kaggle CSV files exist. `make analysis` executes the notebook code in order and regenerates processed files, charts, SQL outputs, and model artifacts. The pipeline uses a direct Python executor by default so it does not depend on a separate Jupyter kernel process.

### 5. Manual notebook order

The notebooks can also be run manually in this order:

```text
01_data_understanding.ipynb
02_data_cleaning.ipynb
03_eda_business_analysis.ipynb
04_sql_business_analysis.ipynb
05_modeling_low_review_risk.ipynb
06_seller_logistics_lift_analysis.ipynb
```

The second notebook generates the processed analytical tables. The fourth notebook creates a local DuckDB database at `data/database/olist.duckdb`.

## SQL Layer

DuckDB is used as an embedded local database. No separate database application is required.

The SQL files answer reusable business questions:

- `01_business_kpis.sql`: executive KPI summary
- `02_growth_analysis.sql`: monthly gross payment volume, orders, average payment value, and month-over-month growth
- `03_delivery_experience.sql`: delivery delay buckets and review risk
- `04_category_region_analysis.sql`: category and state performance
- `05_customer_review_risk.sql`: high-risk order segments

## Project Limitations

- The dataset is historical and covers 2016 to 2018.
- The low-review model uses post-delivery features such as actual delivery days, so it is best suited for post-delivery recovery or operational review.
- A purchase-time risk model would require a separate feature set excluding actual delivery outcomes.
- `payment_total` includes both product value and freight, so I treat it as gross payment volume rather than merchandise-only GMV.
- The analysis is observational and should not be interpreted as causal proof.

## Recommended Next Steps

- Build a Streamlit or Power BI dashboard from `orders_analysis_base.csv`.
- Build a separate purchase-time version of the low-review risk model.
- Add cohort analysis or repeat-customer behavior proxies to strengthen the growth analysis.
- Add seller-level time-series monitoring.
- Add exact route or carrier-level features if operational data becomes available.
- Move more repeated notebook logic into reusable Python modules under `src/`.
