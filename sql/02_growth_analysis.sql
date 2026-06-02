-- Monthly order, gross payment volume, average payment value, and month-over-month growth.

WITH monthly AS (
    SELECT
        purchase_month,
        COUNT(*) AS orders,
        SUM(payment_total) AS gross_payment_volume,
        AVG(payment_total) AS avg_payment_value
    FROM orders_analysis_base
    WHERE payment_total IS NOT NULL
    GROUP BY purchase_month
)

SELECT
    purchase_month,
    orders,
    ROUND(gross_payment_volume, 2) AS gross_payment_volume,
    ROUND(avg_payment_value, 2) AS avg_payment_value,
    ROUND((orders - LAG(orders) OVER (ORDER BY purchase_month)) * 1.0
        / NULLIF(LAG(orders) OVER (ORDER BY purchase_month), 0), 4) AS orders_mom_growth,
    ROUND((gross_payment_volume - LAG(gross_payment_volume) OVER (ORDER BY purchase_month))
        / NULLIF(LAG(gross_payment_volume) OVER (ORDER BY purchase_month), 0), 4) AS payment_volume_mom_growth
FROM monthly
ORDER BY purchase_month;
