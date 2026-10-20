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

The response holds `duty_rate`, `duty` and `total`.

!!! warning
    Only `Free` and percentage rates are supported. A specific rate such as `$1.20/kg` returns HTTP 422.

GST is not calculated in v0.1. Results are indicative only.
