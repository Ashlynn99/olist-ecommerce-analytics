-- Identify order segments with high low-review risk.

WITH risk_base AS (
    SELECT
        order_id,
        main_product_category,
        customer_state,
        primary_payment_type,
        payment_total,
        freight_share_of_payment,
        delivery_days,
        delivery_delta_days,
        is_low_review,
        CASE
            WHEN delivery_delta_days <= 0 THEN 'on_time_or_early'
            WHEN delivery_delta_days <= 7 THEN 'late_1_to_7_days'
            ELSE 'late_8_plus_days'
        END AS delay_segment,
        CASE
            WHEN freight_share_of_payment < 0.10 THEN 'low_freight_share'
            WHEN freight_share_of_payment < 0.25 THEN 'medium_freight_share'
            ELSE 'high_freight_share'
        END AS freight_segment
    FROM orders_analysis_base
    WHERE is_delivered
      AND review_score_mean IS NOT NULL
      AND payment_total IS NOT NULL
)

SELECT
    delay_segment,
    freight_segment,
    COUNT(*) AS orders,
    ROUND(AVG(payment_total), 2) AS aov,
    ROUND(AVG(delivery_days), 2) AS avg_delivery_days,
    ROUND(AVG(CAST(is_low_review AS INTEGER)), 4) AS low_review_rate
FROM risk_base
GROUP BY delay_segment, freight_segment
HAVING COUNT(*) >= 100
ORDER BY low_review_rate DESC, orders DESC;
