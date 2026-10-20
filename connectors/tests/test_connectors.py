import importlib
import json

import pytest

from spec.validate import validate_record

NAMES = ["cbsa_tariff", "canadabuys", "statcan_trade"]


def _fetch(name, **kw):
    return list(importlib.import_module(f"connectors.{name}").fetch(**kw))


@pytest.mark.parametrize("name", NAMES)
def test_sample_records_validate(name):
    records = _fetch(name)
    assert len(records) >= 10
    for rec in records:
        assert validate_record(rec) == [], (rec["id"], validate_record(rec))
    assert len({r["id"] for r in records}) == len(records)


@pytest.mark.parametrize("name", NAMES)
def test_live_not_implemented(name):
    with pytest.raises(NotImplementedError):
        _fetch(name, live=True)


def test_statcan_skips_zero_quantity():
    recs = _fetch("statcan_trade")
    assert all(r["attributes"]["price"]["amount"] > 0 for r in recs)
    assert not any(r["attributes"]["subject"]["hs_code"] == "950300" for r in recs)


@pytest.mark.parametrize("name", NAMES)
def test_cli_writes_jsonl(name, tmp_path):
    from connectors import _base
    out = tmp_path / "o.jsonl"
    mod = importlib.import_module(f"connectors.{name}")
    assert _base.run_cli(name, mod.fetch, ["--out", str(out)]) == 0
    lines = out.read_text().splitlines()
    assert len(lines) >= 10 and json.loads(lines[0])["source"] == name
