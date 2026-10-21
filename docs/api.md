# API

The API is FastAPI with SQLite by default. Set `DATABASE_URL` to use Postgres. Interactive OpenAPI docs are at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/records` | Validate and upsert one record or an array, keyed on `id` |
| GET | `/records` | List records. Filters: `type`, `source`, `q`, `limit`, `offset` |
| GET | `/records/{id}` | Fetch one record |
| GET | `/tariff/{hs_code}` | Best-match tariff line, by longest HS prefix |
| POST | `/landed-cost` | Duty and total for a declared value |

## Tariff lookup

```
curl http://localhost:8000/tariff/0902.30.00.00
```

## Landed cost

```
curl -X POST http://localhost:8000/landed-cost \
  -H 'Content-Type: application/json' \
  -d '{"hs_code": "09023000", "origin_country": "US",
       "declared_value": {"amount": 1000, "currency": "CAD"}, "treatment": "MFN"}'
```

Optional `quantity` and `unit` are needed for specific rates (`kg`, `tonne`, `litre`, `dozen`, `each`, `hl`, with common aliases). Per-tonne rates accept kg quantities and per-hl rates accept litres.

The response holds `rate` (the raw CBSA string), `basis` (`ad_valorem`, `specific` or `compound`), `components` (the arithmetic, one line per part), `duty_rate` (effective duty as a percentage of value), `duty` and `total`.

Compound example, `5% but not less than 4.74¢/kg or more than 9.48¢/kg`:

```
curl -X POST http://localhost:8000/landed-cost \
  -H 'Content-Type: application/json' \
  -d '{"hs_code": "09023000", "origin_country": "US",
       "declared_value": {"amount": 1000, "currency": "CAD"},
       "quantity": 2000, "unit": "kg"}'
```

```
{"rate": "5% but not less than 4.74¢/kg or more than 9.48¢/kg",
 "basis": "compound",
 "components": ["5% ad valorem = 50.00",
                "floor 4.74¢/kg × 2000 kg = 94.80",
                "cap 9.48¢/kg × 2000 kg = 189.60"],
 "duty_rate": 9.48, "duty": 94.8, "total": 1094.8, ...}
```

Returns HTTP 422 when a specific rate needs a quantity or unit that is missing or does not match ("this rate needs a quantity and unit in kg"), and when the rate is `N/A` ("rate not applicable for this treatment").

GST is not calculated in v0.1. Results are indicative only.
