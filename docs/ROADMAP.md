# Roadmap

## v0.3.1 (current, 2026-11-24)
Schema with 10 record types (spec v0.3: adds `prohibition`; overlay fields on `surtax_order`; `effective_to` exclusive spec-wide; `stacking` declared, not computed). Live connectors: CBSA tariff (all editions, with edition tracking and diff), Bank of Canada FX, CBSA concordance workbooks, Finance Canada counter-tariff list. Sample connectors: CanadaBuys, StatCan trade. FastAPI service with SQLite (Postgres via `DATABASE_URL`), static web UI.

Landed cost: every CBSA duty-rate form; origin surtax with the v0.3 conditions honoured (content basis → 422 `surtax_content_basis`; more than one order → 422 `surtax_ambiguous`; `exempt_if` with the FTA tri-state); CAD conversion at the BoC rate for the shipment date; prohibited goods → 409 before anything is computed; a `jurisdiction` switch (CA; US returns 501 `jurisdiction_no_data` until its data is loaded); cascading fees with GST opt-in for Canada. The computation is a pure function, `tradelattice.api.landed.compute()`, with no database, HTTP or clock; `/landed-cost` is a thin wrapper (ADR 0005). `tradelattice.golden` ships 17 parity cases and the comparison rule as package data, so a consumer running its own implementation checks against the same file it installed.

## Next
- **December 1, 2026 amendment** (CBSA Customs Notice 26-27): the first edition published from CARM-generated files. The HTML chapter pages the tariff reader parses are stated to be unchanged; the concordance workbook layout is not stated, and `cbsa_concordance` has never seen a CARM-generated table. It refuses unrecognised layouts rather than guessing; a third layout is added the week the table publishes if needed. Then the T2027 yearly concordance (last year's table came the week of December 8).
- `fee_rule` record type: the GST rate and the US MPF/HMF schedules move from `jurisdictions.py` into records with a connector and a bundled sample (ADR 0001, schema-first). This is the data-model change deferred from v0.3.1.
- US data: `usitc_hts`, `treasury_fx`, `us_overlays` (Section 232/301/338 and prohibitions, hand-curated rules file with `last_verified` on every row). Gated on a paying Canadian partner or an inbound US broker.
- Hosted demo instance with the full live schedule, surtax list and FX loaded.

## Deferred
- **Stored-data audit.** A `validate --db` (or `tradelattice-api audit`) mode that runs the current validator over every record already in a database and reports failures by id, so an instance loaded under an older spec surfaces records a newer semantic check rejects (first case: `effective_to` before `effective_from`, enforced from v0.3). Needed before the first hosted instance is upgraded in place.
- TRQ in-quota / over-quota rate pairs in `tariff_line.rates[]` and the duty parser.
- Surtax remission orders and exclusions.
- PST/HST (depends on the importer's province and registration: a tenant fact, not a line fact).
- Authentication and authorization; multi-tenant deployments.
- Real-time feeds.

## Later ideas
- Additional connectors (provincial tenders, port data, supplier registries)
- Postgres-first deployment guide
- HS 2028 concordance load when CBSA publishes (edition in force Jan 1, 2028)
- Other countries' tariff and procurement connectors
