# ADR 0001: Schema first

Status: Accepted

## Context
Adoption depends on others being able to map their data into a shared model quickly. A large app without a stable model gains little network effect.

## Decision
The versioned JSON Schema (2020-12) in `spec/` is the primary artifact. Connectors and the API depend on it; it depends on nothing. Records share an envelope and are validated against the schemas on write.

## Consequences
- Anyone can adopt TradeLattice by emitting conformant JSON, in any language.
- Schema changes follow semver; breaking changes are costly and need an ADR.
- Dependency direction is `web -> api -> spec <- connectors`.
