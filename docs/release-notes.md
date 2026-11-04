# Release notes

## v0.2 (2026-11-03)

- Added record types `surtax_order`, `fx_rate` and `hs_concordance`, and added them to the envelope `type` enum.
- Added optional `edition` (pattern `^T\d{4}(-\d+)?$`) to `tariff_line`.
- Bumped every schema `$id` from `/schemas/v0.1/` to `/schemas/v0.2/`.
- v0.1 validators reject the new record types by design, because the envelope `type` enum is closed.
