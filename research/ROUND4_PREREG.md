# Round 4 pre-registration: per-alert confidence score for the Explosive-Scanner (frozen 2026-11-06, before any score-vs-outcome result)

Follows the project's alert-confidence design (setup + execution, reported separately, tiers A-D). F2 (2024-01..2026-07) stays sealed.

## Score definition (frozen)
n = number of SIGNAL screens firing on the alert date (A3, A2, B3, R2a, R2b), 1..5.
* setup = min(100, 25*n)
* liq = 1.0 if dv50p >= $20M, 0.75 if >= $5M, 0.50 if >= $2M; px = 1.0 if close >= $5 else 0.60; fresh = 1 if the data's last session is the latest completed session else 0.
* execution = 100 * mean(liq, px, fresh)  (purely mechanical: cost tier and data validity; it makes NO claim about returns)
* score = 0.35*setup + 0.65*execution IF the setup factor validates (below), else score = execution only (setup weight 0, as for Sniper and the IBS bots).
* caps: fresh = 0 -> score <= 49; merger/tender filing within 90 days -> score <= 69 (tier C max). Offering filing and 8-K item 3.02 are displayed warnings with no cap (weaker evidence).
* tiers: A 85-100, B 70-84, C 50-69, D <50 (actionability, not expected profit).

## Validation (episodes = first flag after a 20-session cooldown, as in the backtest)
* V1 (decides shipping): AUC of n for E50 (max close within 63 sessions >= +50%); derive on D2 (2019-01..2021-09), confirm on V2 (2022-01..2023-09); 95% month-cluster bootstrap (1,000 draws, seed 20261106). Setup factor ships only if BOTH lower bounds > 0.5.
* V2: same AUC against net-of-cost positive return under rule X (xnet > 0).
* V3: AUC of the execution score for E50 and xnet>0 (reported; expected not to predict).
* V4: AUC of the final score for E50 and xnet>0 on V2; "predictive" label only if the lower bound > 0.5.
* V5: hit rate of E50 by n (1, 2, 3+) on D2, V2 and pooled with Wilson 95% CIs; the odds line shown in alerts is the pooled rate for the alert's bucket.
* V6: merger/tender filing in the last 90 days: E50 rate and xnet vs other alerts on V2 (reported; the cap stays on mechanism + D3 evidence unless V2 contradicts it clearly: lift > 1.2 with lower CI > 1).
