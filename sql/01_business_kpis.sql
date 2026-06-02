-- Overall executive KPIs for the Olist marketplace.

SELECT
    COUNT(*) AS total_orders,
    SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) AS delivered_orders,
    ROUND(SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 4) AS delivery_rate,
    ROUND(SUM(payment_total), 2) AS gross_payment_volume,
    ROUND(AVG(payment_total), 2) AS avg_payment_value,
    ROUND(SUM(product_total), 2) AS product_total,
    ROUND(SUM(freight_total), 2) AS freight_total,
    ROUND(SUM(freight_total) / NULLIF(SUM(payment_total), 0), 4) AS freight_share,
    ROUND(AVG(CASE WHEN is_delivered THEN delivery_days END), 2) AS avg_delivery_days,
    ROUND(AVG(CASE WHEN is_delivered THEN CAST(is_late AS INTEGER) END), 4) AS late_rate,
    ROUND(AVG(review_score_mean), 2) AS avg_review_score,
    ROUND(AVG(CAST(is_low_review AS INTEGER)), 4) AS low_review_rate
FROM orders_analysis_base;
