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
from datetime import date, datetime
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

from approval_levels_admin import create_approval_level, list_approval_levels  # noqa: E402
from approval_levels_cache import fetch_active_approval_levels  # noqa: E402
from auth_dependency import get_actor, get_tenant_id, requested_by_label  # noqa: E402
from billing_export import billing_ready_consumption, to_csv  # noqa: E402
from config import Settings  # noqa: E402
from consumption_anomaly_rules_admin import (  # noqa: E402
    create_consumption_anomaly_rule,
    deactivate_consumption_anomaly_rule,
    list_consumption_anomaly_rules,
)
from control_order_gateway import request_control_order  # noqa: E402
from control_service import (  # noqa: E402
    InsufficientRoleError,
    InvalidTransitionError,
    approve_order,
    get_control_order_detail,
    list_control_orders,
)
from dashboard import dashboard_overview  # noqa: E402
from fleet_aggregation import fleet_summary, gateway_summary  # noqa: E402
from get_consumption import get_consumption  # noqa: E402
from list_invalid_readings import list_invalid_readings  # noqa: E402
from manual_edit import ReadingNotFoundError, edit_reading  # noqa: E402
from vee_summary import list_estimated_readings, vee_summary  # noqa: E402
from observability import ingestion_metrics  # noqa: E402
from on_demand_reader import MeterNotReadableError, read_meter_now  # noqa: E402
from meter_ping import MeterNotReachableError, ping_meter  # noqa: E402
from protocol_mapping_admin import create_protocol_mapping, list_protocol_mappings  # noqa: E402
from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import InvalidCredentialsError, authenticate  # noqa: E402
from service_orders import list_service_orders  # noqa: E402
from vee_rules_admin import create_vee_rule, deactivate_vee_rule, list_vee_rules  # noqa: E402
from vee_rules_admin import RuleNotFoundError as VeeRuleNotFoundError  # noqa: E402
from consumption_anomaly_rules_admin import RuleNotFoundError as AnomalyRuleNotFoundError  # noqa: E402

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
        {
            "tenant_id": body.tenant_id,
            "role": identity["role"],
            "user_id": identity["user_id"],
            "email": body.email,  # Sprint C5: convencion real de origen (auth_dependency.requested_by_label)
        },
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


@app.get("/vee/summary")
def vee_summary_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return vee_summary(conn, tenant_id)


@app.get("/vee/estimated-readings")
def estimated_readings_endpoint(tenant_id: str = Depends(get_tenant_id), limit: int = 100) -> list[dict]:
    with db_conn() as conn:
        return list_estimated_readings(conn, tenant_id, limit)


class EditReadingRequest(BaseModel):
    meter_id: str
    channel: str
    timestamp: str
    new_value: float
    user_name: str
    justification: str


@app.post("/vee/invalid-readings/edit")
def edit_reading_endpoint(body: EditReadingRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """F51 (Nivel 3, Sprint C4): edición manual auditada (F18, Sprint 4)
    ahora accionable desde la UI, no solo desde código."""
    with db_conn() as conn:
        try:
            edit_reading(
                conn, tenant_id, body.meter_id, body.channel, datetime.fromisoformat(body.timestamp),
                body.new_value, body.user_name, body.justification,
            )
        except ReadingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "edited"}


@app.get("/control-orders")
def list_control_orders_endpoint(tenant_id: str = Depends(get_tenant_id), status: str | None = None) -> list[dict]:
    with db_conn() as conn:
        return list_control_orders(conn, tenant_id, status)


@app.get("/control-orders/{order_id}")
def get_control_order_detail_endpoint(order_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        detail = get_control_order_detail(conn, tenant_id, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return detail


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
    justification: str


@app.post("/control-orders", status_code=201)
def create_control_order(body: ControlOrderRequest, actor: dict = Depends(get_actor)) -> dict:
    # Sprint C5 (G1): requested_by ya no llega en el body -- sale del JWT,
    # nunca de algo que el cliente HTTP pueda escribir a mano.
    with db_conn() as conn:
        levels = fetch_active_approval_levels(conn, actor["tenant_id"])
        order_id = request_control_order(
            conn, actor["tenant_id"], body.meter_id, body.order_type,
            requested_by_label(actor), body.justification, levels,
        )
        return {"order_id": order_id}


@app.post("/control-orders/{order_id}/approve")
def approve_control_order(order_id: str, actor: dict = Depends(get_actor)) -> dict:
    # Sprint C5 (G1): approver_name/approver_role ya no llegan en el body --
    # un aprobador no puede elegir su propio rol en la peticion.
    with db_conn() as conn:
        levels = fetch_active_approval_levels(conn, actor["tenant_id"])
        try:
            approve_order(conn, actor["tenant_id"], order_id, actor["email"], actor["role"], levels)
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InsufficientRoleError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"order_id": order_id, "status": "approved"}


class ReadNowRequest(BaseModel):
    channel: str


@app.post("/meters/{meter_id}/reads")
def read_meter_now_endpoint(meter_id: str, body: ReadNowRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            reading = read_meter_now(conn, actor["tenant_id"], meter_id, body.channel, requested_by=requested_by_label(actor))
        except MeterNotReadableError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row = reading.as_row()
        row["timestamp"] = row["timestamp"].isoformat()
        return row


@app.post("/meters/{meter_id}/ping")
def ping_meter_endpoint(meter_id: str, actor: dict = Depends(get_actor)) -> dict:
    """F07 (Sprint C5, `06-benchmark-e2e-y-brechas.md` G2): "esta vivo el
    medidor" sin leer ningun registro -- asociacion DLMS y listo. Es el
    comando mas liviano del set estandar (connect/disconnect/ping/lectura,
    ver el mismo doc SS2)."""
    with db_conn() as conn:
        try:
            ok = ping_meter(conn, actor["tenant_id"], meter_id, requested_by=requested_by_label(actor))
        except MeterNotReachableError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"meter_id": meter_id, "reachable": ok}


@app.get("/integrations/service-orders")
def service_orders_endpoint(tenant_id: str = Depends(get_tenant_id), limit: int = 50) -> list[dict]:
    """Sprint C5 (G3): panel unificado de "Service Orders" -- une
    `control_order` (suspension/reconexion/desconexion) con las lecturas
    bajo demanda y los pings (auditados en `meter_event` desde Sprint 9),
    sea que los haya pedido el CIS externo, un operador del Portal, o el
    propio sistema (auto-aprobacion)."""
    with db_conn() as conn:
        return list_service_orders(conn, tenant_id, limit)


@app.get("/meters/fleet-summary")
def fleet_summary_endpoint(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int = 3600) -> list[dict]:
    """Sprint C7 (G4): flota agrupada por marca/modelo, con % de medidores
    activos que de verdad estan reportando -- no solo el conteo total."""
    with db_conn() as conn:
        return fleet_summary(conn, tenant_id, stale_after_seconds)


@app.get("/gateways")
def gateways_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    """Sprint C7 (G5): la capa de agregacion -- un concentrador por fila,
    con cuantos medidores y de que marcas agrupa, y el estado real de su
    ultimo ciclo de polling."""
    with db_conn() as conn:
        return gateway_summary(conn, tenant_id)


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


# ══════════════════════════════════════════════════════════════════════════
# Configuración -- editor de reglas (F50, Sprint C3). Transversal, no una
# etapa del pipeline (docs/03-diseno.md SS9.3).
# ══════════════════════════════════════════════════════════════════════════


class VeeRuleRequest(BaseModel):
    type: str
    params: dict
    priority: int = 100


@app.get("/vee-rules")
def list_vee_rules_endpoint(tenant_id: str = Depends(get_tenant_id), active_only: bool = True) -> list[dict]:
    with db_conn() as conn:
        return list_vee_rules(conn, tenant_id, active_only)


@app.post("/vee-rules", status_code=201)
def create_vee_rule_endpoint(body: VeeRuleRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        rule_id = create_vee_rule(conn, tenant_id, body.type, body.params, body.priority)
        return {"id": rule_id}


@app.patch("/vee-rules/{rule_id}")
def deactivate_vee_rule_endpoint(rule_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            deactivate_vee_rule(conn, tenant_id, rule_id)
        except VeeRuleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule_id, "is_active": False}


class ConsumptionAnomalyRuleRequest(BaseModel):
    condition: dict
    action: str


@app.get("/consumption-anomaly-rules")
def list_consumption_anomaly_rules_endpoint(
    tenant_id: str = Depends(get_tenant_id), active_only: bool = True
) -> list[dict]:
    with db_conn() as conn:
        return list_consumption_anomaly_rules(conn, tenant_id, active_only)


@app.post("/consumption-anomaly-rules", status_code=201)
def create_consumption_anomaly_rule_endpoint(
    body: ConsumptionAnomalyRuleRequest, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    with db_conn() as conn:
        rule_id = create_consumption_anomaly_rule(conn, tenant_id, body.condition, body.action)
        return {"id": rule_id}


@app.patch("/consumption-anomaly-rules/{rule_id}")
def deactivate_consumption_anomaly_rule_endpoint(rule_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            deactivate_consumption_anomaly_rule(conn, tenant_id, rule_id)
        except AnomalyRuleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": rule_id, "is_active": False}


class ApprovalLevelRequest(BaseModel):
    order_type: str
    requires_human_approval: bool
    min_required_role: str


@app.get("/control-approval-levels")
def list_approval_levels_endpoint(tenant_id: str = Depends(get_tenant_id), active_only: bool = True) -> list[dict]:
    with db_conn() as conn:
        return list_approval_levels(conn, tenant_id, active_only)


@app.post("/control-approval-levels", status_code=201)
def create_approval_level_endpoint(body: ApprovalLevelRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        level_id = create_approval_level(
            conn, tenant_id, body.order_type, body.requires_human_approval, body.min_required_role
        )
        return {"id": level_id}


class ProtocolMappingRequest(BaseModel):
    brand: str
    model: str
    protocol: str
    obis_mapping: dict
    security_mode: str | None = None


@app.get("/obis-mappings")
def list_protocol_mappings_endpoint(tenant_id: str = Depends(get_tenant_id), active_only: bool = True) -> list[dict]:
    with db_conn() as conn:
        return list_protocol_mappings(conn, tenant_id, active_only)


@app.post("/obis-mappings", status_code=201)
def create_protocol_mapping_endpoint(body: ProtocolMappingRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        mapping_id = create_protocol_mapping(
            conn, tenant_id, body.brand, body.model, body.protocol, body.obis_mapping, body.security_mode
        )
        return {"id": mapping_id}
