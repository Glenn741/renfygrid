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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vee-engine"))

import psycopg  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import PlainTextResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from approval_levels_cache import fetch_active_approval_levels  # noqa: E402
from auth_dependency import get_tenant_id  # noqa: E402
from billing_export import billing_ready_consumption, to_csv  # noqa: E402
from config import Settings  # noqa: E402
from control_order_gateway import request_control_order  # noqa: E402
from control_service import InsufficientRoleError, InvalidTransitionError, approve_order, list_control_orders  # noqa: E402
from dashboard import dashboard_overview  # noqa: E402
from get_consumption import get_consumption  # noqa: E402
from list_invalid_readings import list_invalid_readings  # noqa: E402
from observability import ingestion_metrics  # noqa: E402
from on_demand_reader import MeterNotReadableError, read_meter_now  # noqa: E402
from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import InvalidCredentialsError, authenticate  # noqa: E402

app = FastAPI(title="RenfyGrid Portal/API")
app.state.settings = Settings.from_env()
app.add_middleware(
    CORSMiddleware,
    allow_origins=app.state.settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def db_conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(app.state.settings.dsn, autocommit=True) as conn:
        yield conn


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class LoginRequest(BaseModel):
    tenant_id: str
    email: str
    password: str


@app.post("/auth/login")
def login(body: LoginRequest) -> dict:
    """F47: sin JWT previo -- por eso `tenant_id` viene explícito en el
    body (no hay todavía un mecanismo de "qué tenant es este email" sin que
    el cliente lo diga, ver docs/03-diseno.md SS9.1)."""
    with db_conn() as conn:
        try:
            identity = authenticate(conn, body.tenant_id, body.email, body.password)
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    token = create_token(
        {"tenant_id": body.tenant_id, "role": identity["role"], "user_id": identity["user_id"]},
        app.state.settings.jwt_secret,
    )
    return {"access_token": token, "token_type": "bearer"}


@app.get("/dashboard/overview")
def dashboard_overview_endpoint(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int = 3600) -> dict:
    with db_conn() as conn:
        return dashboard_overview(conn, tenant_id, stale_after_seconds)


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
    anomaly_status: str | None = None,
) -> list[dict]:
    with db_conn() as conn:
        rows = get_consumption(
            conn, tenant_id, meter_id=meter_id, period_start=period_start, period_end=period_end,
            anomaly_status=anomaly_status,
        )
        for row in rows:
            row["period"] = str(row["period"])
            row["created_at"] = row["created_at"].isoformat()
        return rows


@app.get("/vee/invalid-readings")
def invalid_readings_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_invalid_readings(conn, tenant_id)


@app.get("/control-orders")
def list_control_orders_endpoint(tenant_id: str = Depends(get_tenant_id), status: str | None = None) -> list[dict]:
    with db_conn() as conn:
        return list_control_orders(conn, tenant_id, status)


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


@app.get("/billing-export", response_class=PlainTextResponse)
def billing_export_endpoint(
    tenant_id: str = Depends(get_tenant_id), period_start: date | None = None, period_end: date | None = None
) -> str:
    """F25: CSV de consumo listo para facturar (excluye lo que está
    `under_review`) -- ver el docstring de `billing_export.py` sobre el
    alcance real de esto sin un CIS concreto todavía elegido."""
    if period_start is None or period_end is None:
        raise HTTPException(status_code=422, detail="period_start y period_end son obligatorios")
    with db_conn() as conn:
        rows = billing_ready_consumption(conn, tenant_id, period_start, period_end)
        return to_csv(rows)
