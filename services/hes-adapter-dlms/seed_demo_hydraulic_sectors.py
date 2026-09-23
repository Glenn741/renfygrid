"""Agrupa los 100 medidores de acueducto ya sembrados (`seed_demo_water_
meters.py`) en 3 sectores hidraulicos reales (DMA) sobre el barrio San
Fernando, Cali -- y crea un MACRO-medidor real por sector, a pedido
explicito del usuario: "un medidor puede ser MICRO, de un inmueble, o
MACRO de una estacion reguladora de presion en la red (o sector
hidraulico). Por lo tanto deben poder clasificarse. Agrupa los medidores
en 3 sectores hidraulicos y crea un macro medidor para cada sector."

Grounded en el estandar real de DMA/smart metering (ver docs/05-ejecucion.md
2026-09-15 -- KROHNE, McCrometer: el macro-medidor mide el INFLOW TOTAL del
sector en su punto de entrada, tipicamente junto a una valvula reguladora
de presion; los micro-medidores miden el consumo autorizado individual
dentro de ese mismo sector -- la diferencia es el NRW real de ese sector).

Coordenadas reales (ilustrativas, no un catastro oficial) del barrio San
Fernando y el adyacente Tequendama-La Selva, sur-centro de Cali -- 3
sub-sectores con centroides reales distintos, cada uno con su
macro-medidor en un punto de "entrada" plausible (junto a la valvula
reguladora), separado del racimo de micro-medidores.

Ademas: genera la historia de lecturas del macro-medidor (misma cadencia
de 4h/6 meses, pero con MUCHA mayor confiabilidad que un micro-medidor --
es infraestructura critica, con mantenimiento prioritario en cualquier
utility real) de forma consistente con el consumo REAL ya sembrado de sus
micro-medidores + un NRW real distinto por sector (15-25%), y somete un
balance real (`network_balance`, Top-Down) para cada sector -- integracion
real con Balance de Red, no dos numeros sueltos.

Uso:
    python seed_demo_hydraulic_sectors.py "<DSN>" "<TENANT_ID>"
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vee-engine"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-balance"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "consumption"))

import psycopg  # noqa: E402

from balance_service import register_zone, submit_balance  # noqa: E402
from consumption_engine import compute_consumption  # noqa: E402
from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from vee_engine import detect_gaps, estimate_gap, validate_reading  # noqa: E402
from vee_rules_admin import create_vee_rule  # noqa: E402

CHANNEL = "volume_m3"
# Canal PROPIO para los macro-medidores (no reutiliza "volume_m3"): un
# medidor de bloque acumula un volumen ordenes de magnitud mayor que un
# medidor individual -- reutilizar el mismo canal significaria reutilizar
# (o pisar) la regla de rango pensada para un micro-medidor, marcando
# como "invalidas" lecturas de macro perfectamente reales solo por ser
# grandes. Canal distinto = regla de rango distinta, sin ambiguedad.
MACRO_CHANNEL = "volume_m3_bulk"
MACRO_RANGE_MAX_M3 = 5_000_000.0
INTERVAL_HOURS = 4
INTERVAL_SECONDS = INTERVAL_HOURS * 3600
MONTHS = 6

# 3 sectores reales dentro/adyacentes a San Fernando, Cali (ilustrativo,
# no un catastro oficial -- ver docstring del modulo).
SECTORS = [
    {"name": "DMA San Fernando Viejo (Cali, ilustrativo)", "center": (-76.5430, 3.4390), "macro_offset": (-0.0015, 0.0020), "nrw_pct": 16.0},
    {"name": "DMA San Fernando Nuevo (Cali, ilustrativo)", "center": (-76.5390, 3.4360), "macro_offset": (0.0018, -0.0012), "nrw_pct": 21.0},
    {"name": "DMA Tequendama - La Selva (Cali, ilustrativo)", "center": (-76.5460, 3.4330), "macro_offset": (0.0012, 0.0018), "nrw_pct": 24.0},
]

random.seed(20260915)


def _scatter(center: tuple[float, float], spread_deg: float = 0.0025) -> list[float]:
    lon, lat = center
    return [lon + random.uniform(-spread_deg, spread_deg), lat + random.uniform(-spread_deg, spread_deg)]


def _diurnal_factor(hour: int) -> float:
    bucket = hour // INTERVAL_HOURS
    return [0.45, 1.35, 1.05, 0.85, 1.45, 0.85][bucket]


def _aligned_now() -> datetime:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(hours=now.hour % INTERVAL_HOURS)


def run(dsn: str, tenant_id: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM meter WHERE tenant_id = %s AND account_number LIKE 'ACC-AQ-%%' AND meter_type = 'micro' ORDER BY account_number",
                        (tenant_id,),
                    )
                    micro_ids = [str(r[0]) for r in cur.fetchall()]
        if not micro_ids:
            print("No hay medidores 'ACC-AQ-%' -- correr primero seed_demo_water_meters.py")
            return 1
        print(f"{len(micro_ids)} micro-medidores encontrados para repartir en {len(SECTORS)} sectores")

        # 1 gateway propio para los macro-medidores (infraestructura critica,
        # comunicacion aparte de la flota residencial/comercial).
        macro_gateway_id = register_gateway(conn, tenant_id, "Concentrador Sectores Hidráulicos", "TCP", {"host": "10.60.90.1", "port": 4059, "client_address": 16})

        # Reglas VEE reales y PROPIAS del canal macro (nunca reutilizar la
        # regla del canal micro -- ver comentario en MACRO_CHANNEL).
        macro_range_rule_id = create_vee_rule(
            conn, tenant_id, "range", {"channel": MACRO_CHANNEL, "min": 0, "max": MACRO_RANGE_MAX_M3}, priority=100
        )
        macro_missing_rule_id = create_vee_rule(
            conn, tenant_id, "missing_interval",
            {"channel": MACRO_CHANNEL, "expected_interval_seconds": INTERVAL_SECONDS, "tolerance_seconds": 600, "estimation_method": "linear_interpolation"},
            priority=100,
        )
        macro_rules = [{"id": macro_range_rule_id, "type": "range", "params": {"channel": MACRO_CHANNEL, "min": 0, "max": MACRO_RANGE_MAX_M3}, "priority": 100}]
        print(f"vee_rule macro range: {macro_range_rule_id} | missing_interval: {macro_missing_rule_id}")

        chunk_size = -(-len(micro_ids) // len(SECTORS))  # ceil
        now = _aligned_now()
        start = now - timedelta(days=30 * MONTHS)
        n_intervals = int((now - start).total_seconds() // INTERVAL_SECONDS) + 1

        for sector_idx, sector in enumerate(SECTORS):
            zone_id = register_zone(
                conn, tenant_id, sector["name"], "dma", data_source="renfygrid",
                network_length_km=round(random.uniform(4.0, 9.0), 1),
                num_connections=len(micro_ids) // len(SECTORS) * 15,  # 1 medidor por ~15 conexiones reales (mezcla de predios sin medidor propio en el barrio)
                avg_pressure_mca=round(random.uniform(28.0, 38.0), 1),
                nrw_threshold_pct=30.0,
                centroid_lon=sector["center"][0], centroid_lat=sector["center"][1],
            )
            sector_micro_ids = micro_ids[sector_idx * chunk_size: (sector_idx + 1) * chunk_size]
            print(f"\n=== {sector['name']} (zone_id={zone_id}) -- {len(sector_micro_ids)} micro-medidores ===")

            # Reubicar los micro-medidores del sector: zone_id + geometria real dispersa.
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        for meter_id in sector_micro_ids:
                            geom = {"type": "Point", "coordinates": _scatter(sector["center"])}
                            cur.execute(
                                "UPDATE meter SET zone_id = %s, geometry = %s WHERE id = %s AND tenant_id = %s",
                                (zone_id, psycopg.types.json.Json(geom), meter_id, tenant_id),
                            )

            # Consumo REAL total del sector en toda la ventana (6 meses) --
            # cierre menos apertura por medidor, sumado (mismo criterio real
            # de consumption_engine.compute_consumption).
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        total_micro = 0.0
                        meters_with_data = 0
                        for meter_id in sector_micro_ids:
                            cur.execute(
                                "SELECT (array_agg(value ORDER BY \"timestamp\" ASC))[1], (array_agg(value ORDER BY \"timestamp\" DESC))[1] "
                                "FROM validated_reading WHERE tenant_id = %s AND meter_id = %s AND is_valid = true",
                                (tenant_id, meter_id),
                            )
                            row = cur.fetchone()
                            if row and row[0] is not None and row[1] is not None:
                                total_micro += compute_consumption(float(row[0]), float(row[1]))
                                meters_with_data += 1
            print(f"Consumo micro real (6 meses, {meters_with_data} medidores con dato): {total_micro:.1f} m³")

            # Macro-medidor real: volumen total = consumo micro real * (1 + NRW del sector).
            nrw_fraction = sector["nrw_pct"] / 100.0
            macro_total_volume = total_micro / (1 - nrw_fraction)  # SIV tal que (SIV - consumo)/SIV = NRW
            macro_account = f"ACC-MACRO-{sector_idx + 1:02d}"
            macro_geom = {"type": "Point", "coordinates": [sector["center"][0] + sector["macro_offset"][0], sector["center"][1] + sector["macro_offset"][1]]}
            macro_meter_id = register_meter(
                conn, tenant_id, macro_account, f"SN-MACRO-{sector_idx + 1:03d}", "Sensus", "DLMS_COSEM", model="OMNI C2 (macro-medición)",
                location={"city": "Cali", "note": f"Macro-medidor de entrada -- {sector['name']}, junto a válvula reguladora de presión (ilustrativo)"},
                meter_type="macro", zone_id=zone_id, geometry=macro_geom,
            )
            link_meter_to_gateway(conn, tenant_id, macro_meter_id, macro_gateway_id, server_address=sector_idx + 1)
            print(f"Macro-medidor {macro_account} creado (meter_id={macro_meter_id}), volumen real objetivo (6m, NRW {sector['nrw_pct']}%): {macro_total_volume:.1f} m³")

            # Historia real de lecturas del macro -- alta confiabilidad
            # (infraestructura critica): 1% falta, 0.2% inconsistente.
            avg_delta = macro_total_volume / n_intervals
            cumulative = random.uniform(5000.0, 15000.0)  # macro-medidor con historia real de operacion previa
            timestamps: list[datetime] = []
            stored_value: list[float | None] = [None] * n_intervals
            for i in range(n_intervals):
                ts = start + timedelta(hours=INTERVAL_HOURS * i)
                timestamps.append(ts)
                cumulative += avg_delta * _diurnal_factor(ts.hour) * random.uniform(0.9, 1.1)
                r = random.random()
                if r < 0.01:
                    continue  # falta (raro -- macro con prioridad de mantenimiento real)
                if r < 0.012:
                    stored_value[i] = round(cumulative * random.uniform(50, 200), 3)  # inconsistente, tambien raro
                else:
                    stored_value[i] = round(cumulative, 3)

            raw_rows = [(tenant_id, macro_meter_id, timestamps[i], MACRO_CHANNEL, stored_value[i], "real") for i in range(n_intervals) if stored_value[i] is not None]
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value, source_quality) VALUES (%s, %s, %s, %s, %s, %s)",
                            raw_rows,
                        )

            present_seq = [(timestamps[i], stored_value[i]) for i in range(n_intervals) if stored_value[i] is not None]
            val_rows = []
            for ts, val in present_seq:
                vr = validate_reading(val, MACRO_CHANNEL, macro_rules)
                val_rows.append((tenant_id, macro_meter_id, ts, val, "real", MACRO_CHANNEL, vr.is_valid, vr.vee_rule_id, vr.notes, ts + timedelta(minutes=random.randint(1, 8))))
            for gap in detect_gaps(present_seq, INTERVAL_SECONDS, tolerance_seconds=600):
                for p in estimate_gap(gap, INTERVAL_SECONDS, "linear_interpolation"):
                    val_rows.append((tenant_id, macro_meter_id, p.timestamp, round(p.value, 3), "estimated", MACRO_CHANNEL, True, macro_missing_rule_id, "Estimado automáticamente (interpolación lineal) por intervalo faltante", p.timestamp + timedelta(minutes=random.randint(1, 8))))

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO validated_reading (tenant_id, meter_id, \"timestamp\", value, source, channel, is_valid, vee_rule_id, validation_notes, created_at) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            val_rows,
                        )
            print(f"Macro-medidor: {len(raw_rows)} lecturas reales, {len(val_rows)} filas validadas insertadas")

            # Balance real del sector (Top-Down) usando el macro como SIV y
            # el consumo micro real como facturado -- ultimo mes completo.
            period_end = date.today()
            period_start = period_end - timedelta(days=30)
            balance = submit_balance(
                conn, tenant_id, zone_id, period_start, period_end, "top_down",
                system_input_volume=round(macro_total_volume / (MONTHS * 30) * 30, 1),
                billed_metered_consumption=round(total_micro / (MONTHS * 30) * 30, 1),
            )
            print(f"Balance real del sector: NRW {balance['nrw_pct']}%, ILI {balance.get('ili')}, excede tope: {balance['exceeds_threshold']}")

    print("\nListo. 3 sectores hidráulicos reales con macro-medidor + balance real cada uno.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2]))
