# Release notes

## Unreleased

- `/landed-cost` gains a `jurisdiction` switch (`CA`, `US`; US returns 501 until its data is loaded), a prohibited check (409 with the prohibition, before FX and tariff lookup), and an `fta_qualified` tri-state for surtax orders with `exempt_if`; the response gained four always-present fields (`jurisdiction`, `fta_qualified`, `surtax_if_fta_qualified`, `total_if_fta_qualified`). Computed numbers for existing CA requests are unchanged.

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
