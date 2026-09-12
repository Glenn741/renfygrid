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

from network_model_engine import InvalidModelError, SimulationSummary, load_model, run_simulation  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


class ModelNotFoundError(LookupError):
    """No existe ese `network_model` para este tenant."""


def register_model(
    conn: psycopg.Connection,
    tenant_id: str,
    name: str,
    inp_content: str,
    storage_dir: str,
) -> dict[str, Any]:
    """Registra una nueva version de un modelo `.inp` -- versiona por
    `name` (mismo nombre resubmitido = version siguiente, historial
    completo conservado, igual que `network_balance`). Valida el archivo
    ANTES de insertar la fila: un `.inp` invalido nunca llega a quedar
    registrado (`InvalidModelError` se propaga, el archivo se borra)."""
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
                    "INSERT INTO network_model (id, tenant_id, name, format, version, file_ref) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (str(model_id), tenant_id, name, "epanet_inp", max_version + 1, str(file_path)),
                )

    return {"model_id": str(model_id), "name": name, "version": max_version + 1}


def list_models(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Solo la version MAS RECIENTE por nombre -- el historial completo
    queda en BD (mismo criterio de `network_balance.list_balances`)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT ON (name) id, name, format, version, valid_from "
                    "FROM network_model WHERE tenant_id = %s ORDER BY name, version DESC",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [
        {"model_id": str(row[0]), "name": row[1], "format": row[2], "version": row[3], "valid_from": row[4].isoformat()}
        for row in rows
    ]


def _model_file_ref(conn: psycopg.Connection, tenant_id: str, model_id: str) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT file_ref FROM network_model WHERE id = %s AND tenant_id = %s",
                    (model_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise ModelNotFoundError(f"No existe el modelo {model_id} para este tenant")
    return row[0]


def run_and_store_simulation(
    conn: psycopg.Connection,
    tenant_id: str,
    model_id: str,
    scenario: str,
) -> dict[str, Any]:
    """Corre una simulacion EPANET real (WNTR) sobre el `.inp` de ese
    modelo y guarda el resultado -- `InvalidModelError`/`SimulationFailedError`
    de `network_model_engine` se propagan tal cual (el llamador -- `main.py`
    -- las traduce a 404/422, nunca un 200 con un resultado a medias)."""
    file_ref = _model_file_ref(conn, tenant_id, model_id)
    summary: SimulationSummary = run_simulation(file_ref)
    results_dict = summary.to_dict()

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
