# Release notes

## v0.2 (2026-11-03)

- Added record types `surtax_order`, `fx_rate` and `hs_concordance`, and added them to the envelope `type` enum.
- Added optional `edition` (pattern `^T\d{4}(-\d+)?$`) to `tariff_line`.
- Bumped every schema `$id` from `/schemas/v0.1/` to `/schemas/v0.2/`.
- v0.1 validators reject the new record types by design, because the envelope `type` enum is closed.
- Moved the `api`, `spec` and `connectors` packages under `src/tradelattice/`, so the installed package is `tradelattice`. Module paths are now `tradelattice.api`, `tradelattice.spec` and `tradelattice.connectors` (for example `python -m tradelattice.connectors.cbsa_tariff`, `python -m tradelattice.api.cli`, `uvicorn tradelattice.api.main:app`). Behaviour is unchanged; set `TRADELATTICE_WEB_DIR` to point the API at a different `web/` directory.
- Added the `boc_fx` connector, which emits `fx_rate` records from the Bank of Canada Valet API (live by default, fetching the last 10 days unless a window is given; bundled sample offline).
- Added the `cbsa_concordance` connector, which loads CBSA/Finance Canada concordance workbooks (xlsx; 8-digit HS-cycle and yearly 10-digit) as `hs_concordance` records; adds the `openpyxl` dependency.
- Added the `cbsa_surtax` connector, which emits `surtax_order` records from Finance Canada's counter-tariff lists on US-origin goods (629 lines effective 2026-09-08) plus an `applicable()` lookup helper; remission orders and exclusions are not modelled.
