"""`tradelattice.api.landed.compute` is a pure function over records (ADR 0005).

These tests never start the app or touch a database: they build a RecordSet in memory, call
compute() directly, and check the golden file that any parity consumer reads.
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from tradelattice.api import jurisdictions
from tradelattice.api.landed import NotComputable, Prohibited, RecordSet, compute
from tradelattice.api.schemas import LandedCostIn

GOLDEN = Path(__file__).parent / "golden" / "landed_cost.jsonl"
MONEY = {"duty", "surtax", "surtax_if_fta_qualified", "total", "total_if_fta_qualified",
         "value_cad", "amount", "base_amount"}


def test_landed_imports_no_db_no_http():
    code = (
        "import sys; import tradelattice.api.landed; "
        "bad = {'fastapi', 'sqlalchemy', 'starlette'} & set(sys.modules); "
        "assert not bad, bad"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def _run(case: dict):
    records = RecordSet(**case["records"])
    req = LandedCostIn(**case["request"])
    jur = jurisdictions.get(case["jurisdiction"])
    today = date.fromisoformat(case["today"])
    try:
        out = compute(req, records, jur, today)
    except Prohibited as e:
        return 409, e.payload
    except NotComputable as e:
        return e.status, {"detail": e.detail, "reason": e.reason}
    return 200, out.model_dump()


def _assert_subset(expected, actual, path=""):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        for k, v in expected.items():
            assert k in actual, f"{path}.{k} missing"
            _assert_subset(v, actual[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            _assert_subset(e, a, f"{path}[{i}]")
    elif path.rsplit(".", 1)[-1] in MONEY and isinstance(expected, int | float) and expected is not None:
        assert actual is not None and abs(actual - expected) <= 0.01, f"{path}: {actual} != {expected}"
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


def _cases():
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["name"])
def test_golden(case):
    status, body = _run(case)
    assert status == case["expect"]["status"], (case["name"], body)
    _assert_subset(case["expect"]["body"], body, case["name"])


def test_golden_names_unique():
    names = [c["name"] for c in _cases()]
    assert len(names) == len(set(names))


def test_compute_is_deterministic_and_input_pure():
    case = next(c for c in _cases() if c["name"] == "steel-us-cusma-10000usd")
    before = json.dumps(case["records"], sort_keys=True)
    a = _run(case)
    b = _run(case)
    assert a == b
    assert json.dumps(case["records"], sort_keys=True) == before  # records are not mutated


def test_fx_publisher_label_in_components():
    case = next(c for c in _cases() if c["name"] == "steel-us-cusma-10000usd")
    _, body = _run(case)
    assert body["components"][0] == "FX USD→CAD at 1.3994 (BoC 2026-11-03): 10,000.00 USD = 13,994.00 CAD"


def test_records_of_another_jurisdiction_are_ignored():
    case = next(c for c in _cases() if c["name"] == "steel-us-cusma-10000usd")
    records = json.loads(json.dumps(case["records"]))
    foreign = json.loads(json.dumps(records["surtax_orders"][0]))
    foreign["id"], foreign["jurisdiction"], foreign["attributes"]["pct"] = "s:us", "US", "99"
    records["surtax_orders"].append(foreign)
    status, body = _run({**case, "records": records})
    assert status == 200 and body["surtax"] == 6997.0
