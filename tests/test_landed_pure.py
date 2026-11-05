"""`tradelattice.api.landed.compute` is a pure function over records (ADR 0005).

These tests never start the app or touch a database: they build a RecordSet in memory, call
compute() directly, and check the golden file that any parity consumer reads.
"""
import json
import subprocess
import sys
from datetime import date

import pytest

from tradelattice.api import jurisdictions
from tradelattice.api.landed import NotComputable, Prohibited, RecordSet, compute
from tradelattice.api.schemas import LandedCostIn
from tradelattice.golden import cases, check


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


@pytest.mark.parametrize("case", cases(), ids=lambda c: c["name"])
def test_golden(case):
    status, body = _run(case)
    assert status == case["expect"]["status"], (case["name"], body)
    check(case["expect"]["body"], body, case["name"])


def test_golden_names_unique():
    names = [c["name"] for c in cases()]
    assert len(names) == len(set(names))


def test_compute_is_deterministic_and_input_pure():
    case = next(c for c in cases() if c["name"] == "steel-us-cusma-10000usd")
    before = json.dumps(case["records"], sort_keys=True)
    a = _run(case)
    b = _run(case)
    assert a == b
    assert json.dumps(case["records"], sort_keys=True) == before  # records are not mutated


def test_fx_publisher_label_in_components():
    case = next(c for c in cases() if c["name"] == "steel-us-cusma-10000usd")
    _, body = _run(case)
    assert body["components"][0] == "FX USD→CAD at 1.3994 (BoC 2026-11-03): 10,000.00 USD = 13,994.00 CAD"


def test_records_of_another_jurisdiction_are_ignored():
    case = next(c for c in cases() if c["name"] == "steel-us-cusma-10000usd")
    records = json.loads(json.dumps(case["records"]))
    foreign = json.loads(json.dumps(records["surtax_orders"][0]))
    foreign["id"], foreign["jurisdiction"], foreign["attributes"]["pct"] = "s:us", "US", "99"
    records["surtax_orders"].append(foreign)
    status, body = _run({**case, "records": records})
    assert status == 200 and body["surtax"] == 6997.0


def test_golden_ships_as_package_data():
    """A pip install from a pinned commit or tag must carry the file (Mandible review §6b)."""
    code = "from tradelattice.golden import cases; assert len(cases()) >= 14"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_check_rule():
    check({"total": 1.0, "x": [{"amount": 2.0}]}, {"total": 1.009, "x": [{"amount": 1.995}], "y": 1})
    with pytest.raises(AssertionError):
        check({"total": 1.0}, {"total": 1.02})
    with pytest.raises(AssertionError):
        check({"reason": "a"}, {"reason": "b"})
    with pytest.raises(AssertionError):
        check({"x": [1, 2]}, {"x": [1]})
