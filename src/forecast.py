"""Monte Carlo simulation + Kalshi pick optimizer.

Each simulation draws one shared national error, one error per state, and one per
race, so outcomes are correlated the way real elections are (a polling miss hits
every race at once). Win probability q = share of sims the Democrat wins.

Pick rule: expected points of picking X = q_X * -log2(p_X), with p = Kalshi price.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C

# Senate seats NOT up in 2026 (verify!): current 53 R - 47 D/I; R defend 22 (incl. OH & FL specials), D defend 13
SENATE_NOT_UP = {"D": 34, "R": 31}
SENATE_MAJORITY_D = 51        # VP (R) breaks 50-50 ties
HOUSE_MAJORITY = 218


def simulate(r: pd.DataFrame, shift: float, seed: int = C.RANDOM_SEED, n: int = C.N_SIMS):
    rng = np.random.default_rng(seed)
    states = r["state"].unique()
    s_idx = r["state"].map({s: i for i, s in enumerate(states)}).values
    nat = rng.normal(0, C.NATIONAL_SD, size=(n, 1))
    reg = rng.normal(0, C.REGIONAL_SD, size=(n, len(states)))[:, s_idx]
    # fat tails for race-level noise (t with 5 df, rescaled to unit variance)
    t = rng.standard_t(5, size=(n, len(r))) / np.sqrt(5 / 3)
    sims = (r["mu"].values + shift)[None, :] + nat + reg + t * r["race_sd"].values[None, :]
    return sims          # shape (n_sims, n_races), D margin


def market_left_prob(r: pd.DataFrame, kalshi: pd.DataFrame | None) -> pd.Series:
    """Kalshi-implied probability for the race's 'left side' (leading non-R candidate)."""
    if kalshi is None:
        return pd.Series(np.nan, index=r.index)
    ct = _candidate_table(r.assign(q_dem=0.5, top_two_same_party=False), kalshi)
    left = ct[ct["side"] == "left"].groupby("race_id")["p"].first()
    return r["race_id"].map(left)


def blend_with_market(r: pd.DataFrame, sims: np.ndarray, kalshi) -> tuple[pd.DataFrame, np.ndarray]:
    """Blend model and market in log-odds; shift each race's sims so P(D side wins) = blended q.
    Shifting (not resampling) keeps the national/state correlation structure intact."""
    r = r.copy()
    q_model = (sims > 0).mean(axis=0).clip(0.002, 0.998)
    p_mkt = market_left_prob(r, kalshi).clip(0.01, 0.99)
    w = np.where(r["poll_margin"].notna(), C.MODEL_WEIGHT_WITH_POLLS, r["chamber"].map(C.MODEL_WEIGHT))
    lg = lambda x: np.log(x / (1 - x))
    # favorite-longshot correction: sharpen the market's odds before blending
    mkt_logit = C.LONGSHOT_K * lg(p_mkt.values)
    blended = 1 / (1 + np.exp(-(w * lg(q_model) + (1 - w) * mkt_logit)))
    skip = r["uncontested"].values | r["top_two_same_party"].values | p_mkt.isna().values
    q_final = np.where(skip, q_model, blended)
    sims = sims.copy()
    for i in np.where(~skip)[0]:
        delta = -np.quantile(sims[:, i], 1 - q_final[i])
        sims[:, i] += delta
    r["q_model_only"] = q_model
    r["kalshi_p_left"] = p_mkt.values
    r["model_weight"] = np.where(skip, 1.0, w)
    return r, sims


def probabilities(r: pd.DataFrame, sims: np.ndarray) -> pd.DataFrame:
    r = r.copy()
    r["q_dem"] = (sims > 0).mean(axis=0)
    r["margin_mean"] = sims.mean(axis=0)
    r["margin_lo80"] = np.percentile(sims, 10, axis=0)
    r["margin_hi80"] = np.percentile(sims, 90, axis=0)
    tail = 100 * (1 - C.MARGIN_CI) / 2
    lo, hi = np.percentile(sims, tail, axis=0), np.percentile(sims, 100 - tail, axis=0)
    r["upset_within_margin"] = (lo < 0) & (hi > 0)
    # races the margin model can't speak to
    unc = r["uncontested"]
    r.loc[unc & (r["dem_candidate"].notna()) & (r["rep_candidate"].isna()), "q_dem"] = 0.995
    r.loc[unc & (r["rep_candidate"].notna()) & (r["dem_candidate"].isna()), "q_dem"] = 0.005
    r["q_dem"] = r["q_dem"].clip(0.005, 0.995)
    r["model_winner"] = np.where(r["q_dem"] >= 0.5, "D", "R")
    r["model_confidence"] = np.maximum(r["q_dem"], 1 - r["q_dem"])
    return r


def _candidate_table(r: pd.DataFrame, kalshi: pd.DataFrame | None) -> pd.DataFrame:
    """One row per (race, candidate) with our q and Kalshi p."""
    rows = []
    kg = {k: g for k, g in kalshi.groupby("race_id")} if kalshi is not None else {}
    for _, x in r.iterrows():
        k = kg.get(x["race_id"])
        if k is None or k["price"].isna().all():
            # no market: two-party rows, price unknown
            for party, name, q in [("D", x["dem_candidate"], x["q_dem"]), ("R", x["rep_candidate"], 1 - x["q_dem"])]:
                if pd.notna(name):
                    rows.append({"race_id": x["race_id"], "candidate": name, "party": party,
                                 "side": "left" if party == "D" else "right", "q": q, "p": np.nan})
            continue
        k = k.copy()
        k["p_raw"] = k["price"].fillna(0)                 # what the judges score against
        tot = k["p_raw"].sum()
        if tot < 0.95:                                     # a candidate's market is missing (e.g., AK-0)
            k = pd.concat([k, pd.DataFrame([{"candidate": "UNLISTED other candidate", "party": "I",
                                             "p_raw": 1 - tot}])], ignore_index=True)
            tot = 1.0
        k["p"] = k["p_raw"] / tot                          # normalized: used only for implied probabilities
        k = k.sort_values("p", ascending=False).reset_index(drop=True)
        same_party = bool(x.get("top_two_same_party", False)) or (k["party"].nunique() == 1 and len(k) > 1)
        # The two leading candidates by price are the "two sides".
        #  - left side  = leading non-R candidate (a D, or an independent like Osborn NE-S who is the real challenger)
        #  - right side = the R; if no serious R, the other top-two candidate (e.g., Kiley (I) vs Pan (D) in CA-06)
        non_r = k[k["party"] != "R"]
        left = non_r.index[0] if len(non_r) else None
        r_rows = k[k["party"] == "R"]
        right = r_rows.index[0] if len(r_rows) and r_rows["p"].iloc[0] >= 0.05 else next((i for i in k.index if i != left), None)
        minor_p = k.loc[[i for i in k.index if i not in (left, right)], "p"].sum()
        for i, c in k.iterrows():
            if same_party or left is None or right is None:
                q = c["p"]                                        # no model edge
            elif i == left:
                q = x["q_dem"] * (1 - minor_p)
            elif i == right:
                q = (1 - x["q_dem"]) * (1 - minor_p)
            else:
                q = c["p"]                                        # minor candidates: trust market
            rows.append({"race_id": x["race_id"], "candidate": c["candidate"] if pd.notna(c["candidate"]) else f'{c["party"]} nominee',
                         "party": c["party"], "side": "left" if i == left else ("right" if i == right else "minor"),
                         "q": q, "p": c["p"], "p_raw": c["p_raw"]})
    ct = pd.DataFrame(rows)
    if "p_raw" not in ct:
        ct["p_raw"] = np.nan
    ct["p_scored"] = ct["p_raw"].fillna(ct["p"]).clip(C.PRICE_FLOOR, C.PRICE_CEIL)
    ct["points_if_right"] = -np.log2(ct["p_scored"])
    ct["ev"] = ct["q"] * ct["points_if_right"]
    ct["edge"] = ct["q"] - ct["p"]
    return ct


def make_picks(ct: pd.DataFrame, res: pd.DataFrame | None = None) -> pd.DataFrame:
    within = res.set_index("race_id")["upset_within_margin"].to_dict() if res is not None else {}
    out = []
    for rid, g in ct.groupby("race_id"):
        g = g[~g["candidate"].astype(str).str.startswith("UNLISTED")].reset_index(drop=True)
        fav = g.loc[g["q"].idxmax()]
        has_price = g["p"].notna().all()
        elig = g[g["q"] >= C.MIN_Q_FOR_PICK]
        maxev = elig.loc[elig["ev"].fillna(-1).idxmax()] if (has_price and len(elig)) else fav
        # safe: model favorite, unless an underdog (by market) has a big edge AND better EV
        safe = fav
        if has_price:
            under = g[(g["p"] < 0.5) & (g["edge"] >= C.SAFE_EDGE)]
            if len(under):
                u = under.loc[under["ev"].idxmax()]
                if u["ev"] > fav["ev"]:
                    safe = u
        # margin_ev (comparison): maximize EV wherever an upset is within our margin of error
        mev = maxev if within.get(rid, False) else fav
        # floor_ev (DEFAULT): underdog only if we give them >= UNDERDOG_FLOOR and it pays more on average
        fl = fav
        if has_price:
            dogs = g[(g.index != fav.name) & (g["q"] >= C.UNDERDOG_FLOOR)]
            if len(dogs):
                d = dogs.loc[dogs["ev"].idxmax()]
                if d["ev"] > fav["ev"]:
                    fl = d
        out.append({
            "race_id": rid,
            "pick": f'{fl["candidate"]} ({fl["party"]})',
            "pick_party": fl["party"], "pick_win_prob": fl["q"], "pick_kalshi_price": fl["p_raw"] if pd.notna(fl.get("p_raw")) else fl["p"],
            "pick_points_if_right": fl["points_if_right"], "ev_pick": fl["ev"],
            "pick_is_model_favorite": bool(fl.name == fav.name),
            "pick_is_underdog": bool(has_price and (fl["p_raw"] if pd.notna(fl.get("p_raw")) else fl["p"]) < 0.5),
            "pick_margin_ev": f'{mev["candidate"]} ({mev["party"]})',
            "floor_ev_party": fl["party"], "floor_ev_cand": fl["candidate"],
            "margin_ev_party": mev["party"],
            "pick_model_favorite": f'{fav["candidate"]} ({fav["party"]})',
            "pick_safe": f'{safe["candidate"]} ({safe["party"]})',
            "pick_max_ev": f'{maxev["candidate"]} ({maxev["party"]})',
            "safe_party": safe["party"], "maxev_party": maxev["party"], "fav_party": fav["party"],
            "margin_ev_cand": mev["candidate"], "safe_cand": safe["candidate"],
            "maxev_cand": maxev["candidate"], "fav_cand": fav["candidate"],
            "ev_safe": safe["ev"], "ev_max_ev": maxev["ev"], "ev_favorite": fav["ev"],
            "has_kalshi_price": has_price,
        })
    return pd.DataFrame(out)


def score_distribution(r: pd.DataFrame, sims: np.ndarray, ct: pd.DataFrame, picks: pd.DataFrame, rng_seed=7):
    """Simulate total competition score for each strategy using our correlated sims."""
    rng = np.random.default_rng(rng_seed)
    d_win = sims > 0                                       # (n, races)
    idx = {rid: i for i, rid in enumerate(r["race_id"])}
    pts = {k: np.zeros(sims.shape[0]) for k in ["fav", "safe", "floor_ev", "margin_ev", "maxev"]}
    ctg = {k: g for k, g in ct.groupby("race_id")}
    for _, pk in picks.iterrows():
        g = ctg[pk["race_id"]]
        i = idx[pk["race_id"]]
        u = rng.random(sims.shape[0])
        minor_total = g.loc[g["side"] == "minor", "q"].sum()
        for key in pts:
            row = g[g["candidate"] == pk[f"{key}_cand"]].iloc[0]
            if not np.isfinite(row["points_if_right"]):
                continue
            # a minor candidate wins with prob = their q (shared draw u); otherwise the sim margin decides
            minor_wins = u < minor_total
            if row["side"] == "left":
                won = ~minor_wins & d_win[:, i]
            elif row["side"] == "right":
                won = ~minor_wins & ~d_win[:, i]
            else:
                won = minor_wins & (rng.random(sims.shape[0]) < row["q"] / max(minor_total, 1e-9))
            pts[key] += won * row["points_if_right"]
    return pd.DataFrame({
        k: {"mean": v.mean(), "p10": np.percentile(v, 10), "median": np.median(v), "p90": np.percentile(v, 90)}
        for k, v in pts.items()
    }).T.rename(index={"fav": "model_favorite", "safe": "safe", "floor_ev": "floor_25 (DEFAULT)",
                       "margin_ev": "margin_ev (80% rule)", "maxev": "max_ev"})


def chamber_summary(r: pd.DataFrame, sims: np.ndarray) -> dict:
    d_win = sims > 0
    house = (r["chamber"] == "House").values
    sen = (r["chamber"] == "Senate").values
    # pin uncontested outcomes
    for i, (u, q) in enumerate(zip(r["uncontested"], r["q_dem"])):
        if u:
            d_win[:, i] = q > 0.5
    h = d_win[:, house].sum(axis=1)
    s = d_win[:, sen].sum(axis=1) + SENATE_NOT_UP["D"]
    return {
        "house_dem_seats_mean": float(h.mean()), "house_dem_seats_80": (int(np.percentile(h, 10)), int(np.percentile(h, 90))),
        "p_dem_house": float((h >= HOUSE_MAJORITY).mean()),
        "senate_dem_seats_mean": float(s.mean()), "senate_dem_seats_80": (int(np.percentile(s, 10)), int(np.percentile(s, 90))),
        "p_dem_senate": float((s >= SENATE_MAJORITY_D).mean()),
    }
