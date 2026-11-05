"""TradeLattice API."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from . import jurisdictions
from .db import get_session, init_db
from .landed import NotComputable, Prohibited, RecordSet, best_tariff, compute, normalize_hs
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


def _records(session: Session, type_: str) -> list[dict]:
    return [r.to_dict() for r in session.scalars(select(Record).where(Record.type == type_))]


def _not_computable(e: NotComputable) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"detail": e.detail, "reason": e.reason})


@app.get("/tariff/{hs_code}", response_model=RecordOut)
def get_tariff(hs_code: str, session: Db) -> dict | JSONResponse:
    try:
        return best_tariff(_records(session, "tariff_line"), normalize_hs(hs_code))
    except NotComputable as e:
        return _not_computable(e)


@app.post("/landed-cost", response_model=LandedCostOut)
def landed_cost(body: LandedCostIn, session: Db) -> LandedCostOut | JSONResponse:
    """Thin wrapper: load records, call the pure `compute()`, map its exceptions (ADR 0005)."""
    jcode = body.jurisdiction.strip().upper()
    try:
        jur = jurisdictions.get(jcode)
    except KeyError as e:
        raise HTTPException(422, f"unknown jurisdiction {jcode!r}") from e
    records = RecordSet(
        tariff_lines=_records(session, "tariff_line"),
        fx_rates=_records(session, "fx_rate"),
        surtax_orders=_records(session, "surtax_order"),
        prohibitions=_records(session, "prohibition"),
    )
    try:
        return compute(body, records, jur, datetime.now(UTC).date())
    except Prohibited as e:
        return JSONResponse(status_code=409, content=e.payload)
    except NotComputable as e:
        return _not_computable(e)


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
