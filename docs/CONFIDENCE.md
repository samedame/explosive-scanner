# Alert score: what it is, and the validation (pre-registered 2026-11-06, `prereg/ROUND4_PREREG.md`)

Each alert shows **Odds** (the historical hit rate for alerts like it) and **Tradeability X/100 (tier A-D)**. It is called tradeability, not confidence, on purpose: validation showed the score does not rank explosions.

## What was tested (episodes with a 20-session cooldown; 2,622 in 2019-21, 1,758 in 2022-23; sealed 2024-26 window untouched)
| Score | Target | 2019-21 AUC (95% CI) | 2022-23 AUC (95% CI) | Verdict |
|---|---|---|---|---|
| Setup = # of screens firing | +50% within 63 sessions | 0.515 (0.497-0.532) | 0.536 (0.511-0.568) | **Fails** the rule (both lower bounds must exceed 0.5). Not scored. |
| Setup | positive net return | 0.499 (0.489-0.510) | 0.506 (0.499-0.513) | none |
| Execution (liquidity, price, freshness) | +50% within 63 sessions | **0.374** (0.336-0.403) | **0.376** (0.325-0.424) | Anti-correlated: liquid names explode less. |
| Execution | positive net return | 0.560 (0.531-0.594) | 0.534 (0.503-0.562) | Weakly positive: cheaper-to-trade names keep more of what they make. |

An AUC of 0.5 is a coin flip. So the shipped score (execution only, setup weight 0) is an **actionability and cost rank**, with a small genuine link to net results, and the opposite of a forecast of explosions. That is why every alert prints the odds line next to it.

## The odds line (pooled 2019-2023 episodes)
| Screens firing | Alerts | Gained +50% in 63 sessions (95% CI) | 2019-21 | 2022-23 |
|---|---|---|---|---|
| 1 | 4,153 | 10.3% (9.4-11.3%) | 13.6% | 5.4% |
| 2 or more | 227 | 18.1% (13.6-23.6%) | 20% | 14% (n=85) |

The base rate fell from 14% to 6% between the two periods, so treat the pooled number as a generous upper estimate.

## Warnings
* **MERGER/TENDER filing (90 days)**: caps the tier at C. In 2022-23, 1 of 47 such alerts gained +50% (2%) vs 6% for the rest; discovery lift was 0.6x. The sample is small; the cap stays because the mechanism (a pending deal pins the price) is sound and the data did not contradict it.
* Offering filing: shown as information only. History is mixed (0.94x lift in discovery, 9.6% vs 5.2% hit rate in 2022-23).
* 8-K item 3.02 (equity sale): information only, too few cases (31).
* Stale data (not the latest session): caps at tier D.

## Limits
Backtest, not live. Scores for names whose SEC fields could not be fetched omit the SEC warnings (it never says "none" when it does not know). The forward scorecard will re-test the odds line out of sample once there are about 150 alerts.
