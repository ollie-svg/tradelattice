import json
import os
import re
from datetime import date, timedelta

import pytest

from tradelattice.connectors import boc_fx
from tradelattice.spec.validate import validate_record

RATE = re.compile(r"^-?\d+(\.\d+)?$")


def _sample():
    return list(boc_fx.fetch())


def test_sample_volume_and_validity():
    recs = _sample()
    assert len(recs) >= 60
    for rec in recs:
        assert validate_record(rec) == [], (rec["id"], validate_record(rec))
    assert len({r["id"] for r in recs}) == len(recs)
    for rec in recs:
        assert isinstance(rec["attributes"]["rate"], str)
        assert RATE.match(rec["attributes"]["rate"])


def test_usd_last_day_matches_sample_file():
    data = json.loads(boc_fx.SAMPLE.read_text(encoding="utf-8"))
    last = data["observations"][-1]
    rec = next(r for r in _sample() if r["id"] == f"boc_fx:{last['d']}:USD")
    assert rec["attributes"]["rate"] == last["FXUSDCAD"]["v"]
    assert rec["attributes"]["on"] == last["d"]


def test_currency_filter_and_missing_skipped():
    payload = {"observations": [
        {"d": "2026-11-03", "FXUSDCAD": {"v": "1.4"}, "FXEURCAD": {"v": "1.6"}},
        {"d": "2026-11-02", "FXUSDCAD": {"v": "1.3"}},
    ]}
    assert len(list(boc_fx.records_from_payload(payload))) == 3
    only = list(boc_fx.records_from_payload(payload, ["eur"]))
    assert [r["id"] for r in only] == ["boc_fx:2026-11-03:EUR"]


@pytest.mark.skipif(not os.environ.get("TRADELATTICE_LIVE"), reason="set TRADELATTICE_LIVE=1")
def test_live_three_day_window():
    end = date.today()
    recs = list(boc_fx.fetch(live=True, start=end - timedelta(days=3), end=end))
    assert recs
    for rec in recs:
        assert validate_record(rec) == []
