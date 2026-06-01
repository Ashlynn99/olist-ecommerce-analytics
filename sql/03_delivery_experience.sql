-- Delivery timing buckets and their relationship with review risk.

WITH delivered_reviews AS (
    SELECT
        order_id,
        delivery_days,
        delivery_delta_days,
        review_score_mean,
        is_low_review,
        CASE
            WHEN delivery_delta_days <= -7 THEN '7+ days early'
            WHEN delivery_delta_days <= 0 THEN 'On time/early'
            WHEN delivery_delta_days <= 3 THEN '1-3 days late'
            WHEN delivery_delta_days <= 7 THEN '4-7 days late'
            WHEN delivery_delta_days <= 14 THEN '8-14 days late'
            ELSE '15+ days late'
        END AS delivery_bucket
    FROM orders_analysis_base
    WHERE is_delivered
      AND delivery_delta_days IS NOT NULL
      AND review_score_mean IS NOT NULL
)

SELECT
    delivery_bucket,
    COUNT(*) AS orders,
    ROUND(AVG(delivery_days), 2) AS avg_delivery_days,
    ROUND(AVG(delivery_delta_days), 2) AS avg_delivery_delta_days,
    ROUND(AVG(review_score_mean), 2) AS avg_review_score,
    ROUND(AVG(CAST(is_low_review AS INTEGER)), 4) AS low_review_rate
FROM delivered_reviews
GROUP BY delivery_bucket
ORDER BY
    CASE delivery_bucket
        WHEN '7+ days early' THEN 1
        WHEN 'On time/early' THEN 2
        WHEN '1-3 days late' THEN 3
        WHEN '4-7 days late' THEN 4
        WHEN '8-14 days late' THEN 5
        WHEN '15+ days late' THEN 6
    END;
