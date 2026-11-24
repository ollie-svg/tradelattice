# ADR 0005: the landed-cost calculator is a reference computation on the record

Status: Accepted (2026-11-05)

## Context
TradeLattice is an open data standard plus a reference stack (ADR 0001; decision of Oct 20). Landed cost is in charter — "tariff lookup, landed cost, edition diff, free forever" — but by v0.3 `/landed-cost` had grown into 134 lines of arithmetic inside a FastAPI route bound to a database session. A downstream consumer that computes on the same records (Mandible, the commercial arm) could not call it, so it re-implemented the arithmetic, and a review on Nov 5 found the two implementations disagreeing on three semantics (`effective_to` boundary, `basis`, `exempt_if`) and silent on a fourth (prohibitions). Brokers will use the free calculator to check any paid number; if the two disagree, the paid one loses.

## Decision
The boundary rule between the record project and its consumers, extended:

> A fact about the record goes upstream; a decision computed on the record stays in the consumer. A reference computation on the record may live upstream, **as a pure function over records with no database or HTTP in it**, and a consumer treats that function as the oracle: either calling it per line, or running its own implementation in parity against it in CI. Two independent implementations of the same arithmetic are a defect, not redundancy.

Corollary: where the record declares a semantic that nobody computes yet (`stacking`), the reference computation and every consumer refuse the same way rather than each picking an answer.

Concretely:
- `tradelattice.api.landed.compute(request, records, jurisdiction, today) -> LandedCostOut` is that function. It imports no `fastapi`, no `sqlalchemy`, reads no clock (`today` is an argument) and makes no network call; a test asserts the import graph. The route is a thin wrapper that loads a `RecordSet` from the session and maps `Prohibited` to 409 and `NotComputable` to its status.
- Refusals are typed. `Prohibited` carries the 409 payload. `NotComputable` carries `status`, a stable `reason` code and a human `detail`; the route returns `{"detail", "reason"}`. The `reason` vocabulary is listed in `docs/api.md` and is shared with consumers' own `not_computed` reasons.
- `tradelattice.golden` ships the parity cases as package data: self-contained cases (records, request, jurisdiction, today, expected status and body subset) via `cases()`, and the comparison rule via `check()` — money fields within 0.01, everything else exactly. A consumer running its own implementation reads the same file and applies the same rule, from the package it installed, so a pinned commit or tag carries its own tests.
- The alignment branch is merged with history, never squashed, and tagged `v0.3.1` when the version bump lands; consumers may pin a SHA on the branch in the meantime and nothing they pinned is orphaned.
- The `compute` signature and the `RecordSet` fields are frozen within a minor version; a change is a minor bump with a release-note line. Consumers pin a commit.
- Records are scoped by envelope `jurisdiction` inside `compute()`: a jurisdiction with no `tariff_line` records returns `jurisdiction_no_data` (501) rather than pretending.

## Consequences
- Upstream's own web UI and tests can compute without SQLite.
- Arithmetic stays as it was in v0.3 (duty in float, `round(.., 6)` into Decimal for the fee cascade). A Decimal-end-to-end rewrite is deferred; the 0.01 parity tolerance covers it until then.
- Loading every record of four types per request is fine at today's scale (12,470 tariff lines) and is the obvious place to add a prefix pre-filter for a hosted instance.
- What stays with consumers: book-level and edition-to-edition analysis, route economics, optimisation, reporting. None of it is a fact about the record.
