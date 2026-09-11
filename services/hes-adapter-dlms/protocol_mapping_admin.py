"""Editor de mapeo OBIS por marca/modelo (F50/E19, Sprint C10) -- CRUD real
sobre `meter_protocol` desde el Portal Web, en vez de SQL directo (unico
camino hasta ahora, ver `obis_mapping.py`). Mismo patron de versionado que
`control_approval_level` (`services/control/approval_levels_admin.py`), no
el de `vee_rule`: `meter_protocol` SI tiene una clave de version bien
definida -- `(tenant_id, brand, model)`, indexada en `meter_protocol_active_idx`
(0001_init.sql) -- y `obis_mapping.channels_for` toma la ultima fila activa
para esa marca/modelo. Por eso `create_protocol_mapping` SI cierra la
version anterior para esa misma marca/modelo antes de insertar la nueva --
dejar dos filas activas para la misma marca/modelo seria la misma condicion
de carrera que `approval_levels_admin` ya evita para `order_type`.

Cambiar el mapeo desde aca no lo aplica solo: el poller sigue leyendo el
snapshot en disco que escribe `refresh_obis_mapping_cache.py` (Config
Loader, docs/03-diseno.md SS2) -- el mismo criterio de F06 desde Sprint 2,
no algo nuevo que este sprint invente.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def list_protocol_mappings(conn: psycopg.Connection, tenant_id: str, active_only: bool = True) -> list[dict]:
    clause = "AND valid_to IS NULL" if active_only else ""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, brand, model, protocol, obis_mapping, security_mode, version, valid_from, valid_to "
                    f"FROM meter_protocol WHERE tenant_id = %s {clause} ORDER BY brand, model",
                    (tenant_id,),
                )
                return [
                    {
                        "id": str(row[0]), "brand": row[1], "model": row[2], "protocol": row[3],
                        "obis_mapping": row[4], "security_mode": row[5], "version": row[6],
                        "valid_from": row[7].isoformat() if row[7] else None,
                        "valid_to": row[8].isoformat() if row[8] else None,
                    }
                    for row in cur.fetchall()
                ]


def create_protocol_mapping(
    conn: psycopg.Connection,
    tenant_id: str,
    brand: str,
    model: str,
    protocol: str,
    obis_mapping: dict[str, Any],
    security_mode: str | None = None,
) -> str:
    """Cierra (`valid_to = now()`) la version anterior activa para la misma
    `(brand, model)`, si existe, antes de crear la nueva -- mantiene la
    invariante "a lo sumo una version activa por marca/modelo" que
    `obis_mapping.channels_for` asume. `version` sube a mano (no hay
    trigger): 1 si es la primera vez que se ve esa marca/modelo."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT version FROM meter_protocol "
                    "WHERE tenant_id = %s AND brand = %s AND model = %s AND valid_to IS NULL",
                    (tenant_id, brand, model),
                )
                row = cur.fetchone()
                next_version = (row[0] + 1) if row else 1

                cur.execute(
                    "UPDATE meter_protocol SET valid_to = now() "
                    "WHERE tenant_id = %s AND brand = %s AND model = %s AND valid_to IS NULL",
                    (tenant_id, brand, model),
                )
                cur.execute(
                    "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping, security_mode, version) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        tenant_id, brand, model, protocol,
                        psycopg.types.json.Json(obis_mapping), security_mode, next_version,
                    ),
                )
                (mapping_id,) = cur.fetchone()
                return str(mapping_id)
