# TradeLattice

**An open data standard and reference stack for what goods actually cost at the border.** Canada first; the schema is country-agnostic.

TradeLattice defines a small, versioned JSON Schema for the records a customs broker, importer or researcher needs — tariff lines, surtax orders, exchange rates, HS concordances, prohibitions, suppliers, tenders, shipments, price observations — and ships connectors that load the real published data into it, an API that computes a landed cost from those records, and a web UI you can run in a minute.

The numbers are traceable: every landed-cost response itemises each step (exchange rate and date, duty rate and basis, surtax and the order it came from, each fee and tax), so a broker can check it against their own entry.

## What it does today

- **Tariff lookup** across the full current CBSA Customs Tariff edition (12,470 lines, T2026-2), pulled live from CBSA's own pages, with longest-prefix matching.
- **Landed cost** for a tariff line, origin, declared value and shipment date: converts to CAD at the Bank of Canada rate for that date, evaluates every duty-rate form in the schedule (ad valorem, specific, compound, "not less than"), adds any surtax in force for the origin, and optionally GST on the duty-paid value.
- **Prohibited goods** return a 409 with the order cited, not a number.
- **Edition tracking:** a weekly job detects a new CBSA edition, diffs every rate against the previous one, and opens an issue with the changes.
- **Concordance:** loads CBSA's HS concordance workbooks and classifies each mapping (same, renumbered, split, merged) so a broker's book can be migrated with the ambiguous lines flagged for review.

Live connectors: `cbsa_tariff`, `cbsa_surtax` (Finance Canada counter-tariff list), `boc_fx` (Bank of Canada), `cbsa_concordance`. Sample-only: `canadabuys`, `statcan_trade`.

## Quickstart

```
pip install -e .[dev]
make load-samples        # run every connector from bundled samples and load SQLite
make serve               # start the API on :8000, then open http://localhost:8000
make test
```

Then, for real data instead of samples:

```
python -m tradelattice.connectors.cbsa_tariff --live --out tariff.jsonl    # full current edition
python -m tradelattice.connectors.cbsa_surtax --live --out surtax.jsonl
python -m tradelattice.connectors.boc_fx --live --out fx.jsonl
for f in tariff surtax fx; do python -m tradelattice.api.cli load $f.jsonl; done
```

One request:

```
curl -X POST localhost:8000/landed-cost -H 'content-type: application/json' -d '{
  "hs_code": "7208.36.00", "origin_country": "US",
  "declared_value": {"amount": 10000, "currency": "USD"},
  "treatment": "UST", "shipment_date": "2026-11-04", "include_taxes": true
}'
```

returns the CAD value at the BoC rate, duty under CUSMA (Free), the 50% counter-tariff surtax in force for US-origin steel, GST on the duty-paid value, and the total — each as its own line.

## The spec

Ten record types sharing one envelope, published as JSON Schema 2020-12 under `src/tradelattice/spec/schemas/` (current: **v0.3**). Adding a type or an optional field is a minor bump; old records keep validating. Validate anything with:

```
python -m tradelattice.spec.validate records.jsonl
```

Spec changes are proposed as issues before PRs; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Learn more

- Website and full docs: <https://tradelattice.ca>
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Roadmap: [docs/ROADMAP.md](docs/ROADMAP.md) · Release notes: [docs/release-notes.md](docs/release-notes.md)
- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md) · [GOVERNANCE.md](GOVERNANCE.md) · [SECURITY.md](SECURITY.md)

## Status and limits

Pre-1.0. Results are indicative and are not customs, legal or tax advice. Not modelled yet: surtax remission orders and exclusions, PST/HST, tariff-rate quotas, and the US jurisdiction (registered, returns 501 until its data is loaded). Python 3.11+.

Maintained by [Browes AI](https://browes.ai). Licensed under Apache-2.0.
