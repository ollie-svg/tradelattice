# Connectors

A connector maps one public dataset into spec records. Each lives in `src/tradelattice/connectors/<name>/`.

| Connector | Source dataset | Emits | Sample | `--live` |
| --- | --- | --- | --- | --- |
| `cbsa_tariff` | CBSA Customs Tariff schedule | `tariff_line` | Bundled CSV | Not implemented |
| `canadabuys` | CanadaBuys open tender notices | `tender` | Bundled CSV | Not implemented |
| `statcan_trade` | Statistics Canada merchandise trade by HS6 | `price_observation` (unit value = value / quantity) | Bundled CSV | Not implemented |
| `boc_fx` | Bank of Canada Valet daily exchange rates | `fx_rate` | Bundled JSON | Implemented (default useful path) |

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
