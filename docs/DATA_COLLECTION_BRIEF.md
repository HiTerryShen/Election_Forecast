# Data Collection Brief: 2026 U.S. House & Senate Forecast

You are collecting data for an election-forecasting model (Stanford competition). Election day is **November 3, 2026**. Today is **November 1, 2026**. Another AI will load your files with Python, so **exact column names and formats matter**.

## Ground rules

1. **Never invent or estimate a value.** If you cannot find it, leave the cell blank. A blank is fine; a guess ruins the model.
2. Every file gets a `source` column (URL) and, where relevant, an `as_of` date.
3. Output **CSV files** (UTF-8, comma-separated, header row). One file per section below, using the filename given.
4. **District key convention (used in every file):**
   - `state` = 2-letter postal code (e.g., `CA`)
   - `district` = integer; **at-large districts = `0`**
   - For Senate rows: `district` = `S` for the regular race, `S2` for a special election (Ohio and Florida specials in 2026)
   - `race_id` = `state-district`, e.g., `CA-22`, `WY-0`, `OH-S`, `OH-S2`
5. **Party codes:** `D`, `R`, `I` (independent/other). Treat independents who caucus with Democrats or run with Democratic backing (e.g., NE Senate) as `I` and add a note.
6. Percentages as numbers 0–100 (e.g., `52.3`), prices as decimals 0–1 (e.g., `0.87`).
7. For states that **redrew their maps for 2026**, district numbers must refer to the **2026 lines**, not the old ones.

---

## Priority 1 (needed first, the model can't run without these)

### 1. `kalshi_prices.csv`: Kalshi market prices, Nov 1, 2026
This is what the competition scores against. **If the competition organizers provided an official price file, use that instead and skip this section.** Otherwise collect from Kalshi's race-level markets (kalshi.com, House and Senate categories) or the 270toWin Kalshi table (270towin.com/2026-house-election/table/kalshi-2026-house-prediction-market-prices).

**Long format, one row per candidate per race:**

| column | example |
|---|---|
| race_id | `PA-07` |
| chamber | `House` or `Senate` |
| state | `PA` |
| district | `7` |
| candidate | `Jane Doe` |
| party | `D` |
| price | `0.62` (last traded price or Yes midpoint) |
| price_type | `last` or `mid` |
| as_of | `2026-11-01 14:00 ET` |
| source | URL |

Goal: **all 435 House + 35 Senate races.** If a race has no Kalshi market, include the row with `price` blank.

### 2. `races_2026.csv`: Every race on the ballot

One row per race (470 rows: 435 House + 35 Senate).

| column | notes |
|---|---|
| race_id, chamber, state, district | per convention |
| incumbent | name, blank if new/vacant seat |
| incumbent_party | D/R/I |
| incumbent_running | `Y` / `N` |
| incumbent_terms | number of terms served (House: 2-year terms; Senate: 6-year terms) |
| open_seat | `Y` / `N` |
| dem_candidate | general-election nominee |
| rep_candidate | general-election nominee |
| other_candidate | notable independent/third party, else blank |
| other_party | |
| uncontested | `Y` if only one major-party candidate on the ballot |
| top_two_same_party | `Y` for CA/WA races with two same-party finalists (e.g., D vs D) |
| redistricted_2026 | `Y` if the district's lines changed for 2026 |
| cook_rating | e.g., `Solid R`, `Lean D`, `Toss-up` |
| sabato_rating | Sabato's Crystal Ball |
| inside_elections_rating | |
| source | URL(s) |

Sources: Wikipedia "2026 United States House of Representatives elections" and "2026 United States Senate elections", Ballotpedia, Cook Political Report, Sabato's Crystal Ball.

### 3. `redistricting_2026.csv`: State-level status

One row per state that **adopted or attempted** a mid-decade redraw (likely: TX, CA, MO, NC, OH, UT, FL, LA, TN, AL, VA, and any others).

| column | notes |
|---|---|
| state | |
| new_map_in_effect_2026 | `Y` / `N` |
| who_drew | legislature / court / commission / ballot measure |
| partisan_direction | `R` / `D` / `neutral` |
| expected_seat_shift | e.g., `+5 R`, from Cook/NCSL/Ballotpedia |
| litigation_status | short note |
| affected_districts | list of district numbers whose lines changed |
| source | URL |

### 4. `cook_pvi.csv`: Cook Partisan Voting Index

| column | notes |
|---|---|
| race_id, state, district | 2026 lines |
| pvi_raw | as printed, e.g., `R+5`, `D+12`, `EVEN` |
| pvi_num | signed number: **Democratic = positive**, Republican = negative (D+12 → `12`, R+5 → `-5`, EVEN → `0`) |
| pvi_version | `2025` (original) or `2026 redraw` (Cook's recalculation for new lines) |
| source | |

Also include **state PVI** for the 35 Senate states (district = `S`).

Source: cookpolitical.com/cook-pvi (free download with registration), or Wikipedia's PVI tables.

### 5. `pres_by_district.csv`: Presidential results by district

| column | notes |
|---|---|
| race_id, state, district | |
| map | `2024_lines` or `2026_lines` |
| trump_2024, harris_2024 | % of vote |
| trump_2020, biden_2020 | % of vote |
| source | |

Need **both** the old (2024) lines and the new (2026) lines for redistricted states. Source: The Downballot's presidential-by-district spreadsheets (they publish recalculations for new maps), Daily Kos Elections archive, or Wikipedia.

---

## Priority 2 (historical results for the 2024 backtest)

### 6. `house_results_history.csv`
2018, 2020, 2022, and 2024 U.S. House general-election results.

| column | notes |
|---|---|
| year, state, district | lines in use that year |
| dem_candidate, dem_pct | |
| rep_candidate, rep_pct | |
| winner_party | |
| incumbent_party | before the election |
| incumbent_running | Y/N |
| uncontested | Y/N |

Best source: **MIT Election Data + Science Lab, "U.S. House 1976–2024"** on Harvard Dataverse. If you get the raw MIT CSV, **just send the raw file as-is**; we'll reformat it.

Also: **`senate_results_history.csv`** with the same format for Senate races 2018–2024 (MIT also has this).

---

## Priority 3 (district features)

### 7. `acs_district.csv`: Census demographics (119th Congress districts)

If you can run Census API calls, use these (no key needed). Otherwise download from data.census.gov "Congressional District" profiles. Send the raw JSON or CSV.

- 2024 ACS 1-year:
  `https://api.census.gov/data/2024/acs/acs1/profile?get=NAME,DP05_0018E,DP05_0024PE,DP05_0037PE,DP05_0038PE,DP05_0071PE,DP05_0044PE,DP03_0062E,DP02_0068PE,DP02_0070PE&for=congressional%20district:*`
- 2019 ACS 1-year (for income change):
  `https://api.census.gov/data/2019/acs/acs1/profile?get=NAME,DP03_0062E&for=congressional%20district:*`

Variables: median age, % 65+, % White alone, % Black alone, % Hispanic, % Asian alone, median household income, % bachelor's degree or higher, % veterans. **Note:** some of these DP codes may differ by year; if one fails, find the equivalent code and say which one you used.

For redistricted states, 2026-line demographics may not exist from Census; if The Downballot, Dave's Redistricting, or state redistricting offices publish them, include them with a note.

### 8. `regional_prices.csv`: Inflation and gas prices

- **BLS CPI-U, 12-month % change for September 2026** (latest release): 4 Census regions, 9 divisions, and all ~23 metro areas BLS publishes. Columns: `area, area_type (region/division/metro), cpi_yoy_pct, core_yoy_pct (if available), month, source`.
- **AAA average regular gas price by state**: current (late Oct 2026) and roughly one year earlier, plus the earliest available price from just before the Iran war began. Columns: `state, gas_now, gas_year_ago, gas_prewar, prewar_date, source`.
- **BEA Regional Price Parities** (most recent year) by state and by metro area. Columns: `area, area_type, rpp_all_items, year, source`.

### 9. `iran_war_exposure.csv` (state or district level, whatever is available)
- Major military installations: `state, district (if known), base_name, branch`
- Any state-level polling on the Iran war (approve/disapprove), with pollster and date.

### 10. `polls.csv`: Race-level polls (Senate + competitive House)
All public general-election polls since **Sept 1, 2026**.

| column | |
|---|---|
| race_id | |
| pollster | |
| start_date, end_date | |
| sample_size, population | `LV` / `RV` / `A` |
| dem_pct, rep_pct, other_pct | |
| source | |

Sources: Wikipedia race pages, 270toWin, RealClearPolling, Silver Bulletin, DDHQ.

### 11. `candidate_favorability.csv`: Candidate likability
| column | |
|---|---|
| race_id, candidate, party | |
| favorable_pct, unfavorable_pct | from polls |
| pollster, end_date, source | |

Focus on the 35 Senate races and the ~60 most competitive House races (Toss-up / Lean in any rating).

### 12. `fundraising.csv`: FEC fundraising (competitive races)
From fec.gov (latest pre-general report, filed Oct 2026).
Columns: `race_id, candidate, party, total_receipts, cash_on_hand, as_of, source`.

### 13. `national_environment.csv`: One-off facts
One row per item: `item, value, as_of, source`. Include:
- Generic ballot average (Silver Bulletin, DDHQ, RCP, 538-equivalent)
- Trump job approval average
- Trump approval on Iran / foreign policy
- Trump approval on the economy / inflation
- Kalshi House-control and Senate-control prices

---

## What to send back

- All CSVs above (raw source files are fine if reformatting is hard. **Raw beats invented.**)
- A short `NOTES.md` listing anything you couldn't find, any judgment calls, and any sources that disagreed.

**Order of importance if time is short:** 1 → 2 → 4 → 5 → 3 → 6 → 10 → 7 → 8 → 11 → 12 → 13 → 9.
