# Spec

The data model is JSON Schema 2020-12, version 0.3. Every record shares one Envelope. Breaking changes bump the major version.

## Envelope

All six required fields appear on every record.

| Field | Meaning |
| --- | --- |
| `id` | URI-safe, globally unique: `<source>:<native_id>` |
| `type` | One of the ten types below |
| `source` | Connector name |
| `observed_at` | RFC 3339 timestamp |
| `jurisdiction` | ISO 3166-1 alpha-2, optionally with subdivision, such as `CA-BC` |
| `attributes` | Type-specific object |

## Types

| Type | Purpose | Required attributes |
| --- | --- | --- |
| `product` | A good identified by HS code | `hs_code`, `description` |
| `tariff_line` | Duty rates for an HS code | `hs_code`, `description`, `rates`, `effective_from` |
| `supplier` | A business that supplies goods or services | `name`, `address` |
| `tender` | A public procurement notice | `title`, `buyer`, `published_at`, `url`, `status` |
| `shipment` | A movement of goods between places | `reference`, `mode`, `origin`, `destination`, `line_items` |
| `price_observation` | A price seen for a product or service | `subject`, `price`, `observed_at`, `location`, `source_url` |
| `surtax_order` | One line of a surtax order: a percentage of value for duty on goods of an origin whose tariff code starts with `hs_prefix`, for a date range | `hs_prefix`, `origin_country`, `pct`, `list_id`, `effective_from`, `effective_to` |
| `prohibition` | An import prohibition: goods of an origin whose tariff code starts with `hs_prefix` may not be entered in the jurisdiction for a date range. A state, not a rate: consumers must refuse to compute a landed cost, never return a number | `hs_prefix`, `origin_country`, `list_id`, `effective_from`, `effective_to` |
| `fx_rate` | An exchange rate: multiply a `currency` amount by `rate` to get `to` (CAD is the Canadian convention) | `currency`, `to`, `rate`, `on` |
| `hs_concordance` | A mapping of a tariff code between two tariff editions | `from_code`, `to_code`, `relation`, `from_edition`, `to_edition` |

`tariff_line` also accepts an optional `edition` (pattern `^T\d{4}(-\d+)?$`, for example `T2026-2`). Version 0.2 added the three new types and `edition`; see the [release notes](release-notes.md).

Version 0.3 added the `prohibition` type and the optional `surtax_order` fields below. All are optional and existing v0.2 records validate unchanged.

- `authority`: legal authority for the measure. Known values `s53`, `232`, `301`, `338`, `122`, `201`, `adcvd`; not an enum, so other values are allowed.
- `basis`: what the percentage applies to: `value`, `non_fta_content_value`, `steel_content_value` or `aluminum_content_value`. Default `value`.
- `exempt_if`: condition that exempts goods from the surtax; currently only `fta_qualified`.
- `exclusion_ref`: reference to an exclusion or remission instrument.
- `case_number`: case number, for example an antidumping or countervailing duty case.
- `stacking`: `additive` or `exclusive`. Default `additive`.
- `last_verified`: date the record was last checked against its source.

`prohibition` also accepts optional `authority` (string) and `source_url` (URI).

Semantic rule: for `prohibition` and `surtax_order`, `effective_to`, when not null, must not be before `effective_from`. JSON Schema cannot compare dates, so `tradelattice.spec.validate` enforces this after schema validation (`semantic_checks`).

The `prohibition` example (the US import ban on Canadian dairy products, HS prefix `0401`, effective 2026-09-29) cites a secondary source, the Blakes tariff timeline, pending the text of the proclamation. Treat it as illustrative until the primary source replaces it.

Numeric values in the new types (`pct`, `rate`) are decimal strings. For `hs_concordance`, a split is one record per target with relation `split`, a merge is one record per source with relation `merged`, and `to_code` is null only when the relation is `removed`.

## Schema files

- [envelope.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/envelope.schema.json)
- [product.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/product.schema.json)
- [tariff_line.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/tariff_line.schema.json)
- [supplier.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/supplier.schema.json)
- [tender.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/tender.schema.json)
- [shipment.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/shipment.schema.json)
- [price_observation.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/price_observation.schema.json)
- [surtax_order.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/surtax_order.schema.json)
- [prohibition.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/prohibition.schema.json)
- [fx_rate.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/fx_rate.schema.json)
- [hs_concordance.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/src/tradelattice/spec/schemas/hs_concordance.schema.json)
