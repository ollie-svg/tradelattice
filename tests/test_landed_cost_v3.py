import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tradelattice.api.db import Base, engine
from tradelattice.api.main import app
from tradelattice.api.overlays import PROHIBITED_MESSAGE, prohibited

EXAMPLE = Path(__file__).parent.parent / "src/tradelattice/spec/examples/prohibition.json"
LIST = "finance-ca-counter-tariffs-2026-09-08"


def rec(rid, type_, attrs, jur="CA"):
    return {"id": rid, "type": type_, "source": "t", "observed_at": "2026-01-01T00:00:00Z",
            "jurisdiction": jur, "attributes": attrs}


def sur(rid, prefix, pct, **extra):
    a = {"hs_prefix": prefix, "origin_country": "US", "pct": pct, "list_id": LIST,
         "effective_from": "2026-09-08", "effective_to": None}
    a.update(extra)
    return rec(rid, "surtax_order", a)


def ban_ca():
    return rec("ban:ca", "prohibition", {
        "hs_prefix": "7208", "origin_country": "US", "list_id": "ca-ban-test",
        "authority": "test", "effective_from": "2026-10-01", "effective_to": None,
        "source_url": "https://example.test/ban"})


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        c.post("/records", json=[
            rec("t:72083600", "tariff_line", {
                "hs_code": "72083600", "description": "Steel",
                "rates": [{"treatment": "MFN", "rate": "Free"}],
                "effective_from": "2026-01-01", "effective_to": None}),
            rec("fx:USD:2026-11-03", "fx_rate", {"currency": "USD", "to": "CAD", "rate": "1.3994",
                                                  "on": "2026-11-03", "publisher": "boc"}),
            sur("s:1", "72083600", "50"),
        ])
        yield c


def post(client, **over):
    body = {"hs_code": "7208.36.00", "origin_country": "US",
            "declared_value": {"amount": 1000, "currency": "USD"},
            "shipment_date": "2026-11-04"}
    body.update(over)
    return client.post("/landed-cost", json=body)


def test_a_ca_default_unchanged(client):
    j = post(client).json()
    assert j["surtax"] == 699.70 and j["total"] == 2099.10 and j["value_cad"] == 1399.40
    assert j["jurisdiction"] == "CA" and j["fta_qualified"] is None
    assert j["surtax_if_fta_qualified"] is None and j["total_if_fta_qualified"] is None
    assert len(j["components"]) == 3


def test_b_us_501(client):
    r = post(client, jurisdiction="us")
    assert r.status_code == 501
    assert r.json()["detail"] == "US profile has no data loaded yet; see the roadmap"


def test_c_unknown_jurisdiction(client):
    r = post(client, jurisdiction="ZZ")
    assert r.status_code == 422
    assert r.json()["detail"] == "unknown jurisdiction 'ZZ'"


def test_d_prohibited(client):
    ex = json.loads(EXAMPLE.read_text())
    assert client.post("/records", json=[ex, ban_ca()]).status_code == 200
    r = post(client)
    assert r.status_code == 409
    j = r.json()
    assert j["prohibited"] is True and j["list_id"] == "ca-ban-test"
    assert j["jurisdiction"] == "CA" and j["origin_country"] == "US" and j["hs_code"] == "72083600"
    assert j["effective_from"] == "2026-10-01" and j["effective_to"] is None
    assert j["source_url"] == "https://example.test/ban" and j["message"] == PROHIBITED_MESSAGE
    # before effective_from: computes normally (CAD, as no FX exists that early)
    ok = post(client, shipment_date="2026-09-01", declared_value={"amount": 1000, "currency": "CAD"})
    assert ok.status_code == 200 and ok.json()["surtax"] == 0
    # the US-jurisdiction example does not affect CA requests for other origins
    assert post(client, origin_country="CA", declared_value={"amount": 1, "currency": "CAD"}).status_code == 200


def test_e_fta_tristate(client):
    # fixture has 50% on 72083600; replace with 50% on the shorter prefix 7208
    client.post("/records", json=[sur("s:1", "7208", "50"), sur("s:exempt", "72083600", "25",
                                                                exempt_if="fta_qualified")])
    cad = {"amount": 1000, "currency": "CAD"}
    t = post(client, declared_value=cad, fta_qualified=True).json()
    assert t["surtax"] == 500 and t["surtax_pct"] == "50" and t["surtax_if_fta_qualified"] is None
    f = post(client, declared_value=cad, fta_qualified=False).json()
    assert f["surtax"] == 250 and f["surtax_pct"] == "25" and f["fta_qualified"] is False
    n = post(client, declared_value=cad).json()
    assert n["fta_qualified"] is None
    assert n["surtax"] == 250 and n["surtax_if_fta_qualified"] == 500
    assert n["total"] == 1250 and n["total_if_fta_qualified"] == 1500
    assert "FTA qualification unknown: surtax 250.00 if not qualified, 500.00 if qualified" in n["components"]


def test_f_basis_unsupported(client):
    client.post("/records", json=[sur("s:1", "72083600", "50", basis="non_fta_content_value")])
    r = post(client)
    assert r.status_code == 422
    assert r.json()["detail"] == (
        "surtax basis 'non_fta_content_value' needs a content value; not supported yet")


def test_prohibited_unit():
    def p(prefix, origin="US", frm="2026-10-01", to=None, jur="CA", lid="x"):
        return rec(lid, "prohibition", {"hs_prefix": prefix, "origin_country": origin, "list_id": lid,
                                        "effective_from": frm, "effective_to": to}, jur)
    recs = [p("72", lid="short"), p("7208", lid="long"), p("7208", jur="US", lid="otherjur"),
            p("7208", origin="MX", lid="otherorigin"), p("72083600", to="2026-11-01", lid="expired")]
    hit = prohibited(recs, "72083600", "US", "2026-11-04", "CA")
    assert hit["list_id"] == "long" and hit["authority"] is None and hit["source_url"] is None
    assert prohibited(recs, "72083600", "US", "2026-09-30", "CA") is None  # before effective_from
    assert prohibited(recs, "72083600", "US", "2026-10-15", "CA")["list_id"] == "expired"
    assert prohibited(recs, "72083600", "US", "2026-11-01", "CA")["list_id"] == "long"  # to exclusive
    assert prohibited(recs, "72083600", "MX", "2026-11-04", "CA")["list_id"] == "otherorigin"
    assert prohibited(recs, "72083600", "US", "2026-11-04", "US")["list_id"] == "otherjur"
    assert prohibited(recs, "8501", "US", "2026-11-04", "CA") is None
    assert prohibited([rec("t", "tariff_line", {})], "72", "US", "2026-11-04", "CA") is None
