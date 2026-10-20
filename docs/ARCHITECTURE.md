# TradeLattice — Architecture

**Purpose.** An open data standard and reference stack for coordinating goods and services across a national economy. Canada is the first target; the schema is country-agnostic.

**Strategy.** Be the shared schema, not the biggest app. Adoption comes from (1) a small, stable data model anyone can map into in an afternoon, (2) connectors that bring real public data in on day one, (3) an API and UI that give immediate value to a single user before any network effect exists.

## Layers

```
spec/        Canonical data model: JSON Schema 2020-12, versioned. Country-agnostic.
connectors/  Ingestors that map public datasets → spec records. Each is a plugin: `connectors/<name>/`.
api/         FastAPI service. Stores records (SQLite default, Postgres via DATABASE_URL). REST + OpenAPI.
web/         Static single-page UI (vanilla JS + HTMX-free fetch). Served by the API at `/`.
docs/        Architecture, ADRs, governance, contribution guide.
```

Dependency direction: `web → api → spec ← connectors`. Nothing imports upward.

## Canonical data model (spec/schemas, v0.1)

All records share an `Envelope`:
- `id` (string, URI-safe, globally unique: `<source>:<native_id>`)
- `type` (enum below)
- `source` (string — connector name)
- `observed_at` (RFC3339)
- `jurisdiction` (ISO 3166-1 alpha-2; subdivision allowed as `CA-BC`)
- `attributes` (type-specific object)

Types:
1. **Product** — `hs_code` (6–10 digit HS/tariff line, string), `description`, `unit_of_measure`, `origin_country`.
2. **TariffLine** — `hs_code`, `description`, `rates` (array of `{treatment: "MFN"|"CUSMA"|..., rate: string (e.g. "6.5%", "Free", "$1.20/kg")}`), `effective_from`, `effective_to` (nullable).
3. **Supplier** — `name`, `identifiers` (`{business_number?, duns?, website?}`), `address` (`{line1?, city?, region?, postal_code?, country}`), `capabilities` (array of HS codes or free text), `contact` (optional).
4. **Tender** — `title`, `buyer` (`{name, jurisdiction, level: "federal"|"provincial"|"municipal"|"other"}`), `category_codes` (UNSPSC/GSIN strings), `published_at`, `closes_at`, `value_estimate` (`{amount, currency}` nullable), `url`, `status`.
5. **Shipment** — `reference`, `mode` (`road|rail|air|sea|multimodal`), `origin`, `destination` (both `{country, region?, city?, port_code?}`), `line_items` (array of `{hs_code, quantity, unit, declared_value: {amount, currency}}`), `eta`, `status`.
6. **PriceObservation** — `subject` (`{type: "product"|"service", hs_code?, unspsc?, description}`), `price` (`{amount, currency, per_unit}`), `observed_at`, `location` (`{country, region?, city?}`), `source_url`.

Each type has its own file `spec/schemas/<type>.schema.json` plus `spec/schemas/envelope.schema.json`. `spec/examples/<type>.json` holds one valid example each. `spec/README.md` explains versioning (semver; breaking = major).

## Connectors (v0.1)

Each connector is a Python package under `connectors/<name>/` exposing `fetch(since: datetime | None) -> Iterator[dict]` returning Envelope-shaped dicts, and a CLI entry `python -m connectors.<name> --out records.jsonl`. Connectors **must** work offline from a bundled sample file (`connectors/<name>/sample/`) so tests never hit the network; live fetch is opt-in via `--live`.

1. `cbsa_tariff` — Canada Customs Tariff schedule (CBSA publishes CSV/XLSX of the tariff schedule with MFN and preferential rates) → `TariffLine`.
2. `canadabuys` — CanadaBuys open tender notices CSV (open.canada.ca) → `Tender`.
3. `statcan_trade` — Statistics Canada international merchandise trade (CIMT) by HS6 → `PriceObservation` (unit values = value/quantity).

A builder who cannot confirm a live URL ships the sample-file path and documents the live URL as a TODO with the dataset's open.canada.ca landing page.

## API (v0.1)

FastAPI, Python 3.11+, SQLAlchemy 2, SQLite file `tradelattice.db` by default, `DATABASE_URL` env overrides. Single table `records` (`id PK, type, source, jurisdiction, observed_at, attributes JSON`) plus indexes on `type`, `(type, source)`. Validation on write against the spec schemas (jsonschema library).

Endpoints:
- `GET /health`
- `POST /records` (single or array; upsert on `id`)
- `GET /records?type=&source=&q=&limit=&offset=` (`q` = case-insensitive substring on `attributes` text)
- `GET /records/{id}`
- `GET /tariff/{hs_code}` → best-match TariffLine (longest prefix match)
- `POST /landed-cost` body `{hs_code, origin_country, declared_value: {amount, currency}, treatment?: string}` → `{duty_rate, duty, total}` using the matched TariffLine; GST is **not** computed (documented as out of scope v0.1).
- `GET /` serves `web/index.html`; `/static/*` serves `web/`.

`api/cli.py`: `python -m api.cli load records.jsonl` bulk-loads connector output.

Tests: pytest, TestClient, in-memory SQLite; cover each endpoint and landed-cost prefix matching.

## Web (v0.1)

Single `web/index.html` + `web/app.js` + `web/style.css`. No build step. Three panels: Tariff lookup (HS code → rates), Landed-cost calculator, Tender search. Plain fetch to the API. Must work on a phone-width screen.

## Repo scaffolding

- `LICENSE` Apache-2.0, copyright "TradeLattice Contributors".
- `README.md`: one-paragraph pitch, 5-command quickstart (`pip install -e .[dev]`, run connectors from samples, load, serve, open browser), architecture pointer, contribution pointer.
- `CONTRIBUTING.md`, `GOVERNANCE.md` (BDFL → maintainer council at 3+ maintainers), `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`.
- `pyproject.toml` single project with extras `[dev]` (pytest, ruff).
- `.github/workflows/ci.yml`: ruff + pytest on push/PR, Python 3.11 and 3.12.
- `docs/adr/0001-schema-first.md`, `0002-sqlite-default.md`, `0003-connectors-offline-first.md`.
- `.gitignore`, `Makefile` (`make test`, `make serve`, `make load-samples`).

## Non-goals for v0.1
Auth, multi-tenant, GST/PST, currency conversion, real-time feeds, ML. All deferred and listed in `docs/ROADMAP.md`.
