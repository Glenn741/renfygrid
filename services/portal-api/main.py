"""Portal/API pública multi-tenant (F33, Sprint 8) -- primer servicio HTTP
real de RenfyGrid. Cada endpoint exige un JWT valido (F32, Sprint 0) y usa
el `tenant_id` del token -- nunca uno pasado por el cliente -- para fijar
`tenant_scope` en cada consulta, de modo que RLS (F31, Sprint 0) aisle de
verdad entre tenants.

"Medidores, consumos, eventos, solicitud de control" (`04-plan-sprints.md`
§4) -- el endpoint de control NO llama a `services/control` directo: pasa
por `services/consumption/control_order_gateway.py`, honrando la regla de
`02-arquitectura-general.md` SS6 punto 4 ("el módulo SCR únicamente habla
con los adaptadores HES... se llega a él a través de Gestión de Consumos").

Arranca con:
    uvicorn main:app --host 0.0.0.0 --port 8000
(con RENFYGRID_DSN / RENFYGRID_JWT_SECRET / RENFYGRID_ORDER_SIGNING_SECRET
ya en el entorno -- ver config.py, nunca un valor fijo en código).
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "consumption"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))

import psycopg  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from approval_levels_cache import fetch_active_approval_levels  # noqa: E402
from auth_dependency import get_tenant_id  # noqa: E402
from config import Settings  # noqa: E402
from control_order_gateway import request_control_order  # noqa: E402
from control_service import InsufficientRoleError, InvalidTransitionError, approve_order  # noqa: E402
from get_consumption import get_consumption  # noqa: E402
from observability import ingestion_metrics  # noqa: E402
from on_demand_reader import MeterNotReadableError, read_meter_now  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

app = FastAPI(title="RenfyGrid Portal/API")
app.state.settings = Settings.from_env()


@contextmanager
def db_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(app.state.settings.dsn, autocommit=True) as conn:
        yield conn


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/meters")
def list_meters(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, account_number, serial_number, brand, model, protocol, status "
                        "FROM meter ORDER BY account_number"
                    )
                    return [
                        {
                            "id": str(row[0]), "account_number": row[1], "serial_number": row[2],
                            "brand": row[3], "model": row[4], "protocol": row[5], "status": row[6],
                        }
                        for row in cur.fetchall()
                    ]


@app.get("/consumption")
def consumption_endpoint(
    tenant_id: str = Depends(get_tenant_id),
    meter_id: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    with db_conn() as conn:
        rows = get_consumption(conn, tenant_id, meter_id=meter_id, period_start=period_start, period_end=period_end)
        for row in rows:
            row["period"] = str(row["period"])
            row["created_at"] = row["created_at"].isoformat()
        return rows


@app.get("/events")
def list_events(tenant_id: str = Depends(get_tenant_id), meter_id: str | None = None) -> list[dict]:
    with db_conn() as conn:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    if meter_id:
                        cur.execute(
                            "SELECT id, meter_id, type, \"timestamp\", severity FROM meter_event "
                            "WHERE meter_id = %s ORDER BY \"timestamp\" DESC",
                            (meter_id,),
                        )
                    else:
                        cur.execute(
                            "SELECT id, meter_id, type, \"timestamp\", severity FROM meter_event "
                            "ORDER BY \"timestamp\" DESC"
                        )
                    return [
                        {
                            "id": str(row[0]), "meter_id": str(row[1]), "type": row[2],
                            "timestamp": row[3].isoformat(), "severity": row[4],
                        }
                        for row in cur.fetchall()
                    ]


class ControlOrderRequest(BaseModel):
    meter_id: str
    order_type: str
    requested_by: str
    justification: str


@app.post("/control-orders", status_code=201)
def create_control_order(body: ControlOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        levels = fetch_active_approval_levels(conn, tenant_id)
        order_id = request_control_order(
            conn, tenant_id, body.meter_id, body.order_type, body.requested_by, body.justification, levels
        )
        return {"order_id": order_id}


class ApproveOrderRequest(BaseModel):
    approver_name: str
    approver_role: str


@app.post("/control-orders/{order_id}/approve")
def approve_control_order(order_id: str, body: ApproveOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        levels = fetch_active_approval_levels(conn, tenant_id)
        try:
            approve_order(conn, tenant_id, order_id, body.approver_name, body.approver_role, levels)
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InsufficientRoleError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"order_id": order_id, "status": "approved"}


class ReadNowRequest(BaseModel):
    channel: str


@app.post("/meters/{meter_id}/reads")
def read_meter_now_endpoint(meter_id: str, body: ReadNowRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            reading = read_meter_now(conn, tenant_id, meter_id, body.channel)
        except MeterNotReadableError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row = reading.as_row()
        row["timestamp"] = row["timestamp"].isoformat()
        return row


@app.get("/observability/ingestion")
def ingestion_observability(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int = 3600) -> dict:
    with db_conn() as conn:
        return ingestion_metrics(conn, tenant_id, stale_after_seconds)
