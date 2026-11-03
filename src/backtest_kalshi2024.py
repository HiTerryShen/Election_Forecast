"""Backtest pick strategies on REAL Kalshi 2024 prices (Nov 3, 2024 cutoff) vs actual winners.

A) Market-only: q = Kalshi's own implied probability (no model edge).
   Tests whether taking underdogs at real Kalshi prices paid off in 2024.
B) Model blend (House races only): our pre-election 2024 fundamentals forecast
   (fit on 2022, final generic ballot R+0.3), blended 50/50 with Kalshi in log-odds,
   exactly as the 2026 pipeline does.

    python backtest_kalshi2024.py --kalshi <csv> --data ../data --out ../results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
import model as M
from backtest_strategies import FINAL_GENERIC, pseudo_market
from load_data import load_all, race_id

FLOORS = {"favorite_only": None, "dog_if_>=30%": 0.30, "dog_if_>=20%": 0.20,
          "dog_if_>=10% (80% margin rule)": 0.10, "dog_if_>=5% (max EV)": 0.05}


def load_prices(path) -> pd.DataFrame:
    k = pd.read_csv(path)
    k["race_id"] = [race_id(s, d) for s, d in zip(k["state"], k["district"].astype(str).replace({"S": "S"}))]
    k.loc[k["chamber"] == "Senate", "race_id"] = k["state"] + "-S"
    piv = k.pivot_table(index=["race_id", "chamber"], columns="party", values="yes_price", aggfunc="first").reset_index()
    win = k.groupby("race_id")["winner_party"].first()
    piv["winner"] = piv["race_id"].map(win)
    # a missing side = complement of the other
    piv["D"] = piv["D"].fillna(1 - piv["R"])
    piv["R"] = piv["R"].fillna(1 - piv["D"])
    piv = piv.dropna(subset=["D", "R", "winner"])
    piv["p_d"] = piv["D"] / (piv["D"] + piv["R"])           # implied prob (vig removed)
    return piv


def evaluate(df: pd.DataFrame, q_col: str, label: str) -> list[dict]:
    rows = []
    q_d = df[q_col].values
    d_won = (df["winner"] == "D").values
    for name, fl in FLOORS.items():
        fav_d = q_d >= 0.5
        q_dog = np.where(fav_d, 1 - q_d, q_d)
        dog = np.zeros(len(df), bool) if fl is None else (q_dog >= fl)
        pick_d = np.where(dog, ~fav_d, fav_d)
        raw = np.where(pick_d, df["D"].values, df["R"].values)                 # judges score the raw price
        pts = -np.log2(np.clip(raw, C.PRICE_FLOOR, C.PRICE_CEIL))
        right = pick_d == d_won
        q_pick = np.where(pick_d, q_d, 1 - q_d)
        rows.append({"q_source": label, "strategy": name, "races": len(df),
                     "underdog_picks": int(dog.sum()), "underdogs_won": int((dog & right).sum()),
                     "picks_correct": int(right.sum()), "actual_score": round(float((pts * right).sum()), 2),
                     "expected_score": round(float((pts * q_pick).sum()), 2)})
    return rows


def main(kalshi, data_dir, out_dir):
    k = load_prices(kalshi)
    rows = evaluate(k, "p_d", "market only")
    for ch in ["House", "Senate"]:
        rows += evaluate(k[k["chamber"] == ch], "p_d", f"market only, {ch}")

    # B) our model + 50/50 blend, House races
    data = load_all(data_dir)
    t = M.build_training(data)
    test, train = t[t["year"] == 2024].copy(), t[t["year"] == 2022]
    q_model, _ = pseudo_market(test, train, FINAL_GENERIC[2024], 4.84)
    test["q_model"] = q_model
    h = k[k["chamber"] == "House"].merge(test[["race_id", "q_model"]], on="race_id", how="inner")
    lg = lambda x: np.log(x / (1 - x))
    qm = h["q_model"].clip(0.01, 0.99)
    pm = h["p_d"].clip(0.01, 0.99)
    w = C.MODEL_WEIGHT["House"]
    h["q_blend"] = 1 / (1 + np.exp(-(w * lg(qm) + (1 - w) * lg(pm))))
    rows += evaluate(h, "p_d", "House w/ model data: market only")
    rows += evaluate(h, "q_blend", "House w/ model data: 50/50 model+market")
    rows += evaluate(h, "q_model", "House w/ model data: model only")

    res = pd.DataFrame(rows)
    res.to_csv(Path(out_dir) / "backtest_kalshi2024.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.to_string(index=False))

    # Kalshi calibration: how often did underdogs win?
    q_dog = np.minimum(k["p_d"], 1 - k["p_d"])
    dog_won = np.where(k["p_d"] >= .5, k["winner"] == "R", k["winner"] == "D")
    cal = pd.DataFrame({"b": pd.cut(q_dog, [0, .1, .2, .3, .4, .5]), "q": q_dog, "w": dog_won}).groupby("b", observed=True).agg(
        races=("w", "size"), avg_price=("q", "mean"), underdog_win_rate=("w", "mean"))
    print("\nReal Kalshi 2024 underdog calibration:\n", cal.round(3))
    print("\nHouse races, model vs market:\n", h[["race_id", "q_model", "p_d", "q_blend", "winner"]].round(2).to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kalshi", required=True)
    ap.add_argument("--data", default="../data")
    ap.add_argument("--out", default="../results")
    a = ap.parse_args()
    main(a.kalshi, a.data, a.out)
