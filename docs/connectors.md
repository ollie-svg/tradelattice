# Connectors

A connector maps one public dataset into spec records. Each lives in `connectors/<name>/`.

| Connector | Source dataset | Emits | Sample | `--live` |
| --- | --- | --- | --- | --- |
| `cbsa_tariff` | CBSA Customs Tariff schedule | `tariff_line` | Bundled CSV | Not implemented |
| `canadabuys` | CanadaBuys open tender notices | `tender` | Bundled CSV | Not implemented |
| `statcan_trade` | Statistics Canada merchandise trade by HS6 | `price_observation` (unit value = value / quantity) | Bundled CSV | Not implemented |

## Run a connector

```
python -m connectors.cbsa_tariff --out records.jsonl
python -m connectors.canadabuys --out tenders.jsonl --since 2026-01-01
```

Without `--live`, the connector reads its bundled sample and never touches the network. With `--live`, it raises `NotImplementedError` today and names the dataset URL to implement against. See [ADR 0003](adr/0003-connectors-offline-first.md).

## Write a new connector

Create `connectors/<name>/` with an `__init__.py`, a `__main__.py` and a `sample/` folder. Expose one function:

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
