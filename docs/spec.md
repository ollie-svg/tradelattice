# Spec

The data model is JSON Schema 2020-12, version 0.1. Every record shares one Envelope. Breaking changes bump the major version.

## Envelope

All six required fields appear on every record.

| Field | Meaning |
| --- | --- |
| `id` | URI-safe, globally unique: `<source>:<native_id>` |
| `type` | One of the six types below |
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

## Schema files

- [envelope.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/envelope.schema.json)
- [product.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/product.schema.json)
- [tariff_line.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/tariff_line.schema.json)
- [supplier.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/supplier.schema.json)
- [tender.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/tender.schema.json)
- [shipment.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/shipment.schema.json)
- [price_observation.schema.json](https://github.com/ollie-svg/tradelattice/blob/main/spec/schemas/price_observation.schema.json)
