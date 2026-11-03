# 2026 U.S. House & Senate Forecast Data — collection notes

Collection snapshot: 2026-11-01 17:03 ET.

## Kalshi prices updated

`kalshi_prices.csv` is now populated from Kalshi's public market-data API, filtered to 2026 House candidate contracts and Senate race contracts (including the Florida and Ohio special elections). Each row includes its individual market API URL and the snapshot timestamp. `price_type=last` is Kalshi's last traded YES price; `mid` is the arithmetic midpoint of a usable YES bid/ask pair when a last trade was not available. Prices are decimals from 0 to 1.

Coverage in the CSV: 435 distinct voting House race IDs and 35 distinct Senate race IDs. The District of Columbia delegate market was excluded because it is not one of the 435 voting House seats. All 470 race IDs have candidate-level prices in this revision (950 priced rows, including multiple contracts where Kalshi offered them). The 86 previously blank races were filled with candidate-level Kalshi prices as of the same 2026-11-01 17:03 ET cutoff. The previously blank nominee names for party-level contracts were completed from Kalshi market metadata. Candidate-specific California contracts do not expose party in the market API, so party cells remain blank for those rows rather than being inferred. For NC-11, the Republican price is the NO-side complement of the two-candidate Jamie Ager market. All new prices are last traded prices.

## Other files updated

- `races_2026.csv` has 470 race rows and candidate names. Cook ratings are present for 464 races. Six House at-large Cook ratings and all Sabato/Inside Elections ratings remain blank. Incumbent terms remain blank; some incumbent names are unavailable in the candidate list when the incumbent is not running.
- `cook_pvi.csv` has 435 district PVI values plus state PVI for all 35 Senate races. Redrawn district rows are labeled `2026 redraw`; non-redrawn lines are labeled `2025`.
- `pres_by_district.csv` has 435 rows each for `2024_lines` and `2026_lines`. Published percentages are rounded to whole points; source sheets leave some 2020 values blank for districts that did not exist on those lines.
- `redistricting_2026.csv` marks whether a state map is in effect for 2026. Details such as affected districts, partisan direction, and expected seat shift remain blank unless confirmed.
- `house_results_history.csv` has raw MIT Election Data + Science Lab general-election candidate rows for 2022 and 2024. The raw field names are retained and a `source` column is appended.
- The other requested CSVs remain empty templates pending collection.

## Sources

- Kalshi public market-data API, House series: https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHOUSERACE
- Kalshi public market-data API docs: https://docs.kalshi.com/api-reference/markets/get-markets
- Kalshi 2026 election markets: https://kalshi.com/category/elections/midterms
- 2026 House elections overview: https://en.wikipedia.org/wiki/2026_United_States_House_of_Representatives_elections
- 2025–2026 redistricting overview: https://en.wikipedia.org/wiki/2025%E2%80%932026_United_States_redistricting
- Cook PVI: https://www.cookpolitical.com/cook-pvi
- Census 2024 ACS 1-year API docs: https://api.census.gov/data/2024/acs/acs1.html
- MIT Election Data + Science Lab, U.S. House 1976–2024: https://doi.org/10.7910/DVN/IG0UN2

The files are a transparent starter pack, not a complete forecasting dataset. Empty cells mean “not collected/verified,” not zero.


## Priority data added in this revision

- `races_2026.csv` contains 435 House and 35 Senate races with candidate names and party codes from DeepSyte’s public 2026 ballot candidate compilation. It reports state-certified lists for 41 states and recorded nominees for other states. Sabato/Inside Elections ratings and incumbent terms remain blank where sources did not establish them.
- `cook_pvi.csv` uses the public Cook PVI tables reproduced in Wikipedia, which cites Cook Political Report. Cook Political Report’s 2026 House race table supplies all 435 district values and state-level values for all 35 Senate states. Signed PVI values follow the requested direction.
- `pres_by_district.csv` contains The Downballot’s 2020/2024 presidential percentages for 2024 lines and its 2026-line reallocation, rounded as published.
- `redistricting_2026.csv` marks the nine states whose 2026 maps are in effect per the Census Bureau: AL, CA, FL, LA, NC, OH, TN, TX, UT. Missouri’s proposed map was blocked. Other attempted states are retained as N where tracked; unconfirmed detail fields remain blank.
- `house_results_history.csv` contains raw MIT Election Data + Science Lab general-election rows for 2022 and 2024, via a public data mirror, plus a source URL column.

## Follow-up collection — 2026-11-01

- `kalshi_prices.csv`: added Julia Letlow (R) at 0.90 and Jamie Davis (D) at 0.11 from the Kalshi Louisiana Senate event page. The page showed Yes prices of 90¢ and 11¢ on Nov. 1 but did not expose an exact intraday timestamp; `as_of` is date-only. `price_type=last` reflects the page's displayed live contract price. Source: https://kalshi.com/markets/kxsenatela/who-will-win-the-senate-race-in-louisiana/kxsenatela-26nov
- `polls.csv`: added the Hart Research Associates Louisiana Senate poll (field dates Oct. 28–29; LV n=502; Davis 45, Letlow 45, undecided 10). It is one source-backed record, not a complete Senate/competitive House poll collection. The remaining rows are not represented as zero or estimated.
- `regional_prices.csv`: added all four BLS Census regions, nine divisions, and the BLS selected local CPI areas for September 2026. Dashes in the BLS September selected-area table remain blank. Core CPI is blank because the cited selected-area table publishes all-items CPI only. Added AAA daily state regular-gas prices for all 50 states as of Nov. 1, 2026; year-ago and pre-war gas columns remain blank because a comparable state-by-state historical AAA table for those dates was not accessible in this collection. BEA RPP columns are blank.
- `acs_district.csv` remains header-only. The requested Census 2024 and 2019 API URLs now return a `Missing Key` response. Census’s current developer documentation says API data queries require an API key; no key was available in this environment. No ACS values were substituted. Sources: https://api.census.gov/data/2024/acs/acs1/profile and https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html
- `polls.csv` now includes 95 additional source-linked Senate and Cook Toss Up House poll rows from Polling Forecast’s 2026 poll feed (feed snapshot dated 2026-10-31; https://www.pollingforecast.com/api/us/polls?since=2026-09-01). Senate rows cover AK, FL, IA, KS, ME, MI, MT, NC, NE, OH, SC and TX; House rows cover Cook Toss Up races with public poll entries. Poll field dates and sample/population values are retained when reported; unavailable sample sizes remain blank. The source feed contains more polls than included here, so this is a useful targeted collection, not an exhaustive import of every feed row. Direct poll-source URLs are in each row. Independents Dan Osborn (NE) and Seth Bodnar (MT) follow the requested dem_pct mapping; see row notes. Florida and Ohio are keyed to special races FL-S2 and OH-S2. House race IDs are zero-padded to match the race list.

- Added two additional source-backed Louisiana Senate polls from September and Oct. 29–31. The Oct. 29–31 Lincoln Park Strategies source does not state n; sample_size is blank. For the Oct. 28–29 Hart poll, Polling Forecast records n=502 while WWNO reports 500 in article prose; the CSV follows the poll record's 502 and the notes retain the discrepancy. The current zip includes 98 total poll rows, including the three earlier Louisiana rows.


## 2026-11-02 correction

- Corrected `races_2026.csv` NE-S independent candidate from Chuck Conboy to Dan Osborn. The Nebraska Secretary of State certified Osborn’s Senate petition; FEC identifies Osborn as an independent Senate candidate. The Democratic primary winner withdrew, so `dem_candidate` remains blank. `uncontested=Y` remains under the brief’s definition (only one major-party candidate), while Osborn is listed under `other_candidate`. Sources: https://sos.nebraska.gov/secretary-state-certifies-dan-osborns-us-senate-candidate-petition and https://www.fec.gov/data/candidate/S4NE00207/?cycle=2026&election_full=true.
- ACS JSON files are still not included: Census API calls require an API key, and none has been provided.

- `regional_prices.csv`: filled all 50 state `gas_prewar` entries with AAA-attributed state averages published on 2026-02-18 (two-decimal precision as published), ten days before the conflict began on February 28. The source page identifies AAA as the data source; PolicyViz confirms February 18 as the pre-war comparison date. This is a contemporaneous published baseline, not a reconstructed daily AAA history. Source: https://finance.yahoo.com/news/most-expensive-gas-prices-u-024805576.html; https://policyviz.com/2026/10/22/gas-prices-by-state/.
- `fundraising.csv`: added FEC receipts and cash on hand for Nebraska Senate candidates Dan Osborn and Pete Ricketts, through 2026-10-14 (latest report shown in FEC). Other competitive-race fundraising remains uncollected.
- `candidate_favorability.csv` and `iran_war_exposure.csv` remain header-only; no verified candidate-level favorability/base-by-district dataset was added in this revision.
