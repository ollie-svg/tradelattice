# Release notes

## Unreleased

- The landed-cost computation is extracted from the route into `tradelattice.api.landed.compute(request, records, jurisdiction, today)`, a pure function over envelope dicts with no database, HTTP or clock (ADR 0005); `/landed-cost` and `/tariff/{hs}` are thin wrappers. Every 2xx and 409 response is unchanged. Non-2xx bodies gain a stable `reason` code beside `detail` (`docs/api.md`). Two tightenings that no existing data exercises: `tariff_line` and `surtax_order` records are scoped by envelope `jurisdiction`, and a jurisdiction with no tariff lines loaded returns 501 `jurisdiction_no_data` (the US message is unchanged). `tests/golden/landed_cost.jsonl` holds 14 self-contained parity cases.
- `/landed-cost` gains a `jurisdiction` switch (`CA`, `US`; US returns 501 until its data is loaded), a prohibited check (409 with the prohibition, before FX and tariff lookup), and an `fta_qualified` tri-state for surtax orders with `exempt_if`; the response gained four always-present fields (`jurisdiction`, `fta_qualified`, `surtax_if_fta_qualified`, `total_if_fta_qualified`). Computed numbers for existing CA requests are unchanged.
- `/landed-cost` gains cascading fees and taxes (`api/fees.py`): optional `include_taxes` (default `false`) adds Canadian GST (5% of duty-paid value); the response gains always-present `fees`, `taxes` and `include_taxes`, and `total` / `total_if_fta_qualified` include them. US MPF (dated FY2026/FY2027) and HMF schedules are defined for when the US profile returns data. Totals for requests without `include_taxes` are unchanged.

## v0.3 (2026-11-05)

- Added record type `prohibition` (an import prohibition by origin and tariff-code prefix and date range), and added it to the envelope `type` enum.
- Added optional `surtax_order` attributes `authority`, `basis`, `exempt_if`, `exclusion_ref`, `case_number`, `stacking` and `last_verified`. The `required` list is unchanged, so v0.2 records validate unchanged.
- Added a post-schema semantic check in `tradelattice.spec.validate`: for `prohibition` and `surtax_order`, `effective_to`, when set, must not be before `effective_from`.
- Added examples `prohibition.json` and `surtax_order_us232.json`; extended `surtax_order.json`.
- Bumped every schema `$id` from `/schemas/v0.2/` to `/schemas/v0.3/`.

## v0.2 (2026-11-03)

- Added record types `surtax_order`, `fx_rate` and `hs_concordance`, and added them to the envelope `type` enum.
- Added optional `edition` (pattern `^T\d{4}(-\d+)?$`) to `tariff_line`.
- Bumped every schema `$id` from `/schemas/v0.1/` to `/schemas/v0.2/`.
- v0.1 validators reject the new record types by design, because the envelope `type` enum is closed.
- Moved the `api`, `spec` and `connectors` packages under `src/tradelattice/`, so the installed package is `tradelattice`. Module paths are now `tradelattice.api`, `tradelattice.spec` and `tradelattice.connectors` (for example `python -m tradelattice.connectors.cbsa_tariff`, `python -m tradelattice.api.cli`, `uvicorn tradelattice.api.main:app`). Behaviour is unchanged; set `TRADELATTICE_WEB_DIR` to point the API at a different `web/` directory.
- Added the `boc_fx` connector, which emits `fx_rate` records from the Bank of Canada Valet API (live by default, fetching the last 10 days unless a window is given; bundled sample offline).
- Added the `cbsa_concordance` connector, which loads CBSA/Finance Canada concordance workbooks (xlsx; 8-digit HS-cycle and yearly 10-digit) as `hs_concordance` records; adds the `openpyxl` dependency.
- Added the `cbsa_surtax` connector, which emits `surtax_order` records from Finance Canada's counter-tariff lists on US-origin goods (629 lines effective 2026-09-08) plus an `applicable()` lookup helper; remission orders and exclusions are not modelled.
- `/landed-cost` v2 converts the declared value to CAD at the Bank of Canada rate for a new optional `shipment_date` and adds origin surtax from `surtax_order` records; the response gains `value_cad`, `fx_rate`, `fx_on`, `surtax_pct`, `surtax`, `surtax_list_id`, `declared_currency` and `shipment_date`, `currency` is now always `CAD`, and `total` includes surtax.
