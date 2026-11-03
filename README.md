# Election_Forecast: 2026 U.S. House & Senate

A forecast of all **470 races** on November 3, 2026 (435 House + 35 Senate, including the Ohio and Florida
specials), built for a Stanford prediction competition. It combines a fundamentals regression, poll aggregation,
a prediction-market blend and correlated Monte Carlo simulation, then picks one candidate per race to maximize the
competition's score.

**Final submission:** [`results/FINAL_PICKS_2026.csv`](results/FINAL_PICKS_2026.csv) (neutral scenario).
Full detail is in [`results/PREDICTIONS_2026.xlsx`](results/PREDICTIONS_2026.xlsx).

## Headline forecast (neutral scenario, as of Nov 2, 2026)

| Chamber | Democratic seats (80% range) | P(Democratic control) |
|---|---|---|
| House | 242 (223–262) | 96% |
| Senate | 51.5 (48–55) | 65% |

| Scenario | House D seats | P(D House) | Senate D seats | P(D Senate) |
|---|---|---|---|---|
| D+2.5 | 255 | 99% | 53.3 | 86% |
| **Neutral (submitted)** | **242** | **96%** | **51.5** | **65%** |
| R+2.5 | 230 | 82% | 49.9 | 39% |

## Scoring rule we optimize

A correct pick scores **−log₂(P)**, where P is the picked candidate's **Kalshi price on Nov 1, 2026**
(floored at 0.01, so 6.64 points max); a wrong pick scores 0. Our own probabilities are never scored, only
used to choose. The expected points of a pick are therefore q × −log₂(p), where q is our win probability and
p is Kalshi's price.

## How it works

1. **Fundamentals regression:** expected Democratic margin = national environment (generic ballot D+9 × 0.85)
   + 1.02 × partisan lean (Cook PVI × 2) + 1.77 × incumbency + a redistricting term (incumbent on redrawn turf).
   - Weights are fitted by robust (Huber) regression on 740 contested 2022–2024 House races.
   - They are validated with 10-fold cross-validation grouped by state. Fitted weights call 96.5% of winners, vs 95.4% for hand-guessed weights.
2. **2026-specific adjustments** (prior weights, since no past election can fit them):
   - Census-division CPI above the national rate (hurts the president's party)
   - state gas-price rise since the Iran war began
   - veteran share × war unpopularity
   - senior share
   - fundraising ratio
3. **Poll aggregation:**
   - 98 polls in 29 races, weighted by recency, sample size and voter screen.
   - Partisan-sponsored polls are shifted 4 points against the sponsor and given half weight.
   - The poll average is blended with fundamentals by poll volume.
4. **Market blend:** combined with Kalshi's implied odds in log-odds (model weight 40–65%). Kalshi is first corrected for the
   favorite–longshot bias (×1.2 in log-odds, fitted on real Kalshi 2024 races).
5. **Simulation:** 20,000 correlated elections (national, state and race-level error) give win probabilities
   and 80% margin ranges.
6. **Scenarios:** every race is shifted ±2.5 points *after* the blend and *before* picking.
7. **Pick rule:** pick our predicted winner, unless the other candidate has **≥25%** win probability in our model
   **and** higher expected points. This yields 32 Kalshi-underdog picks.

Why a 25% floor: on **real Kalshi 2024 prices** (41 races), always taking the favorite scored 14.9. Taking every
underdog ≥10% scored 13.4. Underdogs priced under 20% went 0 for 11. Underdog picks paid only where our model
disagreed with the market. See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Repository layout

```
src/
  config.py               every tunable number (UNDERDOG_FLOOR, LONGSHOT_K, MODEL_WEIGHT, scenarios, ...)
  load_data.py            input loaders + race-ID normalization
  model.py                backtest, 2026 features, poll averaging
  forecast.py             simulation, market blend, pick rules, score simulation
  run.py                  main pipeline -> results/
  make_predictions.py     builds PREDICTIONS_2026.xlsx/.csv and FINAL_PICKS_2026.csv
  backtest_strategies.py  pick-rule test vs a stand-in market, 2022/2024
  backtest_kalshi2024.py  pick-rule test on real Kalshi 2024 prices
  make_synthetic.py       fake data for pipeline testing only
data/                     inputs (see Data sources)
results/                  outputs (forecasts, picks, backtests)
docs/                     methodology + data-collection notes
```

## Reproduce

```bash
pip install -r requirements.txt
cd src
python run.py --data ../data --out ../results          # forecasts + picks (~30 s)
python make_predictions.py --results ../results        # submission files
python backtest_strategies.py                          # optional: stand-in market backtest
python backtest_kalshi2024.py --kalshi ../data/kalshi_2024_congress_prices.csv   # optional: real Kalshi backtest
```

Results are deterministic (fixed random seed).

## Data sources

| File | Contents | Source |
|---|---|---|
| `kalshi_prices.csv` | Nov 1, 2026 prices, all 470 races | Kalshi public market-data API |
| `kalshi_2024_congress_prices.csv` | Nov 3, 2024 prices + winners, 41 races | Kalshi historical API; MIT Election Lab |
| `races_2026.csv` | candidates, incumbents, Cook ratings | state candidate lists (via DeepSyte), Cook Political Report |
| `cook_pvi.csv` | district + state PVI (incl. 2026 redraws) | Cook Political Report |
| `pres_by_district.csv` | 2020/2024 presidential results, old + new lines | The Downballot |
| `redistricting_2026.csv` | maps in effect for 2026 | U.S. Census Bureau, NCSL |
| `house_results_history.csv` | 2022 + 2024 House results | MIT Election Data + Science Lab (doi:10.7910/DVN/IG0UN2) |
| `polls.csv` | 98 polls, Sept–Oct 2026 | Polling Forecast feed + linked pollster sources |
| `regional_prices.csv` | Sept 2026 CPI by region/division/metro; state gas prices | BLS; AAA |
| `fundraising.csv` | FEC receipts (partial) | FEC |

Per-row source URLs are inside each CSV. Collection notes: [`docs/DATA_COLLECTION_NOTES.md`](docs/DATA_COLLECTION_NOTES.md).

## Limitations

- A single national polling error moves every race together. Many value picks are Republicans in races where polls lean Democratic.
- The pick-rule calibration rests on 41 real Kalshi 2024 races, a small sample.
- 2026-specific factor weights are judgment calls (capped at about ±2 points of margin).
- Census age/race/income variables are coded but not populated: the Census API now needs a key.
  Add `data/acs_2024.json` and `data/acs_2019.json`, then rerun.
- Same-party California runoffs and minor candidates use Kalshi's price (no model edge).
