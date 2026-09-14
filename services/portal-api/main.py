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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-balance"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-model"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))

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
from account_protection import bulk_mark_protection, list_protected_meters, mark_protection  # noqa: E402
from account_protection import MeterNotFoundError as ProtectionMeterNotFoundError  # noqa: E402
from control_order_gateway import request_control_order  # noqa: E402
from control_service import (  # noqa: E402
    InsufficientRoleError,
    InvalidTransitionError,
    ProtectedAccountError,
    approve_order,
    control_summary,
    get_control_order_detail,
    list_control_orders,
)
from dashboard import dashboard_overview  # noqa: E402
from fleet_aggregation import (  # noqa: E402
    event_summary,
    fleet_summary,
    gateway_summary,
    list_meter_events,
    list_retry_queue,
)
from consumption_summary import ConsumptionNotFoundError, consumption_summary, list_consumption_orders, resolve_anomaly  # noqa: E402
from get_consumption import get_consumption  # noqa: E402
from list_invalid_readings import list_invalid_readings  # noqa: E402
from manual_edit import ReadingNotFoundError, edit_reading  # noqa: E402
from vee_summary import list_edits, list_estimated_readings, vee_summary  # noqa: E402
from observability import ingestion_metrics  # noqa: E402
from on_demand_reader import MeterNotReadableError, read_meter_now  # noqa: E402
from meter_ping import MeterNotReachableError, ping_meter  # noqa: E402
from protocol_mapping_admin import create_protocol_mapping, list_protocol_mappings  # noqa: E402
from balance_service import (  # noqa: E402
    InvalidMethodError,
    MissingRealLossesError,
    ZoneNotFoundError,
    balance_summary,
    list_balances,
    list_zones,
    register_zone,
    submit_balance,
    zones_geojson,
)
from model_service import (  # noqa: E402
    ModelNotFoundError,
    ModelNotLinkedToZoneError,
    NoBalanceForCalibrationError,
    list_models,
    list_simulation_results,
    model_geojson,
    register_model,
    register_model_from_twin,
    run_and_store_simulation,
)
from network_model_engine import CalibrationInputError, InvalidModelError, SimulationFailedError  # noqa: E402
from twin_export import (  # noqa: E402
    AmbiguousPipeConnectivityError,
    MissingGeometryError,
    MissingTankHeadError,
    NoSourceAssetError,
)
from asset_service import (  # noqa: E402
    AssetNotFoundError,
    InvalidAssetStatusError,
    InvalidAssetTypeError,
    assets_geojson,
    connect_assets,
    get_asset_detail,
    list_assets,
    register_asset,
    update_asset_status,
)
from order_service import (  # noqa: E402
    AnomalyNotConfirmedError,
    BayforceIntegrationError,
    BayforceNotConfiguredError,
    InvalidOrderSourceError,
    InvalidOrderTypeError,
    InvalidStatusTransitionError,
    close_from_webhook,
    generate_order,
    get_order_detail,
    list_orders,
    send_to_bayforce,
)
from order_service import AssetNotFoundError as MaintenanceAssetNotFoundError  # noqa: E402
from order_service import OrderNotFoundError as MaintenanceOrderNotFoundError  # noqa: E402
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


@app.get("/consumption/summary")
def consumption_summary_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return consumption_summary(conn, tenant_id)


@app.get("/consumption/orders")
def consumption_orders_endpoint(tenant_id: str = Depends(get_tenant_id), limit: int = 100) -> list[dict]:
    """Sprint C11-6: feed real de las ordenes de relectura/inspeccion
    (F23) -- antes solo visibles con SQL directo."""
    with db_conn() as conn:
        return list_consumption_orders(conn, tenant_id, limit)


class ResolveAnomalyRequest(BaseModel):
    meter_id: str
    period_start: date
    period_end: date
    notes: str


@app.post("/consumption/resolve")
def resolve_anomaly_endpoint(body: ResolveAnomalyRequest, actor: dict = Depends(get_actor)) -> dict:
    """Sprint C11-6: cierra una anomalia investigada -- `anomaly_status`
    existia en el esquema desde Sprint 0, nunca se escribia `resolved`."""
    with db_conn() as conn:
        try:
            resolve_anomaly(
                conn, actor["tenant_id"], body.meter_id, body.period_start, body.period_end,
                actor["email"], body.notes,
            )
        except ConsumptionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "resolved"}


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


@app.get("/vee/edits")
def vee_edits_endpoint(tenant_id: str = Depends(get_tenant_id), limit: int = 100) -> list[dict]:
    with db_conn() as conn:
        return list_edits(conn, tenant_id, limit)


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


@app.get("/control-orders/summary")
def control_summary_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Sprint C11-5: registrado ANTES de `/control-orders/{order_id}` a
    proposito -- si no, FastAPI trataria "summary" como un `order_id`."""
    with db_conn() as conn:
        return control_summary(conn, tenant_id)


@app.get("/meters/protected")
def list_protected_meters_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_protected_meters(conn, tenant_id)


class MeterProtectionRequest(BaseModel):
    protected: bool
    reason: str | None = None


@app.post("/meters/{meter_id}/protection")
def mark_meter_protection_endpoint(
    meter_id: str, body: MeterProtectionRequest, actor: dict = Depends(get_actor)
) -> dict:
    with db_conn() as conn:
        try:
            mark_protection(conn, actor["tenant_id"], meter_id, body.protected, body.reason, actor["email"])
        except ProtectionMeterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"meter_id": meter_id, "protected": body.protected}


class BulkMeterProtectionRequest(BaseModel):
    account_numbers: list[str]
    reason: str


@app.post("/meters/protection/bulk")
def bulk_mark_meter_protection_endpoint(body: BulkMeterProtectionRequest, actor: dict = Depends(get_actor)) -> dict:
    """Carga masiva (ej. un archivo de cuentas excluidas de corte, Sprint
    C11-5) -- por `account_number`, no UUID interno."""
    with db_conn() as conn:
        return bulk_mark_protection(conn, actor["tenant_id"], body.account_numbers, body.reason, actor["email"])


@app.get("/control-orders/{order_id}")
def get_control_order_detail_endpoint(order_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        detail = get_control_order_detail(conn, tenant_id, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return detail


class ControlOrderRequest(BaseModel):
    meter_id: str
    order_type: str
    justification: str
    override_protection: bool = False
    override_justification: str | None = None


@app.post("/control-orders", status_code=201)
def create_control_order(body: ControlOrderRequest, actor: dict = Depends(get_actor)) -> dict:
    # Sprint C5 (G1): requested_by ya no llega en el body -- sale del JWT,
    # nunca de algo que el cliente HTTP pueda escribir a mano.
    with db_conn() as conn:
        levels = fetch_active_approval_levels(conn, actor["tenant_id"])
        try:
            order_id = request_control_order(
                conn, actor["tenant_id"], body.meter_id, body.order_type,
                requested_by_label(actor), body.justification, levels,
                body.override_protection, body.override_justification,
            )
        except ProtectedAccountError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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


@app.get("/meters/event-summary")
def event_summary_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Sprint C11-4: KPIs de alarmas (F05) + salud de comunicacion (F09) +
    cuantos medidores estan en la cola de reintentos ahora mismo (F08)."""
    with db_conn() as conn:
        return event_summary(conn, tenant_id)


@app.get("/meters/events")
def meter_events_endpoint(
    tenant_id: str = Depends(get_tenant_id), event_type: str | None = None, limit: int = 100
) -> list[dict]:
    """Sprint C11-4: feed real de `meter_event` -- alarmas del medidor
    (F05) y auditoria de comunicacion (F09), antes invisibles en el Portal."""
    with db_conn() as conn:
        return list_meter_events(conn, tenant_id, event_type, limit)


@app.get("/meters/retry-queue")
def retry_queue_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    """Sprint C11-4: estado real de la cola de reintentos (F08, Sprint C11)
    -- que medidores estan en backoff ahora mismo y por que."""
    with db_conn() as conn:
        return list_retry_queue(conn, tenant_id)


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


# ══════════════════════════════════════════════════════════════════════════
# Track B -- Balance de Red (Sprint B1, docs/07-track-b-alcance-funcional.md):
# venta modular, sin depender de un medidor RenfyGrid (data_source='external').
# ══════════════════════════════════════════════════════════════════════════


class NetworkZoneRequest(BaseModel):
    name: str
    type: str
    data_source: str = "external"
    parent_zone_id: str | None = None
    network_length_km: float | None = None
    num_connections: int | None = None
    avg_pressure_mca: float | None = None
    avg_service_connection_length_km: float | None = None
    nrw_threshold_pct: float | None = None
    centroid_lat: float | None = None
    centroid_lon: float | None = None


@app.post("/network-zones", status_code=201)
def create_network_zone_endpoint(body: NetworkZoneRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        zone_id = register_zone(
            conn, tenant_id, body.name, body.type, body.data_source, body.parent_zone_id,
            body.network_length_km, body.num_connections, body.avg_pressure_mca,
            body.avg_service_connection_length_km, body.nrw_threshold_pct,
            body.centroid_lat, body.centroid_lon,
        )
        return {"zone_id": zone_id}


@app.get("/network-balances/summary")
def network_balance_summary_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return balance_summary(conn, tenant_id)


@app.get("/network-zones/geojson")
def network_zones_geojson_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """GeoJSON real de las zonas -- Track B, modulo de georreferenciacion
    (`docs/07-track-b-alcance-funcional.md` SS7)."""
    with db_conn() as conn:
        return zones_geojson(conn, tenant_id)


@app.get("/network-zones")
def list_network_zones_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_zones(conn, tenant_id)


class NetworkBalanceRequest(BaseModel):
    period_start: date
    period_end: date
    method: str
    system_input_volume: float
    billed_metered_consumption: float = 0.0
    billed_unbilled_consumption: float = 0.0
    unbilled_authorized_consumption: float = 0.0
    apparent_losses: float = 0.0
    # Sprint B2: opcional para 'top_down' (se calcula como residual real si
    # se omite, AWWA M36); obligatorio para 'bottom_up' (medido/estimado
    # directo, nunca como residual -- 422 si falta).
    real_losses: float | None = None


@app.post("/network-zones/{zone_id}/balance", status_code=201)
def submit_network_balance_endpoint(
    zone_id: str, body: NetworkBalanceRequest, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Ingesta de un periodo de balance -- propia o externa (CIS/HES de
    terceros, `01-planteamiento.md` SS3). Calcula NRW/ILI al insertar."""
    with db_conn() as conn:
        try:
            return submit_balance(
                conn, tenant_id, zone_id, body.period_start, body.period_end, body.method,
                body.system_input_volume, body.billed_metered_consumption, body.billed_unbilled_consumption,
                body.unbilled_authorized_consumption, body.apparent_losses, body.real_losses,
            )
        except ZoneNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (InvalidMethodError, MissingRealLossesError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/network-balances")
def list_network_balances_endpoint(tenant_id: str = Depends(get_tenant_id), zone_id: str | None = None) -> list[dict]:
    with db_conn() as conn:
        return list_balances(conn, tenant_id, zone_id)


# ══════════════════════════════════════════════════════════════════════════
# Track B, Sprint B3 -- Modelado Hidraulico (WNTR/EPANET real)
# ══════════════════════════════════════════════════════════════════════════


class NetworkModelRequest(BaseModel):
    name: str
    inp_content: str
    zone_id: str | None = None


@app.post("/network-models", status_code=201)
def create_network_model_endpoint(body: NetworkModelRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return register_model(
                conn, tenant_id, body.name, body.inp_content,
                app.state.settings.network_model_storage_dir, body.zone_id,
            )
        except InvalidModelError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/network-models")
def list_network_models_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_models(conn, tenant_id)


class SimulateRequest(BaseModel):
    scenario: str = "base"
    calibrate: bool = False


@app.post("/network-models/{model_id}/simulate", status_code=201)
def simulate_network_model_endpoint(
    model_id: str, body: SimulateRequest, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Corre una simulacion EPANET real (WNTR) sobre el modelo cargado --
    `404` si el modelo no existe, `422` si el `.inp` guardado no es valido
    o la simulacion no converge (nunca un 200 con un resultado fabricado).

    `calibrate=true` (Sprint B4, vinculo Modelo<->Balance): usa
    `network_balance.real_losses` real de la zona vinculada al modelo como
    insumo de calibracion -- `422` si el modelo no esta vinculado a una
    zona o esa zona todavia no tiene ningun balance (nunca se calibra con
    un numero de ejemplo)."""
    with db_conn() as conn:
        try:
            return run_and_store_simulation(conn, tenant_id, model_id, body.scenario, body.calibrate)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (InvalidModelError, SimulationFailedError, ModelNotLinkedToZoneError,
                NoBalanceForCalibrationError, CalibrationInputError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/network-models/{model_id}/simulations")
def list_network_model_simulations_endpoint(model_id: str, tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_simulation_results(conn, tenant_id, model_id)


@app.get("/network-models/{model_id}/geojson")
def network_model_geojson_endpoint(model_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """GeoJSON real del modelo -- Track B, modulo de georreferenciacion
    (`docs/07-track-b-alcance-funcional.md` SS7), mismo patron de "backend
    expone GeoJSON" que `Mapa de Deuda` de RenFlow."""
    with db_conn() as conn:
        try:
            return model_geojson(conn, tenant_id, model_id)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidModelError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# Track B, Sprint B5 -- Gemelo Digital (inventario de activos + conectividad)
# ══════════════════════════════════════════════════════════════════════════


class NetworkAssetRequest(BaseModel):
    type: str
    zone_id: str | None = None
    attributes: dict = {}
    geometry: dict | None = None
    status: str = "operational"


@app.post("/network-assets", status_code=201)
def create_network_asset_endpoint(body: NetworkAssetRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return register_asset(conn, tenant_id, body.type, body.zone_id, body.attributes, body.geometry, body.status)
        except (InvalidAssetTypeError, InvalidAssetStatusError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/network-assets/geojson")
def network_assets_geojson_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """GeoJSON real de los activos -- Track B, modulo de georreferenciacion
    (`docs/07-track-b-alcance-funcional.md` SS7)."""
    with db_conn() as conn:
        return assets_geojson(conn, tenant_id)


@app.get("/network-assets")
def list_network_assets_endpoint(
    tenant_id: str = Depends(get_tenant_id), zone_id: str | None = None, asset_type: str | None = None
) -> list[dict]:
    with db_conn() as conn:
        return list_assets(conn, tenant_id, zone_id, asset_type)


@app.get("/network-assets/{asset_id}")
def get_network_asset_endpoint(asset_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """El activo + su conectividad real (Sprint B5: "Un activo cargado via
    API queda visible con su conectividad")."""
    with db_conn() as conn:
        try:
            return get_asset_detail(conn, tenant_id, asset_id)
        except AssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class AssetStatusRequest(BaseModel):
    status: str


@app.patch("/network-assets/{asset_id}/status")
def update_network_asset_status_endpoint(
    asset_id: str, body: AssetStatusRequest, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    with db_conn() as conn:
        try:
            return update_asset_status(conn, tenant_id, asset_id, body.status)
        except AssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidAssetStatusError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class AssetConnectivityRequest(BaseModel):
    source_asset_id: str
    target_asset_id: str
    connection_type: str


@app.post("/asset-connectivity", status_code=201)
def create_asset_connectivity_endpoint(body: AssetConnectivityRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Conecta dos activos reales -- `404` si alguno no existe PARA ESTE
    TENANT (verificacion explicita vía `network_asset`, `asset_connectivity`
    no tiene RLS propio -- ver `asset_service.py`)."""
    with db_conn() as conn:
        try:
            return connect_assets(conn, tenant_id, body.source_asset_id, body.target_asset_id, body.connection_type)
        except AssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# Track B, Sprint B6 -- generar un modelo EPANET desde el Gemelo Digital
# ══════════════════════════════════════════════════════════════════════════


class GenerateModelRequest(BaseModel):
    name: str


@app.post("/network-zones/{zone_id}/generate-model", status_code=201)
def generate_network_model_from_twin_endpoint(
    zone_id: str, body: GenerateModelRequest, tenant_id: str = Depends(get_tenant_id)
) -> dict:
    """Genera un `.inp` real desde los activos/conectividad de esa zona y
    lo registra por el mismo camino que un `.inp` subido a mano -- `422`
    con el motivo REAL si falta una fuente (`tank`), geometría, o la
    topología de un activo `pipe` es ambigua (nunca un modelo fabricado
    "a medias")."""
    with db_conn() as conn:
        try:
            return register_model_from_twin(conn, tenant_id, zone_id, body.name, app.state.settings.network_model_storage_dir)
        except (NoSourceAssetError, MissingGeometryError, MissingTankHeadError, AmbiguousPipeConnectivityError, InvalidModelError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# Track B, Sprint B7 -- Gestion de Mantenimiento + integracion BayForce
# ══════════════════════════════════════════════════════════════════════════


class GenerateOrderRequest(BaseModel):
    asset_id: str
    type: str
    source: str
    reason: str | None = None


@app.post("/maintenance-orders", status_code=201)
def create_maintenance_order_endpoint(body: GenerateOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Genera una orden real -- `422` si el tipo/fuente no son validos o
    la anomalia real que justificaria una fuente automatica no se cumple
    ahora mismo (`AnomalyNotConfirmedError`); `404` si el activo no
    existe."""
    with db_conn() as conn:
        try:
            return generate_order(conn, tenant_id, body.asset_id, body.type, body.source, body.reason)
        except MaintenanceAssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (InvalidOrderTypeError, InvalidOrderSourceError, AnomalyNotConfirmedError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/maintenance-orders")
def list_maintenance_orders_endpoint(
    tenant_id: str = Depends(get_tenant_id), status: str | None = None, asset_id: str | None = None
) -> list[dict]:
    with db_conn() as conn:
        return list_orders(conn, tenant_id, status, asset_id)


@app.get("/maintenance-orders/{order_id}")
def get_maintenance_order_endpoint(order_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return get_order_detail(conn, tenant_id, order_id)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/maintenance-orders/{order_id}/send-to-bayforce")
def send_maintenance_order_to_bayforce_endpoint(order_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Envia la orden real a BayForce (HTTP real al webhook configurado) --
    `422` si BayForce no esta configurado para este tenant, si la orden no
    esta en `generated`, o si BayForce no responde/responde algo
    invalido (nunca un 200 con un envio fabricado); `404` si la orden no
    existe."""
    with db_conn() as conn:
        try:
            return send_to_bayforce(conn, tenant_id, order_id, app.state.settings.bayforce_webhook_url)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (BayforceNotConfiguredError, InvalidStatusTransitionError, BayforceIntegrationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class BayforceWebhookRequest(BaseModel):
    bayforce_order_ref: str
    status: str


@app.post("/maintenance-orders/bayforce-webhook")
def bayforce_webhook_endpoint(body: BayforceWebhookRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Webhook real de cierre -- BayForce (o el modulo de integraciones que
    ya recibe sus eventos, ver `core/renflow/bayforce/main.py` `/wfms/events`)
    llama aca para avanzar el estado real de la orden. Mismo mecanismo de
    autenticacion que ya usa el portal para un CIS externo (JWT del
    tenant) -- no se inventa un esquema de firma nuevo para esto. `422` si
    la transicion de estado pedida no es valida desde el estado actual;
    `404` si no existe ninguna orden con ese `bayforce_order_ref`."""
    with db_conn() as conn:
        try:
            return close_from_webhook(conn, tenant_id, body.bayforce_order_ref, body.status)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
