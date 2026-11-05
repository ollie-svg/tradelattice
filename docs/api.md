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

`POST /landed-cost` takes an optional `jurisdiction` (default `CA`, case-insensitive), echoed in the response. An unregistered code returns 422 `unknown jurisdiction 'XX'`. `US` is registered but returns **501** `US profile has no data loaded yet; see the roadmap`, before any lookup. Optional `mode` (`road`, `rail`, `air`, `sea`, `multimodal`) is accepted and currently unused.

Prohibited goods: before FX and tariff lookup, `prohibition` records for the request's jurisdiction, origin and date whose `hs_prefix` prefixes the HS code are matched (longest prefix wins). A match returns **409** with `{"prohibited": true, "hs_code", "origin_country", "jurisdiction", "list_id", "authority", "effective_from", "effective_to", "source_url", "message"}`. This is a correct non-2xx answer, not a fault: no landed cost is computed for goods that may not be entered.

FTA tri-state: a `surtax_order` with `exempt_if: "fta_qualified"` is skipped when `fta_qualified` is `true`, applied when `false`, and when omitted or `null` both outcomes are reported. `surtax` and `total` are the not-qualified figures; `surtax_if_fta_qualified` and `total_if_fta_qualified` are the qualified ones (both `null` when `fta_qualified` is set, or no exempt order matched). Within each set only the longest-prefix order applies; stacking is not supported yet. Example: a 25% order with `exempt_if` on `72083600` and a 50% order on `7208`, on 1000 CAD, give `surtax` 250.00, `surtax_if_fta_qualified` 500.00 and the component line `FTA qualification unknown: surtax 250.00 if not qualified, 500.00 if qualified`. A chosen order whose `basis` is not `value` returns 422 `surtax basis 'non_fta_content_value' needs a content value; not supported yet`.

## Landed cost

`POST /landed-cost` returns the landed cost in CAD. In order: the declared value is converted to CAD at the Bank of Canada rate for the shipment date, duty is evaluated on that CAD value, and any origin surtax is added.

Request fields: `hs_code`, `origin_country` (2 letters, case-insensitive), `declared_value` (`amount`, `currency`), optional `treatment` (default `MFN`), optional `quantity` and `unit` for specific rates, and optional `shipment_date` (ISO date, default today UTC).

- **FX**: when `declared_value.currency` is not `CAD`, the latest `fx_rate` record (`currency` = declared, `to` = `CAD`) with `on` on or before `shipment_date` is used. If none exists the API returns 422 `no CAD exchange rate on or before <date> for <CUR>; load the boc_fx connector`.
- **Duty**: ad valorem, specific or compound, on `value_cad`. Specific components are already in CAD and unaffected by currency. `quantity` and `unit` accept `kg`, `tonne`, `litre`, `dozen`, `each`, `hl`, with common aliases.
- **Surtax**: the `surtax_order` records in force on `shipment_date` for the HS code and origin are matched (`cbsa_surtax.applicable`); the longest prefix wins and `surtax = value_cad * pct / 100`. It applies in addition to duty whatever the treatment (a CUSMA-Free line from the US still pays it).
- Money is rounded to 2 dp at the end only. `total = value_cad + duty + surtax`; `duty_rate` is `duty / value_cad * 100`.

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

Known gaps: surtax remission orders and exclusions are not modelled, and GST/PST are out of scope. Results are indicative only.

The web UI directory defaults to `<repo>/web`, found by walking up from the package to the nearest `pyproject.toml`; set `TRADELATTICE_WEB_DIR` to serve it from elsewhere (an installed copy outside the source tree shows a placeholder at `/` otherwise).
