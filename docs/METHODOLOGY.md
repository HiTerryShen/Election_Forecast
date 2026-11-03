# Methodology

## 1. Order of operations (every race)

1. **Fundamentals** → expected Democratic margin (points)
2. **Polls** blended in → updated margin
3. **Simulation** (20,000 correlated elections) → model win probability
4. **Kalshi blend** (log-odds, after long-shot correction) → final win probability
5. **Scenario shift** (+2.5 / 0 / −2.5 points of margin), applied after the blend
6. **Pick rule** (25% underdog floor + expected points), run on the shifted probabilities

## 2. Fundamentals

House:

    margin = national + 1.73 + 1.02·lean + 1.77·inc + 1.08·(inc × redrawn) + prior_adj

Senate (fixed weights):

    margin = national + 0.85·lean + 3·inc + prior_adj

- `national` = generic ballot D+9.0 × 0.85 discount = D+7.65
- `lean` = Cook PVI × 2 (PVI is a vote-share gap; we model margins)
- `inc` = +1 Democratic incumbent running, −1 Republican, 0 open seat

The fitted coefficients come from Huber robust regression on 2022 + 2024 contested House races (740).
2022 rows from states redrawn before 2024 are excluded, since they can't be matched to 2024-lines presidential data.
Incumbency in 2024 is detected by whether the 2022 winner appears on the 2024 ballot.

| Out-of-sample (10-fold CV grouped by state) | Winners called | RMSE (margin pts) | Log loss (bits) |
|---|---|---|---|
| Fitted weights | 96.5% | 7.3 | 0.155 |
| Guessed weights (lean + 4·inc) | 95.4% | 7.5 | 0.164 |

### 2026 adjustments (`prior_adj`, prior weights in `config.PRIOR_WEIGHTS`)

| Factor | Weight |
|---|---|
| Division CPI minus national CPI (3.7%), × president's party sign | 0.8 D per point |
| State gas % change since Feb 18 (pre-war) minus national change | 0.05 D per % |
| Veteran share deviation × war unpopularity | 0.10 |
| Military base × war unpopularity | 0.5 |
| Share 65+ deviation (health salience) | 0.10 |
| Candidate net-favorability gap | 0.25 |
| log(D receipts / R receipts) | 1.0 |

## 3. Polls

- Each poll's weight = exp(−age/21 days) × √(n/600) × voter screen (LV 1.0, RV 0.8, adults 0.5).
- Repeated releases from one pollster are down-weighted.
- Campaign- or party-sponsored polls are shifted 4 points against the sponsor and get half weight.
- Margin = w·poll + (1−w)·fundamentals, where w = n_eff / (n_eff + K), with K = 3 for the Senate and 4 for the House.
- Race SD shrinks toward a 3.5-point poll error as w grows.

## 4. Simulation

Each simulation adds three errors:

- national: SD 3 points, shared by every race
- state: SD 2, shared within a state
- race: from the backtest residuals (about 5 points), drawn from a t-distribution with 5 df for fat tails

## 5. Kalshi blend

    q = logistic( w · logit(q_model) + (1 − w) · 1.2 · logit(p_kalshi) )

- The model weight w is 0.65 where polls exist, 0.50 for other House races and 0.40 for other Senate races.
- The 1.2 factor corrects the favorite–longshot bias. It was fitted by maximum likelihood on 41 real Kalshi 2024 races (MLE 1.25; bootstrap 80% range 0.85–2.0).
- Each race's simulated margins are shifted so P(D side wins) = q. This preserves the correlation structure.
- Where the leading non-Republican is an independent (e.g., NE, MT), that candidate is the "D side".

## 6. Pick rule

For each race:

1. Start with our predicted winner (higher q).
2. Switch to another candidate only if their q ≥ 0.25 **and** q × −log₂(raw Kalshi price) exceeds the predicted winner's.

Points always use the raw Kalshi price, which is what judges score.

## 7. Pick-strategy backtests

**Real Kalshi 2024 prices, 41 races** (`backtest_kalshi2024.py`), using Kalshi's own odds as probabilities:

| Strategy | Underdog picks / won | Actual score |
|---|---|---|
| Always favorite | 0 | 14.9 |
| Underdog if ≥30% | 19 / 5 | 10.9 |
| Underdog if ≥20% | 30 / 8 | 14.1 |
| Underdog if ≥10% | 33 / 8 | 13.4 |
| Underdog if ≥5% | 35 / 8 | 13.2 |

- Underdogs priced under 20% went 0 for 11.
- Favorites won 80% of the time when priced at about 71%.
- On the 23 House races where our 2024 model could be added, the 50/50 model + Kalshi blend with a 30% floor scored 16.9 (6 of 8 underdogs won), vs 10.5 for favorites.

**Stand-in market, 2022/2024 House** (`backtest_strategies.py`): long shots beat favorites in both years.
This stand-in market lacked the long-shot bias, so the real-Kalshi test takes precedence.

**Polls on/off (2026):** removing polls changes 3 of 29 polled-race picks. The with-polls pick list has
higher expected points whether Kalshi, the polls or either model version turns out right, so polls stay in.
