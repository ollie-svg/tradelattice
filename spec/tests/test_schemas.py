"""Schema tests: examples validate; negative cases fail."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from spec.validate import validate_record

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*.json"))


def load(name: str) -> dict:
    path = Path(__file__).parent.parent / "examples" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_nine_examples_exist():
    assert len(EXAMPLES) == 9


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
