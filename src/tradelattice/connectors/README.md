# connectors

Offline-first data connectors (ADR 0003). Each emits Envelope records validating against `src/tradelattice/spec/schemas`.

| Connector | Output | Sample |
|---|---|---|
| `cbsa_tariff` | `tariff_line` | `cbsa_tariff/sample/customs_tariff_sample.csv` |
| `canadabuys` | `tender` | `canadabuys/sample/tender_notices_sample.csv` |
| `statcan_trade` | `price_observation` | `statcan_trade/sample/cimt_imports_sample.csv` |
| `boc_fx` | `fx_rate` | `boc_fx/sample/fx_rates_daily_sample.json` |

```
python -m tradelattice.connectors.<name> --out records.jsonl [--since 2026-02-01] [--live]
```

`--live` raises `NotImplementedError` for all connectors except `cbsa_tariff` and `boc_fx`. Live sources:
- cbsa_tariff: live mode implemented (HTML chapter pages, T2026-2; `--live [--chapters 9,20]`), see https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/2026/menu-eng.html
- boc_fx: live mode implemented (Bank of Canada Valet, `FX_RATES_DAILY`), see below
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
