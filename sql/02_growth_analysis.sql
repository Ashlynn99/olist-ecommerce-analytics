-- Monthly order, GMV, AOV, and month-over-month growth.

WITH monthly AS (
    SELECT
        purchase_month,
        COUNT(*) AS orders,
        SUM(payment_total) AS gmv,
        AVG(payment_total) AS aov
    FROM orders_analysis_base
    WHERE payment_total IS NOT NULL
    GROUP BY purchase_month
)

SELECT
    purchase_month,
    orders,
    ROUND(gmv, 2) AS gmv,
    ROUND(aov, 2) AS aov,
    ROUND((orders - LAG(orders) OVER (ORDER BY purchase_month)) * 1.0
        / NULLIF(LAG(orders) OVER (ORDER BY purchase_month), 0), 4) AS orders_mom_growth,
    ROUND((gmv - LAG(gmv) OVER (ORDER BY purchase_month))
        / NULLIF(LAG(gmv) OVER (ORDER BY purchase_month), 0), 4) AS gmv_mom_growth
FROM monthly
ORDER BY purchase_month;
