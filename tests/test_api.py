import copy
import json
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from api import cli
from api.db import Base, engine, init_db
from api.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # lifespan creates tables
        yield c


def tariff(code, rates=None, rid=None, desc="Tea"):
    return {
        "id": rid or f"t:{code}",
        "type": "tariff_line",
        "source": "t",
        "observed_at": "2026-01-01T00:00:00Z",
        "jurisdiction": "CA",
        "attributes": {
            "hs_code": code,
            "description": desc,
            "rates": rates if rates is not None else [{"treatment": "MFN", "rate": "10%"}],
            "effective_from": "2026-01-01",
            "effective_to": None,
        },
    }


def product(pid="p:1"):
    return {
        "id": pid,
        "type": "product",
        "source": "p",
        "observed_at": "2026-01-01T00:00:00Z",
        "jurisdiction": "CA",
        "attributes": {"hs_code": "090230", "description": "Green Widget"},
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_post_single_and_get(client):
    r = client.post("/records", json=product())
    assert r.status_code == 200 and r.json()["count"] == 1
    got = client.get("/records/p:1")
    assert got.status_code == 200
    assert got.json()["attributes"]["description"] == "Green Widget"
    assert client.get("/records/p:missing").status_code == 404


def test_post_array_and_upsert(client):
    a, b = product("p:1"), product("p:2")
    assert client.post("/records", json=[a, b]).json()["count"] == 2
    a2 = copy.deepcopy(a)
    a2["attributes"]["description"] = "Changed"
    client.post("/records", json=a2)
    rows = client.get("/records").json()
    assert len(rows) == 2
    assert client.get("/records/p:1").json()["attributes"]["description"] == "Changed"


def test_invalid_record_422(client):
    bad = product()
    bad["attributes"]["hs_code"] = "abc"
    r = client.post("/records", json=[product("p:9"), bad])
    assert r.status_code == 422
    assert any("hs_code" in e for e in r.json()["detail"])
    assert client.get("/records").json() == []  # nothing written


def test_list_filters(client):
    other = product("q:1")
    other["source"] = "q"
    other["attributes"]["description"] = "Other thing"
    client.post("/records", json=[product("p:1"), product("p:2"), other, tariff("090200")])
    assert len(client.get("/records").json()) == 4
    assert len(client.get("/records?type=product").json()) == 3
    assert len(client.get("/records?type=product&source=q").json()) == 1
    assert [r["id"] for r in client.get("/records?q=GREEN WIDGET").json()] == ["p:1", "p:2"]
    assert len(client.get("/records?limit=2").json()) == 2
    assert len(client.get("/records?limit=2&offset=3").json()) == 1
    assert client.get("/records?limit=501").status_code == 422
    assert client.get("/records?limit=0").status_code == 422


def test_tariff_prefix(client):
    # Schema requires 6-10 digit hs_code, so use 090200 / 090230 / 09023000.
    client.post("/records", json=[tariff("090200"), tariff("090230"), tariff("09023000")])
    assert client.get("/tariff/0902300000").json()["attributes"]["hs_code"] == "09023000"
    assert client.get("/tariff/0902309999").json()["attributes"]["hs_code"] == "090230"
    assert client.get("/tariff/090230").json()["attributes"]["hs_code"] == "090230"
    assert client.get("/tariff/0902.00.12").json()["attributes"]["hs_code"] == "090200"
    assert client.get("/tariff/1234567890").status_code == 404
    assert client.get("/tariff/abc").status_code == 422


def landed(client, **over):
    body = {
        "hs_code": "0902300000",
        "origin_country": "US",
        "declared_value": {"amount": 200, "currency": "CAD"},
    }
    body.update(over)
    return client.post("/landed-cost", json=body)


def test_landed_cost(client):
    client.post(
        "/records",
        json=[
            tariff("090200", [{"treatment": "MFN", "rate": "5%"}]),
            tariff(
                "090230",
                [
                    {"treatment": "MFN", "rate": "6.5%"},
                    {"treatment": "CUSMA", "rate": "Free"},
                    {"treatment": "ZERO", "rate": "0%"},
                    {"treatment": "SPEC", "rate": "$1.20/kg"},
                ],
            ),
        ],
    )
    r = landed(client)
    assert r.status_code == 200
    assert r.json() == {
        "hs_code": "0902300000",
        "matched_hs_code": "090230",
        "treatment": "MFN",
        "duty_rate": 6.5,
        "duty": 13.0,
        "total": 213.0,
        "currency": "CAD",
        "rate": "6.5%",
        "components": ["6.5% ad valorem = 13.00"],
        "basis": "ad_valorem",
    }
    assert landed(client, treatment="CUSMA").json()["duty"] == 0
    assert landed(client, treatment="ZERO").json()["duty_rate"] == 0
    s = landed(client, treatment="SPEC")
    assert s.status_code == 422 and "kg" in s.json()["detail"]
    ok = landed(client, treatment="SPEC", quantity=10, unit="kg")
    assert ok.status_code == 200
    # 1.20 * 10 kg = 12.00; effective 12/200*100 = 6.0
    assert ok.json()["duty"] == 12.0 and ok.json()["basis"] == "specific"
    assert ok.json()["duty_rate"] == 6.0
    assert ok.json()["components"] == ["$1.20/kg × 10 kg = 12.00"]
    bad = landed(client, treatment="SPEC", quantity=10, unit="litre")
    assert bad.status_code == 422
    assert landed(client, treatment="NOPE").status_code == 404
    assert landed(client, hs_code="9999999999").status_code == 404


def test_root_and_static(client):
    r = client.get("/")
    assert r.status_code == 200


def test_cli_load(tmp_path):
    init_db()
    f = tmp_path / "r.jsonl"
    lines = [json.dumps(tariff(f"09023{i}", rid=f"t:{i}")) for i in range(3)]
    lines.append("{bad")
    f.write_text("\n".join(lines) + "\n")
    assert cli.load(str(f)) == (3, 1)
    assert cli.load(str(f)) == (3, 1)  # idempotent
    with TestClient(app) as c:
        assert len(c.get("/records?type=tariff_line").json()) == 3


def test_landed_cost_compound_and_na(client):
    client.post(
        "/records",
        json=[
            tariff(
                "090230",
                [
                    {"treatment": "MFN", "rate": "5% but not less than 4.74¢/kg or more than 9.48¢/kg"},
                    {"treatment": "NA", "rate": "Free, CPUKT N/A"},
                ],
            )
        ],
    )
    r = landed(client, declared_value={"amount": 1000, "currency": "CAD"}, quantity=2000, unit="kg")
    assert r.status_code == 200
    j = r.json()
    # 5% = 50; floor 0.0474*2000 = 94.80; cap 0.0948*2000 = 189.60 -> 94.80; 94.8/1000*100 = 9.48
    assert j["duty"] == 94.8 and j["duty_rate"] == 9.48 and j["basis"] == "compound"
    assert j["rate"].startswith("5% but")
    assert j["components"] == [
        "5% ad valorem = 50.00",
        "floor 4.74¢/kg × 2000 kg = 94.80",
        "cap 9.48¢/kg × 2000 kg = 189.60",
    ]
    assert landed(client).status_code == 422
    na = landed(client, treatment="NA")
    assert na.status_code == 422 and na.json()["detail"] == "rate not applicable for this treatment"
