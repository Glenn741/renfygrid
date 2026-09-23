"""Mapa de medidores + distribucion estadistica real de la medicion + vista
de sectores hidraulicos (2026-09-15, a pedido explicito del usuario:
"agrega mas KPIs con algo grafico para mostrar la distribucion estadistica
de los datos de medicion. Incluye un mapa de medidores para ver capas...
Ademas, recuerda que un medidor puede ser MICRO... o MACRO...").

Grounded en el estandar real de DMA/smart metering (ver docs/05-ejecucion.md
2026-09-15 -- KROHNE "Equipping DMAs with electromagnetic water meters",
McCrometer "Using Flow Meters To Reduce Non-Revenue Water"): un
macro-medidor mide el INFLOW TOTAL de un sector hidraulico (DMA) en su
punto de entrada (tipicamente junto a una valvula reguladora de presion);
los micro-medidores miden el consumo autorizado individual dentro de ese
mismo sector. La diferencia entre ambos es el NRW real de ese sector --
`sector_summary` calcula esto con datos REALES de `validated_reading`, no
un balance declarado a mano (a diferencia de `network_balance`, que sigue
siendo la fuente de verdad official -- esto es una vista operativa rapida
sobre la medicion cruda, no reemplaza Balance de Red)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "consumption"))

import psycopg  # noqa: E402

from consumption_engine import compute_consumption  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

CONSUMPTION_WINDOW_DAYS = 30
# Bandas de consumo (m3 en 30 dias) -- genericas para separar residencial
# bajo/tipico/alto y comercial, mismo criterio que las bandas genericas ya
# usadas en VEE (docs/05-ejecucion.md Sprint C11-3: sin benchmark propio del
# sector todavia, se documenta el criterio en vez de esconderlo).
CONSUMPTION_BUCKETS = [(0, 10), (10, 20), (20, 40), (40, 80), (80, 150), (150, None)]


def meters_geojson(conn: psycopg.Connection, tenant_id: str, stale_after_seconds: int | None) -> dict:
    """FeatureCollection real -- cada medidor georreferenciado, con las
    propiedades que alimentan las capas tematicas del mapa (estado en
    linea/caido, tipo micro/macro, marca, sector). Un medidor sin
    `geometry` real simplemente no aparece (nunca una coordenada
    inventada)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, m.account_number, m.brand, m.model, m.meter_type, m.status, m.geometry, "
                    "  z.name AS zone_name, "
                    "  (SELECT max(r.\"timestamp\") FROM raw_reading r WHERE r.meter_id = m.id) AS last_reading_at, "
                    "  (SELECT count(*) FROM validated_reading vr WHERE vr.meter_id = m.id AND vr.is_valid = false) AS invalid_count "
                    "FROM meter m LEFT JOIN network_zone z ON z.id = m.zone_id "
                    "WHERE m.geometry IS NOT NULL"
                )
                rows = cur.fetchall()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    features = []
    for meter_id, account_number, brand, model, meter_type, status, geometry, zone_name, last_reading_at, invalid_count in rows:
        if stale_after_seconds is None:
            is_stale = None
        else:
            is_stale = last_reading_at is None or (now - last_reading_at).total_seconds() > stale_after_seconds
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "meter_id": str(meter_id),
                "account_number": account_number,
                "brand": brand,
                "model": model,
                "meter_type": meter_type,
                "status": status,
                "zone_name": zone_name,
                "is_stale": is_stale,
                "invalid_count": invalid_count,
                "last_reading_at": last_reading_at.isoformat() if last_reading_at else None,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def consumption_distribution(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Distribucion estadistica real del consumo de los ultimos
    `CONSUMPTION_WINDOW_DAYS` -- cierre menos apertura por medidor MICRO
    (mismo criterio real que `consumption_engine.compute_consumption`),
    agrupada en bandas para un histograma. Nunca un promedio inventado: un
    medidor sin al menos 2 lecturas reales/estimadas en la ventana
    simplemente no entra en el conteo."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT vr.meter_id, "
                    "  (array_agg(vr.value ORDER BY vr.\"timestamp\" ASC))[1] AS opening, "
                    "  (array_agg(vr.value ORDER BY vr.\"timestamp\" DESC))[1] AS closing "
                    "FROM validated_reading vr JOIN meter m ON m.id = vr.meter_id "
                    "WHERE vr.tenant_id = %s AND m.meter_type = 'micro' AND vr.is_valid = true "
                    "  AND vr.\"timestamp\" > now() - (%s || ' days')::interval "
                    "GROUP BY vr.meter_id HAVING count(*) >= 2",
                    (tenant_id, CONSUMPTION_WINDOW_DAYS),
                )
                rows = cur.fetchall()

    consumptions = [compute_consumption(float(opening), float(closing)) for _, opening, closing in rows]
    buckets = []
    for low, high in CONSUMPTION_BUCKETS:
        label = f"{low}-{high} m³" if high is not None else f">{low} m³"
        count = sum(1 for c in consumptions if c >= low and (high is None or c < high))
        buckets.append({"label": label, "count": count})

    return {
        "window_days": CONSUMPTION_WINDOW_DAYS,
        "meters_with_data": len(consumptions),
        "avg_m3": round(sum(consumptions) / len(consumptions), 2) if consumptions else None,
        "min_m3": round(min(consumptions), 2) if consumptions else None,
        "max_m3": round(max(consumptions), 2) if consumptions else None,
        "buckets": buckets,
    }


def exception_rate_by_brand(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """% de excepciones reales por marca -- para comparar calidad de dato
    entre fabricantes (una senal real de operacion, no solo un adorno)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.brand, count(*) FILTER (WHERE vr.source = 'real'), "
                    "  count(*) FILTER (WHERE vr.source = 'real' AND vr.is_valid = false) "
                    "FROM validated_reading vr JOIN meter m ON m.id = vr.meter_id "
                    "WHERE vr.tenant_id = %s GROUP BY m.brand ORDER BY m.brand",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [
        {
            "brand": brand, "total_processed": total, "invalid_count": invalid,
            "exception_rate_pct": round(100.0 * invalid / total, 2) if total else None,
        }
        for brand, total, invalid in rows
    ]


def sector_summary(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Por sector hidraulico (DMA) con un macro-medidor real: inflow del
    macro vs. suma de consumo de los micro del mismo sector -- NRW
    operativo real, calculado sobre medicion cruda (distinto de
    `network_balance`, que sigue siendo la fuente oficial declarada --
    esto es una vista rapida derivada del HES, no la reemplaza).

    A diferencia de `consumption_distribution` (ventana movil de 30 dias,
    valida para un histograma de habitos de consumo), esto usa TODO el
    historial disponible de cada medidor: comparar macro vs. micro en una
    ventana corta es estadisticamente ruidoso (el macro y cada micro no
    llegan exactamente en los mismos instantes, sus huecos/estimaciones
    no coinciden 1 a 1) -- el NRW real de un sector es una metrica de
    periodo largo por diseno (AWWA M36 recomienda balances mensuales o
    mas, nunca uno de unos pocos dias)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT z.id, z.name, "
                    "  (SELECT m.id FROM meter m WHERE m.zone_id = z.id AND m.meter_type = 'macro' LIMIT 1) AS macro_meter_id, "
                    "  (SELECT count(*) FROM meter m WHERE m.zone_id = z.id AND m.meter_type = 'micro') AS micro_count "
                    "FROM network_zone z WHERE z.tenant_id = %s ORDER BY z.name",
                    (tenant_id,),
                )
                zones = cur.fetchall()

                def _window_delta(meter_id: str) -> float | None:
                    cur.execute(
                        "SELECT (array_agg(value ORDER BY \"timestamp\" ASC))[1], (array_agg(value ORDER BY \"timestamp\" DESC))[1] "
                        "FROM validated_reading WHERE tenant_id = %s AND meter_id = %s AND is_valid = true",
                        (tenant_id, meter_id),
                    )
                    row = cur.fetchone()
                    if row is None or row[0] is None or row[1] is None:
                        return None
                    return compute_consumption(float(row[0]), float(row[1]))

                result = []
                for zone_id, zone_name, macro_meter_id, micro_count in zones:
                    macro_volume = _window_delta(str(macro_meter_id)) if macro_meter_id else None
                    cur.execute(
                        "SELECT id FROM meter WHERE tenant_id = %s AND zone_id = %s AND meter_type = 'micro'",
                        (tenant_id, zone_id),
                    )
                    micro_ids = [str(r[0]) for r in cur.fetchall()]
                    micro_deltas = [d for d in (_window_delta(mid) for mid in micro_ids) if d is not None]
                    micro_total = sum(micro_deltas) if micro_deltas else None
                    nrw_pct = None
                    if macro_volume is not None and micro_total is not None and macro_volume > 0:
                        nrw_pct = round(100.0 * (macro_volume - micro_total) / macro_volume, 1)
                    result.append({
                        "zone_id": str(zone_id), "zone_name": zone_name,
                        "macro_meter_id": str(macro_meter_id) if macro_meter_id else None,
                        "micro_count": micro_count, "micro_with_data": len(micro_deltas),
                        "macro_volume_m3": round(macro_volume, 1) if macro_volume is not None else None,
                        "micro_total_m3": round(micro_total, 1) if micro_total is not None else None,
                        "nrw_pct": nrw_pct,
                        "window": "todo el historial disponible",
                    })
    return result
