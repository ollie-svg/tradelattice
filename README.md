# TradeLattice

TradeLattice is an open data standard and reference stack for coordinating goods and services across a national economy. It defines a small, stable JSON Schema data model (products, tariff lines, suppliers, tenders, shipments, price observations), ships connectors that map real Canadian public datasets into it, and provides an API and web UI that are useful to a single user on day one. Canada is the first target; the schema is country-agnostic.

## Quickstart

```
pip install -e .[dev]
make load-samples        # run connectors from bundled samples and write records
make serve               # load into SQLite and start the API on :8000
python -m webbrowser http://localhost:8000
make test
```

(Connectors, API and web UI are built in `connectors/`, `api/` and `web/`; see the Makefile for exact commands.)

Validate the spec examples: `python -m spec.validate spec/examples/*.json`

## Learn more

- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md) and [GOVERNANCE.md](GOVERNANCE.md)

Licensed under Apache-2.0.
