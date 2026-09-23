"""Registro de medidores/concentradores (F01/F11, Sprint 1) -- alta de un
`meter` y un `gateway`, y el enlace entre ambos con la direccion DLMS del
medidor dentro de ese gateway (`meter.server_address`, ver migracion
0003_gateway_connection.sql).

Nada fijo aca: cada funcion recibe todos los datos por parametro y los
guarda tal cual en BD -- el registro real de un medidor (marca, protocolo,
ubicacion, host/puerto del concentrador) es exactamente el tipo de dato que
el principio de "cero hardcode" (docs/02-arquitectura-general.md SS1) exige
que viva en tabla, no en codigo.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def register_gateway(
    conn: psycopg.Connection,
    tenant_id: str,
    name: str,
    transport_protocol: str,
    connection: dict[str, Any],
) -> str:
    """`connection` es libre segun `transport_protocol` -- para 'TCP':
    {"host": ..., "port": ..., "client_address": ...}."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO gateway (tenant_id, name, transport_protocol, connection) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (tenant_id, name, transport_protocol, psycopg.types.json.Json(connection)),
                )
                (gateway_id,) = cur.fetchone()
                return str(gateway_id)


def register_meter(
    conn: psycopg.Connection,
    tenant_id: str,
    account_number: str,
    serial_number: str,
    brand: str,
    protocol: str,
    model: str | None = None,
    location: dict[str, Any] | None = None,
    meter_type: str = "micro",
    zone_id: str | None = None,
    geometry: dict[str, Any] | None = None,
) -> str:
    """`meter_type` (migracion 0020): 'micro' (medidor de cliente/inmueble
    individual, DEFAULT -- la inmensa mayoria de los medidores reales de
    cualquier utility) o 'macro' (medidor de bloque en la entrada de un
    sector hidraulico/DMA, mide el inflow TOTAL del sector -- se declara
    EXPLICITO al crearlo, nunca por default). `zone_id` vincula el
    medidor a su sector hidraulico real (`network_zone`); `geometry` es
    un Point GeoJSON real para el mapa de medidores -- ambos opcionales."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO meter "
                    "(tenant_id, account_number, serial_number, brand, model, protocol, location, meter_type, zone_id, geometry) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        tenant_id,
                        account_number,
                        serial_number,
                        brand,
                        model,
                        protocol,
                        psycopg.types.json.Json(location) if location else None,
                        meter_type,
                        zone_id,
                        psycopg.types.json.Json(geometry) if geometry else None,
                    ),
                )
                (meter_id,) = cur.fetchone()
                return str(meter_id)


def link_meter_to_gateway(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    gateway_id: str,
    server_address: int,
) -> None:
    """Enlaza el medidor a su concentrador y fija la direccion DLMS del
    medidor dentro de ese gateway -- sin esto, el poller (F03) no sabe a
    quien pedirle una lectura de ese medidor."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO meter_gateway (meter_id, gateway_id) VALUES (%s, %s)",
                    (meter_id, gateway_id),
                )
                cur.execute(
                    "UPDATE meter SET server_address = %s WHERE id = %s",
                    (server_address, meter_id),
                )
