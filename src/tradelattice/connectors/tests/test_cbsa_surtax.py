import os
from collections import Counter

import pytest

from tradelattice.connectors import cbsa_surtax as cs
from tradelattice.connectors.cbsa_surtax.parse import parse_finance_list_html
from tradelattice.spec.validate import validate_record


def _sample():
    return list(cs.fetch())


def test_sample_volume_validity_unique_distribution():
    recs = _sample()
    assert len(recs) == 629
    for rec in recs:
        assert validate_record(rec) == [], (rec["id"], validate_record(rec))
    assert len({r["id"] for r in recs}) == len(recs)
    assert Counter(r["attributes"]["pct"] for r in recs) == {"50": 413, "25": 195, "15": 21}


def test_record_shape():
    rec = next(r for r in _sample() if r["attributes"]["hs_prefix"] == "04021010")
    assert rec["id"] == "cbsa_surtax:finance-ca-counter-tariffs-2026-09-08:04021010:US"
    assert rec["observed_at"] == "2026-09-08T00:00:00Z"
    assert rec["attributes"]["pct"] == "50"
    assert rec["attributes"]["effective_to"] is None


def test_applicable():
    recs = _sample()
    hit = cs.applicable(recs, "0402101000", "US", "2026-10-01")
    assert [a["hs_prefix"] for a in hit] == ["04021010"]
    assert hit[0]["pct"] == "50"
    assert cs.applicable(recs, "0402.10.10.00", "US", "2026-10-01") == hit
    assert cs.applicable(recs, "0402101000", "MX", "2026-10-01") == []
    assert cs.applicable(recs, "0402101000", "US", "2026-09-07") == []


def test_applicable_window_and_longest_prefix():
    def rec(prefix, frm, to):
        return {"type": "surtax_order", "attributes": {
            "hs_prefix": prefix, "origin_country": "US", "pct": "25", "list_id": "x",
            "effective_from": frm, "effective_to": to}}
    recs = [rec("04", "2026-01-01", None), rec("040210", "2026-01-01", "2026-06-01"),
            rec("04021010", "2026-01-01", None)]
    assert [a["hs_prefix"] for a in cs.applicable(recs, "0402101000", "US", "2026-03-01")] == [
        "04021010", "040210", "04"]
    assert [a["hs_prefix"] for a in cs.applicable(recs, "0402101000", "US", "2026-06-01")] == [
        "04021010", "04"]


def test_parse_html_skips_malformed():
    html = """<table><tr><th>Tariff item</th><th>HS</th><th>Desc</th><th>Rate</th></tr>
    <tr><td>0402.10.10</td><td>Milk</td><td>Powder &amp; solids</td><td>50</td></tr>
    <tr><td>7208.10.00</td><td>Steel</td><td>Hot-rolled</td><td>25</td></tr>
    <tr><td>bad item</td><td>X</td><td>Y</td><td>25</td></tr>
    <tr><td>0901.11.00</td><td>Coffee</td><td>Not roasted</td><td>n/a</td></tr></table>"""
    rows = parse_finance_list_html(html)
    assert rows == [
        {"item": "0402.10.10", "heading": "Milk", "desc": "Powder & solids", "rate": 50},
        {"item": "7208.10.00", "heading": "Steel", "desc": "Hot-rolled", "rate": 25},
    ]


def test_url_requires_list_id_and_date():
    with pytest.raises(ValueError, match="--list-id"):
        list(cs.fetch(live=True, url="https://example.com/x"))


@pytest.mark.skipif(not os.environ.get("TRADELATTICE_LIVE"), reason="set TRADELATTICE_LIVE=1")
def test_live():
    recs = list(cs.fetch(live=True))
    assert len(recs) == 629
    for rec in recs:
        assert validate_record(rec) == []
