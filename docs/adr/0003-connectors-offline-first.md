# ADR 0003: Connectors are offline-first

Status: Accepted

## Context
Public data URLs change, rate-limit, or disappear. Tests that hit the network are flaky, and contributors should be able to work without connectivity.

## Decision
Every connector bundles a sample file in `connectors/<name>/sample/` and works from it by default. Live fetching is opt-in via `--live`. Tests never touch the network. Where a live URL cannot be confirmed, it is documented as a TODO with the dataset's open.canada.ca landing page.

## Consequences
- Deterministic tests and demos.
- Samples must be kept representative of the live format.
- Live fetch paths need separate manual verification.
