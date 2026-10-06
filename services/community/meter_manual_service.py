"""Lectura manual de micro y macromedidor (Track D, D1.4a, migracion 0032).

La lectura va a `raw_reading` con source_quality = 'manual': el pase VEE la
valida como a cualquier otra, y de ahi salen consumo y balance. Aqui solo:
  - que medidor y que canal: solo los canales que ese medidor ya reporta o,
    si es nuevo, los que reportan los medidores del mismo tipo (micro/macro)
    de la junta. Nunca un canal escrito en el codigo.
  - que el registro acumulado no baje sin confirmacion (pack_engine).
  - idempotencia por `client_id` (app sin conexion).
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import InvalidRecordError, check_register  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


class MeterNotFoundError(LookupError):
    """Medidor o canal inexistente para esta junta."""


class MeterReadingConflictError(ValueError):
    """Ya hay una lectura de ese medidor y canal en ese mismo instante."""


def _check_uuid(value: str | None, what: str) -> None:
    if value is None:
        return
    try:
        uuid.UUID(str(value))
    except ValueError:
        raise MeterNotFoundError(f"No existe {what} {value!r}") from None


def _channels(cur: psycopg.Cursor, tenant_id: str, meter_id: str, meter_type: str) -> list[dict]:
    """Canales del medidor con su ultima lectura; si nunca reporto, los
    canales que usan los medidores del mismo tipo en la junta."""
    cur.execute(
        "SELECT DISTINCT ON (channel) channel, value, \"timestamp\", source_quality FROM raw_reading "
        "WHERE tenant_id = %s AND meter_id = %s ORDER BY channel, \"timestamp\" DESC",
        (tenant_id, meter_id),
    )
    own = [{"channel": r[0], "last_value": float(r[1]), "last_at": r[2].isoformat(), "last_source": r[3]}
           for r in cur.fetchall()]
    if own:
        return own
    cur.execute(
        "SELECT DISTINCT r.channel FROM raw_reading r JOIN meter m ON m.id = r.meter_id "
        "WHERE r.tenant_id = %s AND m.meter_type = %s ORDER BY 1",
        (tenant_id, meter_type),
    )
    return [{"channel": r[0], "last_value": None, "last_at": None, "last_source": None} for r in cur.fetchall()]


def find_meters(
    conn: psycopg.Connection, tenant_id: str, search: str | None = None, meter_type: str | None = None,
    with_channels: bool = True, limit: int = 50,
) -> list[dict]:
    """Medidores por cuenta o serie (o todos), con sus canales y ultima lectura."""
    clauses, params = ["m.tenant_id = %s", "m.status = 'active'"], [tenant_id]
    if search:
        clauses.append("(m.account_number ILIKE %s OR m.serial_number ILIKE %s)")
        params += [f"%{search.strip()}%", f"%{search.strip()}%"]
    if meter_type:
        clauses.append("m.meter_type = %s")
        params.append(meter_type)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.account_number, m.serial_number, m.brand, m.meter_type, z.name FROM meter m "
                    "LEFT JOIN network_zone z ON z.id = m.zone_id "
                    f"WHERE {' AND '.join(clauses)} ORDER BY m.meter_type DESC, m.account_number LIMIT %s",
                    (*params, max(1, min(limit, 1000))),
                )
                rows = cur.fetchall()
                out = []
                for mid, account, serial, brand, mtype, zone in rows:
                    item = {"meter_id": str(mid), "account_number": account, "serial_number": serial, "brand": brand,
                            "meter_type": mtype, "zone_name": zone}
                    if with_channels:
                        item["channels"] = _channels(cur, tenant_id, str(mid), mtype)
                    out.append(item)
    return out


_MANUAL_COLUMNS = ("id, meter_id, channel, value, read_at, read_by, previous_value, lower_confirmed, notes, client_id")


def _manual_row(r: tuple) -> dict:
    return {
        "manual_reading_id": str(r[0]), "meter_id": str(r[1]), "channel": r[2], "value": float(r[3]),
        "read_at": r[4].isoformat(), "read_by": r[5], "previous_value": float(r[6]) if r[6] is not None else None,
        "lower_confirmed": r[7], "notes": r[8], "client_id": str(r[9]) if r[9] else None,
    }


def record_manual_meter_reading(
    conn: psycopg.Connection,
    tenant_id: str,
    meter_id: str,
    channel: str,
    value: float,
    read_at: datetime,
    read_by: str,
    lower_confirmed: bool = False,
    notes: str | None = None,
    client_id: str | None = None,
) -> dict:
    _check_uuid(meter_id, "el medidor")
    _check_uuid(client_id, "el identificador del dispositivo")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                if client_id:
                    cur.execute(f"SELECT {_MANUAL_COLUMNS} FROM manual_meter_reading WHERE tenant_id = %s AND client_id = %s",
                                (tenant_id, client_id))
                    row = cur.fetchone()
                    if row:
                        return {**_manual_row(row), "duplicate": True, "delta": None}
                cur.execute("SELECT meter_type FROM meter WHERE id = %s AND tenant_id = %s", (meter_id, tenant_id))
                meter = cur.fetchone()
                if meter is None:
                    raise MeterNotFoundError(f"No existe el medidor {meter_id} para esta junta")
                channels = _channels(cur, tenant_id, meter_id, meter[0])
                known = {c["channel"]: c for c in channels}
                if channel not in known:
                    raise MeterNotFoundError(
                        f"El canal {channel!r} no corresponde a este medidor (válidos: {sorted(known) or 'ninguno conocido'})"
                    )
                # La anterior: la ultima lectura de ese canal ANTES del instante leido.
                cur.execute(
                    "SELECT value FROM raw_reading WHERE tenant_id = %s AND meter_id = %s AND channel = %s "
                    "AND \"timestamp\" < %s ORDER BY \"timestamp\" DESC LIMIT 1",
                    (tenant_id, meter_id, channel, read_at),
                )
                prev = cur.fetchone()
                previous = float(prev[0]) if prev else None
                check = check_register(previous, float(value), lower_confirmed)
                try:
                    with conn.transaction():
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value, source_quality) "
                            "VALUES (%s, %s, %s, %s, %s, 'manual')",
                            (tenant_id, meter_id, read_at, channel, value),
                        )
                except psycopg.errors.UniqueViolation:
                    raise MeterReadingConflictError("Ya hay una lectura de ese medidor y canal en ese mismo instante") from None
                cur.execute(
                    "INSERT INTO manual_meter_reading (tenant_id, meter_id, channel, value, read_at, read_by, previous_value, "
                    f"lower_confirmed, notes, client_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {_MANUAL_COLUMNS}",
                    (tenant_id, meter_id, channel, value, read_at, read_by, previous, check["went_down"],
                     (notes or "").strip() or None, client_id),
                )
                saved = _manual_row(cur.fetchone())
    return {**saved, "duplicate": False, "delta": check["delta"]}


def list_manual_meter_readings(
    conn: psycopg.Connection, tenant_id: str, meter_id: str | None = None, since: datetime | None = None, limit: int = 200,
) -> list[dict]:
    _check_uuid(meter_id, "el medidor")
    clauses, params = ["r.tenant_id = %s"], [tenant_id]
    if meter_id:
        clauses.append("r.meter_id = %s")
        params.append(meter_id)
    if since:
        clauses.append("r.read_at >= %s")
        params.append(since)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join('r.' + c.strip() for c in _MANUAL_COLUMNS.split(','))}, m.account_number, m.meter_type "
                    "FROM manual_meter_reading r JOIN meter m ON m.id = r.meter_id "
                    f"WHERE {' AND '.join(clauses)} ORDER BY r.read_at DESC LIMIT %s",
                    (*params, max(1, min(limit, 1000))),
                )
                return [{**_manual_row(r[:10]), "account_number": r[10], "meter_type": r[11]} for r in cur.fetchall()]
