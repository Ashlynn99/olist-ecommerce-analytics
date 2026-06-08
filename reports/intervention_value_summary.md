# Intervention Cost and Expected-Value Simulation

## Objective

I translated the purchase-time and post-delivery low-review risk rankings into intervention-capacity and value scenarios.

This is a retrospective scenario simulation, not a measured causal impact study. The model identifies historical low-review risk, while intervention effectiveness and recovery value are explicit assumptions that should be validated through a controlled experiment.

## Base-Case Assumptions

| Strategy | Cost per Contact | Assumed Effectiveness | Value per Successful Recovery |
|---|---:|---:|---:|
| Purchase-time prevention | 3 BRL | 15% | 75 BRL |
| Post-delivery recovery | 12 BRL | 35% | 75 BRL |

The purchase-time action represents a lower-cost automated communication or operational escalation. The post-delivery action represents a higher-cost human support or service-recovery workflow.

## Recommended Base-Case Strategies

| Strategy | Risk Coverage | Orders Contacted | Low Reviews Captured | Expected Net Value | Incremental Value vs Random | ROI | Break-Even Effectiveness |
|---|---:|---:|---:|---:|---:|---:|---:|
| Purchase-time prevention | 5% | 2,624 | 13.4% | 2,759 BRL | 6,678 BRL | 35.1% | 11.1% |
| Post-delivery recovery | 5% | 2,624 | 25.3% | 15,158 BRL | 37,421 BRL | 48.1% | 23.6% |

## Interpretation

- The recommended coverage is the tested risk segment with the highest expected net value under the base assumptions.
- Incremental value versus random isolates the benefit of using the model ranking instead of contacting the same number of randomly selected orders.
- Purchase-time prevention is cheaper and can act earlier, but the model's lower precision limits the economically attractive coverage range.
- Post-delivery recovery is more expensive per order, but its stronger risk concentration supports higher expected net value.
- The sensitivity analysis shows when either strategy becomes unprofitable as cost rises or effectiveness falls.
- Under the conservative assumptions, neither tested strategy produces positive net value; the economically appropriate decision would be not to launch until assumptions improve or a pilot demonstrates stronger effects.

## Decision Boundary

These values should not be presented as realized savings. A production decision should begin with a randomized pilot that measures actual intervention effectiveness, customer response, cost per contact, and longer-term customer value. The scenario model can then be updated with experimentally observed parameters.
