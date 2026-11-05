"""Schema tests: examples validate; negative cases fail."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tradelattice.spec.validate import validate_record

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.json"))


def load(name: str) -> dict:
    path = Path(__file__).parent.parent / "examples" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_eleven_examples_exist():
    assert len(EXAMPLES) == 11


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates(path):
    assert validate_record(json.loads(path.read_text(encoding="utf-8"))) == []


def test_tariff_line_unknown_attribute_fails():
    rec = load("tariff_line")
    rec["attributes"]["bogus"] = 1
    assert validate_record(rec)


def test_tariff_line_bad_edition_fails():
    rec = load("tariff_line")
    rec["attributes"]["edition"] = "2026-2"
    assert validate_record(rec)


def test_fx_rate_to_is_not_const():
    rec = load("fx_rate")
    rec["attributes"]["to"] = "USD"
    rec["attributes"]["currency"] = "CAD"
    assert validate_record(rec) == []


def test_fx_rate_numeric_must_be_string():
    rec = load("fx_rate")
    rec["attributes"]["rate"] = 1.3812
    assert validate_record(rec)


def test_envelope_accepts_fx_rate_type():
    rec = load("fx_rate")
    assert rec["type"] == "fx_rate"
    assert validate_record(rec) == []


def test_concordance_null_to_code_with_removed_ok():
    rec = copy.deepcopy(load("hs_concordance"))
    rec["attributes"]["to_code"] = None
    rec["attributes"]["relation"] = "removed"
    assert validate_record(rec) == []


def test_concordance_null_to_code_with_renumbered_rejected():
    # to_code may be null only when relation is "removed". This is expressed in the schema
    # with if/then (JSON Schema 2020-12), so it is enforced at validation time.
    rec = copy.deepcopy(load("hs_concordance"))
    rec["attributes"]["to_code"] = None
    rec["attributes"]["relation"] = "renumbered"
    assert validate_record(rec)


def test_surtax_order_requires_effective_to():
    rec = load("surtax_order")
    del rec["attributes"]["effective_to"]
    assert validate_record(rec)


def test_v02_shaped_surtax_order_validates():
    rec = load("surtax_order")
    for k in ("authority", "basis", "stacking", "last_verified"):
        del rec["attributes"][k]
    assert validate_record(rec) == []


def test_surtax_bad_basis_rejected():
    rec = load("surtax_order")
    rec["attributes"]["basis"] = "weight"
    assert validate_record(rec)


def test_surtax_bad_exempt_if_rejected():
    rec = load("surtax_order")
    rec["attributes"]["exempt_if"] = "origin"
    assert validate_record(rec)


def test_surtax_effective_to_before_from_fails_semantic_check():
    rec = load("surtax_order")
    rec["attributes"]["effective_to"] = "2026-01-01"
    errors = validate_record(rec)
    assert any("must not be before effective_from" in e for e in errors)


def test_prohibition_effective_to_before_from_fails_semantic_check():
    rec = load("prohibition")
    rec["attributes"]["effective_to"] = "2026-09-28"
    errors = validate_record(rec)
    assert len(errors) == 1
    assert "effective_to" in errors[0] and "must not be before effective_from" in errors[0]


def test_prohibition_effective_to_equal_from_ok():
    rec = load("prohibition")
    rec["attributes"]["effective_to"] = rec["attributes"]["effective_from"]
    assert validate_record(rec) == []


def test_prohibition_with_pct_rejected():
    rec = load("prohibition")
    rec["attributes"]["pct"] = "25"
    assert validate_record(rec)


def test_envelope_accepts_prohibition_type():
    rec = load("prohibition")
    assert rec["type"] == "prohibition"
    assert validate_record(rec) == []
