# connectors

Offline-first data connectors (ADR 0003). Each emits Envelope records validating against `spec/schemas`.

| Connector | Output | Sample |
|---|---|---|
| `cbsa_tariff` | `tariff_line` | `cbsa_tariff/sample/customs_tariff_sample.csv` |
| `canadabuys` | `tender` | `canadabuys/sample/tender_notices_sample.csv` |
| `statcan_trade` | `price_observation` | `statcan_trade/sample/cimt_imports_sample.csv` |

```
python -m connectors.<name> --out records.jsonl [--since 2026-02-01] [--live]
```

`--live` raises `NotImplementedError` for all connectors except `cbsa_tariff`. Live sources:
- cbsa_tariff: live mode implemented (HTML chapter pages, T2026-2; `--live [--chapters 9,20]`), see https://www.cbsa-asfc.gc.ca/trade-commerce/tariff-tarif/2026/menu-eng.html
- canadabuys: https://canadabuys.canada.ca/en/tender-opportunities
- statcan_trade: https://www150.statcan.gc.ca/

Sample data is illustrative, not authoritative. Shared helpers live in `_base.py`.
