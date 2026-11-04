# ADR 0004: src layout under one `tradelattice` package

Status: Accepted

## Context
The top-level packages `api`, `spec` and `connectors` were installed directly onto `sys.path`, claiming generic names that collide with other projects.

## Decision
Move them to `src/tradelattice/{api,spec,connectors}` and install a single `tradelattice` package. Tests stay in `tests/` and beside the packages, and run against the installed package rather than the source root.

## Consequences
- Nothing else on a downstream `sys.path` is shadowed by `api`, `spec` or `connectors`.
- All imports and `python -m` commands use the `tradelattice.` prefix; package data is declared per sub-package.
