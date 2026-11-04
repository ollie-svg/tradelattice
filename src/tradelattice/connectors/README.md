# connectors

Offline-first data connectors (ADR 0003). Each emits Envelope records validating against `src/tradelattice/spec/schemas`.

| Connector | Output | Sample |
|---|---|---|
| `cbsa_tariff` | `tariff_line` | `cbsa_tariff/sample/customs_tariff_sample.csv` |
| `canadabuys` | `tender` | `canadabuys/sample/tender_notices_sample.csv` |
| `statcan_trade` | `price_observation` | `statcan_trade/sample/cimt_imports_sample.csv` |
| `boc_fx` | `fx_rate` | `boc_fx/sample/fx_rates_daily_sample.json` |
| `cbsa_concordance` | `hs_concordance` | `cbsa_concordance/sample/*.xlsx` |

```
python -m tradelattice.connectors.<name> --out records.jsonl [--since 2026-02-01] [--live]
```

`--live` raises `NotImplementedError` for all connectors except `cbsa_tariff`, `boc_fx` and `cbsa_concordance`. Live sources:
- cbsa_tariff: live mode implemented (HTML chapter pages, T2026-2; `--live [--chapters 9,20]`), see https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/2026/menu-eng.html
- boc_fx: live mode implemented (Bank of Canada Valet, `FX_RATES_DAILY`), see below
- cbsa_concordance: live mode implemented (yearly menu page -> xlsx workbooks), see below
- canadabuys: https://canadabuys.canada.ca/en/tender-opportunities
- statcan_trade: https://www150.statcan.gc.ca/

Sample data is illustrative, not authoritative. Shared helpers live in `_base.py`.

## boc_fx

Emits one `fx_rate` record per (date, currency) from the Bank of Canada Valet API (`FX_RATES_DAILY`, 24+ currencies to CAD). Ids are `boc_fx:<date>:<CUR>`; `attributes.rate` is the decimal string as published. Live fetch uses an explicit date window, never `recent=N`.

```
python -m tradelattice.connectors.boc_fx --out fx.jsonl --live [--since YYYY-MM-DD] [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--currencies USD,EUR]
```

Default live window: the last 10 calendar days ending today (UTC). `--since` sets the start; `--start`/`--end` override. Without `--live` it reads the bundled 3-day sample.

CBSA valuation uses the BoC rate on the date of direct shipment, so consumers should pick the record whose `on` is the latest one <= that date.

## cbsa_concordance

Loads CBSA / Finance Canada concordance workbooks (xlsx) as `hs_concordance` records, one per (from, to) code pair. It accepts any CBSA concordance workbook: the 8-digit HS-cycle tables (`conc-8-finance-2022.xlsx`, old to new) and the yearly 10-digit within-year table (`conc-10-finance-2026.xlsx`, published new to obsolete and flipped to from=obsolete, to=new). The next HS edition is HS 2028, in force 2028-01-01; no HS 2027/2028 table is published yet.

```
python -m tradelattice.connectors.cbsa_concordance --out conc.jsonl [--live] [--year 2026] [--file conc-10-finance-2026.xlsx] [--from-edition T2021 --to-edition T2022] [--report]
```

- Without `--live` it reads both bundled workbooks (1,472 + 23 records; editions T2021 to T2022 and T2025 to T2026).
- `--live` fetches `https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/<year>/menu-eng.html` (default: current UTC year), downloads the linked concordance workbooks and parses them. `--file` restricts to one filename.
- Editions default to `T<year-1>` to `T<year>` (assumes the January file supersedes the prior year's last edition). A `conc-8` file needs `--from-edition` and `--to-edition`, otherwise `ValueError`.
- Relations: `same` (equal codes, 1:1), `renumbered` (different codes, 1:1), `split` (source has several targets; wins over `merged` when both apply), `merged` (target has several sources, source has one target). `removed` is never produced: every row has both codes.
- `observed_at` is `<to_edition year>-01-01T00:00:00Z` (assumed edition start). `--report` prints counts by relation and by Finance change code (SC, WC, ...) to stderr; change codes are not stored in records.
