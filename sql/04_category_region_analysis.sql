-- Category performance with gross payment volume and experience metrics.

SELECT
    main_product_category,
    orders,
    ROUND(gross_payment_volume, 2) AS gross_payment_volume,
    ROUND(avg_payment_value, 2) AS avg_payment_value,
    ROUND(freight_share, 4) AS freight_share,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    ROUND(late_rate, 4) AS late_rate,
    ROUND(avg_review_score, 2) AS avg_review_score,
    ROUND(low_review_rate, 4) AS low_review_rate
FROM v_category_summary
WHERE orders >= 300
ORDER BY gross_payment_volume DESC
LIMIT 20;

-- Customer state performance.

SELECT
    customer_state,
    orders,
    ROUND(gross_payment_volume, 2) AS gross_payment_volume,
    ROUND(avg_payment_value, 2) AS avg_payment_value,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    ROUND(late_rate, 4) AS late_rate,
    ROUND(avg_review_score, 2) AS avg_review_score,
    ROUND(low_review_rate, 4) AS low_review_rate
FROM v_state_summary
ORDER BY gross_payment_volume DESC
LIMIT 20;
