"""FAKE data in the exact input formats, only to test the pipeline end-to-end.
Nothing here is real. Do not submit results built from it."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from load_data import SEATS, STATE_FIPS

SENATE_2026 = "AL AK AR CO DE GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC OK OR RI SC SD TN TX VA WV WY".split()
SPECIALS = ["OH", "FL"]


def main(d):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    rows, pvi, pres, hist, kal, polls = [], [], [], [], [], []
    fips = {v: k for k, v in STATE_FIPS.items()}
    acs = [["NAME", "DP05_0018E", "DP05_0024PE", "DP05_0037PE", "DP05_0038PE", "DP05_0071PE", "DP05_0044PE",
            "DP03_0062E", "DP02_0068PE", "DP02_0070PE", "state", "congressional district"]]
    acs19 = [["NAME", "DP03_0062E", "state", "congressional district"]]
    races = [(s, str(i if n > 1 else 0)) for s, n in SEATS.items() for i in range(1, n + 1)]
    races += [(s, "S") for s in SENATE_2026] + [(s, "S2") for s in SPECIALS]
    for s, dist in races:
        lean20 = rng.normal(0, 18)
        lean24 = lean20 - 3 + rng.normal(0, 3)
        inc = "D" if lean24 + rng.normal(0, 6) > 0 else "R"
        running = rng.random() > 0.1
        unc = (abs(lean24) > 35) and rng.random() < 0.4
        rid = f"{s}-{dist}"
        rows.append(dict(race_id=rid, chamber="Senate" if dist.startswith("S") else "House", state=s, district=dist,
                         incumbent=f"Inc {rid}", incumbent_party=inc, incumbent_running="Y" if running else "N",
                         incumbent_terms=int(rng.integers(1, 10)), open_seat="N" if running else "Y",
                         dem_candidate=None if (unc and inc == "R") else f"Dem {rid}",
                         rep_candidate=None if (unc and inc == "D") else f"Rep {rid}",
                         uncontested="Y" if unc else "N", top_two_same_party="N",
                         redistricted_2026="Y" if s in {"TX", "CA", "NC", "OH", "UT", "FL"} else "N", source="synthetic"))
        pv = (lean24 - (-1.5)) / 2
        pvi.append(dict(state=s, district=dist, pvi_raw=("D+%d" % round(pv)) if pv > 0 else ("R+%d" % round(-pv)), pvi_version="2025"))
        if not dist.startswith("S"):
            for mp in ["2024_lines", "2026_lines"]:
                l24 = lean24 + (rng.normal(0, 6) if mp == "2026_lines" and s in {"TX", "CA"} else 0)
                pres.append(dict(state=s, district=dist, map=mp, harris_2024=50 + (l24 - 1.5) / 2, trump_2024=50 - (l24 - 1.5) / 2,
                                 biden_2020=50 + (lean20 + 4.5) / 2, trump_2020=50 - (lean20 + 4.5) / 2))
            for yr, nat in [(2022, -2.8), (2024, -2.7)]:
                m = nat + 0.95 * lean20 + (4 if inc == "D" else -4) + rng.normal(0, 5)
                hist.append(dict(year=yr, state=s, district=dist, dem_pct=50 + m / 2, rep_pct=50 - m / 2,
                                 incumbent_party=inc, incumbent_running="Y", uncontested="N"))
            cd = "00" if dist == "0" else dist.zfill(2)
            acs.append([rid, rng.normal(39, 4), rng.normal(17, 4), rng.normal(60, 18), rng.normal(12, 10), rng.normal(19, 15),
                        rng.normal(6, 6), rng.normal(78000, 20000), rng.normal(34, 10), rng.normal(6, 2), fips[s], cd])
            acs19.append([rid, rng.normal(64000, 15000), fips[s], cd])
        true_m = 7.6 + lean24 + rng.normal(0, 6)
        pd_ = float(np.clip(1 / (1 + np.exp(-true_m / 4)), 0.01, 0.99))
        if not (unc):
            kal += [dict(state=s, district=dist, candidate=f"Dem {rid}", party="D", price=round(pd_, 2), as_of="2026-11-01"),
                    dict(state=s, district=dist, candidate=f"Rep {rid}", party="R", price=round(1 - pd_, 2), as_of="2026-11-01")]
        if abs(true_m) < 10 or dist.startswith("S"):
            for k in range(int(rng.integers(1, 6))):
                pm = true_m + rng.normal(0, 4)
                polls.append(dict(race_id=rid, pollster=f"P{k % 3}", end_date=f"2026-10-{rng.integers(1, 30):02d}",
                                  sample_size=600, population="LV", dem_pct=48 + pm / 2, rep_pct=48 - pm / 2))
    pd.DataFrame(rows).to_csv(d / "races_2026.csv", index=False)
    pd.DataFrame(pvi).to_csv(d / "cook_pvi.csv", index=False)
    pd.DataFrame(pres).to_csv(d / "pres_by_district.csv", index=False)
    pd.DataFrame(hist).to_csv(d / "house_results_history.csv", index=False)
    pd.DataFrame(kal).to_csv(d / "kalshi_prices.csv", index=False)
    pd.DataFrame(polls).to_csv(d / "polls.csv", index=False)
    (d / "acs_2024.json").write_text(json.dumps([[str(x) for x in r] for r in acs]))
    (d / "acs_2019.json").write_text(json.dumps([[str(x) for x in r] for r in acs19]))
    pd.DataFrame([dict(area=a, area_type="region", cpi_yoy_pct=v) for a, v in
                  {"Northeast": 4.2, "Midwest": 4.2, "West": 3.4, "South": 3.5}.items()]).to_csv(d / "regional_prices.csv", index=False)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../synthetic")
