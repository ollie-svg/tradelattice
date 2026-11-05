import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from tradelattice.api.db import Base, engine
from tradelattice.api.main import app


def rec(rid, type_, attrs):
    return {"id": rid, "type": type_, "source": "t", "observed_at": "2026-01-01T00:00:00Z",
            "jurisdiction": "CA", "attributes": attrs}


def fx(on, rate, cur="USD"):
    return rec(f"fx:{cur}:{on}", "fx_rate",
               {"currency": cur, "to": "CAD", "rate": rate, "on": on, "publisher": "boc"})


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        c.post("/records", json=[
            rec("t:72083600", "tariff_line", {
                "hs_code": "72083600", "description": "Steel",
                "rates": [{"treatment": "MFN", "rate": "Free"}, {"treatment": "UST", "rate": "Free"}],
                "effective_from": "2026-01-01", "effective_to": None}),
            fx("2026-10-30", "1.3900"),
            fx("2026-11-03", "1.3994"),
            rec("s:1", "surtax_order", {
                "hs_prefix": "72083600", "origin_country": "US", "pct": "50",
                "list_id": "finance-ca-counter-tariffs-2026-09-08",
                "effective_from": "2026-09-08", "effective_to": None,
                "source_url": "https://example.test/"}),
        ])
        yield c


def post(client, **over):
    body = {"hs_code": "7208.36.00", "origin_country": "US",
            "declared_value": {"amount": 1000, "currency": "USD"},
            "shipment_date": "2026-11-04"}
    body.update(over)
    return client.post("/landed-cost", json=body)


def test_a_fx_and_surtax(client):
    r = post(client)
    assert r.status_code == 200
    j = r.json()
    assert j["fx_rate"] == "1.3994" and j["fx_on"] == "2026-11-03"
    assert j["value_cad"] == 1399.40 and j["duty"] == 0
    assert j["surtax"] == 699.70 and j["surtax_pct"] == "50"
    assert j["surtax_list_id"] == "finance-ca-counter-tariffs-2026-09-08"
    assert j["total"] == 2099.10
    assert j["currency"] == "CAD" and j["declared_currency"] == "USD"
    assert j["shipment_date"] == "2026-11-04"
    assert "FX USD→CAD at 1.3994 (BoC 2026-11-03): 1,000.00 USD = 1,399.40 CAD" in j["components"]
    assert ("surtax 50% of 1,399.40 (finance-ca-counter-tariffs-2026-09-08, origin US) = 699.70"
            in j["components"])


def test_b_earlier_rate(client):
    j = post(client, shipment_date="2026-11-01").json()
    assert j["fx_rate"] == "1.3900" and j["fx_on"] == "2026-10-30"
    assert j["value_cad"] == 1390.0


def test_c_other_origin(client):
    j = post(client, origin_country="mx").json()
    assert j["surtax"] == 0 and j["surtax_list_id"] is None and j["surtax_pct"] is None
    assert j["total"] == 1399.40


def test_d_before_order(client):
    # USD has no fx record that early (422), so use CAD to isolate the surtax date window.
    assert post(client, shipment_date="2026-09-01").status_code == 422
    j = post(client, shipment_date="2026-09-01", declared_value={"amount": 1000, "currency": "CAD"}).json()
    assert j["surtax"] == 0 and j["surtax_list_id"] is None


def test_e_cad(client):
    j = post(client, declared_value={"amount": 1000, "currency": "CAD"}).json()
    assert j["fx_rate"] is None and j["fx_on"] is None
    assert j["value_cad"] == 1000 and j["surtax"] == 500 and j["total"] == 1500


def test_f_missing_fx(client):
    r = post(client, declared_value={"amount": 10, "currency": "EUR"})
    assert r.status_code == 422
    assert r.json()["detail"] == (
        "no CAD exchange rate on or before 2026-11-04 for EUR; load the boc_fx connector")


def test_g_validation(client):
    assert post(client, shipment_date="not-a-date").status_code == 422
    assert post(client, origin_country="USA").status_code == 422
    assert post(client, origin_country="1x").status_code == 422
