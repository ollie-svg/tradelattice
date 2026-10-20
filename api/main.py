"""OpenGoods API."""
from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from .db import get_session, init_db
from .models import Record
from .schemas import LandedCostIn, LandedCostOut, RecordOut, UpsertResult
from .store import upsert_records
from .validation import validate_records

Db = Annotated[Session, Depends(get_session)]
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="OpenGoods API", version="0.1.0", lifespan=lifespan)


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


def parse_rate(rate: str) -> float:
    s = rate.strip()
    if s.lower() == "free":
        return 0.0
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        return float(m.group(1))
    raise HTTPException(422, "specific rates not supported in v0.1")


@app.post("/landed-cost", response_model=LandedCostOut)
def landed_cost(body: LandedCostIn, session: Db) -> LandedCostOut:
    hs = _normalize_hs(body.hs_code)
    line = _best_tariff(session, hs)
    treatment = body.treatment or "MFN"
    rate_str = next(
        (r["rate"] for r in line.attributes.get("rates", []) if r.get("treatment") == treatment),
        None,
    )
    if rate_str is None:
        raise HTTPException(404, f"no rate for treatment {treatment!r} on {line.attributes['hs_code']}")
    pct = parse_rate(rate_str)
    amount = body.declared_value.amount
    duty = round(amount * pct / 100, 2)
    return LandedCostOut(
        hs_code=hs,
        matched_hs_code=str(line.attributes["hs_code"]),
        treatment=treatment,
        duty_rate=pct,
        duty=duty,
        total=round(amount + duty, 2),
        currency=body.declared_value.currency,
    )


if (WEB_DIR / "index.html").is_file():

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

else:

    @app.get("/", include_in_schema=False)
    def index_placeholder() -> PlainTextResponse:
        return PlainTextResponse("OpenGoods API is running. web/index.html not found.")


if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
