# Golden landed-cost cases

`landed_cost.jsonl` is the parity file for the landed-cost reference computation
(`tradelattice.api.landed.compute`, ADR 0005). One JSON object per line:

| Field | Meaning |
|---|---|
| `name` | Unique case id |
| `note` | Why the case exists (optional) |
| `records` | A `RecordSet` as four lists of envelope dicts: `tariff_lines`, `fx_rates`, `surtax_orders`, `prohibitions`. Self-contained; no connector output is needed |
| `request` | The `POST /landed-cost` body (`LandedCostIn`) |
| `jurisdiction` | The registered jurisdiction code passed to `compute()` |
| `today` | The date passed as `today`; `compute()` never reads a clock |
| `expect.status` | 200, or the status `compute()` raises as `Prohibited` (409) / `NotComputable` (its `status`) |
| `expect.body` | A subset of the response body (200: `LandedCostOut` fields; 409: the `Prohibited` payload; other: `{"reason": ...}`) |

Comparison rule (the same for every consumer): money fields — `duty`, `surtax`,
`surtax_if_fta_qualified`, `total`, `total_if_fta_qualified`, `value_cad`, and `amount` /
`base_amount` inside `fees[]` and `taxes[]` — match within **0.01**; everything else matches
exactly. `tests/test_landed_pure.py::test_golden` is the in-repo runner; a consumer running
its own implementation in parity reads this file and applies the same rule.

Add a case whenever a verified number or a refusal is worth freezing. Never edit an expected
value to make a test pass without a release-note line saying which number changed and why.
