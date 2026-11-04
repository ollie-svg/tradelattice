import os
from collections import Counter

import pytest

from tradelattice.connectors import cbsa_concordance as cc
from tradelattice.connectors.cbsa_concordance.parse import (
    Pair,
    derive_relations,
    load_workbook_pairs,
)
from tradelattice.spec.validate import validate_record


def _sample():
    return list(cc.fetch())


def test_sample_volume_validity_unique():
    recs = _sample()
    assert len(recs) == 1472 + 23
    for rec in recs:
        assert validate_record(rec) == [], (rec["id"], validate_record(rec))
    assert len({r["id"] for r in recs}) == len(recs)


def test_2022_relation_counts():
    recs = [r for r in _sample() if r["attributes"]["to_edition"] == "T2022"]
    rel = Counter(r["attributes"]["relation"] for r in recs)
    assert rel["same"] == 3
    # identity pair inside a split is split, not same
    pairs = load_workbook_pairs(cc.SAMPLE_DIR / "conc-8-finance-2022.xlsx")
    src = Counter(p.from_code for p in pairs)
    ident = next(p for p in pairs if p.from_code == p.to_code and src[p.from_code] > 1)
    r = next(x for x in recs if x["attributes"]["from_code"] == ident.from_code
             and x["attributes"]["to_code"] == ident.to_code)
    assert r["attributes"]["relation"] == "split"
    assert rel["renumbered"] >= 50
    assert rel["split"] > 0 and rel["merged"] > 0
    assert sum(rel.values()) == 1472


def test_10_digit_sample_direction_and_relation():
    recs = [r for r in _sample() if r["attributes"]["to_edition"] == "T2026"]
    assert len(recs) == 23
    hit = next(r for r in recs
               if r["attributes"]["from_code"] == "2825600000"
               and r["attributes"]["to_code"] == "2825600010")
    assert hit["attributes"]["relation"] == "split"
    assert hit["attributes"]["from_edition"] == "T2025"
    assert hit["observed_at"] == "2026-01-01T00:00:00Z"


def test_parse_keeps_change_codes():
    pairs = load_workbook_pairs(cc.SAMPLE_DIR / "conc-8-finance-2022.xlsx")
    assert Counter(p.change for p in pairs)["SC"] == 247


def test_derive_relations_rules():
    pairs = [Pair("1", "1"), Pair("2", "3"), Pair("4", "5"), Pair("4", "6"),
             Pair("7", "9"), Pair("8", "9"), Pair("10", "11"), Pair("10", "12"),
             Pair("13", "12")]
    rel = [r["relation"] for r in derive_relations(pairs)]
    assert rel == ["same", "renumbered", "split", "split", "merged", "merged",
                   "split", "split", "merged"]


def test_conc8_live_without_editions_raises():
    with pytest.raises(ValueError, match="--from-edition"):
        list(cc.fetch(live=True, year=2022, file="conc-8-finance-2022.xlsx"))


@pytest.mark.skipif(not os.environ.get("TRADELATTICE_LIVE"), reason="set TRADELATTICE_LIVE=1")
def test_live_2026():
    recs = list(cc.fetch(live=True, year=2026))
    assert recs
    for rec in recs:
        assert validate_record(rec) == []
