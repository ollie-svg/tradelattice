import json
import os
from pathlib import Path

import pytest

from connectors.cbsa_tariff import EDITION, fetch, records_from_html
from connectors.cbsa_tariff.parse import parse_chapter_html, parse_preferential
from spec.validate import validate_record

FIXTURE = Path(__file__).parent.parent / "cbsa_tariff" / "fixtures" / "ch09-2026-2.html"


@pytest.fixture(scope="module")
def records():
    return list(records_from_html(
        FIXTURE.read_text(encoding="utf-8"),
        effective_from=EDITION["effective_from"], observed_at="2026-10-21T00:00:00Z",
    ))


def test_fixture_record_count_and_validity(records):
    assert len(records) >= 60
    for rec in records:
        assert validate_record(rec) == [], (rec["id"], validate_record(rec))
    assert len({r["id"] for r in records}) == len(records)


def test_coffee_row(records):
    rec = next(r for r in records if r["id"] == "cbsa_tariff:0901.11.00.10")
    attrs = rec["attributes"]
    assert attrs["hs_code"] == "0901110010"
    assert {"treatment": "MFN", "rate": "Free"} in attrs["rates"]
    assert {"treatment": "UST", "rate": "Free"} in attrs["rates"]
    assert attrs["effective_from"] == "2026-09-01" and attrs["effective_to"] is None


def test_empty_ss_gives_eight_digits(records):
    rec = next(r for r in records if r["id"] == "cbsa_tariff:0901.11.00")
    assert rec["attributes"]["hs_code"] == "09011100"


def test_heading_rows_skipped():
    items = {r["tariff_item"] for r in parse_chapter_html(FIXTURE.read_text(encoding="utf-8"))}
    assert "09.01" not in items and "0902.10" not in items and "Tariff Item" not in items


def test_parse_preferential_two_groups():
    assert parse_preferential("CCCT, LDCT, GPT: Free; UST: 2%") == [
        {"treatment": "CCCT", "rate": "Free"},
        {"treatment": "LDCT", "rate": "Free"},
        {"treatment": "GPT", "rate": "Free"},
        {"treatment": "UST", "rate": "2%"},
    ]
    assert parse_preferential("CCCT: Free\nUST: $1.20/kg") == [
        {"treatment": "CCCT", "rate": "Free"},
        {"treatment": "UST", "rate": "$1.20/kg"},
    ]
    assert parse_preferential("") == []


def test_nbsp_nested_tags_multiline():
    html = ("<table><tr><td>0101.21.00</td><td>&nbsp;</td><td><p>Horses</p> - <b>Pure-bred</b></td>"
            "<td>NMB</td><td>Free</td><td>CCCT, LDCT:<br>Free;<br>UST: 2%</td></tr></table>")
    (row,) = parse_chapter_html(html)
    assert row["ss"] == "" and row["uom"] == "NMB"
    assert row["description"] == "Horses - Pure-bred"
    assert parse_preferential(row["preferential"])[-1] == {"treatment": "UST", "rate": "2%"}


@pytest.mark.skipif(not os.environ.get("TRADELATTICE_LIVE"), reason="set TRADELATTICE_LIVE=1 for network tests")
def test_live_chapter_9():
    recs = list(fetch(live=True, chapters=[9]))
    assert len(recs) >= 60
    assert all(validate_record(r) == [] for r in recs)
    json.dumps(recs[0])
