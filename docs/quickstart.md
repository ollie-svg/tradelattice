# Quickstart

TradeLattice needs Python 3.11 or newer. The steps below use only the bundled sample data.

## Install

```
git clone https://github.com/ollie-svg/tradelattice
cd tradelattice
pip install -e .[dev]
```

## Run the connectors from samples

```
make load-samples
```

This runs the three connectors against their bundled sample files. It writes `records.jsonl`, then loads it into SQLite.

## Serve and open the browser

```
make serve
python -m webbrowser http://localhost:8000
```

The API listens on port 8000. The web UI is served at `/`, and OpenAPI docs at `/docs`.

## Load your own data

Write one JSON record per line (JSONL). Each record must match the [Envelope](spec.md). This is a valid `tariff_line` record, shown on one line in the file:

```json
{
  "id": "cbsa_tariff:0902.30.00.00",
  "type": "tariff_line",
  "source": "cbsa_tariff",
  "observed_at": "2026-01-01T00:00:00Z",
  "jurisdiction": "CA",
  "attributes": {
    "hs_code": "09023000",
    "description": "Black tea (fermented) and partly fermented tea, in immediate packings of a content not exceeding 3 kg",
    "rates": [
      {"treatment": "MFN", "rate": "Free"},
      {"treatment": "CUSMA", "rate": "Free"}
    ],
    "effective_from": "2026-01-01",
    "effective_to": null
  }
}
```

Validate your file, then load it:

```
python -m spec.validate spec/examples/*.json
python -m api.cli load my-records.jsonl
```
