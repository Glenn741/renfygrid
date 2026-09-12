"""Servicio de Modelado Hidraulico (Track B, Sprint B3, F39/F40) --
registro/versionado de modelos EPANET (`network_model`) y ejecucion de
simulaciones reales via WNTR (`simulation_result`). Toca BD y disco (a
diferencia de `network_model_engine.py`, que es logica pura sobre un
archivo) -- esta capa arma la ruta del archivo, llama al motor, y guarda
el resultado; nunca simula ella misma.

Almacenamiento: el contenido del `.inp` se escribe a disco bajo
`storage_dir/<tenant_id>/<model_id>.inp` -- ruta que se guarda en
`network_model.file_ref`. `storage_dir` siempre llega por argumento
(nunca una ruta fija en codigo, mismo principio que `infra/db/backup.py`).
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from network_model_engine import (  # noqa: E402
    CalibrationInputError,
    InvalidModelError,
    LinkStats,
    NodeStats,
    SimulationSummary,
    calibrate_and_simulate,
    load_model,
    model_topology_geojson,
    run_simulation,
)
from renmeter_common.db import tenant_scope  # noqa: E402


class ModelNotFoundError(LookupError):
    """No existe ese `network_model` para este tenant."""


class ModelNotLinkedToZoneError(ValueError):
    """Se pidio calibrar con balance real pero el modelo no esta vinculado
    a ninguna `network_zone` -- nunca se calibra "al aire"."""


class NoBalanceForCalibrationError(ValueError):
    """El modelo esta vinculado a una zona, pero esa zona todavia no tiene
    ningun `network_balance` registrado -- nada real con que calibrar."""


def register_model(
    conn: psycopg.Connection,
    tenant_id: str,
    name: str,
    inp_content: str,
    storage_dir: str,
    zone_id: str | None = None,
) -> dict[str, Any]:
    """Registra una nueva version de un modelo `.inp` -- versiona por
    `name` (mismo nombre resubmitido = version siguiente, historial
    completo conservado, igual que `network_balance`). Valida el archivo
    ANTES de insertar la fila: un `.inp` invalido nunca llega a quedar
    registrado (`InvalidModelError` se propaga, el archivo se borra).

    `zone_id` (Sprint B4, opcional): vincula el modelo a una zona real de
    Balance de Red -- permite calibrar con `network_balance.real_losses`
    al simular. `None` = modelo sin vincular, sigue funcionando igual sin
    calibracion."""
    model_id = uuid.uuid4()
    file_path = Path(storage_dir) / tenant_id / f"{model_id}.inp"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(inp_content, encoding="utf-8")

    try:
        load_model(str(file_path))
    except InvalidModelError:
        file_path.unlink(missing_ok=True)
        raise

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(max(version), 0) FROM network_model WHERE tenant_id = %s AND name = %s",
                    (tenant_id, name),
                )
                (max_version,) = cur.fetchone()
                cur.execute(
                    "INSERT INTO network_model (id, tenant_id, name, format, version, file_ref, zone_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (str(model_id), tenant_id, name, "epanet_inp", max_version + 1, str(file_path), zone_id),
                )

    return {"model_id": str(model_id), "name": name, "version": max_version + 1}


def list_models(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Solo la version MAS RECIENTE por nombre -- el historial completo
    queda en BD (mismo criterio de `network_balance.list_balances`)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT ON (name) id, name, format, version, valid_from, zone_id "
                    "FROM network_model WHERE tenant_id = %s ORDER BY name, version DESC",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [
        {
            "model_id": str(row[0]), "name": row[1], "format": row[2], "version": row[3],
            "valid_from": row[4].isoformat(), "zone_id": str(row[5]) if row[5] else None,
        }
        for row in rows
    ]


def _model_row(conn: psycopg.Connection, tenant_id: str, model_id: str) -> tuple[str, str | None]:
    """`(file_ref, zone_id)` -- `zone_id` es `None` si el modelo no esta
    vinculado a ninguna zona."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT file_ref, zone_id FROM network_model WHERE id = %s AND tenant_id = %s",
                    (model_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise ModelNotFoundError(f"No existe el modelo {model_id} para este tenant")
    return row[0], (str(row[1]) if row[1] else None)


def _model_file_ref(conn: psycopg.Connection, tenant_id: str, model_id: str) -> str:
    return _model_row(conn, tenant_id, model_id)[0]


def _latest_zone_balance_for_calibration(
    conn: psycopg.Connection, tenant_id: str, zone_id: str
) -> tuple[float, float] | None:
    """`(real_losses_m3, period_days)` del balance mas reciente (por
    periodo, luego por version) de esa zona -- `None` si la zona todavia
    no tiene ningun balance."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT real_losses, (upper(period) - lower(period)) "
                    "FROM network_balance WHERE tenant_id = %s AND zone_id = %s "
                    "ORDER BY upper(period) DESC, version DESC LIMIT 1",
                    (tenant_id, zone_id),
                )
                row = cur.fetchone()
    if row is None:
        return None
    real_losses, period_days = row
    return float(real_losses), float(period_days)


def run_and_store_simulation(
    conn: psycopg.Connection,
    tenant_id: str,
    model_id: str,
    scenario: str,
    calibrate: bool = False,
) -> dict[str, Any]:
    """Corre una simulacion EPANET real (WNTR) sobre el `.inp` de ese
    modelo y guarda el resultado -- `InvalidModelError`/`SimulationFailedError`
    de `network_model_engine` se propagan tal cual (el llamador -- `main.py`
    -- las traduce a 404/422, nunca un 200 con un resultado a medias).

    `calibrate=True` (Sprint B4): usa `network_balance.real_losses` de la
    ULTIMA version del balance mas reciente de la zona vinculada como
    insumo REAL de calibracion (emisores por presion) -- `ModelNotLinkedToZoneError`
    si el modelo no tiene `zone_id`, `NoBalanceForCalibrationError` si la
    zona todavia no tiene ningun balance. Nunca se calibra "a medias" o
    con un numero de ejemplo."""
    file_ref, zone_id = _model_row(conn, tenant_id, model_id)

    if calibrate:
        if zone_id is None:
            raise ModelNotLinkedToZoneError(
                f"El modelo {model_id} no esta vinculado a ninguna zona -- no hay balance real con que calibrar"
            )
        balance = _latest_zone_balance_for_calibration(conn, tenant_id, zone_id)
        if balance is None:
            raise NoBalanceForCalibrationError(
                f"La zona {zone_id} vinculada a este modelo todavia no tiene ningun balance registrado"
            )
        real_losses_m3, period_days = balance
        calibration = calibrate_and_simulate(file_ref, real_losses_m3, period_days)
        results_dict = calibration.to_dict()
        results_dict["calibrated"] = True
    else:
        summary: SimulationSummary = run_simulation(file_ref)
        results_dict = summary.to_dict()
        results_dict["calibrated"] = False

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO simulation_result (tenant_id, network_model_id, scenario, results) "
                    "VALUES (%s, %s, %s, %s) RETURNING id, calculated_at",
                    (tenant_id, model_id, scenario, Json(results_dict)),
                )
                (simulation_id, calculated_at) = cur.fetchone()

    return {
        "simulation_id": str(simulation_id),
        "model_id": model_id,
        "scenario": scenario,
        "calculated_at": calculated_at.isoformat(),
        **results_dict,
    }


def list_simulation_results(conn: psycopg.Connection, tenant_id: str, model_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, scenario, results, calculated_at FROM simulation_result "
                    "WHERE tenant_id = %s AND network_model_id = %s ORDER BY calculated_at DESC",
                    (tenant_id, model_id),
                )
                rows = cur.fetchall()
    return [
        {"simulation_id": str(row[0]), "scenario": row[1], "calculated_at": row[3].isoformat(), **row[2]}
        for row in rows
    ]


def _latest_simulation_summary(conn: psycopg.Connection, tenant_id: str, model_id: str) -> SimulationSummary | None:
    """Reconstruye el `SimulationSummary` desde el `jsonb` guardado de la
    ULTIMA corrida -- `None` si el modelo nunca se simulo (el mapa se
    muestra igual, sin colorear por presion/caudal)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT results FROM simulation_result WHERE tenant_id = %s AND network_model_id = %s "
                    "ORDER BY calculated_at DESC LIMIT 1",
                    (tenant_id, model_id),
                )
                row = cur.fetchone()
    if row is None:
        return None
    results = row[0]
    return SimulationSummary(
        duration_hours=results["duration_hours"],
        num_nodes=results["num_nodes"],
        num_links=results["num_links"],
        nodes={k: NodeStats(**v) for k, v in results["nodes"].items()},
        links={k: LinkStats(**v) for k, v in results["links"].items()},
    )


def model_geojson(conn: psycopg.Connection, tenant_id: str, model_id: str) -> dict:
    """GeoJSON real del modelo (Track B, modulo de georreferenciacion,
    `docs/07-track-b-alcance-funcional.md` SS7) -- enriquecido con las
    estadisticas de la ULTIMA simulacion guardada si existe."""
    file_ref = _model_file_ref(conn, tenant_id, model_id)
    latest = _latest_simulation_summary(conn, tenant_id, model_id)
    return model_topology_geojson(file_ref, latest)
