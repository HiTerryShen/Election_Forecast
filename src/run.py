"""Run the whole pipeline.

    python run.py --data ../data --out ../results            # real data
    python run.py --data ../synthetic --out ../results_test  # pipeline test

Steps: validate race list -> backtest 2022/2024 -> 2026 margins -> polls ->
3 scenarios (D+2.5 / neutral / R+2.5) -> Kalshi pick optimizer -> score simulation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import config as C
import forecast as F
import model as M
from load_data import SEATS, load_all


def validate_races(races: pd.DataFrame) -> list[str]:
    msgs = []
    h = races[races["chamber"] == "House"]
    s = races[races["chamber"] == "Senate"]
    msgs.append(f"House races: {len(h)} (expect 435) | Senate races: {len(s)} (expect 35)")
    counts = h.groupby("state").size()
    for st, n in SEATS.items():
        got = int(counts.get(st, 0))
        if got != n:
            msgs.append(f"  !! {st}: {got} House rows, apportionment says {n}")
    dup = races["race_id"][races["race_id"].duplicated()]
    if len(dup):
        msgs.append(f"  !! duplicate race_ids: {sorted(set(dup))}")
    return msgs


def main(data_dir: str, out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = load_all(data_dir)
    log = []

    # 1. race list
    races = data["races"]
    # "Uncontested" only if Kalshi shows no challenger at >= 5% (catches independents like Osborn NE-S, Kiley CA-06)
    if data["kalshi"] is not None:
        second = data["kalshi"].groupby("race_id")["price"].apply(lambda s: s.sort_values(ascending=False).iloc[1] if len(s) > 1 else 0)
        real_race = races["race_id"].map(second).fillna(0) >= 0.05
        flipped = races.loc[races["uncontested"] & real_race, "race_id"].tolist()
        races.loc[races["uncontested"] & real_race, "uncontested"] = False
        log.append(f"Un-flagged as uncontested (Kalshi shows a real challenger): {flipped}")
        data["races"] = races
    log += validate_races(races)
    races.sort_values(["chamber", "state", "district"]).to_csv(out / "race_list.csv", index=False)

    # 2. backtest
    bt = None
    if data["house_hist"] is not None and data["pres"] is not None:
        bt = M.backtest(data)
        bt["coefs"].to_csv(out / "backtest_coefficients.csv")
        bt["metrics"].to_csv(out / "backtest_metrics.csv", index=False)
        log.append(f"Backtest out-of-sample race SD (robust): {bt['district_sd']:.2f} pts")
        log.append("Backtest metrics:\n" + bt["metrics"].round(3).to_string(index=False))
        log.append("Fitted coefficients:\n" + bt["coefs"].round(3).to_string())
    district_sd = bt["district_sd"] if bt else C.DISTRICT_SD

    # 3. 2026 features + polls
    r = M.build_2026(data, bt)
    r = M.blend_polls(r, data.get("polls"), district_sd)
    r.to_csv(out / "features_2026.csv", index=False)

    summaries = {}
    for name, shift in C.SCENARIOS.items():
        sims = F.simulate(r, 0.0)
        rb, sims = F.blend_with_market(r, sims, data["kalshi"])
        # scenario shift AFTER blending, so the market doesn't pull it back toward neutral
        movable = ~(r["uncontested"].values | r["top_two_same_party"].values)
        sims[:, movable] += shift
        # pin uncontested races
        for i, (u, d, rep) in enumerate(zip(r["uncontested"], r["dem_candidate"], r["rep_candidate"])):
            if u:
                sims[:, i] = 60.0 if pd.notna(d) and pd.isna(rep) else -60.0
        res = F.probabilities(rb, sims)
        ct = F._candidate_table(res, data["kalshi"])
        picks = F.make_picks(ct, res)
        res = res.merge(picks, on="race_id", how="left")
        cols = ["race_id", "chamber", "state", "district", "incumbent", "incumbent_party", "dem_candidate", "rep_candidate",
                "other_candidate", "redrawn", "lean", "mu_fund", "poll_margin", "mu", "margin_lo80", "margin_hi80",
                "q_model_only", "kalshi_p_left", "model_weight", "q_dem", "model_winner", "model_confidence",
                "upset_within_margin", "pick", "pick_win_prob", "pick_kalshi_price", "pick_points_if_right",
                "ev_pick", "pick_is_underdog", "pick_is_model_favorite", "pick_margin_ev", "pick_safe", "ev_safe", "pick_max_ev", "ev_max_ev", "pick_model_favorite"]
        res[[c for c in cols if c in res]].sort_values(["chamber", "state", "district"]).to_csv(
            out / f"forecast_{name}.csv", index=False)
        ct.to_csv(out / f"candidates_{name}.csv", index=False)
        summ = F.chamber_summary(res, sims)
        sd = F.score_distribution(res, sims, ct, picks)
        sd.to_csv(out / f"score_sim_{name}.csv")
        summaries[name] = {**summ, "score_sim": sd.round(2).to_dict(orient="index")}
        log.append(f"\n=== Scenario {name} (shift {shift:+}) ===")
        log.append(json.dumps(summ, indent=1))
        log.append("Simulated competition score by strategy:\n" + sd.round(2).to_string())

    (out / "summary.json").write_text(json.dumps(summaries, indent=1, default=str))
    (out / "run_log.txt").write_text("\n".join(log))
    print("\n".join(log))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data")
    ap.add_argument("--out", default="../results")
    a = ap.parse_args()
    main(a.data, a.out)
