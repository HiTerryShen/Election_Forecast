"""Build the submission list results/PREDICTIONS_2026.xlsx (+ .csv) from run.py's outputs.

    python make_predictions.py --results ../results
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl.styles import Font, PatternFill

FIX = {"Republican party (R)": "Dan Sullivan (R)", "Democratic party (D)": "Mary Peltola (D)"}   # AK-S party-level market


def main(res_dir):
    d = Path(res_dir)
    f = pd.read_csv(d / "forecast_neutral.csv")
    dp = pd.read_csv(d / "forecast_D_plus.csv").set_index("race_id")
    rp = pd.read_csv(d / "forecast_R_plus.csv").set_index("race_id")
    c = pd.read_csv(d / "candidates_neutral.csv")
    fav = c.loc[c.groupby("race_id")["q"].idxmax()].set_index("race_id")
    out = pd.DataFrame({
        "Race": f.race_id, "Chamber": f.chamber, "State": f.state, "District": f.district,
        "Democrat / lead non-R": f.dem_candidate.fillna(f.other_candidate), "Republican": f.rep_candidate,
        "Predicted winner": f.race_id.map(fav.candidate + " (" + fav.party + ")"),
        "Win probability": f.race_id.map(fav.q).round(3),
        "D margin, 80% range low": f.margin_lo80.round(1), "D margin, 80% range high": f.margin_hi80.round(1),
        "Kalshi price (D / lead non-R)": f.kalshi_p_left.round(3),
        "OUR PICK (submit)": f.pick,
        "Pick = predicted winner?": np.where(f.pick_is_model_favorite, "Yes", "No - underdog value pick"),
        "Pick Kalshi price": f.pick_kalshi_price.round(3), "Points if right": f.pick_points_if_right.round(2),
        "Pick win probability": f.pick_win_prob.round(3),
        "Pick if D+2.5": f.race_id.map(dp["pick"]), "Pick if R+2.5": f.race_id.map(rp["pick"]),
    }).replace(FIX)
    out.loc[out.Race == "AK-S", "Republican"] = "Dan Sullivan"
    out["_o"] = np.where(out.Chamber == "Senate", 0, 1)
    out["_d"] = pd.to_numeric(out.District, errors="coerce").fillna(0)
    out = out.sort_values(["_o", "State", "_d"]).drop(columns=["_o", "_d"])
    out.to_csv(d / "PREDICTIONS_2026.csv", index=False)
    with pd.ExcelWriter(d / "PREDICTIONS_2026.xlsx", engine="openpyxl") as w:
        for name, part in [("All races", out), ("Senate", out[out.Chamber == "Senate"]),
                           ("Value picks", out[out["Pick = predicted winner?"] != "Yes"])]:
            part.to_excel(w, sheet_name=name, index=False)
            ws = w.sheets[name]
            ws.freeze_panes = "B2"
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="DDEBF7")
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(34, max(10, max(len(str(x.value or "")) for x in col[:80]) + 2))
    print(f"wrote {len(out)} races to {d / 'PREDICTIONS_2026.xlsx'}")

    # compact submission file: one pick per race, neutral scenario
    pk = out["OUR PICK (submit)"]
    final = pd.DataFrame({
        "race_id": out.Race, "chamber": out.Chamber, "state": out.State,
        "district": out.District.astype(str).replace({"S": "Senate", "S2": "Senate (special)", "0": "At-large"}),
        "pick_candidate": pk.str.rsplit(" (", n=1).str[0], "pick_party": pk.str.extract(r"\((\w)\)$")[0],
        "pick_win_probability": out["Pick win probability"], "pick_kalshi_price_nov1": out["Pick Kalshi price"],
    })
    assert len(final) == 470 and final.race_id.is_unique and final.notna().all().all()
    final.to_csv(d / "FINAL_PICKS_2026.csv", index=False)
    print(f"wrote {d / 'FINAL_PICKS_2026.csv'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="../results")
    main(ap.parse_args().results)
