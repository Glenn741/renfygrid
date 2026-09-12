"""Servicio de Balance de Red (Track B, Sprint B1/B1-2, F/E8) -- registro de
`network_zone` e ingesta de `network_balance`, propia o externa
(`data_source`, `01-planteamiento.md` SS3, principio de modularidad).

Toca BD (a diferencia de `network_balance_engine.py`, que es logica pura):
esta capa arma los `WaterBalanceInputs`/`ZoneInfrastructure` desde las
filas reales, llama al motor, y guarda el resultado -- nunca calcula una
formula ella misma.

Sprint B1-2 (sobre B1, a pedido del usuario -- "que le falta al B1?"):
NRW en volumen bruto no compara nada sin el tamano del sistema -- se
guarda tambien como `%` del System Input Volume, junto con un chequeo de
consistencia (`balance_check_pct`) y la comparacion contra un tope
regulatorio CONFIGURABLE por zona (`network_zone.nrw_threshold_pct`,
nunca un 30% fijo en codigo -- la CRA en Colombia usa ese numero, otro
regulador usa otro).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.range import Range  # noqa: E402

from network_balance_engine import (  # noqa: E402
    WaterBalanceInputs,
    ZoneInfrastructure,
    balance_check_pct,
    infrastructure_leakage_index,
    non_revenue_water,
    non_revenue_water_pct,
)
from renmeter_common.db import tenant_scope  # noqa: E402


class ZoneNotFoundError(LookupError):
    """No existe esa `network_zone` para este tenant."""


def register_zone(
    conn: psycopg.Connection,
    tenant_id: str,
    name: str,
    zone_type: str,
    data_source: str = "external",
    parent_zone_id: str | None = None,
    network_length_km: float | None = None,
    num_connections: int | None = None,
    avg_pressure_mca: float | None = None,
    avg_service_connection_length_km: float | None = None,
    nrw_threshold_pct: float | None = None,
    centroid_lat: float | None = None,
    centroid_lon: float | None = None,
) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO network_zone "
                    "(tenant_id, name, type, data_source, parent_zone_id, network_length_km, "
                    " num_connections, avg_pressure_mca, avg_service_connection_length_km, nrw_threshold_pct, "
                    " centroid_lat, centroid_lon) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        tenant_id, name, zone_type, data_source, parent_zone_id,
                        network_length_km, num_connections, avg_pressure_mca, avg_service_connection_length_km,
                        nrw_threshold_pct, centroid_lat, centroid_lon,
                    ),
                )
                (zone_id,) = cur.fetchone()
                return str(zone_id)


def list_zones(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, type, data_source, parent_zone_id, network_length_km, "
                    "       num_connections, avg_pressure_mca, avg_service_connection_length_km, nrw_threshold_pct, "
                    "       centroid_lat, centroid_lon "
                    "FROM network_zone WHERE tenant_id = %s ORDER BY name",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [
        {
            "zone_id": str(row[0]), "name": row[1], "type": row[2], "data_source": row[3],
            "parent_zone_id": str(row[4]) if row[4] else None,
            "network_length_km": float(row[5]) if row[5] is not None else None,
            "num_connections": row[6],
            "avg_pressure_mca": float(row[7]) if row[7] is not None else None,
            "avg_service_connection_length_km": float(row[8]) if row[8] is not None else None,
            "nrw_threshold_pct": float(row[9]) if row[9] is not None else None,
            "centroid_lat": float(row[10]) if row[10] is not None else None,
            "centroid_lon": float(row[11]) if row[11] is not None else None,
        }
        for row in rows
    ]


def _zone_row(conn: psycopg.Connection, tenant_id: str, zone_id: str) -> tuple[ZoneInfrastructure, float | None]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT network_length_km, num_connections, avg_pressure_mca, "
                    "       avg_service_connection_length_km, nrw_threshold_pct "
                    "FROM network_zone WHERE id = %s AND tenant_id = %s",
                    (zone_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise ZoneNotFoundError(f"No existe la zona {zone_id} para este tenant")
    length_km, num_connections, pressure, service_length_km, threshold_pct = row
    infra = ZoneInfrastructure(
        network_length_km=float(length_km) if length_km is not None else None,
        num_connections=num_connections,
        avg_pressure_mca=float(pressure) if pressure is not None else None,
        avg_service_connection_length_km=float(service_length_km) if service_length_km is not None else None,
    )
    return infra, (float(threshold_pct) if threshold_pct is not None else None)


def submit_balance(
    conn: psycopg.Connection,
    tenant_id: str,
    zone_id: str,
    period_start,
    period_end,
    method: str,
    system_input_volume: float,
    billed_metered_consumption: float = 0.0,
    billed_unbilled_consumption: float = 0.0,
    unbilled_authorized_consumption: float = 0.0,
    apparent_losses: float = 0.0,
    real_losses: float = 0.0,
) -> dict[str, Any]:
    """Ingesta de un periodo de balance (F/B1) -- propia (`data_source='renfygrid'`,
    calculada desde `validated_reading` en un sprint futuro) o externa (un
    CIS/HES de terceros que ya trae los 5 componentes de la matriz, sin
    medidor RenfyGrid de por medio, `01-planteamiento.md` SS3). Calcula y
    guarda `nrw`/`nrw_pct`/`ili`/`balance_check_pct`/`exceeds_threshold` al
    insertar -- nunca recalculados en cada lectura del panel."""
    zone_infra, threshold_pct = _zone_row(conn, tenant_id, zone_id)
    inputs = WaterBalanceInputs(
        system_input_volume=system_input_volume,
        billed_metered_consumption=billed_metered_consumption,
        billed_unbilled_consumption=billed_unbilled_consumption,
        unbilled_authorized_consumption=unbilled_authorized_consumption,
        apparent_losses=apparent_losses,
        real_losses=real_losses,
    )
    period_days = (period_end - period_start).days
    nrw = non_revenue_water(inputs)
    nrw_pct = non_revenue_water_pct(inputs)
    ili = infrastructure_leakage_index(inputs, zone_infra, period_days)
    check_pct = balance_check_pct(inputs)
    exceeds_threshold = (nrw_pct > threshold_pct) if (nrw_pct is not None and threshold_pct is not None) else None

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(max(version), 0) FROM network_balance "
                    "WHERE tenant_id = %s AND zone_id = %s AND period = %s",
                    (tenant_id, zone_id, Range(period_start, period_end, bounds="[)")),
                )
                (max_version,) = cur.fetchone()
                cur.execute(
                    "INSERT INTO network_balance "
                    "(tenant_id, zone_id, period, method, system_input_volume, billed_metered_consumption, "
                    " billed_unbilled_consumption, unbilled_authorized_consumption, apparent_losses, "
                    " real_losses, nrw, nrw_pct, ili, balance_check_pct, exceeds_threshold, version) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        tenant_id, zone_id, Range(period_start, period_end, bounds="[)"), method,
                        system_input_volume, billed_metered_consumption, billed_unbilled_consumption,
                        unbilled_authorized_consumption, apparent_losses, real_losses, nrw, nrw_pct, ili,
                        check_pct, exceeds_threshold, max_version + 1,
                    ),
                )
                (balance_id,) = cur.fetchone()

    return {
        "balance_id": str(balance_id), "nrw": nrw, "nrw_pct": nrw_pct, "ili": ili,
        "balance_check_pct": check_pct, "exceeds_threshold": exceeds_threshold, "version": max_version + 1,
    }


def list_balances(conn: psycopg.Connection, tenant_id: str, zone_id: str | None = None) -> list[dict]:
    """La version MAS RECIENTE por zona/periodo (un mismo periodo puede
    resubmitirse -- ej. una correccion del cliente -- sin perder el
    historial, mismo criterio que un reenvio corrige, no borra)."""
    clause = "AND b.zone_id = %s" if zone_id else ""
    params: tuple = (tenant_id, zone_id) if zone_id else (tenant_id,)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT DISTINCT ON (b.zone_id, b.period) "
                    f"       b.id, b.zone_id, z.name, b.period, b.method, b.system_input_volume, "
                    f"       b.billed_metered_consumption, b.billed_unbilled_consumption, "
                    f"       b.unbilled_authorized_consumption, b.apparent_losses, b.real_losses, "
                    f"       b.nrw, b.nrw_pct, b.ili, b.balance_check_pct, b.exceeds_threshold, "
                    f"       b.version, b.calculated_at "
                    f"FROM network_balance b JOIN network_zone z ON z.id = b.zone_id "
                    f"WHERE b.tenant_id = %s {clause} "
                    f"ORDER BY b.zone_id, b.period, b.version DESC",
                    params,
                )
                rows = cur.fetchall()
    return [
        {
            "balance_id": str(row[0]), "zone_id": str(row[1]), "zone_name": row[2], "period": str(row[3]),
            "method": row[4], "system_input_volume": float(row[5]), "billed_metered_consumption": float(row[6]),
            "billed_unbilled_consumption": float(row[7]), "unbilled_authorized_consumption": float(row[8]),
            "apparent_losses": float(row[9]), "real_losses": float(row[10]),
            "nrw": float(row[11]) if row[11] is not None else None,
            "nrw_pct": float(row[12]) if row[12] is not None else None,
            "ili": float(row[13]) if row[13] is not None else None,
            "balance_check_pct": float(row[14]) if row[14] is not None else None,
            "exceeds_threshold": row[15],
            "version": row[16], "calculated_at": row[17].isoformat(),
        }
        for row in rows
    ]


def balance_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Resumen a nivel de portafolio de zonas (Sprint B1-2) -- mismo patron
    de KPIs de resumen que el resto de paneles del proyecto: cuantas zonas
    hay, cuantas ya tienen un balance, el NRW% promedio de las mas
    recientes, cuantas exceden su tope regulatorio, y el peor ILI."""
    balances = list_balances(conn, tenant_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM network_zone WHERE tenant_id = %s", (tenant_id,))
                (total_zones,) = cur.fetchone()

    nrw_pcts = [b["nrw_pct"] for b in balances if b["nrw_pct"] is not None]
    ilis = [b["ili"] for b in balances if b["ili"] is not None]
    zones_over_threshold = [b for b in balances if b["exceeds_threshold"] is True]

    return {
        "total_zones": total_zones,
        "zones_with_balance": len(balances),
        "avg_nrw_pct": round(sum(nrw_pcts) / len(nrw_pcts), 1) if nrw_pcts else None,
        "worst_ili": round(max(ilis), 2) if ilis else None,
        "zones_exceeding_threshold": len(zones_over_threshold),
    }


def zones_geojson(conn: psycopg.Connection, tenant_id: str) -> dict:
    """GeoJSON real de las zonas (Track B, modulo de georreferenciacion,
    `docs/07-track-b-alcance-funcional.md` SS7) -- un `Point` por zona QUE
    TENGA `centroid_lat`/`centroid_lon` cargado (nunca un centroide
    inventado para las que no lo tienen -- simplemente no aparecen en el
    mapa). Cada feature trae el ultimo balance de esa zona si existe
    (`nrw_pct`/`ili`/`exceeds_threshold`), `None` si la zona aun no tiene
    ningun balance registrado."""
    zones = list_zones(conn, tenant_id)
    balances_by_zone = {b["zone_id"]: b for b in list_balances(conn, tenant_id)}

    features = []
    for zone in zones:
        if zone["centroid_lat"] is None or zone["centroid_lon"] is None:
            continue
        balance = balances_by_zone.get(zone["zone_id"])
        props = {
            "id": zone["zone_id"], "name": zone["name"], "type": zone["type"],
            "nrw_pct": balance["nrw_pct"] if balance else None,
            "ili": balance["ili"] if balance else None,
            "exceeds_threshold": balance["exceeds_threshold"] if balance else None,
            "nrw_threshold_pct": zone["nrw_threshold_pct"],
        }
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [zone["centroid_lon"], zone["centroid_lat"]]},
            "properties": props,
        })
    return {"type": "FeatureCollection", "features": features}
