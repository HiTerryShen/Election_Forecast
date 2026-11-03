"""Fundamentals model: 2022/2024 backtest -> fitted weights -> 2026 expected margins.

Target: D two-party margin (points). National environment enters as a fixed offset
(uniform swing), so the backtest learns how districts deviate from the national vote.

    margin = national + b_lean*lean + b_inc*inc + b_redraw*(inc*redrawn) + demographics ... + priors
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

import config as C
from load_data import CENSUS_DIVISION, CENSUS_REGION

# Polls commissioned by a campaign/party lean toward their sponsor by ~4 pts of margin (sponsor detected from notes/source)
SPONSOR_BIAS = 4.0

NATIONAL_PRES_MARGIN = {2020: 4.5, 2024: -1.5}       # D minus R, popular vote
# States whose House lines changed between 2022 and 2024
REDRAWN_FOR_2024 = {"AL", "GA", "LA", "NC", "NY"}

DEMO_COLS = ["pct_hispanic", "pct_black", "pct_asian", "pct_ba_plus", "pct_65plus", "log_income", "income_growth_pct"]
# Share of the 2020->2024 demographic realignment trend assumed to carry into 2026
# (2024 presidential lean already captures most of it). Judgment call; tune with partners.
DEMO_TREND_CARRY = 0.5


def _demo_features(acs: pd.DataFrame | None, ids: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame({"race_id": pd.Series(ids).drop_duplicates().values})   # unique: merging dup ids multiplies rows
    if acs is None:
        for c in DEMO_COLS:
            out[c] = 0.0
        return out
    a = acs.copy()
    if "median_income" in a:
        a["log_income"] = np.log(a["median_income"].clip(lower=1))
    out = out.merge(a[["race_id"] + [c for c in DEMO_COLS if c in a]], on="race_id", how="left")
    for c in DEMO_COLS:
        if c not in out:
            out[c] = 0.0
        # center on national district mean so coefficients are deviations
        out[c] = (out[c] - out[c].mean()).fillna(0.0)
    return out


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------
def build_training(data: dict) -> pd.DataFrame:
    hist, pres = data["house_hist"], data["pres"]
    if hist is None or pres is None:
        raise ValueError("Need house_results_history.csv and pres_by_district.csv for the backtest")
    p24 = pres[pres["map"].str.startswith("2024")][["race_id", "pres20_margin", "pres24_margin"]]
    h = hist[hist["year"].isin([2022, 2024]) & ~hist["uncontested"]].merge(p24, on="race_id", how="inner")
    # 2022 results can only be matched to 2024-lines presidential data where lines didn't change
    h = h[~((h["year"] == 2022) & h["state"].isin(REDRAWN_FOR_2024))]

    # lean known *before* each election: only 2020 presidential results
    h["lean"] = h["pres20_margin"] - NATIONAL_PRES_MARGIN[2020]
    h["national"] = h["year"].map(C.NATIONAL_HOUSE_MARGIN)

    # incumbency: use supplied columns, else infer 2024 incumbent from 2022 winner
    if "incumbent_party" in h:
        run = h.get("incumbent_running", "Y").astype(str).str.upper().str.startswith("Y")
        h["inc"] = np.where(run, h["incumbent_party"].map({"D": 1, "R": -1}).fillna(0), 0)
    else:
        # 2024: incumbent = 2022 winner, counted only if their surname is on the 2024 ballot
        prev = hist[hist["year"] == 2022][["race_id", "winner_party", "winner_name"]].rename(
            columns={"winner_party": "prev_w", "winner_name": "prev_name"})
        h = h.merge(prev, on="race_id", how="left")
        last = h["prev_name"].fillna("").astype(str).str.replace(r"[^A-Za-z ]", "", regex=True).str.split().str[-1].fillna("")
        running = [bool(l) and l.upper() in str(c).upper() for l, c in zip(last, h.get("cand_names", ""))]
        h["inc"] = np.where((h["year"] == 2024) & np.array(running), h["prev_w"].map({"D": 1, "R": -1}).fillna(0), 0)
        # 2022 incumbency is unknown from this file -> separate indicator so it doesn't bias the 2024 estimate
        h["inc_unknown"] = (h["year"] == 2022).astype(int)
    if "inc_unknown" not in h:
        h["inc_unknown"] = 0
    h["redrawn"] = ((h["year"] == 2024) & h["state"].isin(REDRAWN_FOR_2024)).astype(int)
    h["inc_x_redrawn"] = h["inc"] * h["redrawn"]
    h = h.merge(_demo_features(data["acs"], h["race_id"]), on="race_id", how="left")
    return h


FIT_COLS = ["lean", "inc", "inc_x_redrawn", "inc_unknown"] + DEMO_COLS


def fit(train: pd.DataFrame):
    X = sm.add_constant(train[FIT_COLS].astype(float), has_constant="add")
    y = train["dem_margin"] - train["national"]
    # robust (Huber) regression: blowout / weird races shouldn't dominate
    return sm.RLM(y, X, M=sm.robust.norms.HuberT()).fit()


def predict_fitted(res, df: pd.DataFrame) -> np.ndarray:
    X = sm.add_constant(df[FIT_COLS].astype(float), has_constant="add")
    return res.predict(X) + df["national"].values


def predict_guess(df: pd.DataFrame) -> np.ndarray:
    """Hand-guessed weights (the 'put in weights' approach)."""
    return df["national"] + 1.0 * df["lean"] + 4.0 * df["inc"]


def _metrics(y, mu, sd):
    from scipy.stats import norm
    p = norm.cdf(mu / sd).clip(0.01, 0.99)
    win = (y > 0).astype(int)
    return {
        "rmse": float(np.sqrt(np.mean((y - mu) ** 2))),
        "mae": float(np.mean(np.abs(y - mu))),
        "call_accuracy": float(np.mean((mu > 0) == (y > 0))),
        "brier": float(np.mean((p - win) ** 2)),
        "log_loss_bits": float(-np.mean(win * np.log2(p) + (1 - win) * np.log2(1 - p))),
    }


def backtest(data: dict) -> dict:
    """Leave-one-year-out: fit on 2022 -> test 2024, fit on 2024 -> test 2022.
    Compare fitted weights against guessed weights. Final model is fit on both years."""
    t = build_training(data).reset_index(drop=True)
    # 10-fold cross-validation grouped by STATE (a state's districts are never in train and test at once)
    states = np.array(sorted(t["state"].unique()))
    rng = np.random.default_rng(0)
    fold_of = dict(zip(rng.permutation(states), np.arange(len(states)) % 10))
    t["fold"] = t["state"].map(fold_of)
    mu_f = np.full(len(t), np.nan)
    for f in range(10):
        tr, te = t["fold"] != f, t["fold"] == f
        mu_f[te.values] = predict_fitted(fit(t[tr]), t[te])
    t["mu_cv"] = mu_f
    t["mu_guess"] = predict_guess(t).values
    rows, oos_resid = [], [t["dem_margin"].values - mu_f]
    for yr in [2024, 2022, "all"]:
        s = t if yr == "all" else t[t["year"] == yr]
        y = s["dem_margin"].values
        for name, col in [("fitted (CV)", "mu_cv"), ("guessed", "mu_guess")]:
            sd = float(np.std(y - s[col].values))
            rows.append({"test_year": yr, "model": name, "n": len(s), **_metrics(y, s[col].values, sd)})
    final = fit(t)
    # robust SD of out-of-sample residuals = race-level noise for 2026
    allr = np.concatenate(oos_resid) if oos_resid else final.resid.values
    mad_sd = float(1.4826 * np.median(np.abs(allr - np.median(allr))))
    coefs = pd.DataFrame({"coef": final.params, "se": final.bse})
    return {"train": t, "fit": final, "coefs": coefs, "metrics": pd.DataFrame(rows), "district_sd": mad_sd}


# ---------------------------------------------------------------------------
# 2026 feature matrix
# ---------------------------------------------------------------------------
def build_2026(data: dict, bt: dict | None) -> pd.DataFrame:
    r = data["races"].copy()
    nat = C.GENERIC_BALLOT_2026 * C.GENERIC_BALLOT_DISCOUNT
    r["national"] = nat

    # --- partisan lean: Cook PVI (x2 -> margin scale), fallback to 2024 pres on 2026 lines
    lean = pd.Series(np.nan, index=r.index)
    if data["pvi"] is not None:
        lean = r["race_id"].map(data["pvi"].set_index("race_id")["pvi_num"]) * 2
    if data["pres"] is not None:
        p = data["pres"].copy()
        p["_new"] = p["map"].str.startswith("2026").astype(int)
        p = p.sort_values("_new").groupby("race_id").last()
        pres_lean = r["race_id"].map(p["pres24_margin"]) - NATIONAL_PRES_MARGIN[2024]
        r["pres_lean_2024"] = pres_lean
        lean = lean.fillna(pres_lean)
        # PVI change from redistricting (old-lines vs new-lines Harris margin)
        old = data["pres"][data["pres"]["map"].str.startswith("2024")].set_index("race_id")["pres24_margin"]
        new = data["pres"][data["pres"]["map"].str.startswith("2026")].set_index("race_id")["pres24_margin"]
        r["lean_shift_redraw"] = r["race_id"].map(new - old).fillna(0)
    else:
        r["lean_shift_redraw"] = 0.0
    r["lean"] = lean
    r["lean_missing"] = r["lean"].isna()
    r["lean"] = r["lean"].fillna(0)

    # --- incumbency
    r["inc"] = np.where(r["incumbent_running"], r["incumbent_party"].map({"D": 1, "R": -1}).fillna(0), 0)
    r["redrawn"] = r["redistricted_2026"].astype(int)
    r["inc_x_redrawn"] = r["inc"] * r["redrawn"]

    # --- demographics (fitted trend, partially carried)
    r = r.merge(_demo_features(data["acs"], r["race_id"]), on="race_id", how="left")

    # --- 2026-only factors (prior weights). Sign: +pain hurts president's party (R in 2026) -> +D
    pres_sign = 1 if C.PRESIDENT_PARTY[2026] == "R" else -1
    r["cpi_excess"] = 0.0
    r["gas_change_pct"] = 0.0
    rp = data.get("regional_prices")
    if rp is not None:
        rp = rp.copy()
        at = rp.get("area_type", "").astype(str).str.lower()
        cpi = lambda kind: pd.to_numeric(rp[at == kind].set_index("area")["cpi_yoy_pct"], errors="coerce")
        # finest available: Census division, falling back to region
        div = r["state"].map(CENSUS_DIVISION).map(cpi("division"))
        reg = r["state"].map(CENSUS_REGION).map(cpi("region"))
        r["cpi_excess"] = div.fillna(reg) - C.NATIONAL_CPI_YOY_2026
        if "gas_now" in rp:
            g = rp[pd.to_numeric(rp["gas_now"], errors="coerce").notna()].copy()
            g["state"] = g["state"].astype(str).str.upper()
            g = g.set_index("state")
            now = pd.to_numeric(g["gas_now"])
            pre = pd.to_numeric(g.get("gas_prewar"), errors="coerce") if "gas_prewar" in g else pd.Series(np.nan, index=g.index)
            if pre.notna().sum() >= 40:     # % change since the war started
                chg = 100 * (now / pre - 1)
            else:                            # fallback: today's price premium vs national average (%)
                # level != shock (CA is always pricey): half weight, capped at +/-20%
                chg = (0.5 * 100 * (now / now.mean() - 1)).clip(-20, 20)
            r["gas_change_pct"] = r["state"].map(chg - chg.mean())
        r[["cpi_excess", "gas_change_pct"]] = r[["cpi_excess", "gas_change_pct"]].fillna(0)

    war = -C.IRAN_WAR_NET_SUPPORT / 20.0            # ~1.05 when net support is -21
    vet = r["race_id"].map(data["acs"].set_index("race_id")["pct_veteran"]) if (data["acs"] is not None and "pct_veteran" in data["acs"]) else pd.Series(np.nan, index=r.index)
    r["veteran_dev"] = (vet - vet.mean()).fillna(0)
    r["has_base"] = 0
    ie = data.get("iran_war_exposure")
    if ie is not None and "race_id" in ie:
        r["has_base"] = r["race_id"].isin(set(ie["race_id"])).astype(int)

    # candidate quality: favorability + fundraising
    r["net_fav_diff"] = 0.0
    fav = data.get("candidate_favorability")
    if fav is not None:
        fav = fav.copy()
        fav["net"] = pd.to_numeric(fav["favorable_pct"], errors="coerce") - pd.to_numeric(fav["unfavorable_pct"], errors="coerce")
        fav["party"] = fav["party"].astype(str).str.upper().str[0]
        piv = fav.groupby(["race_id", "party"])["net"].mean().unstack()
        diff = piv.get("D", np.nan) - piv.get("R", np.nan)
        r["net_fav_diff"] = r["race_id"].map(diff).fillna(0)
    r["log_fundraising_ratio"] = 0.0
    fr = data.get("fundraising")
    if fr is not None:
        fr = fr.copy()
        fr["party"] = fr["party"].astype(str).str.upper().str[0]
        piv = fr.groupby(["race_id", "party"])["total_receipts"].sum().unstack()
        left = piv.get("D", pd.Series(np.nan, index=piv.index)).fillna(piv.get("I", pd.Series(np.nan, index=piv.index)))  # independent = D side when no D
        ratio = np.log((left + 1e4) / (piv.get("R", np.nan) + 1e4)).clip(-2, 2)
        r["log_fundraising_ratio"] = r["race_id"].map(ratio).fillna(0)

    W = C.PRIOR_WEIGHTS
    r["prior_adj"] = (
        W["cpi_excess_x_pres"] * r["cpi_excess"] * pres_sign
        + W["gas_change_pct_x_pres"] * r["gas_change_pct"] * pres_sign
        + W["veteran_x_war"] * r["veteran_dev"] * war
        + W["base_x_war"] * r["has_base"] * war
        + W["age65_x_health"] * r["pct_65plus"]
        + W["net_fav_diff"] * r["net_fav_diff"]
        + W["log_fundraising_ratio"] * r["log_fundraising_ratio"]
    )

    # --- fundamentals expected margin
    if bt is not None:
        b = bt["fit"].params
        mu = r["national"] + b["const"] + b["lean"] * r["lean"] + b["inc"] * r["inc"] + b["inc_x_redrawn"] * r["inc_x_redrawn"]
        for c in DEMO_COLS:
            mu = mu + DEMO_TREND_CARRY * b.get(c, 0.0) * r[c]
    else:  # guessed weights if no backtest data
        mu = r["national"] + r["lean"] + 4.0 * r["inc"] - 1.5 * r["inc_x_redrawn"]
    r["mu_fund"] = mu + r["prior_adj"]

    # Senate: statewide races are less elastic to lean and more candidate-driven
    sen = r["chamber"] == "Senate"
    r.loc[sen, "mu_fund"] = r.loc[sen, "national"] + 0.85 * r.loc[sen, "lean"] + 3.0 * r.loc[sen, "inc"] + r.loc[sen, "prior_adj"]
    return r


# ---------------------------------------------------------------------------
# Polls
# ---------------------------------------------------------------------------
def poll_average(polls: pd.DataFrame | None, today="2026-11-01") -> pd.DataFrame:
    if polls is None or len(polls) == 0:
        return pd.DataFrame(columns=["race_id", "poll_margin", "n_polls"])
    p = polls.copy()
    p["end_date"] = pd.to_datetime(p["end_date"], errors="coerce")
    p["age"] = (pd.Timestamp(today) - p["end_date"]).dt.days.clip(lower=0).fillna(60)
    p["n"] = pd.to_numeric(p.get("sample_size"), errors="coerce").fillna(600)
    pop_w = p.get("population", "LV").astype(str).str.upper().map({"LV": 1.0, "RV": 0.8, "A": 0.5}).fillna(0.8)
    p["w"] = np.exp(-p["age"] / 21) * np.sqrt(p["n"] / 600) * pop_w
    p["m"] = pd.to_numeric(p["dem_pct"], errors="coerce") - pd.to_numeric(p["rep_pct"], errors="coerce")
    p = p.dropna(subset=["m"])
    txt = (p.get("note", "").astype(str) + " " + p.get("source", "").astype(str)).str.lower()
    dem_sponsor = txt.str.contains(r"commissioned by .*(democrat|campaign)|democratic party|dccc|dscc") & ~txt.str.contains("republican")
    rep_sponsor = txt.str.contains(r"commissioned by .*republican|nrcc|nrsc|gop") & ~dem_sponsor
    p.loc[dem_sponsor, "m"] -= SPONSOR_BIAS
    p.loc[rep_sponsor, "m"] += SPONSOR_BIAS
    p.loc[dem_sponsor | rep_sponsor, "w"] *= 0.5
    # one pollster shouldn't dominate: down-weight repeated releases
    p["w"] = p["w"] / p.groupby(["race_id", "pollster"])["w"].transform("count").clip(lower=1) ** 0.5
    g = p.groupby("race_id").apply(lambda x: pd.Series({
        "poll_margin": np.average(x["m"], weights=x["w"]),
        "n_polls": float(x["w"].sum() / x["w"].max()) if len(x) else 0.0,   # effective number
    }))
    return g.reset_index()


def blend_polls(r: pd.DataFrame, polls: pd.DataFrame | None, district_sd: float) -> pd.DataFrame:
    pa = poll_average(polls)
    r = r.merge(pa, on="race_id", how="left")
    r["n_polls"] = r["n_polls"].fillna(0)
    K = r["chamber"].map(C.POLL_K)
    r["poll_w"] = r["n_polls"] / (r["n_polls"] + K)
    r["mu"] = np.where(r["poll_margin"].notna(),
                       r["poll_w"] * r["poll_margin"] + (1 - r["poll_w"]) * r["mu_fund"], r["mu_fund"])
    base_sd = np.where(r["chamber"] == "Senate", district_sd + C.SENATE_EXTRA_SD, district_sd)
    r["race_sd"] = (1 - r["poll_w"]) * base_sd + r["poll_w"] * C.POLL_HOUSE_EFFECT_SD
    r.loc[r["lean_missing"] & r["poll_margin"].isna(), "race_sd"] *= 1.5
    return r
