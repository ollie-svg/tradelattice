# Roadmap

## v0.3 (current)
Schema with 10 record types (spec v0.3: adds `prohibition`; overlay fields on `surtax_order`). Live connectors: CBSA tariff (all editions, with edition tracking and diff), Bank of Canada FX, CBSA concordance workbooks, Finance Canada counter-tariff list. Sample connectors: CanadaBuys, StatCan trade. FastAPI service with SQLite (Postgres via `DATABASE_URL`), static web UI. Landed cost with every CBSA duty-rate form, origin surtax, and CAD conversion at the BoC rate for the shipment date.

## Next
- Jurisdiction switch on `/landed-cost`: `jurisdiction`, `fta_qualified`, `mode`; HTTP 409 for prohibited goods; both outcomes when FTA qualification is unknown.
- Cascading fees: ordered fee rules per jurisdiction; GST opt-in for Canada; MPF/HMF for the US.
- US data: `usitc_hts`, `treasury_fx`, `us_overlays` (Section 232/301/338 and prohibitions, hand-curated rules file with `last_verified` on every row). Gated on a paying Canadian partner or an inbound US broker.
- Hosted demo instance with the full live schedule, surtax list and FX loaded.

## Deferred
- **Stored-data audit.** A `validate --db` (or `tradelattice-api audit`) mode that runs the current validator over every record already in a database and reports failures by id, so an instance loaded under an older spec surfaces records a newer semantic check rejects (first case: `effective_to` before `effective_from`, enforced from v0.3). Needed before the first hosted instance is upgraded in place.
- TRQ in-quota / over-quota rate pairs in `tariff_line.rates[]` and the duty parser.
- Surtax remission orders and exclusions.
- PST/HST (depends on the importer's province and registration: a tenant fact, not a line fact).
- Authentication and authorization; multi-tenant deployments.
- Real-time feeds.
- ML (matching, forecasting, classification).

## Later ideas
- Additional connectors (provincial tenders, port data, supplier registries)
- Postgres-first deployment guide
- HS 2028 concordance load when CBSA publishes (edition in force Jan 1, 2028)
- Other countries' tariff and procurement connectors
