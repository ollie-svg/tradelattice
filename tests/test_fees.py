import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from tradelattice.api.db import Base, engine
from tradelattice.api.fees import FeeRule, evaluate
from tradelattice.api.jurisdictions import CA_FEES, US_FEES
from tradelattice.api.main import app


def rule(name="X", kind="pct", rate="10", amount=None, base="value", mn=None, mx=None,
         when=None, frm="2020-01-01", to=None, cat="fee"):
    return FeeRule(name, "test", kind, rate, amount, base, mn, mx, when, frm, to, cat, None)


CTX = {"value": D(1000), "duty": D(100), "surtax": D(500)}
ON = "2026-11-04"


def ev(rules, on=ON, mode=None, taxes=False, ctx=CTX):
    return evaluate(rules, ctx, on, mode, taxes)


def test_pct_on_value():
    fees, taxes = ev([rule(rate="2.5")])
    assert taxes == []
    assert fees == [{"name": "X", "authority": "test", "base": "value",
                     "base_amount": 1000.0, "amount": 25.0}]


def test_cascade_duty_paid_value():
    fees, _ = ev([rule(rate="5", base="duty_paid_value")])
    assert fees[0]["base_amount"] == 1600.0 and fees[0]["amount"] == 80.0


def test_pct_on_duty_and_surtax():
    fees, _ = ev([rule("D", rate="10", base="duty"), rule("S", rate="10", base="surtax")])
    assert [f["amount"] for f in fees] == [10.0, 50.0]


def test_flat():
    fees, _ = ev([rule(kind="flat", rate=None, amount="12.345")])
    assert fees[0]["amount"] == 12.35  # half-up


def test_min_clamp():
    assert ev([rule(rate="1", mn="50")])[0][0]["amount"] == 50.0


def test_max_clamp():
    assert ev([rule(rate="10", mx="30")])[0][0]["amount"] == 30.0


def test_applies_when_mode():
    r = rule(when={"mode": "sea"})
    assert ev([r], mode="sea")[0] != []
    assert ev([r], mode="air")[0] == []
    assert ev([r])[0] == []
    assert ev([rule()], mode="air")[0] != []


def test_date_window():
    mpf = [r for r in US_FEES if r.name == "MPF"]
    nov = ev(mpf, on="2026-11-04")[0]
    assert len(nov) == 1 and nov[0]["amount"] == 34.58  # 0.3464% of 1000 = 3.46 -> min 34.58
    jun = ev(mpf, on="2026-06-01")[0]
    assert len(jun) == 1 and jun[0]["amount"] == 33.58
    assert ev(mpf, on="2026-10-01")[0][0]["amount"] == 34.58  # effective_to exclusive
    assert ev(mpf, on="2025-09-30")[0] == []


def test_mpf_unclamped_and_hmf():
    ctx = {"value": D(13994), "duty": D(0), "surtax": D(0)}
    fees, _ = ev(US_FEES, mode="sea", ctx=ctx)
    assert [(f["name"], f["amount"]) for f in fees] == [("MPF", 48.48), ("HMF", 17.49)]
    assert [f["name"] for f in ev(US_FEES, mode="air", ctx=ctx)[0]] == ["MPF"]


def test_tax_skipped_unless_include_taxes():
    r = rule("GST", rate="5", base="duty_paid_value", cat="tax")
    assert ev([r]) == ([], [])
    fees, taxes = ev([r], taxes=True)
    assert fees == [] and taxes[0]["amount"] == 80.0


def test_fees_so_far():
    rules = [rule("A", rate="10"), rule("B", kind="flat", rate=None, amount="5"),
             rule("C", rate="10", base="fees_so_far"),
             rule("T", rate="10", base="fees_so_far", cat="tax")]
    fees, taxes = ev(rules, taxes=True)
    assert [f["amount"] for f in fees] == [100.0, 5.0, 10.5]
    assert taxes[0]["base_amount"] == 115.5  # taxes see fees only


def test_ca_schedule():
    assert [r.name for r in CA_FEES] == ["GST"] and CA_FEES[0].category == "tax"


# ---- API ----

def rec(rid, type_, attrs):
    return {"id": rid, "type": type_, "source": "t", "observed_at": "2026-01-01T00:00:00Z",
            "jurisdiction": "CA", "attributes": attrs}


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
            rec("s:1", "surtax_order", {
                "hs_prefix": "72083600", "origin_country": "US", "pct": "50",
                "list_id": "L", "effective_from": "2026-09-08", "effective_to": None}),
        ])
        yield c


def post(client, **over):
    body = {"hs_code": "7208.36.00", "origin_country": "US",
            "declared_value": {"amount": 1000, "currency": "USD"},
            "shipment_date": "2026-11-04"}
    body.update(over)
    return client.post("/landed-cost", json=body)


def test_api_default_no_fees(client):
    j = post(client).json()
    assert j["fees"] == [] and j["taxes"] == [] and j["include_taxes"] is False
    assert j["total"] == 2099.10 and len(j["components"]) == 3


def test_api_gst(client):
    j = post(client, include_taxes=True).json()
    # duty-paid value = 1399.40 + 0 duty + 699.70 surtax = 2099.10; GST = 5% * 2099.10 = 104.955 -> 104.96
    assert j["include_taxes"] is True and j["fees"] == []
    assert j["taxes"] == [{"name": "GST", "authority": "ETA s.212", "base": "duty_paid_value",
                           "base_amount": 2099.10, "amount": 104.96}]
    assert j["total"] == 2204.06  # 2099.10 + 104.96
    assert j["components"][-1] == "GST 5% of duty-paid value 2,099.10 = 104.96"


def test_api_fta_unknown_both_totals_carry_gst(client):
    # one conditional order (overwrites the fixture's s:1); qualification unknown -> both totals
    client.post("/records", json=[
        rec("s:1", "surtax_order", {"hs_prefix": "72083600", "origin_country": "US", "pct": "25",
                                    "list_id": "L", "effective_from": "2026-09-08",
                                    "effective_to": None, "exempt_if": "fta_qualified"}),
    ])
    cad = {"amount": 1000, "currency": "CAD"}
    j = post(client, declared_value=cad, include_taxes=True).json()
    # not qualified: surtax 250 -> duty-paid 1250 -> GST 62.50 -> total 1312.50
    # qualified:     surtax   0 -> duty-paid 1000 -> GST 50.00 -> total 1050.00
    assert j["surtax"] == 250 and j["taxes"][0]["amount"] == 62.5 and j["total"] == 1312.5
    assert j["surtax_if_fta_qualified"] == 0 and j["total_if_fta_qualified"] == 1050.0


def test_api_two_orders_refuse_before_fees(client):
    client.post("/records", json=[
        rec("s:2", "surtax_order", {"hs_prefix": "7208", "origin_country": "US", "pct": "10",
                                    "list_id": "L2", "effective_from": "2026-09-08",
                                    "effective_to": None}),
    ])
    r = post(client, declared_value={"amount": 1000, "currency": "CAD"}, include_taxes=True)
    assert r.status_code == 422 and r.json()["reason"] == "surtax_ambiguous"


def test_evaluate_accepts_plain_numbers():
    """evaluate() is public; callers may pass floats, not only Decimals."""
    from tradelattice.api.fees import evaluate
    from tradelattice.api.jurisdictions import JURISDICTIONS

    us = JURISDICTIONS["US"].fee_schedule
    fees, _ = evaluate(us, {"value": 13994.0, "duty": 0, "surtax": 0}, "2026-11-04", "sea", False)
    by = {f["name"]: f["amount"] for f in fees}
    assert by["MPF"] == 48.48  # 0.3464% of 13,994.00 = 48.475 -> 48.48
    assert by["HMF"] == 17.49  # 0.125% of 13,994.00 = 17.4925 -> 17.49
    fees, _ = evaluate(us, {"value": 500000.0, "duty": 0, "surtax": 0}, "2026-11-04", "road", False)
    assert [(f["name"], f["amount"]) for f in fees] == [("MPF", 670.86)]  # clamped to FY2027 max
    fees, _ = evaluate(us, {"value": 1000.0, "duty": 0, "surtax": 0}, "2026-06-01", None, False)
    assert [(f["name"], f["amount"]) for f in fees] == [("MPF", 33.58)]  # FY2026 min applies
