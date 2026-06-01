-- Category performance with revenue and experience metrics.

SELECT
    main_product_category,
    orders,
    ROUND(gmv, 2) AS gmv,
    ROUND(aov, 2) AS aov,
    ROUND(freight_share, 4) AS freight_share,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    ROUND(late_rate, 4) AS late_rate,
    ROUND(avg_review_score, 2) AS avg_review_score,
    ROUND(low_review_rate, 4) AS low_review_rate
FROM v_category_summary
WHERE orders >= 300
ORDER BY gmv DESC
LIMIT 20;

-- Customer state performance.

SELECT
    customer_state,
    orders,
    ROUND(gmv, 2) AS gmv,
    ROUND(aov, 2) AS aov,
    ROUND(avg_delivery_days, 2) AS avg_delivery_days,
    ROUND(late_rate, 4) AS late_rate,
    ROUND(avg_review_score, 2) AS avg_review_score,
    ROUND(low_review_rate, 4) AS low_review_rate
FROM v_state_summary
ORDER BY gmv DESC
LIMIT 20;
