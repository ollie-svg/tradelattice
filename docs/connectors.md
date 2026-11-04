# Connectors

A connector maps one public dataset into spec records. Each lives in `src/tradelattice/connectors/<name>/`.

| Connector | Source dataset | Emits | Sample | `--live` |
| --- | --- | --- | --- | --- |
| `cbsa_tariff` | CBSA Customs Tariff schedule | `tariff_line` | Bundled CSV | Not implemented |
| `canadabuys` | CanadaBuys open tender notices | `tender` | Bundled CSV | Not implemented |
| `statcan_trade` | Statistics Canada merchandise trade by HS6 | `price_observation` (unit value = value / quantity) | Bundled CSV | Not implemented |
| `boc_fx` | Bank of Canada Valet daily exchange rates | `fx_rate` | Bundled JSON | Implemented (default useful path) |
| `cbsa_concordance` | CBSA / Finance Canada HS concordance workbooks | `hs_concordance` | Bundled xlsx (two files) | Implemented |

## Run a connector

```
python -m tradelattice.connectors.cbsa_tariff --out records.jsonl
python -m tradelattice.connectors.canadabuys --out tenders.jsonl --since 2026-01-01
```

Without `--live`, the connector reads its bundled sample and never touches the network. With `--live`, it raises `NotImplementedError` today and names the dataset URL to implement against. See [ADR 0003](adr/0003-connectors-offline-first.md).

## boc_fx

Emits one `fx_rate` per (date, currency) to CAD from the Bank of Canada Valet API (`FX_RATES_DAILY`). Live mode is the useful path; without `--live` it reads a bundled 3-day sample.

```
python -m tradelattice.connectors.boc_fx --out fx.jsonl --live --start 2026-10-27 --end 2026-11-03 --currencies USD,EUR
```

Window flags: by default the last 10 calendar days ending today (UTC). `--since` sets the start, `--start` and `--end` set the window explicitly, and `--currencies` filters. The connector always queries a date window, never `recent=N`, which returns stale data.

CBSA valuation uses the BoC rate on the date of direct shipment, so consumers pick the record with `on` <= that date (the latest such one).

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

## Edition tracking

A scheduled workflow (`.github/workflows/cbsa-edition-check.yml`, Mondays 14:00 UTC) checks the CBSA edition index for a new Customs Tariff edition. When one appears it fetches the new and previous revisions, diffs the rates, opens a GitHub issue with the report, and commits the updated state file. Full snapshots are not committed.

Run it by hand:

```
python -m tradelattice.connectors.cbsa_tariff editions --year 2026
python -m tradelattice.connectors.cbsa_tariff check --state data/cbsa_edition.json   # exit 10 = new edition
python -m tradelattice.connectors.cbsa_tariff diff old.jsonl new.jsonl --markdown
make edition-check
make edition-diff OLD=old.jsonl NEW=new.jsonl
```

The last-seen edition is stored in `data/cbsa_edition.json` (`name`, `revision`, `effective_from`, `checked_at`).

## Write a new connector

Create `src/tradelattice/connectors/<name>/` with an `__init__.py`, a `__main__.py` and a `sample/` folder. Expose one function:

```python
def fetch(since: datetime | None = None, live: bool = False) -> Iterator[Envelope]:
    ...
```

The contract:

- Yield Envelope-shaped dicts. Build them with `connectors._base.envelope(...)`.
- Without `live`, read only the bundled sample file.
- With `live`, either fetch real data or raise `live_not_implemented(NAME, LIVE_URL)`.
- Treat `since` as an optional lower bound. Ignore it if the source is a full snapshot.

The `__main__.py` calls `connectors._base.run_cli(NAME, fetch, None)`. That adds the `--out`, `--live` and `--since` flags.
