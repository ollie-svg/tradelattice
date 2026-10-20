# OpenGoods Specification

The canonical data model for OpenGoods: JSON Schema (draft 2020-12) definitions for six record types
that share a common envelope. The spec is country-agnostic; Canada is the first target.

- `schemas/envelope.schema.json` - fields shared by every record (`id`, `type`, `source`, `observed_at`, `jurisdiction`, `attributes`).
- `schemas/<type>.schema.json` - one per type: `product`, `tariff_line`, `supplier`, `tender`, `shipment`, `price_observation`. Each `allOf`s the envelope, pins `type` to a constant and constrains `attributes` (no extra properties).
- `examples/<type>.json` - one valid example per type.

Schema `$id`s have the form `https://opengoods.dev/schemas/v0.1/<name>.schema.json`.

## Versioning

Semantic versioning, reflected in the `$id` path (`v0.1`).

- **Major** (breaking): removing or renaming a field, tightening a constraint, making an optional field required, changing a type.
- **Minor** (compatible): adding optional fields, adding new record types, loosening a constraint.
- **Patch**: documentation and example fixes with no change to validation behaviour.

While the version is `0.x`, minor releases may include breaking changes; these are called out in release notes.

## Validating

```
pip install -e .[dev]
python -m spec.validate spec/examples/*.json
```

A file may hold one record or a JSON array of records. The command exits non-zero if any record fails.
Format keywords (`date-time`, `date`, `uri`) are asserted.
