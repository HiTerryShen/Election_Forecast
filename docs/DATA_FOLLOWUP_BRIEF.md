# Follow-up: data still needed

Thanks, `kalshi_prices.csv` loaded cleanly (863 rows, all 435 House + 35 Senate race IDs present, same 2026-11-01 17:03 ET snapshot). Same rules as the original brief: exact formats, no invented values, blanks are fine.

## 1. URGENT: fill missing Kalshi prices (same file format, same timestamp if possible)

These 86 races are in the file but have **no price**. They are mostly the *competitive* races, which are worth the most points, so this is the top priority. Kalshi probably lists these markets under candidate-name tickers rather than `-D` / `-R` tickers (e.g., `KXHOUSERACE-AZ06-26-<initials>`), which may be why they were missed. Check the race's event page on Kalshi for all candidate markets.

```
AK-0 AZ-1 AZ-2 AZ-6 CA-3 CA-4 CA-7 CA-9 CA-11 CA-12 CA-13 CA-14 CA-21 CA-22 CA-27 CA-29
CA-34 CA-37 CA-40 CA-41 CA-45 CA-47 CA-49 CO-3 CO-8 CT-5 FL-13 FL-23 IA-1 IA-3 IL-17
IN-1 IN-7 ME-2 MI-3 MI-4 MI-7 MI-8 MI-10 MN-2 MO-5 MT-1 NC-1 NC-11 NE-2 NH-1 NJ-5 NJ-7
NJ-9 NM-2 NV-1 NV-3 NV-4 NY-3 NY-4 NY-17 NY-18 NY-19 NY-22 OH-1 OH-9 OH-13 OR-5 PA-1
PA-7 PA-8 PA-10 PA-17 TX-9 TX-15 TX-28 TX-32 TX-34 TX-35 UT-1 UT-2 UT-3 VA-1 VA-2 VA-7
VA-10 WA-3 WA-8 WI-1 WI-3
Senate: KY-S
```

Also fill in the **missing candidate names** (rows where `candidate` is blank, e.g., the R nominee rows in CA-06, WI-02, PA-03, NJ-08, MA-05, MA-07).

Return either a full replacement `kalshi_prices.csv` or a `kalshi_prices_missing.csv` with just these rows.

## 2. Then the rest of the original brief, in this order

1. `races_2026.csv`: all 470 races, incumbents, nominees, `uncontested`, `top_two_same_party`, `redistricted_2026`, ratings
2. `cook_pvi.csv`: district PVI + state PVI for the 35 Senate states
3. `pres_by_district.csv`: 2020 + 2024 presidential results, **old and new lines** for redrawn states
4. `redistricting_2026.csv`
5. `house_results_history.csv`: 2022 + 2024 at minimum (raw MIT Election Lab CSV is fine)
6. `polls.csv`: Senate + competitive House, since Sept 1
7. Census ACS JSON (the two API URLs in the brief)
8. `regional_prices.csv` (CPI incl. **South region**, AAA gas by state now vs pre-war)
9. `candidate_favorability.csv`, `fundraising.csv`
10. `iran_war_exposure.csv`, `national_environment.csv`

### Special handling: independents who are the main challenger
In **NE-S (Dan Osborn), MT-S (Seth Bodnar), ID-S (Todd Achilles), SD-S (Brian Bengs)** the leading non-Republican is an independent. And in **CA-06**, Kevin Kiley (I) vs Richard Pan (D) is the real race. For these races, in `polls.csv` put the leading non-Republican's share in `dem_pct` (for CA-06: Pan in `dem_pct`, Kiley in `rep_pct`) and add a `note` column explaining it. In `races_2026.csv`, list the independent in `other_candidate`.
