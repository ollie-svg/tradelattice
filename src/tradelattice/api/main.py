"""TradeLattice API."""
from __future__ import annotations

import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from tradelattice.connectors.cbsa_surtax import applicable

from .db import get_session, init_db
from .duty import DutyInputError, NotApplicable, basis, evaluate, parse_duty
from .models import Record
from .schemas import LandedCostIn, LandedCostOut, RecordOut, UpsertResult
from .store import upsert_records
from .validation import validate_records

Db = Annotated[Session, Depends(get_session)]


def _find_web_dir() -> Path | None:
    env = os.environ.get("TRADELATTICE_WEB_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent / "web"
    return None


WEB_DIR = _find_web_dir()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="TradeLattice API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/records", response_model=UpsertResult)
def post_records(
    payload: Annotated[Any, Body()], session: Db
) -> UpsertResult:
    records = payload if isinstance(payload, list) else [payload]
    validate_records(records)
    count = upsert_records(session, records)
    session.commit()
    return UpsertResult(count=count, ids=[r["id"] for r in records])


@app.get("/records", response_model=list[RecordOut])
def list_records(
    session: Db,
    type: str | None = None,
    source: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict]:
    stmt = select(Record)
    if type:
        stmt = stmt.where(Record.type == type)
    if source:
        stmt = stmt.where(Record.source == source)
    if q:
        pattern = "%" + q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(
            func.lower(cast(Record.attributes, String)).like(pattern, escape="\\")
        )
    stmt = stmt.order_by(Record.id).limit(limit).offset(offset)
    return [r.to_dict() for r in session.scalars(stmt)]


@app.get("/records/{record_id:path}", response_model=RecordOut)
def get_record(record_id: str, session: Db) -> dict:
    row = session.get(Record, record_id)
    if row is None:
        raise HTTPException(404, "record not found")
    return row.to_dict()


def _normalize_hs(code: str) -> str:
    digits = code.replace(".", "").replace(" ", "")
    if not re.fullmatch(r"[0-9]{2,10}", digits):
        raise HTTPException(422, "hs_code must be 2-10 digits")
    return digits


def _best_tariff(session: Session, hs: str) -> Record:
    rows = session.scalars(select(Record).where(Record.type == "tariff_line")).all()
    best: Record | None = None
    for r in rows:
        code = str(r.attributes.get("hs_code", ""))
        if not code or not hs.startswith(code):
            continue
        if best is None:
            best = r
            continue
        bcode = str(best.attributes["hs_code"])
        if len(code) > len(bcode) or (
            len(code) == len(bcode) and r.observed_at > best.observed_at
        ):
            best = r
    if best is None:
        raise HTTPException(404, f"no tariff line matches {hs}")
    return best


@app.get("/tariff/{hs_code}", response_model=RecordOut)
def get_tariff(hs_code: str, session: Db) -> dict:
    return _best_tariff(session, _normalize_hs(hs_code)).to_dict()


def _fx_for(session: Session, currency: str, on: str) -> tuple[str, str]:
    """Return (rate string, rate date) for the latest fx_rate to CAD on or before `on`."""
    best: dict | None = None
    for r in session.scalars(select(Record).where(Record.type == "fx_rate")):
        a = r.attributes
        if a.get("currency") != currency or a.get("to") != "CAD" or str(a.get("on", "9999")) > on:
            continue
        if best is None or a["on"] > best["on"]:
            best = a
    if best is None:
        raise HTTPException(
            422,
            f"no CAD exchange rate on or before {on} for {currency}; load the boc_fx connector",
        )
    return str(best["rate"]), str(best["on"])


@app.post("/landed-cost", response_model=LandedCostOut)
def landed_cost(body: LandedCostIn, session: Db) -> LandedCostOut:
    hs = _normalize_hs(body.hs_code)
    origin = body.origin_country.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", origin):
        raise HTTPException(422, "origin_country must be a 2-letter country code")
    if body.shipment_date is None:
        ship = datetime.now(UTC).date().isoformat()
    else:
        try:
            ship = date.fromisoformat(body.shipment_date).isoformat()
        except ValueError as e:
            raise HTTPException(422, "shipment_date must be an ISO date (YYYY-MM-DD)") from e
    line = _best_tariff(session, hs)
    treatment = body.treatment or "MFN"
    rate_str = next(
        (r["rate"] for r in line.attributes.get("rates", []) if r.get("treatment") == treatment),
        None,
    )
    if rate_str is None:
        raise HTTPException(404, f"no rate for treatment {treatment!r} on {line.attributes['hs_code']}")
    amount = body.declared_value.amount
    cur = body.declared_value.currency.strip().upper()
    fx_rate: str | None = None
    fx_on: str | None = None
    fx_lines: list[str] = []
    if cur == "CAD":
        value_cad = amount
    else:
        fx_rate, fx_on = _fx_for(session, cur, ship)
        value_cad = amount * float(fx_rate)
        fx_lines.append(
            f"FX {cur}→CAD at {fx_rate} (BoC {fx_on}): {amount:,.2f} {cur} = {value_cad:,.2f} CAD"
        )
    try:
        node = parse_duty(rate_str)
        if isinstance(node, NotApplicable):
            raise DutyInputError("rate not applicable for this treatment")
        raw_duty, components = evaluate(node, value_cad, body.quantity, body.unit)
    except DutyInputError as e:
        raise HTTPException(422, str(e)) from e
    surtax_pct: str | None = None
    surtax_list: str | None = None
    raw_surtax = 0.0
    sur_lines: list[str] = []
    orders = [r.to_dict() for r in session.scalars(select(Record).where(Record.type == "surtax_order"))]
    hits = applicable(orders, hs, origin, ship)
    if hits:
        hit = hits[0]
        surtax_pct = str(hit["pct"])
        surtax_list = hit["list_id"]
        raw_surtax = value_cad * float(surtax_pct) / 100
        sur_lines.append(
            f"surtax {float(surtax_pct):g}% of {value_cad:,.2f} ({surtax_list}, origin {origin}) "
            f"= {raw_surtax:,.2f}"
        )
    duty = round(raw_duty, 2)
    surtax = round(raw_surtax, 2)
    vcad = round(value_cad, 2)
    pct = round(duty / value_cad * 100, 2) if value_cad else 0.0
    return LandedCostOut(
        hs_code=hs,
        matched_hs_code=str(line.attributes["hs_code"]),
        treatment=treatment,
        duty_rate=pct,
        duty=duty,
        total=round(value_cad + raw_duty + raw_surtax, 2),
        currency="CAD",
        declared_currency=cur,
        value_cad=vcad,
        fx_rate=fx_rate,
        fx_on=fx_on,
        surtax_pct=surtax_pct,
        surtax=surtax,
        surtax_list_id=surtax_list,
        shipment_date=ship,
        rate=rate_str,
        components=fx_lines + components + sur_lines,
        basis=basis(node),
    )


if WEB_DIR is not None and (WEB_DIR / "index.html").is_file():

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

else:

    @app.get("/", include_in_schema=False)
    def index_placeholder() -> PlainTextResponse:
        return PlainTextResponse("TradeLattice API is running. web/index.html not found.")


if WEB_DIR is not None and WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
