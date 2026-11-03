"""Loaders for every input file in data_collection_prompt.md.

Each loader returns a tidy DataFrame keyed by race_id ("CA-22", "WY-0", "OH-S", "OH-S2").
Loaders accept the formatted CSVs from the brief, and where noted also the raw
source files (MIT Election Lab CSV, Census API JSON).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "72": "PR",
}
STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}
# Apportionment for the 2020s (sums to 435). Used to validate the race list.
SEATS = {
    "AL": 7, "AK": 1, "AZ": 9, "AR": 4, "CA": 52, "CO": 8, "CT": 5, "DE": 1, "FL": 28,
    "GA": 14, "HI": 2, "ID": 2, "IL": 17, "IN": 9, "IA": 4, "KS": 4, "KY": 6, "LA": 6,
    "ME": 2, "MD": 8, "MA": 9, "MI": 13, "MN": 8, "MS": 4, "MO": 8, "MT": 2, "NE": 3,
    "NV": 4, "NH": 2, "NJ": 12, "NM": 3, "NY": 26, "NC": 14, "ND": 1, "OH": 15, "OK": 5,
    "OR": 6, "PA": 17, "RI": 2, "SC": 7, "SD": 1, "TN": 9, "TX": 38, "UT": 4, "VT": 1,
    "VA": 11, "WA": 10, "WV": 2, "WI": 8, "WY": 1,
}
assert sum(SEATS.values()) == 435

# Census regions for mapping regional CPI when no metro match exists
CENSUS_REGION = {}
for _r, _states in {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}.items():
    for _s in _states.split():
        CENSUS_REGION[_s] = _r
CENSUS_DIVISION = {}
for _d, _states in {
    "New England": "CT ME MA NH RI VT", "Middle Atlantic": "NJ NY PA",
    "East North Central": "IL IN MI OH WI", "West North Central": "IA KS MN MO NE ND SD",
    "South Atlantic": "DE DC FL GA MD NC SC VA WV", "East South Central": "AL KY MS TN",
    "West South Central": "AR LA OK TX", "Mountain": "AZ CO ID MT NV NM UT WY",
    "Pacific": "AK CA HI OR WA",
}.items():
    for _s in _states.split():
        CENSUS_DIVISION[_s] = _d


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def norm_state(x) -> str:
    s = str(x).strip().upper()
    if len(s) == 2:
        return s
    if s.zfill(2) in STATE_FIPS:
        return STATE_FIPS[s.zfill(2)]
    return STATE_NAMES.get(s, s)


def norm_district(x) -> str:
    """'At-large', 'AL', 0, '00', '7' -> '0', '7'; Senate markers kept."""
    s = str(x).strip().upper()
    if s in {"S", "S2", "SEN", "SENATE"}:
        return "S" if s != "S2" else "S2"
    if s in {"AL", "AT-LARGE", "AT LARGE", "", "NAN", "98"}:   # 98 = Census code for at-large
        return "0"
    m = re.search(r"\d+", s)
    return str(int(m.group())) if m else s


def race_id(state, district) -> str:
    return f"{norm_state(state)}-{norm_district(district)}"


def parse_pvi(x) -> float:
    """'R+5' -> -5, 'D+12' -> 12, 'EVEN' -> 0."""
    if pd.isna(x):
        return np.nan
    s = str(x).strip().upper()
    if s.startswith("EVEN"):
        return 0.0
    m = re.match(r"([DR])\s*\+\s*([\d.]+)", s)
    if m:
        return float(m.group(2)) * (1 if m.group(1) == "D" else -1)
    try:
        return float(s)
    except ValueError:
        return np.nan


def _read(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _add_key(df: pd.DataFrame) -> pd.DataFrame:
    if "race_id" in df:   # trust an explicit special-election id (e.g., FL-S2) over a district column saying "S"
        s2 = df["race_id"].astype(str).str.upper().str.endswith("-S2")
        df.loc[s2, "district"] = "S2"
    df["state"] = df["state"].map(norm_state)
    df["district"] = df["district"].map(norm_district)
    df["race_id"] = df["state"] + "-" + df["district"]
    return df


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------
def load_races(d: Path) -> pd.DataFrame:
    df = _add_key(_read(d / "races_2026.csv"))
    for c in ["incumbent_running", "open_seat", "uncontested", "top_two_same_party", "redistricted_2026"]:
        if c in df:
            df[c] = df[c].astype(str).str.upper().str.startswith("Y")
        else:
            df[c] = False
    df["incumbent_terms"] = pd.to_numeric(df.get("incumbent_terms"), errors="coerce").fillna(0)
    df["chamber"] = np.where(df["district"].str.startswith("S"), "Senate", "House")
    return df


def load_kalshi(d: Path) -> pd.DataFrame:
    df = _add_key(_read(d / "kalshi_prices.csv"))
    df["party"] = df["party"].astype(str).str.upper().str[0]
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if df["price"].max() > 1.5:          # given in cents
        df["price"] = df["price"] / 100
    return df


def load_pvi(d: Path) -> pd.DataFrame:
    df = _add_key(_read(d / "cook_pvi.csv"))
    if "pvi_num" not in df or df["pvi_num"].isna().all():
        df["pvi_num"] = df["pvi_raw"].map(parse_pvi)
    df["pvi_num"] = pd.to_numeric(df["pvi_num"], errors="coerce")
    # prefer the 2026-redraw value when both exist
    df["_rank"] = df.get("pvi_version", "").astype(str).str.contains("2026").astype(int)
    df = df.sort_values("_rank").groupby("race_id").last().reset_index()
    return df[["race_id", "pvi_num"] + [c for c in ["pvi_version"] if c in df]]


def load_pres(d: Path) -> pd.DataFrame:
    """Returns one row per (race_id, map) with D-minus-R margins."""
    df = _add_key(_read(d / "pres_by_district.csv"))
    for c in ["trump_2024", "harris_2024", "trump_2020", "biden_2020"]:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df["pres24_margin"] = df["harris_2024"] - df["trump_2024"]
    df["pres20_margin"] = df["biden_2020"] - df["trump_2020"]
    df["map"] = df.get("map", "2024_lines").astype(str)
    return df[["race_id", "state", "district", "map", "pres24_margin", "pres20_margin"]]


def load_house_history(d: Path) -> pd.DataFrame:
    """Accepts formatted house_results_history.csv or the raw MIT Election Lab file.
    Returns one row per (year, race_id) with D two-party margin."""
    p = d / "house_results_history.csv"
    raw = _read(p)
    if "candidatevotes" in raw.columns:          # raw MIT format
        raw = raw[(raw["stage"].astype(str).str.upper() == "GEN") & (~raw.get("special", False).astype(bool))]
        raw = raw[raw["year"] >= 2018]
        raw["party"] = raw["party"].astype(str).str.upper()
        # fold NY/CT fusion lines and MN DFL into D / R
        raw["p"] = np.select(
            [raw["party"].str.contains("DEMOCRAT|DFL|WORKING FAMILIES"),
             raw["party"].str.contains("REPUBLICAN|CONSERVATIVE")], ["D", "R"], "O")
        raw["district"] = raw["district"]
        raw["state"] = raw["state_po"]
        g = raw.groupby(["year", "state", "district", "p"])["candidatevotes"].sum().unstack(fill_value=0)
        g = g.reset_index()
        # winner name + full candidate list (to detect incumbents running again)
        tops = raw.sort_values("candidatevotes").groupby(["year", "state", "district"]).agg(
            winner_name=("candidate", "last"), cand_names=("candidate", lambda s: "|".join(map(str, s))))
        g = g.merge(tops.reset_index(), on=["year", "state", "district"], how="left")
        g["dem_pct"] = 100 * g.get("D", 0) / (g.get("D", 0) + g.get("R", 0)).replace(0, np.nan)
        g["rep_pct"] = 100 - g["dem_pct"]
        g["uncontested"] = (g.get("D", 0) == 0) | (g.get("R", 0) == 0)
        df = _add_key(g)
    else:
        df = _add_key(raw)
        df["uncontested"] = df.get("uncontested", "N").astype(str).str.upper().str.startswith("Y")
    df["dem_margin"] = pd.to_numeric(df["dem_pct"], errors="coerce") - pd.to_numeric(df["rep_pct"], errors="coerce")
    df["winner_party"] = np.where(df["dem_margin"] > 0, "D", "R")
    keep = ["year", "race_id", "state", "district", "dem_margin", "winner_party", "uncontested"]
    for c in ["incumbent_party", "incumbent_running", "winner_name", "cand_names"]:
        if c in df:
            keep.append(c)
    return df[keep]


def load_acs(d: Path) -> pd.DataFrame:
    """Accepts acs_district.csv or raw Census API JSON (acs_2024.json, acs_2019.json)."""
    def from_json(path: Path) -> pd.DataFrame:
        rows = json.loads(path.read_text())
        df = pd.DataFrame(rows[1:], columns=rows[0])
        df["state"] = df["state"].map(lambda f: STATE_FIPS.get(f, f))
        df["district"] = df["congressional district"]
        return _add_key(df)

    rename = {
        "DP05_0018E": "median_age", "DP05_0024PE": "pct_65plus", "DP05_0037PE": "pct_white",
        "DP05_0038PE": "pct_black", "DP05_0071PE": "pct_hispanic", "DP05_0044PE": "pct_asian",
        "DP03_0062E": "median_income", "DP02_0068PE": "pct_ba_plus", "DP02_0070PE": "pct_veteran",
    }
    j24, j19 = d / "acs_2024.json", d / "acs_2019.json"
    if j24.exists():
        df = from_json(j24).rename(columns=rename)
        if j19.exists():
            old = from_json(j19).rename(columns={"DP03_0062E": "median_income_2019"})
            df = df.merge(old[["race_id", "median_income_2019"]], on="race_id", how="left")
    else:
        df = _add_key(_read(d / "acs_district.csv"))
    for c in list(rename.values()) + ["median_income_2019"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
            df.loc[df[c] < -1000, c] = np.nan        # Census null sentinels
    if "median_income_2019" in df:
        df["income_growth_pct"] = 100 * (df["median_income"] / df["median_income_2019"] - 1)
    return df


def load_optional(d: Path, name: str) -> pd.DataFrame | None:
    p = d / name
    if not p.exists():
        return None
    df = _read(p)
    if "state" in df and "district" in df:
        df = _add_key(df)
    elif "race_id" in df:
        parts = df["race_id"].astype(str).str.upper().str.strip().str.split("-", n=1)
        df["race_id"] = [race_id(p[0], p[1]) if len(p) == 2 else "-".join(p) for p in parts]
    return df


def load_all(d: str | Path) -> dict:
    d = Path(d)
    out = {
        "races": load_races(d),
        "kalshi": load_kalshi(d) if (d / "kalshi_prices.csv").exists() else None,
        "pvi": load_pvi(d) if (d / "cook_pvi.csv").exists() else None,
        "pres": load_pres(d) if (d / "pres_by_district.csv").exists() else None,
        "house_hist": load_house_history(d) if (d / "house_results_history.csv").exists() else None,
        "senate_hist": None,
        "acs": load_acs(d) if ((d / "acs_2024.json").exists() or (d / "acs_district.csv").exists()) else None,
    }
    for name in ["redistricting_2026", "polls", "candidate_favorability", "fundraising",
                 "regional_prices", "iran_war_exposure", "senate_results_history"]:
        out[name] = load_optional(d, f"{name}.csv")
    return out
