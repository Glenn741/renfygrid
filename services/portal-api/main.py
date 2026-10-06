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
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
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
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "community"))

import psycopg  # noqa: E402
from fastapi import Depends, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, PlainTextResponse  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from approval_levels_admin import create_approval_level, list_approval_levels  # noqa: E402
from approval_levels_cache import fetch_active_approval_levels  # noqa: E402
from auth_dependency import get_actor, get_session_claims, get_tenant_id, requested_by_label  # noqa: E402
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
from tenant_settings import (  # noqa: E402
    get_hes_settings,
    get_meter_stale_after_seconds,
    get_session_ttl_seconds,
    get_timezone,
    set_meter_stale_after_seconds,
    set_session_ttl_seconds,
    set_timezone,
    tenant_today,
    TimezoneNotConfiguredError,
)
from meter_geo import consumption_distribution, exception_rate_by_brand, meters_geojson, sector_summary  # noqa: E402
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
    CrewNotFoundError,
    FailureCodeNotFoundError,
    InvalidCloseStatusError,
    InvalidOrderSourceError,
    InvalidOrderTypeError,
    InvalidPriorityError,
    InvalidStatusTransitionError,
    assign_order,
    close_from_webhook,
    close_order,
    create_crew,
    create_failure_code,
    create_pm_plan,
    deactivate_crew,
    deactivate_failure_code,
    generate_due_pm_orders,
    generate_order,
    get_order_detail,
    list_crews,
    list_failure_codes,
    list_orders,
    list_pm_plans,
    list_sla_policies,
    maintenance_kpis,
    schedule_order,
    send_to_bayforce,
    set_sla_policy,
    start_order,
    InvalidCommunityWorkError,
    InvalidPmPlanError,
    MaintenanceEventError,
    list_maintenance_events,
    maintenance_event_types,
    maintenance_steps,
    record_maintenance_event,
)
from order_service import AssetNotFoundError as MaintenanceAssetNotFoundError  # noqa: E402
from order_service import OrderNotFoundError as MaintenanceOrderNotFoundError  # noqa: E402
from pack_engine import InvalidAnswersError, InvalidInstrumentationError  # noqa: E402
from pack_service import (  # noqa: E402
    AmbiguousRuleError,
    FindingNotFoundError,
    FollowUpNotFoundError,
    InvalidFindingError,
    ProductNotFoundError,
    PackNotFoundError,
    RuleNotFoundError,
    RunNotFoundError,
    TemplateNotAvailableError,
    active_pack_ids,
    add_follow_up_item,
    adopt_pack,
    create_follow_up_cycle,
    follow_up,
    create_finding,
    evaluate_parameter,
    get_checklist_run,
    get_instrumentation,
    latest_traffic_light,
    list_active_rules,
    list_checklist_runs,
    list_checklist_templates,
    list_component_types,
    list_findings,
    list_packs,
    passport,
    process_route,
    questionnaire_report,
    review_follow_up_milestone,
    set_product_record,
    set_instrumentation,
    submit_checklist_run,
    system_route_report,
    unadopt_pack,
    treatment_train_report,
    update_finding,
    update_follow_up_item,
)
from pack_engine import InvalidRecordError  # noqa: E402
from permissions import (  # noqa: E402
    PermissionAdminError,
    UserNotFoundError,
    create_user,
    current_role,
    effective_permissions,
    list_permissions,
    list_roles,
    list_users,
    required_permission,
    reset_role_permissions,
    set_role_permissions,
    update_user,
)
from calendar_service import annual_calendar  # noqa: E402
from catalog_service import set_region, set_terms, ui_catalog  # noqa: E402
from report_service import (  # noqa: E402
    ReportConflictError,
    ReportNotFoundError,
)
from report_service import generate_report as generate_compliance_report  # noqa: E402
from report_service import get_report as get_compliance_report  # noqa: E402
from report_service import list_reports as list_compliance_reports  # noqa: E402
from report_service import mark_sent as mark_report_sent  # noqa: E402
from observation_service import (  # noqa: E402
    ObservationNotFoundError,
    create_observation,
    list_observations,
    update_observation,
)
from group_service import (  # noqa: E402
    GroupConflictError,
    GroupNotFoundError,
    decide_membership,
    group_dashboard,
    invite_member,
    remove_member,
    set_organization_kind,
)
from group_service import memberships as group_memberships  # noqa: E402
from improvement_service import (  # noqa: E402
    ImprovementConflictError,
    ImprovementNotFoundError,
    create_improvement_input,
    delete_improvement_input,
    improvement_overview,
    minimum_plan,
    product_board,
    save_minimum_plan_entry,
    update_improvement_input,
)
from sanitation_service import (  # noqa: E402
    SanitationNotFoundError,
    add_discharge_followup,
    create_discharge,
    sanitation_overview,
    verify_destination,
)
from warehouse_service import (  # noqa: E402
    WarehouseConflictError,
    WarehouseNotFoundError,
    chlorine_check,
    create_item,
    list_items,
    list_movements,
    record_movement,
    update_item,
    warehouse_catalog,
)
from emergency_service import (  # noqa: E402
    EmergencyNotFoundError,
    activate_emergency,
    add_contact,
    close_activation,
    delete_contact,
    emergency_plan,
    list_activations,
    review_emergency_plan,
    save_plan_entry,
)
from quality_service import (  # noqa: E402
    QualityConflictError,
    QualityNotFoundError,
    create_plan_item,
    get_lab_sample,
    list_lab_samples,
    list_plan,
    list_quality_parameters,
    quality_overview,
    record_lab_sample,
    review_plan,
    update_plan_item,
)
from meter_manual_service import (  # noqa: E402
    MeterNotFoundError,
    MeterReadingConflictError,
    find_meters,
    list_manual_meter_readings,
    record_manual_meter_reading,
)
from operation_service import (  # noqa: E402
    OperationConflictError,
    OperationNotFoundError,
    calculate_dosing,
    create_chemical_product,
    create_log_entry,
    create_sampling_point,
    list_chemical_products,
    list_field_parameters,
    list_field_readings,
    list_log_entries,
    list_operation_moments,
    list_sampling_point_kinds,
    list_sampling_points,
    operation_day,
    record_field_reading,
    update_chemical_product,
    update_sampling_point,
)
from pack_service import AssetNotFoundError as PackAssetNotFoundError  # noqa: E402
from renmeter_common.auth import TokenError, create_token, decode_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import InvalidCredentialsError, authenticate, resolve_tenant_ref  # noqa: E402
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


@app.middleware("http")
async def permission_guard(request: Request, call_next):
    """D1.4b: con token, el usuario debe seguir activo (lecturas y
    escrituras); cada escritura ademas pide su permiso (permissions.py). Sin
    token o con token invalido se deja pasar: el endpoint responde 401 como
    siempre. El rol se lee de la BD (no del token), asi desactivar a alguien
    o cambiarle el rol rige de inmediato, sin esperar a que venza su sesion."""
    needed = required_permission(request.method, request.url.path)
    auth = request.headers.get("authorization") or ""
    if not auth.startswith("Bearer ") or request.url.path == "/auth/login":
        return await call_next(request)
    try:
        claims = decode_token(auth.removeprefix("Bearer ").strip(), app.state.settings.jwt_secret)
    except TokenError:
        return await call_next(request)

    def check() -> tuple[str | None, set[str]]:
        with db_conn() as conn:
            role = current_role(conn, claims["tenant_id"], claims.get("user_id"), claims.get("role"))
            if role is None or needed is None:
                return role, set()
            return role, effective_permissions(conn, claims["tenant_id"], role)

    role, granted = await run_in_threadpool(check)
    if role is None:
        return JSONResponse(status_code=403, content={"detail": "Su usuario está desactivado. Consulte a la administración de la organización."})
    if needed is not None and needed not in granted:
        return JSONResponse(status_code=403, content={"detail": f"Su rol no tiene permiso para esta acción ({needed})."})
    return await call_next(request)


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
            # 2026-10-05: el tenant se puede indicar por su id o por su nombre
            # exacto (p. ej. "jaas001"), para que una junta no tenga que
            # escribir un UUID. Mismo mensaje generico si no se resuelve.
            tenant_id = resolve_tenant_ref(conn, body.tenant_id)
            identity = authenticate(conn, tenant_id, body.email, body.password)
        except InvalidCredentialsError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        # Duracion de la sesion: parametro de la organizacion (Configuracion
        # -> Sesion, migracion 0022), nunca un valor fijo en codigo ni archivo.
        session_ttl = get_session_ttl_seconds(conn, tenant_id)
    if session_ttl is None:
        raise HTTPException(
            status_code=409,
            detail="La organización no tiene configurada la duración de la sesión. Un administrador debe definirla en Configuración → Sesión.",
        )
    token = create_token(
        {
            "tenant_id": tenant_id,
            "role": identity["role"],
            "user_id": identity["user_id"],
            "email": body.email,  # Sprint C5: convencion real de origen (auth_dependency.requested_by_label)
        },
        app.state.settings.jwt_secret,
        expires_in_seconds=session_ttl,
    )
    return {"access_token": token, "token_type": "bearer", "tenant_id": tenant_id, "expires_in": session_ttl}


@app.get("/auth/me")
def session_me(claims: dict = Depends(get_session_claims)) -> dict:
    """Datos de la sesion activa para el encabezado del Portal
    (2026-10-05): organizacion, usuario, rol, inicio y vencimiento. El
    nombre del tenant sale de la BD (no viaja en el token); `tenant` no
    tiene RLS, el filtro por id es explicito."""
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM tenant WHERE id = %s", (claims["tenant_id"],))
            row = cur.fetchone()
        role = current_role(conn, claims["tenant_id"], claims.get("user_id"), claims.get("role"))
        permissions = effective_permissions(conn, claims["tenant_id"], role)
        with conn.cursor() as cur:
            cur.execute("SELECT label FROM app_role WHERE code = %s", (role,))
            label_row = cur.fetchone()
        role_label = label_row[0] if label_row else role
    return {
        "tenant_id": claims["tenant_id"],
        "tenant_name": row[0] if row else None,
        "email": claims.get("email") or claims.get("user_id"),
        "role": role,
        "role_label": role_label,
        "permissions": sorted(permissions),
        "issued_at": datetime.fromtimestamp(claims["iat"], tz=timezone.utc).isoformat() if "iat" in claims else None,
        "expires_at": datetime.fromtimestamp(claims["exp"], tz=timezone.utc).isoformat(),
    }


@app.get("/dashboard/overview")
def dashboard_overview_endpoint(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int | None = None) -> dict:
    """`stale_after_seconds` como query param es un override explícito
    opcional (ej. para depuración) -- si no viene, se resuelve del umbral
    REAL configurado por el tenant (`GET/PUT /settings/hes`), nunca un
    3600 fijo en el código (2026-09-15, a pedido explícito del usuario)."""
    with db_conn() as conn:
        effective = stale_after_seconds if stale_after_seconds is not None else get_meter_stale_after_seconds(conn, tenant_id)
        return dashboard_overview(conn, tenant_id, effective)


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
def fleet_summary_endpoint(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int | None = None) -> list[dict]:
    """Sprint C7 (G4): flota agrupada por marca/modelo, con % de medidores
    activos que de verdad estan reportando -- no solo el conteo total.
    `stale_after_seconds` resuelve del umbral configurado por el tenant si
    no viene explícito (ver `dashboard_overview_endpoint`)."""
    with db_conn() as conn:
        effective = stale_after_seconds if stale_after_seconds is not None else get_meter_stale_after_seconds(conn, tenant_id)
        return fleet_summary(conn, tenant_id, effective)


@app.get("/meters/geojson")
def meters_geojson_endpoint(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int | None = None) -> dict:
    """Mapa de medidores real (2026-09-15) -- capas tematicas (en línea/
    caído, tipo micro/macro, marca) sobre coordenadas reales; un medidor
    sin georreferenciar no aparece."""
    with db_conn() as conn:
        effective = stale_after_seconds if stale_after_seconds is not None else get_meter_stale_after_seconds(conn, tenant_id)
        return meters_geojson(conn, tenant_id, effective)


@app.get("/meters/consumption-distribution")
def consumption_distribution_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Distribución estadística real del consumo (últimos 30 días, solo
    medidores MICRO) -- histograma para el panel de KPIs de HES."""
    with db_conn() as conn:
        return consumption_distribution(conn, tenant_id)


@app.get("/meters/exception-rate-by-brand")
def exception_rate_by_brand_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return exception_rate_by_brand(conn, tenant_id)


@app.get("/meters/sector-summary")
def sector_summary_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    """Por sector hidráulico con macro-medidor real: inflow del macro vs.
    consumo sumado de sus micro-medidores -- NRW operativo real derivado
    de medición cruda (docs/05-ejecucion.md 2026-09-15)."""
    with db_conn() as conn:
        return sector_summary(conn, tenant_id)


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
def ingestion_observability(tenant_id: str = Depends(get_tenant_id), stale_after_seconds: int | None = None) -> dict:
    """`stale_after_seconds` resuelve del umbral configurado por el tenant
    si no viene explícito (ver `dashboard_overview_endpoint`)."""
    with db_conn() as conn:
        effective = stale_after_seconds if stale_after_seconds is not None else get_meter_stale_after_seconds(conn, tenant_id)
        return ingestion_metrics(conn, tenant_id, effective)


class HesSettingsRequest(BaseModel):
    stale_after_seconds: int


@app.get("/settings/hes")
def get_hes_settings_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Umbral real de "medidor caído", configurado por el tenant -- `None`
    si todavía no se configuró (2026-09-15, nunca un valor fijo en código)."""
    with db_conn() as conn:
        return get_hes_settings(conn, tenant_id)


@app.put("/settings/hes")
def set_hes_settings_endpoint(body: HesSettingsRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            set_meter_stale_after_seconds(conn, tenant_id, body.stale_after_seconds)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return get_hes_settings(conn, tenant_id)


@app.get("/settings/session")
def get_session_settings_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Duracion de la sesion de esta organizacion (0022). Aplica a los
    logins siguientes; las sesiones abiertas conservan la suya."""
    with db_conn() as conn:
        return {"session_ttl_seconds": get_session_ttl_seconds(conn, tenant_id)}


class SessionSettingsRequest(BaseModel):
    session_ttl_seconds: int


@app.put("/settings/session")
def set_session_settings_endpoint(body: SessionSettingsRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            set_session_ttl_seconds(conn, tenant_id, body.session_ttl_seconds)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"session_ttl_seconds": get_session_ttl_seconds(conn, tenant_id)}


@app.get("/settings/timezone")
def get_timezone_settings_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Zona horaria de la organizacion (0029): define "hoy" para el
    seguimiento y las fechas de vencimiento."""
    with db_conn() as conn:
        return {"timezone": get_timezone(conn, tenant_id)}


class TimezoneSettingsRequest(BaseModel):
    timezone: str


@app.put("/settings/timezone")
def set_timezone_settings_endpoint(body: TimezoneSettingsRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            set_timezone(conn, tenant_id, body.timezone.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"timezone": get_timezone(conn, tenant_id)}


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
    priority: str
    reason: str | None = None


@app.post("/maintenance-orders", status_code=201)
def create_maintenance_order_endpoint(body: GenerateOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Genera una orden real -- `422` si el tipo/fuente/prioridad no son
    validos o la anomalia real que justificaria una fuente automatica no
    se cumple ahora mismo (`AnomalyNotConfirmedError`); `404` si el
    activo no existe. El SLA (`sla_due_at`) se calcula solo si el tenant
    configuro una politica real para esa prioridad."""
    with db_conn() as conn:
        try:
            return generate_order(conn, tenant_id, body.asset_id, body.type, body.source, body.priority, body.reason)
        except MaintenanceAssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (InvalidOrderTypeError, InvalidOrderSourceError, InvalidPriorityError, AnomalyNotConfirmedError) as exc:
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
    `409` si la orden no esta en `generated` (misma convencion que
    `InvalidTransitionError` de Control/SCR: transicion de estado invalida,
    no un cuerpo de request malformado); `422` si BayForce no esta
    configurado para este tenant, o si BayForce no responde/responde algo
    invalido (nunca un 200 con un envio fabricado); `404` si la orden no
    existe."""
    with db_conn() as conn:
        try:
            return send_to_bayforce(conn, tenant_id, order_id, app.state.settings.bayforce_webhook_url)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (BayforceNotConfiguredError, BayforceIntegrationError) as exc:
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
    tenant) -- no se inventa un esquema de firma nuevo para esto. `409` si
    la transicion de estado pedida no es valida desde el estado actual
    (misma convencion que `InvalidTransitionError` de Control/SCR); `404`
    si no existe ninguna orden con ese `bayforce_order_ref`."""
    with db_conn() as conn:
        try:
            return close_from_webhook(conn, tenant_id, body.bayforce_order_ref, body.status)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


# ══════════════════════════════════════════════════════════════════════════
# CMMS real de dominio (2026-09-14, docs/04-plan-sprints.md SS9) --
# prioridad/SLA, codigos de falla, PM programado, ciclo de vida propio
# (generated -> scheduled -> assigned -> in_progress -> completed |
# cancelled), cierre con sustancia, KPIs. BayForce sigue siendo la
# notificacion de salida OPCIONAL de arriba, nunca esta columna vertebral.
# ══════════════════════════════════════════════════════════════════════════


class ScheduleOrderRequest(BaseModel):
    scheduled_at: datetime


@app.post("/maintenance-orders/{order_id}/schedule")
def schedule_maintenance_order_endpoint(order_id: str, body: ScheduleOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Programa la orden -- `409` si no esta en `generated`; `404` si no existe."""
    with db_conn() as conn:
        try:
            return schedule_order(conn, tenant_id, order_id, body.scheduled_at)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


class AssignOrderRequest(BaseModel):
    crew_id: str


@app.post("/maintenance-orders/{order_id}/assign")
def assign_maintenance_order_endpoint(order_id: str, body: AssignOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Asigna la orden a una cuadrilla real y activa -- `404` si la orden o
    la cuadrilla no existen; `409` si la orden no esta en `scheduled`."""
    with db_conn() as conn:
        try:
            return assign_order(conn, tenant_id, order_id, body.crew_id)
        except (MaintenanceOrderNotFoundError, CrewNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/maintenance-orders/{order_id}/start")
def start_maintenance_order_endpoint(order_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Marca el trabajo como iniciado en campo -- `409` si no esta en
    `assigned`/`sent_to_bayforce`; `404` si no existe."""
    with db_conn() as conn:
        try:
            return start_order(conn, tenant_id, order_id)
        except MaintenanceOrderNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


class CloseOrderRequest(BaseModel):
    status: str
    labor_hours: float | None = None
    materials_used: str | None = None
    root_cause: str | None = None
    failure_code_id: str | None = None
    # Guia 3, ficha 7D y §3.6 (D3.1)
    steps_done: list[int] | None = None
    responsible: str | None = None
    pending_notes: str | None = None
    community_participants: int | None = None
    volunteer_hours: float | None = None
    # Ficha 7F (D6)
    waste_handler: str | None = None
    waste_destination: str | None = None
    sludge_volume_m3: float | None = None


@app.post("/maintenance-orders/{order_id}/close")
def close_maintenance_order_endpoint(order_id: str, body: CloseOrderRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Cierra la orden real -- `completed` (con lo que de verdad se hizo)
    o `cancelled`. `409` si no esta en `in_progress`; `404` si la orden o
    el codigo de falla no existen; `422` si `status` no es uno de los 2
    validos para cerrar."""
    with db_conn() as conn:
        try:
            return close_order(
                conn, tenant_id, order_id, body.status,
                body.labor_hours, body.materials_used, body.root_cause, body.failure_code_id,
                body.steps_done, body.responsible, body.pending_notes, body.community_participants, body.volunteer_hours,
                body.waste_handler, body.waste_destination, body.sludge_volume_m3,
            )
        except InvalidCommunityWorkError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (MaintenanceOrderNotFoundError, FailureCodeNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidCloseStatusError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except InvalidStatusTransitionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/maintenance/kpis")
def maintenance_kpis_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """MTTR, backlog, % de cumplimiento de mantenimiento preventivo y
    ordenes vencidas de SLA -- todo real, nunca aproximado."""
    with db_conn() as conn:
        return maintenance_kpis(conn, tenant_id)


class SlaPolicyRequest(BaseModel):
    priority: str
    target_hours: float


@app.get("/maintenance/sla-policies")
def list_sla_policies_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_sla_policies(conn, tenant_id)


@app.post("/maintenance/sla-policies", status_code=201)
def set_sla_policy_endpoint(body: SlaPolicyRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Crea o reemplaza el SLA objetivo (horas) para una prioridad -- `422`
    si la prioridad no es una de las 4 reales."""
    with db_conn() as conn:
        try:
            return set_sla_policy(conn, tenant_id, body.priority, body.target_hours)
        except InvalidPriorityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class FailureCodeRequest(BaseModel):
    code: str
    label: str


@app.get("/maintenance/failure-codes")
def list_failure_codes_endpoint(tenant_id: str = Depends(get_tenant_id), include_inactive: bool = False) -> list[dict]:
    with db_conn() as conn:
        return list_failure_codes(conn, tenant_id, include_inactive)


@app.post("/maintenance/failure-codes", status_code=201)
def create_failure_code_endpoint(body: FailureCodeRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return create_failure_code(conn, tenant_id, body.code, body.label)


@app.delete("/maintenance/failure-codes/{failure_code_id}", status_code=204)
def deactivate_failure_code_endpoint(failure_code_id: str, tenant_id: str = Depends(get_tenant_id)) -> None:
    with db_conn() as conn:
        deactivate_failure_code(conn, tenant_id, failure_code_id)


class CrewRequest(BaseModel):
    name: str


@app.get("/maintenance/crews")
def list_crews_endpoint(tenant_id: str = Depends(get_tenant_id), include_inactive: bool = False) -> list[dict]:
    with db_conn() as conn:
        return list_crews(conn, tenant_id, include_inactive)


@app.post("/maintenance/crews", status_code=201)
def create_crew_endpoint(body: CrewRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return create_crew(conn, tenant_id, body.name)


@app.delete("/maintenance/crews/{crew_id}", status_code=204)
def deactivate_crew_endpoint(crew_id: str, tenant_id: str = Depends(get_tenant_id)) -> None:
    with db_conn() as conn:
        deactivate_crew(conn, tenant_id, crew_id)


class PmPlanRequest(BaseModel):
    asset_id: str
    order_type: str
    priority: str
    interval_days: int
    next_due_at: datetime
    title: str | None = None
    responsible: str | None = None
    trigger_events: list[str] | None = None


@app.get("/maintenance/pm-plans")
def list_pm_plans_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_pm_plans(conn, tenant_id)


@app.post("/maintenance/pm-plans", status_code=201)
def create_pm_plan_endpoint(body: PmPlanRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Plan de mantenimiento preventivo real, por activo especifico --
    `404` si el activo no existe; `422` si el tipo/prioridad no son
    validos."""
    with db_conn() as conn:
        try:
            return create_pm_plan(conn, tenant_id, body.asset_id, body.order_type, body.priority, body.interval_days,
                                  body.next_due_at, body.title, body.responsible, body.trigger_events)
        except MaintenanceAssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (InvalidOrderTypeError, InvalidPriorityError, InvalidPmPlanError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/maintenance/community-catalog")
def maintenance_community_catalog_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Pasos del mantenimiento y eventos que disparan planes (paquete de
    programa, Guia 3 §3.6)."""
    with db_conn() as conn:
        return {"steps": maintenance_steps(conn, tenant_id)["steps"], "event_types": maintenance_event_types(conn, tenant_id)}


class MaintenanceEventRequest(BaseModel):
    event_type_code: str
    occurred_at: datetime | None = None
    notes: str | None = None


@app.post("/maintenance/events", status_code=201)
def record_maintenance_event_endpoint(body: MaintenanceEventRequest, actor: dict = Depends(get_actor)) -> dict:
    """Lluvia fuerte, deslizamiento o quejas: genera una orden por cada plan
    que espera ese evento."""
    occurred_at = body.occurred_at or datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="occurred_at debe incluir la zona horaria")
    with db_conn() as conn:
        try:
            return record_maintenance_event(conn, actor["tenant_id"], body.event_type_code, occurred_at,
                                            requested_by_label(actor), body.notes)
        except MaintenanceEventError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/maintenance/events")
def list_maintenance_events_endpoint(tenant_id: str = Depends(get_tenant_id), limit: int = 50) -> list[dict]:
    with db_conn() as conn:
        return list_maintenance_events(conn, tenant_id, limit)


@app.post("/maintenance/pm-plans/generate-due")
def generate_due_pm_orders_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    """Genera una orden real por cada plan PM activo cuyo vencimiento ya
    llego -- idempotente en el sentido de que un plan que no vencio no
    genera nada; pensado para correr periodicamente (o a mano desde el
    Portal) mientras no haya un cron propio."""
    with db_conn() as conn:
        return generate_due_pm_orders(conn, tenant_id)


# ══════════════════════════════════════════════════════════════════════════
# Track D, Sprint D0.2 -- motor de paquetes (docs/04-plan-sprints.md SS11.4)
# ══════════════════════════════════════════════════════════════════════════


@app.get("/packs")
def list_packs_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Catalogo de paquetes + los activos de esta junta (`core` siempre)."""
    with db_conn() as conn:
        return {"packs": list_packs(conn), "active": active_pack_ids(conn, tenant_id)}


@app.post("/packs/{pack_id}/adopt")
def adopt_pack_endpoint(pack_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return adopt_pack(conn, tenant_id, pack_id)
        except PackNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/packs/{pack_id}/adopt")
def unadopt_pack_endpoint(pack_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Desactiva un paquete para esta organizacion (0025). `core` no."""
    with db_conn() as conn:
        try:
            return unadopt_pack(conn, tenant_id, pack_id)
        except PackNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/component-types")
def list_component_types_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_component_types(conn, tenant_id)


@app.get("/parameter-rules")
def list_parameter_rules_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    """Reglas vigentes de los paquetes adoptados, con su cita de fuente."""
    with db_conn() as conn:
        try:
            return list_active_rules(conn, tenant_id)
        except AmbiguousRuleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


class EvaluateParameterRequest(BaseModel):
    parameter_code: str
    value: float


@app.post("/parameter-rules/evaluate")
def evaluate_parameter_endpoint(body: EvaluateParameterRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Evalua un valor con la regla vigente del paquete adoptado. 404 si
    ningun paquete adoptado tiene regla (nunca se inventa un umbral)."""
    with db_conn() as conn:
        try:
            return evaluate_parameter(conn, tenant_id, body.parameter_code, body.value)
        except RuleNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AmbiguousRuleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/checklist-templates")
def list_checklist_templates_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_checklist_templates(conn, tenant_id)


class ChecklistAnswerRequest(BaseModel):
    item_key: str
    answer_code: str
    observation: str | None = None
    action: str | None = None
    responsible: str | None = None
    due_date: date | None = None
    asset_id: str | None = None


class ChecklistRunRequest(BaseModel):
    template_id: str
    answers: list[ChecklistAnswerRequest]
    notes: str | None = None
    context: dict[str, str] = {}


@app.post("/checklist-runs", status_code=201)
def submit_checklist_run_endpoint(body: ChecklistRunRequest, actor: dict = Depends(get_actor)) -> dict:
    """Aplicacion completa de una lista. Quien la hizo sale del JWT, nunca
    del body. Crea un hallazgo por cada respuesta que la escala marca."""
    with db_conn() as conn:
        try:
            return submit_checklist_run(
                conn, actor["tenant_id"], body.template_id,
                [a.model_dump() for a in body.answers], requested_by_label(actor), body.notes, body.context,
            )
        except (TemplateNotAvailableError, PackAssetNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidAnswersError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/checklist-templates/{template_id}/analysis")
def questionnaire_analysis_endpoint(template_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Analisis de un cuestionario (CAP: matriz T-05) por grupo y momento."""
    with db_conn() as conn:
        try:
            return questionnaire_report(conn, tenant_id, template_id)
        except TemplateNotAvailableError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/checklist-runs")
def list_checklist_runs_endpoint(tenant_id: str = Depends(get_tenant_id), template_id: str | None = None) -> list[dict]:
    with db_conn() as conn:
        return list_checklist_runs(conn, tenant_id, template_id)


@app.get("/checklist-runs/{run_id}")
def get_checklist_run_endpoint(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return get_checklist_run(conn, tenant_id, run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class FindingRequest(BaseModel):
    description: str
    priority: str
    source_kind: str = "manual"
    asset_id: str | None = None
    location_text: str | None = None
    geometry: dict | None = None
    support_level: str | None = None


@app.post("/findings", status_code=201)
def create_finding_endpoint(body: FindingRequest, actor: dict = Depends(get_actor)) -> dict:
    """Punto critico del mapa tecnico o hallazgo manual."""
    with db_conn() as conn:
        try:
            return create_finding(
                conn, actor["tenant_id"], body.description, body.priority, requested_by_label(actor),
                body.source_kind, body.asset_id, body.location_text, body.geometry, body.support_level,
            )
        except PackAssetNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidFindingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/findings")
def list_findings_endpoint(tenant_id: str = Depends(get_tenant_id), status: str | None = None) -> list[dict]:
    with db_conn() as conn:
        try:
            return list_findings(conn, tenant_id, status)
        except InvalidFindingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class FindingUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    support_level: str | None = None
    to_improvement_plan: bool | None = None


@app.patch("/findings/{finding_id}")
def update_finding_endpoint(finding_id: str, body: FindingUpdateRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return update_finding(
                conn, tenant_id, finding_id, body.status, body.priority, body.support_level, body.to_improvement_plan
            )
        except FindingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidFindingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/process-route")
def process_route_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Ruta del programa (0023): etapas en orden, sus listas y el estado de
    cada una (sin aplicar / al día / vencida / aplicada)."""
    with db_conn() as conn:
        return process_route(conn, tenant_id)


@app.get("/reports/system-route")
def system_route_report_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Recorrido del sistema: componentes ordenados por servicio y tramo."""
    with db_conn() as conn:
        return system_route_report(conn, tenant_id)


@app.get("/reports/treatment-train")
def treatment_train_report_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    """Tren de tratamiento (actividad 3 de la Guia 3) desde lo registrado."""
    with db_conn() as conn:
        return treatment_train_report(conn, tenant_id)


@app.get("/reports/traffic-light")
def traffic_light_report_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Semaforo vigente. `run: null` si nunca se aplico."""
    with db_conn() as conn:
        return {"run": latest_traffic_light(conn, tenant_id)}


# ── Pasaporte de productos y seguimiento 7-30-90 (Track D, 0028) ───────

@app.get("/passport")
def passport_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Pasaporte de productos (T-07): productos de cada etapa con su estado."""
    with db_conn() as conn:
        return passport(conn, tenant_id)


class ProductRecordRequest(BaseModel):
    status: str
    evidence: str | None = None
    to_improvement_plan: bool = False


@app.put("/passport/{pack_id}/{product_code}")
def set_product_record_endpoint(pack_id: str, product_code: str, body: ProductRecordRequest,
                                actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return set_product_record(conn, actor["tenant_id"], pack_id, product_code, body.status,
                                      requested_by_label(actor), body.evidence, body.to_improvement_plan)
        except ProductNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/follow-up")
def follow_up_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Seguimiento a 7, 30 y 90 dias (T-09): ciclos, momentos, compromisos.
    "Hoy" es la fecha en la zona horaria de la organizacion (0029)."""
    with db_conn() as conn:
        try:
            today = tenant_today(conn, tenant_id)
        except TimezoneNotConfiguredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return follow_up(conn, tenant_id, today)


class FollowUpCycleRequest(BaseModel):
    pack_id: str
    anchor_date: date
    title: str


@app.post("/follow-up/cycles", status_code=201)
def create_follow_up_cycle_endpoint(body: FollowUpCycleRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return create_follow_up_cycle(conn, actor["tenant_id"], body.pack_id, body.anchor_date, body.title,
                                          requested_by_label(actor))
        except FollowUpNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class FollowUpItemRequest(BaseModel):
    milestone_code: str
    commitment: str
    responsible: str | None = None
    due_date: date | None = None


@app.post("/follow-up/cycles/{cycle_id}/items", status_code=201)
def add_follow_up_item_endpoint(cycle_id: str, body: FollowUpItemRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return add_follow_up_item(conn, actor["tenant_id"], cycle_id, body.milestone_code, body.commitment,
                                      requested_by_label(actor), body.responsible, body.due_date)
        except FollowUpNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class FollowUpItemUpdateRequest(BaseModel):
    commitment: str | None = None
    responsible: str | None = None
    due_date: date | None = None
    status: str | None = None
    situation: str | None = None
    evidence: str | None = None
    adjustment_action: str | None = None


@app.patch("/follow-up/items/{item_id}")
def update_follow_up_item_endpoint(item_id: str, body: FollowUpItemUpdateRequest,
                                   tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Solo cambia los campos enviados (un null explicito borra el valor)."""
    with db_conn() as conn:
        try:
            return update_follow_up_item(conn, tenant_id, item_id, **body.model_dump(exclude_unset=True))
        except FollowUpNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class FollowUpReviewRequest(BaseModel):
    reviewed_on: date
    summary: str | None = None


@app.put("/follow-up/cycles/{cycle_id}/milestones/{milestone_code}/review")
def review_follow_up_milestone_endpoint(cycle_id: str, milestone_code: str, body: FollowUpReviewRequest,
                                        actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return review_follow_up_milestone(conn, actor["tenant_id"], cycle_id, milestone_code, body.reviewed_on,
                                              requested_by_label(actor), body.summary)
        except FollowUpNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Operacion diaria: puntos, mediciones 7B y bitacora 7C (Track D, 0030) ──

def _tenant_day(conn, tenant_id: str) -> tuple[date, str, datetime, datetime]:
    """Hoy, la zona y los limites del dia en la zona de la organizacion
    (0029). Sin zona horaria -> 409, nunca el dia UTC del servidor."""
    try:
        today = tenant_today(conn, tenant_id)
    except TimezoneNotConfiguredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    tz_name = get_timezone(conn, tenant_id)
    tz = ZoneInfo(tz_name)
    start = datetime.combine(today, datetime.min.time(), tzinfo=tz)
    return today, tz_name, start, start + timedelta(days=1)


@app.get("/operations/catalog")
def operations_catalog_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Tipos de punto, rutina diaria y parametros de campo con su regla."""
    with db_conn() as conn:
        return {
            "point_kinds": list_sampling_point_kinds(conn, tenant_id),
            "moments": list_operation_moments(conn, tenant_id),
            "parameters": list_field_parameters(conn, tenant_id),
        }


@app.get("/operations/today")
def operations_today_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Vista "Hoy" del operador (rutina, puntos que toca medir, mediciones)."""
    with db_conn() as conn:
        today, tz_name, start, end = _tenant_day(conn, tenant_id)
        return operation_day(conn, tenant_id, today, tz_name, start, end)


@app.get("/sampling-points")
def list_sampling_points_endpoint(tenant_id: str = Depends(get_tenant_id), include_inactive: bool = False) -> list[dict]:
    with db_conn() as conn:
        today, tz_name, _, _ = _tenant_day(conn, tenant_id)
        return list_sampling_points(conn, tenant_id, today, tz_name, include_inactive)


class SamplingPointRequest(BaseModel):
    kind_code: str
    name: str
    asset_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    frequency_days: int | None = None


def _operation_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, (OperationNotFoundError, PackAssetNotFoundError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, OperationConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


_OPERATION_ERRORS = (OperationNotFoundError, PackAssetNotFoundError, OperationConflictError, InvalidRecordError)


@app.post("/sampling-points", status_code=201)
def create_sampling_point_endpoint(body: SamplingPointRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return create_sampling_point(conn, tenant_id, body.kind_code, body.name, body.asset_id,
                                         body.latitude, body.longitude, body.frequency_days)
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


class SamplingPointUpdateRequest(BaseModel):
    name: str | None = None
    frequency_days: int | None = None
    active: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    asset_id: str | None = None


@app.patch("/sampling-points/{point_id}")
def update_sampling_point_endpoint(point_id: str, body: SamplingPointUpdateRequest,
                                   tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Solo cambia los campos enviados (un null explicito borra el valor)."""
    with db_conn() as conn:
        try:
            return update_sampling_point(conn, tenant_id, point_id, **body.model_dump(exclude_unset=True))
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


class FieldReadingRequest(BaseModel):
    parameter_code: str
    value: float
    measured_at: datetime | None = None
    sampling_point_id: str | None = None
    action_taken: str | None = None
    client_id: str | None = None


@app.post("/field-readings", status_code=201)
def record_field_reading_endpoint(body: FieldReadingRequest, actor: dict = Depends(get_actor)) -> dict:
    """Medicion de campo (7B). Quien midio sale del JWT. `measured_at` sin
    zona se rechaza: la app sin conexion manda la hora con su zona."""
    measured_at = body.measured_at or datetime.now(timezone.utc)
    if measured_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="measured_at debe incluir la zona horaria")
    with db_conn() as conn:
        try:
            return record_field_reading(conn, actor["tenant_id"], body.parameter_code, body.value, measured_at,
                                        requested_by_label(actor), body.sampling_point_id, body.action_taken,
                                        body.client_id)
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


@app.get("/field-readings")
def list_field_readings_endpoint(
    tenant_id: str = Depends(get_tenant_id), since: datetime | None = None, until: datetime | None = None,
    point_id: str | None = None, parameter_code: str | None = None, limit: int = 200,
) -> list[dict]:
    with db_conn() as conn:
        try:
            return list_field_readings(conn, tenant_id, since, until, point_id, parameter_code, limit)
        except OperationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class OperationLogRequest(BaseModel):
    logged_at: datetime | None = None
    moment_code: str | None = None
    tank_level_pct: float | None = None
    chlorine_applied: float | None = None
    chlorine_applied_unit: str | None = None
    reading_id: str | None = None
    appearance: str | None = None
    status: str | None = None
    notes: str | None = None
    client_id: str | None = None


@app.post("/operation-log", status_code=201)
def create_log_entry_endpoint(body: OperationLogRequest, actor: dict = Depends(get_actor)) -> dict:
    """Toma de la bitacora diaria (7C)."""
    logged_at = body.logged_at or datetime.now(timezone.utc)
    if logged_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="logged_at debe incluir la zona horaria")
    with db_conn() as conn:
        try:
            return create_log_entry(
                conn, actor["tenant_id"], logged_at, requested_by_label(actor), body.moment_code, None,
                body.tank_level_pct, body.chlorine_applied, body.chlorine_applied_unit, body.reading_id,
                body.appearance, body.status, body.notes, body.client_id,
            )
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


@app.get("/operation-log")
def list_log_entries_endpoint(
    tenant_id: str = Depends(get_tenant_id), since: datetime | None = None, until: datetime | None = None, limit: int = 200,
) -> list[dict]:
    with db_conn() as conn:
        return list_log_entries(conn, tenant_id, since, until, limit)


# ── Productos quimicos y dosificacion (Track D, 0031) ──────────────────

@app.get("/chemical-products")
def list_chemical_products_endpoint(tenant_id: str = Depends(get_tenant_id), include_inactive: bool = False) -> list[dict]:
    with db_conn() as conn:
        return list_chemical_products(conn, tenant_id, include_inactive)


class ChemicalProductRequest(BaseModel):
    name: str
    purpose: str
    form: str
    active_pct: float
    notes: str | None = None


@app.post("/chemical-products", status_code=201)
def create_chemical_product_endpoint(body: ChemicalProductRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return create_chemical_product(conn, tenant_id, body.name, body.purpose, body.form, body.active_pct, body.notes)
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


class ChemicalProductUpdateRequest(BaseModel):
    name: str | None = None
    purpose: str | None = None
    form: str | None = None
    active_pct: float | None = None
    notes: str | None = None
    active: bool | None = None


@app.patch("/chemical-products/{product_id}")
def update_chemical_product_endpoint(product_id: str, body: ChemicalProductUpdateRequest,
                                     tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return update_chemical_product(conn, tenant_id, product_id, **body.model_dump(exclude_unset=True))
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


class DosingRequest(BaseModel):
    product_id: str
    flow_lps: float
    dose_mg_l: float


@app.post("/dosing/calculate")
def calculate_dosing_endpoint(body: DosingRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Calculo orientativo de la Guia 3 §3.5 con las guardas del dia. No se
    guarda nada: lo aplicado va a la bitacora 7C."""
    with db_conn() as conn:
        _, _, start, end = _tenant_day(conn, tenant_id)
        try:
            return calculate_dosing(conn, tenant_id, body.product_id, body.flow_lps, body.dose_mg_l, start, end)
        except _OPERATION_ERRORS as exc:
            raise _operation_errors(exc) from exc


# ── Lectura manual de micro y macromedidor (Track D, 0032) ─────────────

@app.get("/manual-reading/meters")
def manual_reading_meters_endpoint(
    tenant_id: str = Depends(get_tenant_id), search: str | None = None, meter_type: str | None = None,
    with_channels: bool = True, limit: int = 50,
) -> list[dict]:
    """Medidores para leer a mano (cuenta o serie), con sus canales y la
    ultima lectura de cada uno."""
    with db_conn() as conn:
        return find_meters(conn, tenant_id, search, meter_type, with_channels, limit)


class ManualMeterReadingRequest(BaseModel):
    meter_id: str
    channel: str
    value: float
    read_at: datetime | None = None
    lower_confirmed: bool = False
    notes: str | None = None
    client_id: str | None = None


@app.post("/manual-reading", status_code=201)
def record_manual_meter_reading_endpoint(body: ManualMeterReadingRequest, actor: dict = Depends(get_actor)) -> dict:
    """La lectura entra a raw_reading (source_quality = 'manual') y la valida
    el pase VEE como a cualquier otra."""
    read_at = body.read_at or datetime.now(timezone.utc)
    if read_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="read_at debe incluir la zona horaria")
    with db_conn() as conn:
        try:
            return record_manual_meter_reading(conn, actor["tenant_id"], body.meter_id, body.channel, body.value, read_at,
                                               requested_by_label(actor), body.lower_confirmed, body.notes, body.client_id)
        except MeterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except MeterReadingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/manual-reading")
def list_manual_meter_readings_endpoint(
    tenant_id: str = Depends(get_tenant_id), meter_id: str | None = None, since: datetime | None = None, limit: int = 200,
) -> list[dict]:
    with db_conn() as conn:
        try:
            return list_manual_meter_readings(conn, tenant_id, meter_id, since, limit)
        except MeterNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Usuarios y roles de la organizacion (Track D, 0033) ────────────────

@app.get("/roles")
def list_roles_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return {"roles": list_roles(conn, tenant_id), "permissions": list_permissions(conn)}


class RolePermissionsRequest(BaseModel):
    permissions: list[str]


def _admin_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, UserNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@app.put("/roles/{role}/permissions")
def set_role_permissions_endpoint(role: str, body: RolePermissionsRequest, actor: dict = Depends(get_actor)) -> dict:
    """Reemplaza los permisos de un rol en esta organizacion."""
    with db_conn() as conn:
        try:
            return set_role_permissions(conn, actor["tenant_id"], role, body.permissions, requested_by_label(actor))
        except (UserNotFoundError, PermissionAdminError) as exc:
            raise _admin_errors(exc) from exc


@app.delete("/roles/{role}/permissions")
def reset_role_permissions_endpoint(role: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Vuelve a los permisos por defecto del rol."""
    with db_conn() as conn:
        try:
            return reset_role_permissions(conn, tenant_id, role)
        except (UserNotFoundError, PermissionAdminError) as exc:
            raise _admin_errors(exc) from exc


@app.get("/users")
def list_users_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_users(conn, tenant_id)


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str


@app.post("/users", status_code=201)
def create_user_endpoint(body: CreateUserRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return create_user(conn, tenant_id, body.email, body.password, body.role)
        except (UserNotFoundError, PermissionAdminError) as exc:
            raise _admin_errors(exc) from exc


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@app.patch("/users/{user_id}")
def update_user_endpoint(user_id: str, body: UpdateUserRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return update_user(conn, actor["tenant_id"], user_id, actor.get("user_id"),
                               body.role, body.is_active, body.password)
        except (UserNotFoundError, PermissionAdminError) as exc:
            raise _admin_errors(exc) from exc


# ── Calidad del agua y laboratorio (Track D, D2, 0034) ─────────────────

def _quality_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, QualityNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, QualityConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


_QUALITY_ERRORS = (QualityNotFoundError, QualityConflictError, InvalidRecordError)


@app.get("/quality/overview")
def quality_overview_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Alertas de calidad abiertas (las criticas aparte), plan de muestreo y su revision."""
    with db_conn() as conn:
        return quality_overview(conn, tenant_id, datetime.now(timezone.utc))


@app.get("/quality/parameters")
def quality_parameters_endpoint(tenant_id: str = Depends(get_tenant_id)) -> list[dict]:
    with db_conn() as conn:
        return list_quality_parameters(conn, tenant_id)


@app.get("/quality/plan")
def quality_plan_endpoint(tenant_id: str = Depends(get_tenant_id), include_inactive: bool = False) -> dict:
    with db_conn() as conn:
        return list_plan(conn, tenant_id, datetime.now(timezone.utc), include_inactive)


class LabPlanItemRequest(BaseModel):
    name: str
    parameters: list[str]
    frequency_days: int
    sampling_point_id: str | None = None
    source_note: str | None = None


@app.post("/quality/plan", status_code=201)
def create_plan_item_endpoint(body: LabPlanItemRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return create_plan_item(conn, tenant_id, body.name, body.parameters, body.frequency_days,
                                    body.sampling_point_id, body.source_note)
        except _QUALITY_ERRORS as exc:
            raise _quality_errors(exc) from exc


class LabPlanItemUpdateRequest(BaseModel):
    name: str | None = None
    parameters: list[str] | None = None
    frequency_days: int | None = None
    sampling_point_id: str | None = None
    source_note: str | None = None
    active: bool | None = None


@app.patch("/quality/plan/{plan_item_id}")
def update_plan_item_endpoint(plan_item_id: str, body: LabPlanItemUpdateRequest,
                              tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return update_plan_item(conn, tenant_id, plan_item_id, **body.model_dump(exclude_unset=True))
        except _QUALITY_ERRORS as exc:
            raise _quality_errors(exc) from exc


class LabPlanReviewRequest(BaseModel):
    reviewed_on: date
    notes: str | None = None


@app.post("/quality/plan/reviews", status_code=201)
def review_plan_endpoint(body: LabPlanReviewRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        return review_plan(conn, actor["tenant_id"], body.reviewed_on, requested_by_label(actor), body.notes)


class LabResultRequest(BaseModel):
    parameter_code: str
    value: float
    qualifier: str = "="


class LabSampleRequest(BaseModel):
    sampled_at: datetime
    laboratory: str
    results: list[LabResultRequest]
    sampling_point_id: str | None = None
    plan_item_id: str | None = None
    report_ref: str | None = None
    reason: str = "plan"
    notes: str | None = None
    discharge_id: str | None = None


@app.post("/quality/samples", status_code=201)
def record_lab_sample_endpoint(body: LabSampleRequest, actor: dict = Depends(get_actor)) -> dict:
    """Muestra de laboratorio con sus resultados (interpretados con la regla
    vigente a la fecha de la muestra)."""
    if body.sampled_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="sampled_at debe incluir la zona horaria")
    with db_conn() as conn:
        try:
            return record_lab_sample(
                conn, actor["tenant_id"], body.sampled_at, body.laboratory, [r.model_dump() for r in body.results],
                requested_by_label(actor), body.sampling_point_id, body.plan_item_id, body.report_ref, body.reason, body.notes,
                body.discharge_id,
            )
        except _QUALITY_ERRORS as exc:
            raise _quality_errors(exc) from exc


@app.get("/quality/samples")
def list_lab_samples_endpoint(tenant_id: str = Depends(get_tenant_id), point_id: str | None = None, limit: int = 100) -> list[dict]:
    with db_conn() as conn:
        try:
            return list_lab_samples(conn, tenant_id, point_id, limit)
        except QualityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/quality/samples/{sample_id}")
def get_lab_sample_endpoint(sample_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return get_lab_sample(conn, tenant_id, sample_id)
        except QualityNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Emergencias (Track D, D5, 0037) ───────────────────────────────────

def _emergency_now(conn, tenant_id: str) -> datetime:
    today, tz_name, _, _ = _tenant_day(conn, tenant_id)
    return datetime.now(ZoneInfo(tz_name))


@app.get("/emergencies")
def emergencies_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Plan de emergencia (catalogo + ajustes de la junta), contactos,
    emergencias activas y revision del plan."""
    with db_conn() as conn:
        return emergency_plan(conn, tenant_id, _emergency_now(conn, tenant_id))


class EmergencyPlanEntryRequest(BaseModel):
    type_code: str | None = None
    custom_label: str | None = None
    responsible: str | None = None
    first_action: str | None = None
    community_message: str | None = None
    external_support: str | None = None
    resources: str | None = None
    active: bool | None = None


@app.put("/emergencies/plan")
def save_emergency_plan_entry_endpoint(body: EmergencyPlanEntryRequest, actor: dict = Depends(get_actor)) -> dict:
    fields = body.model_dump(exclude_unset=True)
    type_code, custom_label = fields.pop("type_code", None), fields.pop("custom_label", None)
    with db_conn() as conn:
        try:
            save_plan_entry(conn, actor["tenant_id"], requested_by_label(actor), type_code, custom_label, **fields)
            return emergency_plan(conn, actor["tenant_id"], _emergency_now(conn, actor["tenant_id"]))
        except EmergencyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class EmergencyContactRequest(BaseModel):
    institution: str
    phone: str
    person: str | None = None
    notes: str | None = None


@app.post("/emergencies/contacts", status_code=201)
def add_emergency_contact_endpoint(body: EmergencyContactRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return add_contact(conn, tenant_id, body.institution, body.phone, body.person, body.notes)
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/emergencies/contacts/{contact_id}", status_code=204)
def delete_emergency_contact_endpoint(contact_id: str, tenant_id: str = Depends(get_tenant_id)) -> None:
    with db_conn() as conn:
        try:
            delete_contact(conn, tenant_id, contact_id)
        except EmergencyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class EmergencyActivationRequest(BaseModel):
    type_code: str | None = None
    plan_entry_id: str | None = None
    notes: str | None = None


@app.post("/emergencies/activations", status_code=201)
def activate_emergency_endpoint(body: EmergencyActivationRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return activate_emergency(conn, actor["tenant_id"], requested_by_label(actor), body.type_code, body.plan_entry_id,
                                      "manual", None, body.notes)
        except EmergencyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class EmergencyCloseRequest(BaseModel):
    notes: str | None = None


@app.post("/emergencies/activations/{activation_id}/close")
def close_emergency_endpoint(activation_id: str, body: EmergencyCloseRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return close_activation(conn, actor["tenant_id"], activation_id, requested_by_label(actor), body.notes)
        except EmergencyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/emergencies/activations")
def list_emergency_activations_endpoint(tenant_id: str = Depends(get_tenant_id), limit: int = 50) -> list[dict]:
    with db_conn() as conn:
        return list_activations(conn, tenant_id, False, max(1, min(limit, 500)))


class EmergencyReviewRequest(BaseModel):
    reviewed_on: date
    notes: str | None = None


@app.post("/emergencies/reviews", status_code=201)
def review_emergency_plan_endpoint(body: EmergencyReviewRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        review_emergency_plan(conn, actor["tenant_id"], body.reviewed_on, requested_by_label(actor), body.notes)
        return emergency_plan(conn, actor["tenant_id"], _emergency_now(conn, actor["tenant_id"]))["review"]


# ── Bodega y EPP (Track D, D4, 0038) ──────────────────────────────────

def _warehouse_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, WarehouseNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, WarehouseConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


_WAREHOUSE_ERRORS = (WarehouseNotFoundError, WarehouseConflictError, InvalidRecordError)


@app.get("/warehouse")
def warehouse_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Catalogo (categorias y EPP por tarea), articulos con existencia y
    alertas, y el cruce del cloro del mes en curso (zona de la organizacion)."""
    with db_conn() as conn:
        today, tz_name, _, _ = _tenant_day(conn, tenant_id)
        tz = ZoneInfo(tz_name)
        month_start = datetime(today.year, today.month, 1, tzinfo=tz)
        items = list_items(conn, tenant_id, today)
        return {
            **warehouse_catalog(conn, tenant_id), "items": items,
            "alerts": {"below_min": sum(1 for i in items if i["below_min"]),
                       "expiring": sum(1 for i in items if i["expiring"])},
            "chlorine_check": chlorine_check(conn, tenant_id, month_start, datetime.now(tz)),
        }


class WarehouseItemRequest(BaseModel):
    name: str
    category_code: str
    unit: str
    min_stock: float | None = None
    chemical_product_id: str | None = None


@app.post("/warehouse/items", status_code=201)
def create_warehouse_item_endpoint(body: WarehouseItemRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return create_item(conn, tenant_id, body.name, body.category_code, body.unit, body.min_stock, body.chemical_product_id)
        except _WAREHOUSE_ERRORS as exc:
            raise _warehouse_errors(exc) from exc


class WarehouseItemUpdateRequest(BaseModel):
    name: str | None = None
    min_stock: float | None = None
    active: bool | None = None


@app.patch("/warehouse/items/{item_id}")
def update_warehouse_item_endpoint(item_id: str, body: WarehouseItemUpdateRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return update_item(conn, tenant_id, item_id, **body.model_dump(exclude_unset=True))
        except _WAREHOUSE_ERRORS as exc:
            raise _warehouse_errors(exc) from exc


class WarehouseMovementRequest(BaseModel):
    item_id: str
    kind: str
    quantity: float
    moved_at: datetime | None = None
    expires_on: date | None = None
    reason: str | None = None
    maintenance_order_id: str | None = None
    client_id: str | None = None


@app.post("/warehouse/movements", status_code=201)
def record_warehouse_movement_endpoint(body: WarehouseMovementRequest, actor: dict = Depends(get_actor)) -> dict:
    moved_at = body.moved_at or datetime.now(timezone.utc)
    if moved_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="moved_at debe incluir la zona horaria")
    with db_conn() as conn:
        try:
            return record_movement(conn, actor["tenant_id"], body.item_id, body.kind, body.quantity, moved_at,
                                   requested_by_label(actor), body.expires_on, body.reason, body.maintenance_order_id, body.client_id)
        except _WAREHOUSE_ERRORS as exc:
            raise _warehouse_errors(exc) from exc


@app.get("/warehouse/movements")
def list_warehouse_movements_endpoint(tenant_id: str = Depends(get_tenant_id), item_id: str | None = None, limit: int = 100) -> list[dict]:
    with db_conn() as conn:
        try:
            return list_movements(conn, tenant_id, item_id, max(1, min(limit, 500)))
        except WarehouseNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Saneamiento (Track D, D6, 0039) ───────────────────────────────────

@app.get("/sanitation")
def sanitation_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Componentes de saneamiento con el estado del retiro de lodos, registro
    7F y descargas productivas con su seguimiento y analisis."""
    with db_conn() as conn:
        today, _, _, _ = _tenant_day(conn, tenant_id)
        return sanitation_overview(conn, tenant_id, today)


@app.post("/sanitation/register/{order_id}/verify")
def verify_sanitation_destination_endpoint(order_id: str, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return verify_destination(conn, actor["tenant_id"], order_id, requested_by_label(actor))
        except SanitationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class DischargeRequest(BaseModel):
    activity_code: str
    name: str
    owner: str | None = None
    location_text: str | None = None
    asset_id: str | None = None
    problem: str | None = None


@app.post("/sanitation/discharges", status_code=201)
def create_discharge_endpoint(body: DischargeRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return create_discharge(conn, actor["tenant_id"], requested_by_label(actor), body.activity_code, body.name, body.owner,
                                    body.location_text, body.asset_id, body.problem)
        except SanitationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class DischargeFollowupRequest(BaseModel):
    note: str
    new_status: str | None = None
    agreement: str | None = None


@app.post("/sanitation/discharges/{discharge_id}/followups", status_code=201)
def add_discharge_followup_endpoint(discharge_id: str, body: DischargeFollowupRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return add_discharge_followup(conn, actor["tenant_id"], discharge_id, requested_by_label(actor), body.note,
                                          body.new_status, body.agreement)
        except SanitationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── Plan minimo, ficha 7G.2 y tablero 7H (Track D, D7, 0040) ──────────

@app.get("/improvement/minimum-plan")
def minimum_plan_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Las filas del plan minimo con la decision de la junta y la evidencia
    viva que respalda cada una."""
    with db_conn() as conn:
        today, tz_name, start, _ = _tenant_day(conn, tenant_id)
        return minimum_plan(conn, tenant_id, today, start, tz_name)


class MinimumPlanEntryRequest(BaseModel):
    decision: str
    responsible: str | None = None
    term: str | None = None
    due_date: date | None = None


@app.put("/improvement/minimum-plan/{pack_id}/{row_code}")
def save_minimum_plan_entry_endpoint(pack_id: str, row_code: str, body: MinimumPlanEntryRequest,
                                     actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return save_minimum_plan_entry(conn, actor["tenant_id"], pack_id, row_code, requested_by_label(actor), body.decision,
                                           body.responsible, body.term, body.due_date)
        except ImprovementNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/improvement/inputs")
def improvement_inputs_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Ficha 7G.2: filas de la junta y lo que la evidencia propone llevar."""
    with db_conn() as conn:
        today, _, _, _ = _tenant_day(conn, tenant_id)
        return improvement_overview(conn, tenant_id, today)


class ImprovementInputRequest(BaseModel):
    source_ref: str | None = None
    problem: str | None = None
    evidence: str | None = None
    proposed_action: str | None = None
    community_action: str | None = None
    support_required: str | None = None
    support_level: str | None = None
    cost_estimate: float | None = None
    cost_note: str | None = None
    term: str | None = None
    priority: str | None = None


@app.post("/improvement/inputs", status_code=201)
def create_improvement_input_endpoint(body: ImprovementInputRequest, actor: dict = Depends(get_actor)) -> dict:
    data = body.model_dump()
    source_ref = data.pop("source_ref")
    with db_conn() as conn:
        today, _, _, _ = _tenant_day(conn, actor["tenant_id"])
        try:
            return create_improvement_input(conn, actor["tenant_id"], requested_by_label(actor), today, source_ref, **data)
        except ImprovementNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ImprovementConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.patch("/improvement/inputs/{input_id}")
def update_improvement_input_endpoint(input_id: str, body: ImprovementInputRequest, actor: dict = Depends(get_actor)) -> dict:
    data = body.model_dump(exclude_unset=True)
    data.pop("source_ref", None)
    with db_conn() as conn:
        try:
            return update_improvement_input(conn, actor["tenant_id"], input_id, **data)
        except ImprovementNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/improvement/inputs/{input_id}", status_code=204)
def delete_improvement_input_endpoint(input_id: str, actor: dict = Depends(get_actor)) -> None:
    with db_conn() as conn:
        try:
            delete_improvement_input(conn, actor["tenant_id"], input_id)
        except ImprovementNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/improvement/products/{template_id}")
def product_board_endpoint(template_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Tablero de productos finales (7H): ultimo estado verificado y la
    evidencia que el sistema tiene de cada producto."""
    with db_conn() as conn:
        try:
            return product_board(conn, tenant_id, template_id)
        except ImprovementNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Agrupacion de juntas (Track D, D12.1, 0042) ───────────────────────

@app.get("/group")
def group_memberships_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Tipo de organizacion, juntas de la agrupacion (si lo es), agrupaciones
    a las que pertenece o que la invitaron, y el catalogo de indicadores."""
    with db_conn() as conn:
        return group_memberships(conn, tenant_id)


class OrganizationKindRequest(BaseModel):
    kind: str


@app.put("/settings/organization-kind")
def organization_kind_endpoint(body: OrganizationKindRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return set_organization_kind(conn, tenant_id, body.kind)
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except GroupConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


class GroupInviteRequest(BaseModel):
    name: str


@app.post("/group/members", status_code=201)
def invite_group_member_endpoint(body: GroupInviteRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return invite_member(conn, actor["tenant_id"], body.name, requested_by_label(actor))
        except GroupNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GroupConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/group/members/{member_tenant_id}")
def remove_group_member_endpoint(member_tenant_id: str, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return remove_member(conn, actor["tenant_id"], member_tenant_id, requested_by_label(actor))
        except GroupNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class MembershipDecisionRequest(BaseModel):
    action: str
    shared: list[str] = []


@app.post("/group/memberships/{group_tenant_id}")
def decide_group_membership_endpoint(group_tenant_id: str, body: MembershipDecisionRequest,
                                     actor: dict = Depends(get_actor)) -> dict:
    """La junta acepta, rechaza, cambia lo que comparte o sale."""
    with db_conn() as conn:
        try:
            return decide_membership(conn, actor["tenant_id"], group_tenant_id, requested_by_label(actor), body.action, body.shared)
        except GroupNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GroupConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/group/dashboard")
def group_dashboard_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Tablero de la agrupacion: solo juntas que aceptaron y solo los
    indicadores que cada una comparte."""
    with db_conn() as conn:
        try:
            return group_dashboard(conn, tenant_id)
        except GroupConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


# ── T-10 Consolidado de observaciones (Track D, D12.2, 0043) ──────────

@app.get("/program/observations")
def program_observations_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Observaciones para mejorar las guias, con las que propone la CAP."""
    with db_conn() as conn:
        return list_observations(conn, tenant_id)


class ObservationRequest(BaseModel):
    stage_code: str | None = None
    source_code: str | None = None
    finding: str | None = None
    proposed_change: str | None = None
    priority: str | None = None
    reviewer: str | None = None
    status: str | None = None
    community: str | None = None


@app.post("/program/observations", status_code=201)
def create_observation_endpoint(body: ObservationRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return create_observation(conn, actor["tenant_id"], requested_by_label(actor), **body.model_dump())
        except ObservationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.patch("/program/observations/{observation_id}")
def update_observation_endpoint(observation_id: str, body: ObservationRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return update_observation(conn, actor["tenant_id"], observation_id, **body.model_dump(exclude_unset=True))
        except ObservationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── Informe de cumplimiento al ente rector (Track D, D12.3, 0044) ─────

@app.get("/reports/compliance")
def compliance_reports_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Plantillas de informe de los paquetes adoptados e informes generados."""
    with db_conn() as conn:
        return list_compliance_reports(conn, tenant_id)


class ComplianceReportRequest(BaseModel):
    report_code: str
    period_from: date
    period_to: date
    pack_id: str | None = None


@app.post("/reports/compliance", status_code=201)
def generate_compliance_report_endpoint(body: ComplianceReportRequest, actor: dict = Depends(get_actor)) -> dict:
    with db_conn() as conn:
        try:
            return generate_compliance_report(conn, actor["tenant_id"], requested_by_label(actor), body.report_code,
                                              body.period_from, body.period_to, body.pack_id)
        except ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/reports/compliance/{report_id}")
def compliance_report_endpoint(report_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return get_compliance_report(conn, tenant_id, report_id)
        except ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


class ReportSentRequest(BaseModel):
    sent_to: str
    sent_on: date
    note: str | None = None


@app.post("/reports/compliance/{report_id}/sent")
def mark_compliance_report_sent_endpoint(report_id: str, body: ReportSentRequest, actor: dict = Depends(get_actor)) -> dict:
    """La junta registra que envio el informe (a quien y cuando)."""
    with db_conn() as conn:
        try:
            return mark_report_sent(conn, actor["tenant_id"], report_id, requested_by_label(actor), body.sent_to, body.sent_on, body.note)
        except ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ReportConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── Catalogos de la organizacion (base generica, 0045) ────────────────

@app.get("/catalog/ui")
def ui_catalog_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Todo lo que la interfaz nombra: etiquetas de codigos, terminologia,
    formatos del paquete, moneda y region de la organizacion."""
    with db_conn() as conn:
        return ui_catalog(conn, tenant_id)


class RegionRequest(BaseModel):
    currency: str
    locale: str


@app.put("/settings/region")
def set_region_endpoint(body: RegionRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return set_region(conn, tenant_id, body.currency.strip().upper(), body.locale.strip())
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class TermValue(BaseModel):
    label: str
    plural: str


class TermsRequest(BaseModel):
    changes: dict[str, TermValue | None]


@app.put("/settings/terms")
def set_terms_endpoint(body: TermsRequest, actor: dict = Depends(get_actor)) -> dict:
    """Como nombra la organizacion cada termino; `null` vuelve al del paquete."""
    with db_conn() as conn:
        try:
            return set_terms(conn, actor["tenant_id"], requested_by_label(actor),
                             {k: (v.model_dump() if v else None) for k, v in body.changes.items()})
        except InvalidRecordError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/calendar")
def annual_calendar_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    """Calendario anual 7G (Track D, D3.2): mantenimiento, listas con
    frecuencia y plan de muestreo, con el % de cumplimiento del ano en curso
    en la zona horaria de la organizacion."""
    with db_conn() as conn:
        today, tz_name, _, _ = _tenant_day(conn, tenant_id)
        tz = ZoneInfo(tz_name)
        return annual_calendar(conn, tenant_id, datetime(today.year, 1, 1, tzinfo=tz), datetime.now(tz))


@app.get("/settings/instrumentation")
def get_instrumentation_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        return {"levels": get_instrumentation(conn, tenant_id)}


class InstrumentationRequest(BaseModel):
    levels: dict[str, str]


@app.put("/settings/instrumentation")
def set_instrumentation_endpoint(body: InstrumentationRequest, tenant_id: str = Depends(get_tenant_id)) -> dict:
    with db_conn() as conn:
        try:
            return {"levels": set_instrumentation(conn, tenant_id, body.levels)}
        except InvalidInstrumentationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
