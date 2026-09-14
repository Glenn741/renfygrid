"""Siembra datos de DEMOSTRACION reales y persistentes (no se borran al
terminar) en el tenant demo ya existente ("RenfyGrid Demo"), a pedido
explicito del usuario ("genera datos sample... simulalos sobre Cali y/o
Bogota") -- para que la funcionalidad del portal se vea con datos
completos, no vacia. Mismo patron que `seed_demo_assets.py`/
`seed_demo_networks.py`: todo por argumento (DSN/tenant), coordenadas
reales (las mismas del modelo hidraulico demo de Cali, `cali_tres_cruces_
dma.inp`), etiquetado "ilustrativo" en el nombre -- nunca presentado como
dato real de una utility real.

Agrega:
  1. Una segunda zona de Balance de Red en CALI (hasta ahora todo el demo
     era Bogota) -- mismas coordenadas/head/elevation del modelo EPANET
     de Cali, para que "Generar modelo (Gemelo Digital)" tambien funcione
     ahi. Balance real con NRW menor al de Bogota (variedad visual real
     en el mapa: una zona en verde, otra en amarillo/rojo segun el tope).
  2. Un 4to activo real (bomba, `out_of_service` a proposito) para que
     haya un disparador REAL de `asset_condition`.
  3. Catalogos de Mantenimiento (SLA por prioridad, codigos de falla,
     cuadrillas) -- vacios en produccion hasta ahora (Fase 1 del CMMS,
     2026-09-14).
  4. Ordenes de mantenimiento reales en distintos estados del ciclo de
     vida (completadas con MTTR real, una vencida de SLA, una en
     progreso, una programada, una recien generada) + un plan PM ya
     completado una vez (para que %cumplimiento tenga algo que mostrar)
     y uno todavia vencido (para que el usuario pueda darle clic a
     "Generar ordenes vencidas" en vivo y ver que pasa algo real).

Uso:
    python seed_demo_cali_and_maintenance.py "<DSN>" "<TENANT_ID>"
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-balance"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))

import psycopg  # noqa: E402

from asset_service import connect_assets, register_asset, update_asset_status  # noqa: E402
from balance_service import register_zone, submit_balance  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from order_service import (  # noqa: E402
    assign_order,
    close_order,
    create_crew,
    create_failure_code,
    create_pm_plan,
    generate_order,
    schedule_order,
    set_sla_policy,
    start_order,
)

BOGOTA_ZONE_NAME = "DMA Chapinero (Bogota, ilustrativo)"
CALI_ZONE_NAME = "DMA Tres Cruces - San Fernando (Cali, ilustrativo)"

# Mismas coordenadas/Head/Elev de cali_tres_cruces_dma.inp (R1/J1) -- para
# que "Generar modelo (Gemelo Digital)" tambien funcione sobre estos
# activos, igual que ya pasa con Bogota.
CALI_TANK_COORDS = [-76.5469, 3.4673]
CALI_TANK_HEAD_M = 1030
CALI_PIPE_COORDS = [-76.5430, 3.4600]
CALI_VALVE_COORDS = [-76.5390, 3.4550]
CALI_VALVE_ELEV_M = 998


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _backdate_order(conn: psycopg.Connection, tenant_id: str, order_id: str, **cols) -> None:
    """Ajusta timestamps de una orden ya creada via los servicios reales
    (que solo saben usar `now()`) para que la demostracion tenga
    antiguedad/MTTR realistas -- nunca cambia el status ni salta
    validaciones, solo corrige CUANDO paso lo que ya paso de verdad."""
    set_clause = ", ".join(f"{col} = %s" for col in cols)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE maintenance_order SET {set_clause} WHERE id = %s AND tenant_id = %s",
                    [*cols.values(), order_id, tenant_id],
                )


def _zone_id(conn: psycopg.Connection, tenant_id: str, name: str) -> str | None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM network_zone WHERE tenant_id = %s AND name = %s", (tenant_id, name))
                row = cur.fetchone()
    return str(row[0]) if row else None


def run(dsn: str, tenant_id: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        bogota_zone_id = _zone_id(conn, tenant_id, BOGOTA_ZONE_NAME)
        if bogota_zone_id is None:
            print(f"No existe la zona {BOGOTA_ZONE_NAME!r} -- correr primero seed_demo_networks.py/seed_demo_assets.py")
            return 1
        print("bogota_zone_id", bogota_zone_id)

        # 1. Zona de Cali (si no existe todavia).
        cali_zone_id = _zone_id(conn, tenant_id, CALI_ZONE_NAME)
        if cali_zone_id is None:
            cali_zone_id = register_zone(
                conn, tenant_id, CALI_ZONE_NAME, "dma", data_source="external",
                network_length_km=9.8, num_connections=1450, avg_pressure_mca=32.0,
                nrw_threshold_pct=30.0, centroid_lat=CALI_TANK_COORDS[1], centroid_lon=CALI_TANK_COORDS[0],
            )
            print("cali_zone_id (nueva)", cali_zone_id)

            cali_tank = register_asset(
                conn, tenant_id, "tank", zone_id=cali_zone_id,
                attributes={"notes": "Tanque elevado San Fernando (ilustrativo)", "capacity_m3": 350, "head_m": CALI_TANK_HEAD_M},
                geometry={"type": "Point", "coordinates": CALI_TANK_COORDS},
            )
            cali_pipe = register_asset(
                conn, tenant_id, "pipe", zone_id=cali_zone_id,
                attributes={"notes": "Tuberia troncal Tres Cruces (ilustrativo)", "material": "HDPE", "diameter_mm": 200},
                geometry={"type": "Point", "coordinates": CALI_PIPE_COORDS},
            )
            cali_valve = register_asset(
                conn, tenant_id, "valve", zone_id=cali_zone_id,
                attributes={"notes": "Valvula de seccionamiento San Fernando (ilustrativo)", "elevation_m": CALI_VALVE_ELEV_M},
                geometry={"type": "Point", "coordinates": CALI_VALVE_COORDS},
            )
            connect_assets(conn, tenant_id, cali_tank["asset_id"], cali_pipe["asset_id"], "flows_into")
            connect_assets(conn, tenant_id, cali_pipe["asset_id"], cali_valve["asset_id"], "flows_into")
            print("cali assets", cali_tank["asset_id"], cali_pipe["asset_id"], cali_valve["asset_id"])

            # Balance real de Cali -- NRW menor al de Bogota (variedad real
            # en el mapa: no todas las zonas rojas/amarillas).
            balance = submit_balance(
                conn, tenant_id, cali_zone_id, date(2026, 8, 1), date(2026, 9, 1), "top_down",
                system_input_volume=8500, billed_metered_consumption=6800,
                billed_unbilled_consumption=250, unbilled_authorized_consumption=100, apparent_losses=300,
            )
            print("cali balance", balance["nrw_pct"], "% NRW, excede tope:", balance["exceeds_threshold"])
        else:
            print("cali_zone_id (ya existia)", cali_zone_id)

        # 2. Activo roto real -- bomba fuera de servicio, dispara asset_condition de verdad.
        pump = register_asset(
            conn, tenant_id, "pump", zone_id=bogota_zone_id,
            attributes={"notes": "Bomba de refuerzo Chapinero (ilustrativo)", "model": "Grundfos CR-15"},
            geometry={"type": "Point", "coordinates": [-74.0500, 4.6555]},
        )
        pump_id = pump["asset_id"]
        update_asset_status(conn, tenant_id, pump_id, "out_of_service")
        print("pump (out_of_service)", pump_id)

        # 3. Catalogos de Mantenimiento (SLA reales por prioridad, horas objetivo tipicas de utility).
        for priority, hours in [("low", 72), ("medium", 24), ("high", 8), ("emergency", 2)]:
            set_sla_policy(conn, tenant_id, priority, hours)
        print("SLA policies: low=72h, medium=24h, high=8h, emergency=2h")

        failure_codes = {}
        for code, label in [
            ("LEAK-JOINT", "Fuga en junta/empaque"),
            ("VLV-STUCK", "Válvula atascada"),
            ("CORROSION", "Corrosión en tubería"),
            ("PUMP-FAIL", "Falla mecánica de bomba"),
            ("SENSOR-CAL", "Sensor descalibrado"),
            ("OBSTRUCTION", "Obstrucción/sedimento"),
        ]:
            fc = create_failure_code(conn, tenant_id, code, label)
            failure_codes[code] = fc["failure_code_id"]
        print(f"{len(failure_codes)} códigos de falla creados")

        crews = {}
        for name in ["Cuadrilla Bogotá Norte", "Cuadrilla Bogotá Sur", "Cuadrilla Cali"]:
            c = create_crew(conn, tenant_id, name)
            crews[name] = c["crew_id"]
        print(f"{len(crews)} cuadrillas creadas")

        now = _now()

        # 4a. Orden completada real -- bomba rota, ciclo completo, MTTR ~5.5h, hace 4 dias.
        o1 = generate_order(conn, tenant_id, pump_id, "corrective", "asset_condition", "high", "Bomba de refuerzo sin arrancar, presión baja reportada")
        schedule_order(conn, tenant_id, o1["order_id"], now - timedelta(days=4, hours=2))
        assign_order(conn, tenant_id, o1["order_id"], crews["Cuadrilla Bogotá Norte"])
        start_order(conn, tenant_id, o1["order_id"])
        close_order(conn, tenant_id, o1["order_id"], "completed", labor_hours=5.5, materials_used="rodamiento + sello mecánico", root_cause="Desgaste de rodamiento por antigüedad", failure_code_id=failure_codes["PUMP-FAIL"])
        created1 = now - timedelta(days=4, hours=6)
        _backdate_order(conn, tenant_id, o1["order_id"], created_at=created1, scheduled_at=now - timedelta(days=4, hours=2), sla_due_at=created1 + timedelta(hours=8), closed_at=created1 + timedelta(hours=5, minutes=30))
        print("orden 1 (completada, MTTR real): ", o1["order_id"])

        # 4b. Orden completada real -- fuga menor, MTTR ~2h, hace 2 dias.
        bogota_valve_id = None
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM network_asset WHERE tenant_id=%s AND zone_id=%s AND type='valve' LIMIT 1", (tenant_id, bogota_zone_id))
                    row = cur.fetchone()
                    bogota_valve_id = str(row[0]) if row else pump_id
        o2 = generate_order(conn, tenant_id, bogota_valve_id, "corrective", "manual", "medium", "Fuga visible reportada por usuario cerca de la válvula")
        schedule_order(conn, tenant_id, o2["order_id"], now - timedelta(days=2, hours=3))
        assign_order(conn, tenant_id, o2["order_id"], crews["Cuadrilla Bogotá Sur"])
        start_order(conn, tenant_id, o2["order_id"])
        close_order(conn, tenant_id, o2["order_id"], "completed", labor_hours=2.0, materials_used="empaque de caucho", root_cause="Empaque deteriorado", failure_code_id=failure_codes["LEAK-JOINT"])
        created2 = now - timedelta(days=2, hours=5)
        _backdate_order(conn, tenant_id, o2["order_id"], created_at=created2, scheduled_at=now - timedelta(days=2, hours=3), sla_due_at=created2 + timedelta(hours=24), closed_at=created2 + timedelta(hours=2))
        print("orden 2 (completada, MTTR real):", o2["order_id"])

        # 4c. Orden VENCIDA de verdad -- emergencia generada hace 3 dias, SLA de 2h ya lejos.
        o3 = generate_order(conn, tenant_id, pump_id, "corrective", "manual", "emergency", "Ruido anormal reportado, revisar antes de que falle igual que la anterior")
        created3 = now - timedelta(days=3)
        _backdate_order(conn, tenant_id, o3["order_id"], created_at=created3, sla_due_at=created3 + timedelta(hours=2))
        print("orden 3 (vencida de SLA, sin cerrar):", o3["order_id"])

        # 4d. Orden en progreso real -- asignada, sin vencer todavia.
        o4 = generate_order(conn, tenant_id, bogota_valve_id, "inspection", "manual", "low", "Inspección rutinaria trimestral")
        schedule_order(conn, tenant_id, o4["order_id"], now + timedelta(hours=6))
        assign_order(conn, tenant_id, o4["order_id"], crews["Cuadrilla Bogotá Norte"])
        start_order(conn, tenant_id, o4["order_id"])
        print("orden 4 (en progreso):", o4["order_id"])

        # 4e. Orden recien generada -- sin tocar, para ver el flujo completo desde cero en vivo.
        o5 = generate_order(conn, tenant_id, pump_id, "preventive", "manual", "low", "Revisión programada de mantenimiento general")
        print("orden 5 (recién generada, lista para programar en vivo):", o5["order_id"])

        # 5. Plan PM ya cumplido una vez (para que %cumplimiento tenga algo real que mostrar)
        #    y un segundo plan TODAVIA vencido (para que el usuario le de clic en vivo).
        past_due = now - timedelta(days=200)
        plan1 = create_pm_plan(conn, tenant_id, bogota_valve_id, "inspection", "low", 180, past_due)
        o_pm = generate_order(conn, tenant_id, bogota_valve_id, "inspection", "pm_schedule", "low", "Mantenimiento preventivo programado (demo)")
        schedule_order(conn, tenant_id, o_pm["order_id"], past_due + timedelta(days=1))
        assign_order(conn, tenant_id, o_pm["order_id"], crews["Cuadrilla Bogotá Sur"])
        start_order(conn, tenant_id, o_pm["order_id"])
        close_order(conn, tenant_id, o_pm["order_id"], "completed", labor_hours=1.5, materials_used="ninguno", root_cause="Sin hallazgos")
        _backdate_order(conn, tenant_id, o_pm["order_id"], created_at=past_due, scheduled_at=past_due + timedelta(days=1), sla_due_at=past_due + timedelta(hours=72), closed_at=past_due + timedelta(days=1, hours=2))
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE maintenance_pm_plan SET next_due_at = %s, last_generated_at = %s WHERE id = %s AND tenant_id = %s",
                        (past_due + timedelta(days=180), past_due, plan1["pm_plan_id"], tenant_id),
                    )
        print("plan PM 1 (ya con historial de cumplimiento):", plan1["pm_plan_id"])

        plan2 = create_pm_plan(conn, tenant_id, pump_id, "preventive", "medium", 90, now - timedelta(days=5))
        print("plan PM 2 (TODAVÍA VENCIDO -- probar 'Generar órdenes vencidas' en vivo):", plan2["pm_plan_id"])

    print("\nListo. Datos de demostración reales sembrados sobre Bogotá + Cali.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2]))
