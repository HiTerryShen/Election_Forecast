"""Global settings for the 2026 forecast. Edit numbers here, not in the code.

Margins are always Democratic two-party margin in points (D% - R%), so +5 = D+5.
"""

# ---------------------------------------------------------------------------
# National environment (sourced via web search, Nov 1 2026 — verify before submitting)
# ---------------------------------------------------------------------------
# Generic ballot averages late Oct 2026: Silver Bulletin D+9.1 (LV, 10/28),
# DDHQ D+8.9 (10/30), FiftyPlusOne D+9 (10/31), RCP D+8.4, CNN 52-43.
GENERIC_BALLOT_2026 = 9.0

# Polls have historically overstated the out-party edge slightly; the backtest
# learns how national House vote maps to district margins, so we convert the
# generic ballot to an expected national House vote with a discount.
GENERIC_BALLOT_DISCOUNT = 0.85          # expected national House margin = 0.85 * 9.0 ≈ D+7.7

# National House popular-vote margins (D minus R, two-party-ish, points).
# Used as the "national environment" feature in the multi-cycle backtest.
NATIONAL_HOUSE_MARGIN = {
    2018: 8.6,
    2020: 3.1,
    2022: -2.8,
    2024: -2.7,
}
# Presidential party in each cycle (for "punish the president's party" interactions)
PRESIDENT_PARTY = {2018: "R", 2020: "R", 2022: "D", 2024: "D", 2026: "R"}

# National CPI y/y (Sept 2026, BLS, NSA): 3.7%. Regional: NE 4.2, MW 4.2, W 3.4, South pending.
NATIONAL_CPI_YOY_2026 = 3.7

# Iran war: Silver Bulletin support ~36 / oppose ~57 (10/28); Pew: 65% disapprove of Trump's handling.
IRAN_WAR_NET_SUPPORT = 36 - 57          # -21

# ---------------------------------------------------------------------------
# Scenarios (Terry's spec: D-shift, neutral, R-shift)
# ---------------------------------------------------------------------------
SCENARIOS = {"D_plus": +2.5, "neutral": 0.0, "R_plus": -2.5}

# ---------------------------------------------------------------------------
# Uncertainty (points of margin). Backtest overwrites DISTRICT_SD with the
# out-of-sample residual SD; these are fallbacks / priors.
# ---------------------------------------------------------------------------
NATIONAL_SD = 3.0      # shared error across every race (polling miss)
REGIONAL_SD = 2.0      # shared within a state
DISTRICT_SD = 5.0      # race-specific
SENATE_EXTRA_SD = 1.5  # Senate races are more candidate-driven
N_SIMS = 20000
RANDOM_SEED = 2026

# ---------------------------------------------------------------------------
# PRIOR (guessed) weights for 2026-only factors that 2018-24 data can't fit.
# Units: points of D margin per unit of the feature. Partners can tune these.
# ---------------------------------------------------------------------------
PRIOR_WEIGHTS = {
    # Regional inflation above national (pp), punishes president's party (R in 2026)
    "cpi_excess_x_pres": 0.8,          # +1pp above national CPI -> +0.8 D
    # Gas price % change since pre-war, punishes president's party
    "gas_change_pct_x_pres": 0.05,     # +20% gas -> +1.0 D
    # Veteran share deviation (pp) x war unpopularity, hurts R slightly
    "veteran_x_war": 0.10,
    # Military base in district x war (deployment/family exposure)
    "base_x_war": 0.5,
    # Seniors share deviation (pp) x Medicare/health salience (2026: ACA subsidy fight)
    "age65_x_health": 0.10,
    # Candidate net favorability difference (D net fav - R net fav), points
    "net_fav_diff": 0.25,
    # log(D receipts / R receipts)
    "log_fundraising_ratio": 1.0,
}

# How much to trust race polls vs fundamentals: poll_weight = n_polls / (n_polls + POLL_K)
POLL_K = {"Senate": 3.0, "House": 4.0}
POLL_HOUSE_EFFECT_SD = 3.5   # extra SD on a poll average

# Weight on OUR MODEL vs the Kalshi-implied probability, blended in log-odds.
# 1.0 = pure model, 0.0 = copy the market. The market prices candidate quality,
# scandals, money and private polling that fundamentals can't see.
# Races with real polls get more model weight (polls are in the model).
MODEL_WEIGHT = {"House": 0.5, "Senate": 0.4}
MODEL_WEIGHT_WITH_POLLS = 0.65

# ---------------------------------------------------------------------------
# Scoring: points = -log2(Kalshi price of our pick) if correct, else 0.
# ---------------------------------------------------------------------------
PRICE_FLOOR = 0.01
PRICE_CEIL = 0.99
# "safe" strategy: take the underdog only if our q exceeds Kalshi's p by this much
SAFE_EDGE = 0.10
# max_ev strategy: never pick a candidate our model gives less than this (tail probs are unreliable)
MIN_Q_FOR_PICK = 0.05
# Comparison strategy "margin_ev": maximize EV wherever an upset is inside our
# MARGIN_CI interval (~ any underdog we give >= 10%). Kept for comparison only.
MARGIN_CI = 0.80

# DEFAULT strategy ("floor_ev", the `pick` column): take the underdog ONLY if our
# blended probability for them is >= UNDERDOG_FLOOR and it earns more expected points;
# otherwise take our predicted winner. Why 25%: on REAL Kalshi 2024 prices, underdogs
# priced under 20% went 0 for 11 and favorites beat cheap long shots; underdog picks
# paid where our model disagreed with the market (50/50 blend, 30% floor: 6 of 8 hit).
UNDERDOG_FLOOR = 0.25
DEFAULT_STRATEGY = "floor_ev"

# Favorite-longshot bias: prediction markets overprice long shots. Before blending,
# Kalshi's implied probability is sharpened in log-odds by LONGSHOT_K
# (fit on 41 Kalshi 2024 races: MLE 1.25, bootstrap 80% range 0.85-2.0; we use 1.2).
# 10% -> ~7%, 25% -> ~21%. Scoring still uses the raw Kalshi price.
LONGSHOT_K = 1.2
