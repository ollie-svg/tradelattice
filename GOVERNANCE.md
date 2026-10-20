# Governance

## Current model: BDFL

TradeLattice starts with a Benevolent Dictator For Life (the founding maintainer), who has final say on the schema, releases and project direction, and who seeks input in public issues and pull requests.

## Maintainers

Maintainers are contributors with merge rights. A contributor with a sustained record of quality work may be nominated by an existing maintainer and is added when the BDFL approves.

## Transition: maintainer council

When the project has **3 or more maintainers**, governance moves to a maintainer council:

- Decisions are made by consensus; if consensus fails, by simple majority of maintainers.
- Breaking schema changes require approval from a majority of the council and an ADR in `docs/adr/`.
- The BDFL becomes one council member.
- New maintainers require a majority vote.

## Decisions

Significant architectural decisions are recorded as ADRs in `docs/adr/`.
