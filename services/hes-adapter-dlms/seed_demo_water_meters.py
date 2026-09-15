"""Siembra un HES real y completo -- 100 medidores de ACUEDUCTO (marcas
reales de AMI de agua: Sensus, Badger Meter, Neptune, Diehl Metering,
Kamstrup), reportando cada 4 horas durante 6 meses, a pedido explicito del
usuario ("enriquecelo con suficientes datos para que refleje todo lo que
maneja un HES"). Deja datos PERSISTENTES (no se borran solos), igual que
`seed_demo_data.py`.

Escenario exacto pedido:
  - 100 medidores, marcas distintas, canal `volume_m3` (registro
    acumulado -- igual criterio que un registro DLMS de energia: nunca
    "resetea", el consumo real sale de la diferencia entre dos lecturas,
    ver consumption_engine.py).
  - Un intervalo esperado cada 4h durante 6 meses (~1095 intervalos por
    medidor).
  - 10% de los intervalos con problema: 9% NO LLEGAN (sin fila en
    raw_reading -- hueco real), 1% llegan con un valor INCONSISTENTE
    (fuera de rango de verdad, no una etiqueta -- un valor absurdo tipo
    error de comunicacion/registro, capturado por una regla `range` real).
  - El VEE procesa automaticamente el 90% de ese 10% (el 9% que faltaba
    por completo) -- estimacion real por interpolacion lineal
    (`vee_engine.estimate_gap`, F16/F17), igual que como ya hace el
    pipeline real (`run_vee_estimation.py`), solo que en bloque en vez de
    lectura por lectura (100 medidores x 6 meses via el poller real
    tardaria dias -- este script usa las mismas funciones puras del
    motor, no un pipeline distinto).
  - El otro 10% de ese 10% (el 1% inconsistente) queda como excepcion
    real (`is_valid=false`) con un valor SUGERIDO calculado (misma
    interpolacion, solo que puesto en `validation_notes` como sugerencia
    -- el valor guardado sigue siendo el recibido, tal cual llego,
    porque corregirlo de verdad es tarea de un supervisor via
    `manual_edit.edit_reading`, no de este script).

No usa el simulador DLMS real ni el poller real por lectura -- a esta
escala (100 x 1095 = ~109500 intervalos) seria horas de I/O de socket
real por nada; en cambio arma los datos con las mismas funciones puras
del motor VEE real (`validate_reading`, `detect_gaps`, `estimate_gap`) y
los inserta en bloque (COPY), preservando exactamente la misma semantica
que si hubieran llegado uno por uno por el pipeline real.

Uso:
    python seed_demo_water_meters.py "<DSN>" "<TENANT_ID>"
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vee-engine"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from manual_edit import edit_reading  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from vee_engine import Gap, detect_gaps, estimate_gap, validate_reading  # noqa: E402
from vee_rules_admin import create_vee_rule  # noqa: E402

CHANNEL = "volume_m3"
INTERVAL_HOURS = 4
INTERVAL_SECONDS = INTERVAL_HOURS * 3600
MONTHS = 6
N_METERS = 100
N_GATEWAYS = 8
RANGE_MAX_M3 = 10_000.0  # tope de sanidad del registro acumulado -- ver docstring

BRANDS: list[tuple[str, list[str]]] = [
    ("Sensus", ["iPERL", "OMNI T2"]),
    ("Badger Meter", ["E-Series Ultrasonic", "M2000"]),
    ("Neptune", ["R900i", "E-Coder"]),
    ("Diehl Metering", ["IZAR RC 866", "HYDRUS"]),
    ("Kamstrup", ["flowIQ 2200", "MULTICAL 21"]),
]

random.seed(20260915)  # reproducible -- misma corrida, mismos numeros, para poder re-verificar


def _aligned_now() -> datetime:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(hours=now.hour % INTERVAL_HOURS)


def _diurnal_factor(hour: int) -> float:
    """Perfil tipico de consumo domestico/comercial de agua -- picos en la
    manana y la noche, valle en la madrugada (bucket de 4h que contiene
    esa hora)."""
    bucket = hour // INTERVAL_HOURS
    return [0.45, 1.35, 1.05, 0.85, 1.45, 0.85][bucket]


def run(dsn: str, tenant_id: str) -> int:
    now = _aligned_now()
    start = now - timedelta(days=30 * MONTHS)
    n_intervals = int((now - start).total_seconds() // INTERVAL_SECONDS) + 1
    print(f"Rango: {start.isoformat()} -> {now.isoformat()} ({n_intervals} intervalos por medidor)")

    with psycopg.connect(dsn, autocommit=True) as conn:
        # Reglas VEE reales -- unica fuente de los limites/metodo, nunca fijos en el motor.
        range_rule_id = create_vee_rule(
            conn, tenant_id, "range", {"channel": CHANNEL, "min": 0, "max": RANGE_MAX_M3}, priority=100
        )
        missing_rule_id = create_vee_rule(
            conn, tenant_id, "missing_interval",
            {"channel": CHANNEL, "expected_interval_seconds": INTERVAL_SECONDS, "tolerance_seconds": 600, "estimation_method": "linear_interpolation"},
            priority=100,
        )
        rules = [{"id": range_rule_id, "type": "range", "params": {"channel": CHANNEL, "min": 0, "max": RANGE_MAX_M3}, "priority": 100}]
        print("vee_rule range:", range_rule_id, "| missing_interval:", missing_rule_id)

        gateway_ids = [
            register_gateway(conn, tenant_id, f"Concentrador Acueducto {i + 1:02d}", "TCP", {"host": f"10.60.{i + 1}.1", "port": 4059, "client_address": 16})
            for i in range(N_GATEWAYS)
        ]
        print(f"{len(gateway_ids)} concentradores creados")

        meters: list[dict] = []
        for m in range(N_METERS):
            brand, models = BRANDS[m % len(BRANDS)]
            model = models[(m // len(BRANDS)) % len(models)]
            account_number = f"ACC-AQ-{m + 1:04d}"
            serial = f"SN-{brand[:3].upper()}-{m + 1:05d}"
            city = "Cali" if m % 5 == 0 else "Bogotá"
            meter_id = register_meter(
                conn, tenant_id, account_number, serial, brand, "DLMS_COSEM", model=model,
                location={"city": city, "note": "medidor de acueducto, ilustrativo"},
            )
            gw_id = gateway_ids[m % N_GATEWAYS]
            link_meter_to_gateway(conn, tenant_id, meter_id, gw_id, server_address=(m // N_GATEWAYS) + 1)
            segment = "commercial" if m % 5 == 4 else "residential"
            meters.append({
                "meter_id": meter_id, "account_number": account_number, "brand": brand, "segment": segment,
                "daily_avg": random.uniform(2.0, 6.0) if segment == "commercial" else random.uniform(0.3, 0.9),
                "start_cumulative": random.uniform(300.0, 3000.0),
            })
        print(f"{len(meters)} medidores registrados ({', '.join(sorted({b for _, models in BRANDS for b in [_]}))})")

        raw_rows: list[tuple] = []
        val_rows: list[tuple] = []  # (tenant_id, meter_id, ts, value, source, channel, is_valid, vee_rule_id, notes, created_at)
        recent_events: list[tuple] = []  # meter_event solo para las ultimas 48h (lo unico que los paneles de 24h miran)
        edit_candidates: list[tuple[str, str, datetime, float, float]] = []  # (meter_id, account_number, ts, bad_value, suggested)
        recent_cutoff = now - timedelta(hours=48)

        n_missing_total = n_bad_total = n_normal_total = 0

        for meter in meters:
            meter_id = meter["meter_id"]
            cumulative = meter["start_cumulative"]
            timestamps: list[datetime] = []
            true_values: list[float] = []
            for i in range(n_intervals):
                ts = start + timedelta(hours=INTERVAL_HOURS * i)
                delta = (meter["daily_avg"] / 6.0) * _diurnal_factor(ts.hour) * random.uniform(0.8, 1.2)
                cumulative += delta
                timestamps.append(ts)
                true_values.append(cumulative)

            stored_value: list[float | None] = [None] * n_intervals
            for i in range(n_intervals):
                r = random.random()
                if r < 0.09:
                    n_missing_total += 1
                    continue  # no llega -- sin fila en raw_reading, hueco real
                if r < 0.10:
                    n_bad_total += 1
                    stored_value[i] = round(true_values[i] * random.uniform(60, 400), 3)  # error de comunicacion/registro real
                else:
                    n_normal_total += 1
                    stored_value[i] = round(true_values[i], 3)

            for i in range(n_intervals):
                if stored_value[i] is None:
                    continue
                raw_rows.append((tenant_id, meter_id, timestamps[i], CHANNEL, stored_value[i], "real"))
                if timestamps[i] >= recent_cutoff:
                    # La comunicacion en si fue exitosa (llego una respuesta) --
                    # que el VALOR resulte invalido es un problema de calidad de
                    # dato, no de comunicacion; son dos cosas distintas a proposito.
                    recent_events.append((
                        tenant_id, meter_id, "communication_success", timestamps[i], "info",
                        {"operation": "poller_read", "duration_ms": random.randint(120, 900), "error": None},
                    ))
            for i in range(n_intervals):
                if stored_value[i] is None and timestamps[i] >= recent_cutoff:
                    recent_events.append((
                        tenant_id, meter_id, "communication_failure", timestamps[i], "warning",
                        {"operation": "poller_read", "duration_ms": None, "error": "timeout: sin respuesta del medidor"},
                    ))

            present_seq = [(timestamps[i], stored_value[i]) for i in range(n_intervals) if stored_value[i] is not None]
            for idx, (ts, val) in enumerate(present_seq):
                vr = validate_reading(val, CHANNEL, rules)
                notes = vr.notes
                if not vr.is_valid and 0 < idx < len(present_seq) - 1:
                    prev_ts, prev_val = present_seq[idx - 1]
                    next_ts, next_val = present_seq[idx + 1]
                    frac = (ts - prev_ts).total_seconds() / (next_ts - prev_ts).total_seconds()
                    suggested = prev_val + (next_val - prev_val) * frac
                    notes = f"{notes} -- valor sugerido por interpolación: {suggested:.2f} m³ (pendiente de validación de un supervisor)"
                    edit_candidates.append((meter_id, meter["account_number"], ts, val, suggested))
                val_rows.append((tenant_id, meter_id, ts, val, "real", CHANNEL, vr.is_valid, vr.vee_rule_id, notes, ts + timedelta(minutes=random.randint(1, 8))))

            gaps = detect_gaps(present_seq, INTERVAL_SECONDS, tolerance_seconds=600)
            for gap in gaps:
                for p in estimate_gap(gap, INTERVAL_SECONDS, "linear_interpolation"):
                    val_rows.append((
                        tenant_id, meter_id, p.timestamp, round(p.value, 3), "estimated", CHANNEL, True, missing_rule_id,
                        "Estimado automáticamente (interpolación lineal) por intervalo faltante",
                        p.timestamp + timedelta(minutes=random.randint(1, 8)),
                    ))

        print(f"Generado: {n_normal_total} normales, {n_missing_total} faltantes, {n_bad_total} inconsistentes "
              f"(total {n_normal_total + n_missing_total + n_bad_total} intervalos)")
        print(f"raw_reading a insertar: {len(raw_rows)}; validated_reading a insertar: {len(val_rows)}; eventos recientes (48h): {len(recent_events)}")

        # NOTA real encontrada al correr esto: Postgres rechaza `COPY FROM`
        # contra una tabla con RLS activo para un rol no-superusuario
        # ("FeatureNotSupported ... Use INSERT statements instead") -- no es
        # una limitacion de este proyecto, es de Postgres mismo. `executemany`
        # con insercion por lotes es el camino real a esta escala.
        def _bulk_insert(sql: str, rows: list[tuple], batch_size: int = 5000) -> None:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        for start_i in range(0, len(rows), batch_size):
                            cur.executemany(sql, rows[start_i:start_i + batch_size])

        _bulk_insert(
            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value, source_quality) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            raw_rows,
        )
        print("raw_reading insertado.")

        _bulk_insert(
            "INSERT INTO validated_reading (tenant_id, meter_id, \"timestamp\", value, source, channel, is_valid, vee_rule_id, validation_notes, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            val_rows,
        )
        print("validated_reading insertado.")

        _bulk_insert(
            "INSERT INTO meter_event (tenant_id, meter_id, type, \"timestamp\", severity, detail) VALUES (%s, %s, %s, %s, %s, %s)",
            [(tid, mid, etype, ets, sev, psycopg.types.json.Json(detail)) for tid, mid, etype, ets, sev, detail in recent_events],
        )
        print("meter_event (48h recientes) insertado.")

        # Unas pocas alarmas reales para que "Eventos y alarmas" no se vea solo de comunicacion.
        alarm_meters = random.sample(meters, 4)
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    for meter in alarm_meters:
                        cur.execute(
                            "INSERT INTO meter_event (tenant_id, meter_id, type, \"timestamp\", severity, detail) "
                            "VALUES (%s, %s, 'meter_alarm', %s, %s, %s)",
                            (
                                tenant_id, meter["meter_id"], now - timedelta(hours=random.randint(1, 36)),
                                random.choice(["warning", "critical"]),
                                psycopg.types.json.Json({"event_code": random.choice([3, 7, 12]), "severity_code": 1}),
                            ),
                        )
        print(f"{len(alarm_meters)} alarmas reales sembradas")

        # Resolver a mano (auditado, real) las excepciones mas ANTIGUAS -- para
        # que "Edición manual" tenga historial y las mas RECIENTES sigan
        # pendientes de verdad (que es justo el escenario pedido).
        edit_candidates.sort(key=lambda c: c[2])
        to_resolve = edit_candidates[:6]
        editors = ["ana.martinez@renfygrid.demo", "carlos.rojas@renfygrid.demo"]
        for meter_id, account_number, ts, bad_value, suggested in to_resolve:
            edit_reading(
                conn, tenant_id, meter_id, CHANNEL, ts, round(suggested, 3),
                random.choice(editors), "Valor corregido tras inspección de campo -- coincide con el consumo histórico del predio",
            )
        print(f"{len(to_resolve)} excepciones antiguas resueltas a mano (historial real de Edición manual); "
              f"{len(edit_candidates) - len(to_resolve)} excepciones recientes siguen pendientes de validación")

    print("\nListo. HES de acueducto sembrado: 100 medidores, 6 meses, 4h de intervalo, 10% con problema real.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2]))
