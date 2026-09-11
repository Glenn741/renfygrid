"""HES / Ingesta -- flota por marca/modelo y capa de agregacion (Sprint C7,
`docs/06-benchmark-e2e-y-brechas.md` G4/G5): el esquema ya tenia
`meter.brand`/`meter.model` desde Sprint 1 y `gateway`/`meter_gateway`
desde Sprint 0-1 -- esto no agrega ninguna tabla, solo las agrega en dos
vistas que nunca existieron.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def fleet_summary(conn: psycopg.Connection, tenant_id: str, stale_after_seconds: int = 3600) -> list[dict]:
    """Por marca/modelo (G4): total de medidores, cuantos estan `active`
    (status), y de esos cuantos reportaron dentro de `stale_after_seconds`
    -- mismo criterio de "caido" que `observability.ingestion_metrics`
    (F34), no uno inventado aparte."""
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
