# Additional Analysis Summary

## 1. Seller Performance Scorecard

I built a seller scorecard to compare marketplace value with customer experience risk.

- High-value high-risk sellers: 35
- Orders associated with high-value high-risk sellers: 9,890

This segment is useful for marketplace operations because it highlights sellers that contribute
meaningful order volume while also creating higher customer dissatisfaction risk.

## 2. Logistics Distance and Cross-State Delivery

I estimated customer-seller distance using zip-code-level geolocation and compared same-state and
cross-state routes.

- Same-state seller-orders: 34,907
- Cross-state seller-orders: 61,767
- Same-state average delivery days: 7.91
- Cross-state average delivery days: 15.03
- Same-state low-review rate: 10.9%
- Cross-state low-review rate: 14.7%
- Longest distance bucket analyzed: 2500+ km, with average
  delivery days of 23.32

This adds context to the delivery-delay finding: longer and cross-state routes are slower and carry
higher review risk.

## 3. Model Lift and Business Simulation

I converted the post-delivery low-review model into a prioritization view for a limited customer
support team.

- Test ROC-AUC: 0.763
- Test PR-AUC: 0.446
- Top 10% highest-risk orders capture 41.7% of low reviews
- Top 10% segment precision: 55.8%
- Top 10% lift vs baseline: 4.17x
- Top 20% highest-risk orders capture 56.5% of low reviews

This makes the model easier to discuss in business terms: it shows how much low-review risk can be
covered if the team only reviews the riskiest delivered orders.

## Project Positioning

These additions keep the project focused while adding practical business depth:

1. Marketplace growth and revenue analysis
2. Seller performance monitoring
3. Logistics network performance
4. Customer satisfaction risk modeling
5. Operational prioritization through lift analysis
