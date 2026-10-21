import json
import os
from pathlib import Path

import pytest

from connectors.cbsa_tariff import editions as ed

FIXTURE = Path(__file__).parent.parent / "cbsa_tariff" / "fixtures" / "menu-2026.html"


def _rec(native_id, rates, hs="0101"):
    return {"id": f"cbsa_tariff:{native_id}", "attributes": {
        "hs_code": hs, "description": f"d {native_id}",
        "rates": [{"treatment": t, "rate": r} for t, r in rates]}}


def _write(path, recs):
    path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    return path


def test_parse_fixture_newest_first():
    eds = ed.parse_editions(FIXTURE.read_text(encoding="utf-8"))
    assert eds[0] == {"name": "T2026-2", "revision": "02", "effective_from": "2026-09-01"}
    assert [e["name"] for e in eds] == ["T2026-2", "T2026-1", "T2026"]
    assert eds[-1]["revision"] == "00"


def test_diff_records(tmp_path):
    old = _write(tmp_path / "old.jsonl", [
        _rec("a", [("MFN", "5%"), ("CPTPP", "0")]),
        _rec("b", [("MFN", "Free")]),
        _rec("gone", [("MFN", "1%")]),
        _rec("same", [("MFN", "2%")]),
    ])
    new = _write(tmp_path / "new.jsonl", [
        _rec("a", [("CPTPP", "0"), ("MFN", "6%")]),
        _rec("b", [("MFN", "Free")]),
        _rec("fresh", [("MFN", "3%")]),
        _rec("same", [("MFN", "2%")]),
    ])
    d = ed.diff_records(old, new)
    assert d["added"] == ["cbsa_tariff:fresh"]
    assert d["removed"] == ["cbsa_tariff:gone"]
    assert [c["id"] for c in d["changed"]] == ["cbsa_tariff:a"]
    md = ed.format_diff_markdown(d, "T2026-1", "T2026-2")
    assert "Added: 1" in md and "Removed: 1" in md and "Changed: 1" in md
    assert "| 0101 | MFN | 5% -> 6% |" in md


def test_diff_order_insensitive(tmp_path):
    old = _write(tmp_path / "o.jsonl", [_rec("a", [("MFN", "5%"), ("X", "1")])])
    new = _write(tmp_path / "n.jsonl", [_rec("a", [("X", "1"), ("MFN", "5%")])])
    assert ed.diff_records(old, new)["changed"] == []


def test_markdown_truncation():
    changed = [{"id": f"i{n}", "hs_code": str(n), "description": "",
                "before": [{"treatment": "MFN", "rate": "1"}],
                "after": [{"treatment": "MFN", "rate": "2"}]} for n in range(205)]
    md = ed.format_diff_markdown({"added": [], "removed": [], "changed": changed}, "a", "b")
    assert "5 more" in md


@pytest.mark.skipif(not os.environ.get("TRADELATTICE_LIVE"), reason="set TRADELATTICE_LIVE=1 for network tests")
def test_live_list_editions():
    eds = ed.list_editions(2026)
    assert eds and eds[0]["name"].startswith("T2026")
    assert ed.current_edition()["name"]


def test_chapter_urls_follow_index_not_revision():
    """T2026-1 changed one chapter; its index points the other 98 at revision 00."""
    from pathlib import Path

    from connectors.cbsa_tariff import chapter_urls, index_url

    ed = {"name": "T2026-1", "revision": "01", "effective_from": "2026-08-06"}
    assert index_url(ed).endswith("/2026/html/tblmod-1-eng.html")
    html = (Path(__file__).parent.parent / "cbsa_tariff" / "fixtures" / "tblmod-1-2026.html").read_text()
    urls = chapter_urls(ed, html)
    assert len(urls) == 99
    revs = {u.split("/html/")[1][:2] for u in urls.values()}
    assert revs == {"00", "01"}
    assert sum(u.split("/html/")[1][:2] == "01" for u in urls.values()) == 1
    assert urls[9].endswith("/html/00/ch09-eng.html")
