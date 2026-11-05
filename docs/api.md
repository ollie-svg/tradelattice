# API

The API is FastAPI with SQLite by default. Set `DATABASE_URL` to use Postgres. Interactive OpenAPI docs are at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/records` | Validate and upsert one record or an array, keyed on `id` |
| GET | `/records` | List records. Filters: `type`, `source`, `q`, `limit`, `offset` |
| GET | `/records/{id}` | Fetch one record |
| GET | `/tariff/{hs_code}` | Best-match tariff line, by longest HS prefix |
| POST | `/landed-cost` | Landed cost in CAD: FX conversion, duty and origin surtax |

## Tariff lookup

```
curl http://localhost:8000/tariff/0902.30.00.00
```

## Jurisdictions

`POST /landed-cost` takes an optional `jurisdiction` (default `CA`, case-insensitive), echoed in the response. An unregistered code returns 422 `unknown jurisdiction 'XX'`. `US` is registered but returns **501** `US profile has no data loaded yet; see the roadmap`, before any lookup. Optional `mode` (`road`, `rail`, `air`, `sea`, `multimodal`) selects mode-dependent fees (for example the US HMF applies only when `mode` is `sea`).

Prohibited goods: before FX and tariff lookup, `prohibition` records for the request's jurisdiction, origin and date whose `hs_prefix` prefixes the HS code are matched (longest prefix wins). A match returns **409** with `{"prohibited": true, "hs_code", "origin_country", "jurisdiction", "list_id", "authority", "effective_from", "effective_to", "source_url", "message"}`. This is a correct non-2xx answer, not a fault: no landed cost is computed for goods that may not be entered.

FTA tri-state: a `surtax_order` with `exempt_if: "fta_qualified"` is skipped when `fta_qualified` is `true`, applied when `false`, and when omitted or `null` both outcomes are reported. `surtax` and `total` are the not-qualified figures; `surtax_if_fta_qualified` and `total_if_fta_qualified` are the qualified ones (both `null` when `fta_qualified` is set, or the applicable order is unconditional). Example: a 25% order with `exempt_if` on `72083600`, on 1000 CAD, gives `surtax` 250.00, `surtax_if_fta_qualified` 0.00 and the component line `FTA qualification unknown: surtax 250.00 if not qualified, 0.00 if qualified`.

Exactly one order may apply. After the `exempt_if` filter, if more than one `surtax_order` is in force for the HS code, origin and date — a longer and a shorter prefix, two lists — the API returns 422 `surtax_ambiguous` naming the orders, because the record declares `stacking` but nothing computes it yet; refusing is the shared rule with every consumer (ADR 0005). Stacking arithmetic arrives with the US overlays. An applicable order whose `basis` is not `value` returns 422 `surtax_content_basis` (`surtax basis 'non_fta_content_value' needs a content value; not supported yet`); the rate is never applied to the full value.

## Landed cost

`POST /landed-cost` returns the landed cost in CAD. The computation is a pure function, `tradelattice.api.landed.compute(request, records, jurisdiction, today)`, over the records the route loads from the database (ADR 0005); the route only loads records and maps the two refusal exceptions below to HTTP. Consumers may call `compute()` directly on their own record set, or run their own implementation against `tests/golden/landed_cost.jsonl`.

### Refusals and reason codes

A 409 means the goods may not be entered (`prohibited: true`, see Jurisdictions above). Every other non-2xx body is `{"detail": <message>, "reason": <code>}` with one of these stable codes:

| Status | `reason` | When |
| --- | --- | --- |
| 404 | `tariff_not_found` | no `tariff_line` of the jurisdiction prefixes the HS code |
| 404 | `rate_not_found` | the matched line has no rate for the treatment |
| 422 | `invalid_request` | `hs_code`, `origin_country` or `shipment_date` is malformed |
| 422 | `fx_missing` | no `fx_rate` into the jurisdiction's currency on or before the shipment date |
| 422 | `rate_not_applicable` | the rate cannot be evaluated from the inputs (a specific rate with no quantity, a not-applicable treatment) |
| 422 | `surtax_ambiguous` | more than one `surtax_order` applies after the `exempt_if` filter; `stacking` is declared, not computed |
| 422 | `surtax_content_basis` | an applicable `surtax_order` has a `basis` other than `value`; the request carries no content value and the rate is never applied to the full value |
| 501 | `jurisdiction_no_data` | the jurisdiction is registered but has no `tariff_line` records loaded (today: `US`) |

`unknown jurisdiction 'XX'` (422) is raised by the route before any computation and carries no code. Records are scoped by their envelope `jurisdiction`: a `surtax_order` or `tariff_line` filed under another jurisdiction is ignored. In order: the declared value is converted to CAD at the Bank of Canada rate for the shipment date, duty is evaluated on that CAD value, and any origin surtax is added.

Request fields: `hs_code`, `origin_country` (2 letters, case-insensitive), `declared_value` (`amount`, `currency`), optional `treatment` (default `MFN`), optional `quantity` and `unit` for specific rates, and optional `shipment_date` (ISO date, default today UTC).

- **FX**: when `declared_value.currency` is not `CAD`, the latest `fx_rate` record (`currency` = declared, `to` = `CAD`) with `on` on or before `shipment_date` is used. If none exists the API returns 422 `no CAD exchange rate on or before <date> for <CUR>; load the boc_fx connector`.
- **Duty**: ad valorem, specific or compound, on `value_cad`. Specific components are already in CAD and unaffected by currency. `quantity` and `unit` accept `kg`, `tonne`, `litre`, `dozen`, `each`, `hl`, with common aliases.
- **Surtax**: the `surtax_order` records in force on `shipment_date` for the HS code and origin are matched (`cbsa_surtax.applicable`); exactly one may apply (see Jurisdictions) and `surtax = value_cad * pct / 100`. It applies in addition to duty whatever the treatment (a CUSMA-Free line from the US still pays it).
- Money is rounded to 2 dp at the end only. `total = value_cad + duty + surtax + fees + taxes`; `duty_rate` is `duty / value_cad * 100`.

```
curl -X POST http://localhost:8000/landed-cost \
  -H 'Content-Type: application/json' \
  -d '{"hs_code": "7208.36.00", "origin_country": "US",
       "declared_value": {"amount": 1000, "currency": "USD"},
       "treatment": "MFN", "shipment_date": "2026-11-04"}'
```

```
{"hs_code": "72083600", "matched_hs_code": "72083600", "treatment": "MFN",
 "duty_rate": 0.0, "duty": 0.0, "total": 2099.1,
 "currency": "CAD", "declared_currency": "USD",
 "value_cad": 1399.4, "fx_rate": "1.3994", "fx_on": "2026-11-03",
 "surtax_pct": "50", "surtax": 699.7,
 "surtax_list_id": "finance-ca-counter-tariffs-2026-09-08",
 "shipment_date": "2026-11-04",
 "rate": "Free", "basis": "ad_valorem",
 "components": ["FX USD→CAD at 1.3994 (BoC 2026-11-03): 1,000.00 USD = 1,399.40 CAD",
                "0% ad valorem = 0.00",
                "surtax 50% of 1,399.40 (finance-ca-counter-tariffs-2026-09-08, origin US) = 699.70"]}
```

`currency` is always `CAD`; `declared_currency` echoes the input. `fx_rate`, `fx_on`, `surtax_pct` and `surtax_list_id` are `null` when not used.

Other 422 responses: a specific rate with a missing or mismatched quantity or unit ("this rate needs a quantity and unit in kg"), an `N/A` rate ("rate not applicable for this treatment"), an unparseable `shipment_date`, and an `origin_country` that is not two letters.

Known gaps: surtax remission orders and exclusions are not modelled, and PST/HST are out of scope (see Fees and taxes). Results are indicative only.

## Fees and taxes

Each jurisdiction has an ordered fee schedule. `/landed-cost` evaluates it after duty and surtax with Decimal arithmetic and rounds each amount once, half-up to 2 dp. Rules run in list order against a context of `value` (CAD), `duty` and `surtax`. A rule's `base` is one of `value`, `duty`, `surtax`, `duty_paid_value` (= value + duty + surtax) or `fees_so_far` (the sum of fee amounts, not taxes, evaluated earlier in the list). A rule applies only when `effective_from <= shipment_date < effective_to` (`effective_to` may be null) and its `applies_when` matches (`{"mode": "sea"}` requires the request `mode` to be `sea`; no condition means always). `min` and `max` clamp the amount. Rules with `category: "tax"` are skipped unless the request sets `include_taxes: true` (default `false`, so existing totals are unchanged).

The response always carries `fees` and `taxes` (lists of `{name, authority, base, base_amount, amount}`) and echoes `include_taxes`. `total` and `total_if_fta_qualified` include them; the FTA branch recomputes its own fees and taxes because duty-paid value changes with surtax. `components` gains one line per fee or tax, for example `GST 5% of duty-paid value 20,991.00 = 1,049.55` or `MPF 0.3464% of value 13,994.00 = 48.48 (min 34.58, max 670.86)`; a clamp that applied reads `(clamped to max 670.86)`.

| Jurisdiction | Name | Rate | Base | Min / max | Effective | Authority |
|---|---|---|---|---|---|---|
| CA | GST (tax) | 5% | duty-paid value | none | 1991-01-01 onward | [ETA s.212](https://laws-lois.justice.gc.ca/eng/acts/E-15/) |
| US | MPF (fee), FY2026 | 0.3464% | value | 33.58 / 651.50 | 2025-10-01 to 2026-10-01 | 19 CFR 24.23 / FR 2026-15530 |
| US | MPF (fee), FY2027 | 0.3464% | value | 34.58 / 670.86 | 2026-10-01 onward | 19 CFR 24.23 / FR 2026-15530 |
| US | HMF (fee), sea only | 0.125% | value | none | 1987-04-01 onward | 26 USC 4461 |

The US schedule is defined and unit-tested but only runs once the US profile returns data (it currently returns 501).

PST and HST are deliberately absent: they depend on the importer's province and registration, which are tenant facts and not properties of the goods.

The web UI directory defaults to `<repo>/web`, found by walking up from the package to the nearest `pyproject.toml`; set `TRADELATTICE_WEB_DIR` to serve it from elsewhere (an installed copy outside the source tree shows a placeholder at `/` otherwise).
