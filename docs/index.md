---
title: Home
description: The open data standard for goods, tariffs, tenders and shipments. Canada first, country-agnostic by design.
---

# TradeLattice

**The open data standard for goods, tariffs, tenders and shipments. Canada first, country-agnostic by design.**

## Who it is for

### Customs brokers

Look up the best-matching tariff line for an HS code. See MFN and CUSMA rates side by side.

### Importers

Estimate duty and landed cost before you ship. Compare treatments for the same goods.

### Public buyers

Search open tender notices and price observations in one schema. Reuse the same records across systems.

## Quickstart

```
pip install -e .[dev]
make load-samples        # run connectors from bundled samples and write records
make serve               # load into SQLite and start the API on :8000
python -m webbrowser http://localhost:8000
make test
```

See the [full quickstart](quickstart.md) for details.

Results are indicative only and are not customs, legal or tax advice.

## Check our numbers

TradeLattice has never been checked against a real customs entry. We are asking licensed customs brokers, and importers who hold their own entries, to change that.

Share twenty past entry lines with your own duty, surtax and GST totals, with importer names and transaction numbers removed. They stay private. In return we run your tariff items against CBSA's December 2026 amendment and the January 2027 renumbering, and send you every line that changes.

Nothing is for sale and there is no deadline. Email [hello@tradelattice.ca](mailto:hello@tradelattice.ca).
