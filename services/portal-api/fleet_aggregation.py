"""HES / Ingesta -- flota por marca/modelo y capa de agregacion (Sprint C7,
`docs/06-benchmark-e2e-y-brechas.md` G4/G5): el esquema ya tenia
`meter.brand`/`meter.model` desde Sprint 1 y `gateway`/`meter_gateway`
desde Sprint 0-1 -- esto no agrega ninguna tabla, solo las agrega en dos
vistas que nunca existieron.

Eventos/alarmas + cola de reintentos (Sprint C11-4): el usuario pidio el
mismo ejercicio de benchmark real que ya se hizo para VEE. Lo que aparece
consistente en HES de referencia (Genus/Kimbal/tblocks, ScienceDirect
"Data Concentrator", Eaton Brightlayer -- ver docs/05-ejecucion.md Sprint
C11-4 para las fuentes) es "operational dashboards, communication
statistics, meter reachability reports, and alarm management" -- eso ya
esta CONSTRUIDO en el backend desde F05 (alarmas reales via push DLMS,
`event_listener.py`) y F09 (auditoria de cada intento de comunicacion,
`communication_audit.py`), pero nunca se expuso en el Portal: no habia
forma de ver un evento/alarma real, ni el estado de la cola de reintentos
de F08 (Sprint C11). Nada de esto es un dato inventado -- son las mismas
filas reales que F05/F08/F09 ya escriben."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def fleet_summary(conn: psycopg.Connection, tenant_id: str, stale_after_seconds: int | None) -> list[dict]:
    """Por marca/modelo (G4): total de medidores, cuantos estan `active`
    (status), y de esos cuantos reportaron dentro de `stale_after_seconds`
    -- mismo criterio de "caido" que `observability.ingestion_metrics`
    (F34), no uno inventado aparte. `stale_after_seconds=None` (tenant sin
    configurar, ver `tenant_settings.py`): `reporting`/`reporting_pct`
    quedan `None` -- no hay ventana real contra la cual contar, "0
    reportando" seria un falso negativo fabricado."""
    if stale_after_seconds is None:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT m.brand, m.model, count(*) AS total, count(*) FILTER (WHERE m.status = 'active') AS active_status "
                        "FROM meter m GROUP BY m.brand, m.model ORDER BY m.brand, m.model"
                    )
                    rows_no_window = cur.fetchall()
        return [
            {"brand": brand, "model": model, "total": total, "active": active_status, "reporting": None, "reporting_pct": None}
            for brand, model, total, active_status in rows_no_window
        ]

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.brand, m.model, count(*) AS total, "
                    "  count(*) FILTER (WHERE m.status = 'active') AS active_status, "
                    "  count(*) FILTER (WHERE m.status = 'active' AND EXISTS ("
                    "    SELECT 1 FROM raw_reading r WHERE r.meter_id = m.id "
                    "    AND r.\"timestamp\" > now() - (%s || ' seconds')::interval"
                    "  )) AS reporting "
                    "FROM meter m "
                    "GROUP BY m.brand, m.model "
                    "ORDER BY m.brand, m.model",
                    (stale_after_seconds,),
                )
                rows = cur.fetchall()

    return [
        {
            "brand": brand,
            "model": model,
            "total": total,
            "active": active_status,
            "reporting": reporting,
            "reporting_pct": round(100.0 * reporting / total, 1) if total else 0.0,
        }
        for brand, model, total, active_status, reporting in rows
    ]


def gateway_summary(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Capa de agregacion (G5): cada concentrador agrupa medidores de una o
    varias marcas -- aca se ve cuantos, cuales marcas, y como viene su
    ultimo ciclo de polling real (F09, `meter_event` con
    `detail->>'operation' = 'poller_read'`)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT g.id, g.name, g.connection, "
                    "  count(DISTINCT mg.meter_id) AS meter_count, "
                    "  array_remove(array_agg(DISTINCT m.brand), NULL) AS brands, "
                    "  (SELECT max(e.\"timestamp\") FROM meter_event e "
                    "     JOIN meter_gateway mg2 ON mg2.meter_id = e.meter_id "
                    "     WHERE mg2.gateway_id = g.id AND e.detail->>'operation' = 'poller_read') AS last_poll_at, "
                    "  (SELECT count(*) FILTER (WHERE e.type = 'communication_success') FROM meter_event e "
                    "     JOIN meter_gateway mg3 ON mg3.meter_id = e.meter_id "
                    "     WHERE mg3.gateway_id = g.id AND e.detail->>'operation' = 'poller_read' "
                    "     AND e.\"timestamp\" > now() - interval '24 hours') AS success_24h, "
                    "  (SELECT count(*) FROM meter_event e "
                    "     JOIN meter_gateway mg4 ON mg4.meter_id = e.meter_id "
                    "     WHERE mg4.gateway_id = g.id AND e.detail->>'operation' = 'poller_read' "
                    "     AND e.\"timestamp\" > now() - interval '24 hours') AS total_24h "
                    "FROM gateway g "
                    "LEFT JOIN meter_gateway mg ON mg.gateway_id = g.id "
                    "LEFT JOIN meter m ON m.id = mg.meter_id "
                    "GROUP BY g.id, g.name, g.connection "
                    "ORDER BY g.name"
                )
                rows = cur.fetchall()

    result = []
    for gateway_id, name, connection, meter_count, brands, last_poll_at, success_24h, total_24h in rows:
        result.append(
            {
                "gateway_id": str(gateway_id),
                "name": name,
                "host": (connection or {}).get("host"),
                "port": (connection or {}).get("port"),
                "meter_count": meter_count,
                "brands": brands or [],
                "last_poll_at": last_poll_at.isoformat() if last_poll_at else None,
                # None (no informacion todavia), no 0 -- un concentrador sin
                # ciclos de polling en 24h no es lo mismo que uno con 0% de
                # exito, mismo fail-safe que F34.
                "success_rate_24h": round(100.0 * success_24h / total_24h, 1) if total_24h else None,
            }
        )
    return result


def event_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """KPIs de eventos/alarmas + salud de comunicacion en las ultimas 24h
    -- lo que un HES de referencia llama "alarm management" +
    "communication statistics" (ver docstring del modulo)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FILTER (WHERE type = 'meter_alarm'), "
                    "       count(*) FILTER (WHERE type = 'meter_alarm' AND severity = 'critical'), "
                    "       count(*) FILTER (WHERE type = 'communication_failure'), "
                    "       count(*) FILTER (WHERE type = 'communication_success') "
                    "FROM meter_event WHERE tenant_id = %s AND \"timestamp\" > now() - interval '24 hours'",
                    (tenant_id,),
                )
                alarms_24h, critical_alarms_24h, comm_failures_24h, comm_success_24h = cur.fetchone()

                cur.execute("SELECT count(*) FROM poller_retry_queue WHERE tenant_id = %s", (tenant_id,))
                (meters_in_retry_queue,) = cur.fetchone()

    comm_total_24h = comm_failures_24h + comm_success_24h
    return {
        "alarms_24h": alarms_24h,
        "critical_alarms_24h": critical_alarms_24h,
        "comm_failures_24h": comm_failures_24h,
        "comm_success_rate_24h": round(100.0 * comm_success_24h / comm_total_24h, 1) if comm_total_24h else None,
        "meters_in_retry_queue": meters_in_retry_queue,
    }


def list_meter_events(conn: psycopg.Connection, tenant_id: str, event_type: str | None = None, limit: int = 100) -> list[dict]:
    """Feed real de `meter_event` (F05 alarmas + F09 auditoria de
    comunicacion) con marca/modelo/concentrador para dar contexto -- antes
    invisible en el Portal salvo el conteo agregado de exito 24h."""
    clause = "AND e.type = %s" if event_type else ""
    params: tuple = (tenant_id, event_type, limit) if event_type else (tenant_id, limit)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT e.meter_id, m.account_number, m.brand, m.model, g.name, "
                    f"       e.type, e.severity, e.detail, e.\"timestamp\" "
                    f"FROM meter_event e "
                    f"JOIN meter m ON m.id = e.meter_id "
                    f"LEFT JOIN meter_gateway mg ON mg.meter_id = m.id "
                    f"LEFT JOIN gateway g ON g.id = mg.gateway_id "
                    f"WHERE e.tenant_id = %s {clause} "
                    f"ORDER BY e.\"timestamp\" DESC LIMIT %s",
                    params,
                )
                rows = cur.fetchall()

    return [
        {
            "meter_id": str(meter_id),
            "account_number": account_number,
            "brand": brand,
            "model": model,
            "gateway_name": gateway_name,
            "type": event_type_,
            "severity": severity,
            "detail": detail,
            "timestamp": timestamp.isoformat(),
        }
        for meter_id, account_number, brand, model, gateway_name, event_type_, severity, detail, timestamp in rows
    ]


def list_retry_queue(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Estado real de `poller_retry_queue` (F08, Sprint C11) -- que
    medidores estan en backoff ahora mismo, hace cuanto, y por que --
    antes construido solo en el backend, nunca visible."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT q.meter_id, m.account_number, m.brand, m.model, "
                    "       q.failure_count, q.next_retry_at, q.last_error, q.updated_at "
                    "FROM poller_retry_queue q JOIN meter m ON m.id = q.meter_id "
                    "WHERE q.tenant_id = %s ORDER BY q.next_retry_at",
                    (tenant_id,),
                )
                rows = cur.fetchall()

    return [
        {
            "meter_id": str(meter_id),
            "account_number": account_number,
            "brand": brand,
            "model": model,
            "failure_count": failure_count,
            "next_retry_at": next_retry_at.isoformat(),
            "last_error": last_error,
            "updated_at": updated_at.isoformat(),
        }
        for meter_id, account_number, brand, model, failure_count, next_retry_at, last_error, updated_at in rows
    ]
