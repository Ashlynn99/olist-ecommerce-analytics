# Cohort and Observed Repeat-Purchase Analysis

## Scope

I analyzed delivered orders using `customer_unique_id` to measure observed repeat-purchase behavior.

The dataset covers a limited historical window, so these metrics should not be interpreted as true
long-term retention. To reduce right-censoring, the primary comparison uses a fixed 90-day repeat
window and only includes customers whose first purchase occurred at least 90 days before the final
observed order date.

## Main Results

| Metric | Value |
|---|---:|
| Customers with delivered orders | 93,358 |
| Observed repeat customers | 2,801 |
| Observed repeat-customer rate | 3.0% |
| Customers eligible for 90-day analysis | 75,320 |
| 90-day repeat rate | 2.3% |
| Median days to second delivered order | 29 |

## First-Order Experience and Repeat Behavior

- First order on time: 2.3% repeated within 90 days
- First order late: 2.1% repeated within 90 days
- First order without a low review: 2.3% repeated within 90 days
- First order with a low review: 2.4% repeated within 90 days

These comparisons are descriptive and do not establish causality. Customer intent, category purchase
cycles, and other unobserved factors may affect both first-order experience and repeat behavior.

Among first-order categories with at least 300 eligible customers, the highest observed 90-day
repeat rate was `home_appliances` at 7.7%.

## Business Use

This analysis adds a customer-lifecycle view to the project. It can support onboarding-quality
monitoring, category-specific repeat-purchase strategy, and evaluation of whether poor first-order
experiences are associated with weaker observed repeat behavior.
