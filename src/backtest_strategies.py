"""Retrospective test of pick strategies on the 2024 (and 2022) House elections.

We have no 2024 Kalshi prices, so we build a PSEUDO-MARKET from information available
before each election: 2020 presidential lean, incumbency, and the final generic-ballot
polling average. Its probabilities play the role of Kalshi prices, and also of our q
(no edge over the market), so the test answers one question:

    Against a reasonable pre-election market, would taking underdogs have paid,
    given what actually happened?

Strategies: always the favorite, or take the underdog whenever its probability is at
least a floor (30% / 20% / 10% ~ our 80%-margin rule / 5% ~ max EV).
Scoring: -log2(price of pick) if correct, else 0 (prices clipped to [0.01, 0.99]).

    python backtest_strategies.py --data ../data --out ../results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
import model as M
from load_data import load_all

# Final generic-ballot polling averages (D minus R). 2024: RCP R+0.3 (47.0-46.7).
# 2022: RCP about R+2.5 (approximate, from memory; 538 was about R+1.2).
FINAL_GENERIC = {2024: -0.3, 2022: -2.5}
INC_PRIOR = 2.0            # incumbency, points of margin per side (pre-specified, not fit on the test year)
FLOORS = {"favorite_only": None, "dog_if_>=30%": 0.30, "dog_if_>=20%": 0.20,
          "dog_if_>=10% (~80% margin rule)": 0.10, "dog_if_>=5% (~max EV)": 0.05}


def pseudo_market(test: pd.DataFrame, train: pd.DataFrame, nat: float, sd_race: float, seed=1) -> np.ndarray:
    fit = M.fit(train)
    b = fit.params
    mu = nat + b["const"] + b["lean"] * test["lean"].values + INC_PRIOR * test["inc"].values
    rng = np.random.default_rng(seed)
    n = 20000
    states = test["state"].unique()
    si = test["state"].map({s: i for i, s in enumerate(states)}).values
    sims = (mu[None, :] + rng.normal(0, C.NATIONAL_SD, (n, 1))
            + rng.normal(0, C.REGIONAL_SD, (n, len(states)))[:, si]
            + rng.standard_t(5, (n, len(test))) / np.sqrt(5 / 3) * sd_race)
    q = (sims > 0).mean(axis=0)
    return np.round(np.clip(q, 0.01, 0.99), 2), sims > 0       # market-style cents


def score(q_d: np.ndarray, d_won: np.ndarray, floor):
    """Pick per race; return points earned (actual) and expected points."""
    fav_is_d = q_d >= 0.5
    q_dog = np.where(fav_is_d, 1 - q_d, q_d)
    take_dog = np.zeros_like(fav_is_d) if floor is None else (q_dog >= floor)
    pick_d = np.where(take_dog, ~fav_is_d, fav_is_d)
    p_pick = np.where(pick_d, q_d, 1 - q_d)
    pts = -np.log2(np.clip(p_pick, C.PRICE_FLOOR, C.PRICE_CEIL))
    right = pick_d == d_won
    return pts, right, take_dog, p_pick


def run(data_dir, out_dir):
    data = load_all(data_dir)
    t = M.build_training(data)
    rows, detail = [], []
    for year, other in [(2024, 2022), (2022, 2024)]:
        test, train = t[t["year"] == year].copy(), t[t["year"] == other]
        if year == 2022:
            test["inc"] = 0          # 2022 incumbency not in our data (lines changed)
        q_d, sim_dwin = pseudo_market(test, train, FINAL_GENERIC[year], 4.84)
        d_won = test["dem_margin"].values > 0
        for name, fl in FLOORS.items():
            pts, right, dog, p_pick = score(q_d, d_won, fl)
            actual = float((pts * right).sum())
            # expected score if the pseudo-market were exactly calibrated, + spread across simulated elections
            sim_scores = (pts[None, :] * (np.where(np.where(dog, ~(q_d >= .5), q_d >= .5)[None, :], sim_dwin, ~sim_dwin))).sum(axis=1)
            rows.append({
                "year": year, "strategy": name, "races": len(test),
                "underdog_picks": int(dog.sum()), "underdogs_won": int((dog & right).sum()),
                "picks_correct": int(right.sum()), "actual_score": round(actual, 1),
                "expected_score": round(float(sim_scores.mean()), 1),
                "sim_p10": round(float(np.percentile(sim_scores, 10)), 1),
                "sim_p90": round(float(np.percentile(sim_scores, 90)), 1),
            })
        # calibration of the pseudo-market by bucket (did 20% underdogs win ~20% of the time?)
        q_dog = np.where(q_d >= .5, 1 - q_d, q_d)
        dog_won = np.where(q_d >= .5, ~d_won, d_won)
        bins = pd.cut(q_dog, [0, .05, .10, .20, .30, .40, .50], include_lowest=True)
        cal = pd.DataFrame({"bucket": bins, "q": q_dog, "won": dog_won}).groupby("bucket", observed=True).agg(
            races=("won", "size"), avg_market_prob=("q", "mean"), underdog_win_rate=("won", "mean"))
        cal.insert(0, "year", year)
        detail.append(cal.reset_index())
    res = pd.DataFrame(rows)
    cal = pd.concat(detail)
    out = Path(out_dir)
    res.to_csv(out / "backtest_strategies.csv", index=False)
    cal.to_csv(out / "backtest_calibration.csv", index=False)
    pd.set_option("display.width", 200)
    print(res.to_string(index=False))
    print("\nUnderdog calibration (pseudo-market):")
    print(cal.round(3).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data")
    ap.add_argument("--out", default="../results")
    a = ap.parse_args()
    run(a.data, a.out)
