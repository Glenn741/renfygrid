"""Carga en un tenant EXISTENTE (el demo "RenfyGrid Demo", a pedido del
usuario 2026-10-05) todo lo de las Guias 3 y 4 de Municipios Azules que la
plataforma ya modela, como un sistema comunitario ILUSTRATIVO (nombres con
"(ilustrativo)" -- nunca presentado como una junta real). Lo que la
plataforma todavia no modela (padron, caja, costos, tarifa, morosidad,
POA, rendicion de cuentas, registro diario de cloro) NO se carga: no hay
donde guardarlo sin inventar tablas (D1 y D8-D11 del plan).

Cubre, con los ejemplos de referencia de las guias:
  Guia 3  Actividad 1   mapa tecnico: componentes de agua y saneamiento
                        encadenados + puntos criticos
          Actividad 2   semaforo: inicial (hace 90 dias) y actual
          Actividad 3   tren de tratamiento: etapas, estado y problemas
          Actividad 5   saneamiento: fosa, caja, descarga de quesera
          7A, 7E, 7G.1  inspecciones con accion, responsable y fecha
          3.6 y 7G      calendario: planes preventivos/inspeccion por componente
          7D, 7F        ordenes de mantenimiento en todo el ciclo de vida
                        (lavado de reservorio y limpieza con minga, fuga,
                        rebose vencido de SLA, extraccion de lodos)
          7G.2          hallazgos marcados para el plan de mejora
          Verificacion inicial
  Guia 4  Verificacion inicial, 4A, 4B

Las fechas se llevan al pasado (mismo criterio que
seed_demo_cali_and_maintenance.py) para que el historial, el MTTR y las
ordenes vencidas tengan sentido. Si el tenant ya tiene revisiones
aplicadas, no hace nada.

Uso:
    python seed_demo_guias_tenant.py "<DSN>" "<TENANT_ID>" [perfil]
    (perfil: san_jose por defecto, o gualaceo -- ver PROFILES)
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))

import psycopg  # noqa: E402

from asset_service import connect_assets, register_asset  # noqa: E402
from order_service import (  # noqa: E402
    assign_order,
    close_order,
    create_crew,
    create_failure_code,
    create_pm_plan,
    generate_order,
    list_crews,
    list_failure_codes,
    schedule_order,
    start_order,
)
from pack_service import adopt_pack, create_finding, submit_checklist_run, update_finding  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

ACTOR = "portal:seed-guias@renfygrid.demo"
SYSTEM = "Sistema comunitario San José (ilustrativo)"
NOW = datetime.now(timezone.utc)

WATER = [
    ("source", "water_source", "Vertiente El Molino", "operational"),
    ("intake", "intake", "Captación de la vertiente", "operational"),
    ("sand_trap", "sand_trap", "Desarenador", "maintenance"),
    ("conveyance", "conveyance", "Conducción principal (cruce de la quebrada)", "maintenance"),
    ("sedimentation", "sedimentation", "Sedimentador", "maintenance"),
    ("filtration", "filtration", "Filtro lento de arena", "maintenance"),
    ("disinfection", "disinfection", "Hipoclorador por goteo", "operational"),
    ("tank", "tank", "Reservorio de 40 m³", "operational"),
    ("network_high", "distribution_network", "Red sector alto", "maintenance"),
]
WATER_EXTRA = [
    ("network_low", "distribution_network", "Red sector bajo", "operational", "tank"),
    ("valve", "valve", "Válvula de tramo de la conducción", "operational", None),
]
SANITATION = [
    ("toilets_school", "sanitary_unit", "Baterías sanitarias de la escuela", "operational"),
    ("grease_trap", "grease_trap", "Trampa de grasa del comedor escolar", "operational"),
    ("box_school", "inspection_box", "Caja de revisión junto a la escuela", "out_of_service"),
    ("sewer", "sewer_network", "Red sanitaria del centro poblado", "operational"),
    ("septic", "septic_tank", "Fosa séptica del centro comunitario", "maintenance"),
    ("wetland", "wastewater_plant", "Humedal construido", "operational"),
    ("discharge", "discharge_point", "Descarga a la quebrada", "operational"),
]


# Perfiles: el mismo caso de la guia ubicado en distintos lugares. Solo
# cambian el nombre del sistema, los nombres de los componentes y (si se
# dan) coordenadas aproximadas para el mapa -- siempre ilustrativas.
PROFILES: dict[str, dict] = {
    "san_jose": {"system": SYSTEM, "names": {}, "coords": {}},
    "gualaceo": {
        "system": "Sistema comunitario de agua y saneamiento — zona rural de Gualaceo, Azuay (ilustrativo)",
        "names": {
            "source": "Vertiente de la microcuenca alta",
            "conveyance": "Conducción principal (cruce de quebrada)",
            "tank": "Reservorio de 40 m³ de la comunidad",
            "toilets_school": "Baterías sanitarias de la escuela de la comunidad",
            "septic": "Fosa séptica de la casa comunal",
            "discharge": "Descarga a quebrada afluente del río Santa Bárbara",
            "warehouse": "Bodega de la junta en la casa comunal",
        },
        # [lon, lat] aproximados en la zona rural al noreste de Gualaceo (ilustrativos).
        "coords": {
            "source": [-78.7450, -2.8700], "intake": [-78.7470, -2.8710], "sand_trap": [-78.7490, -2.8720],
            "conveyance": [-78.7550, -2.8760], "valve": [-78.7570, -2.8770], "sedimentation": [-78.7600, -2.8790],
            "filtration": [-78.7605, -2.8795], "disinfection": [-78.7610, -2.8800], "tank": [-78.7615, -2.8805],
            "warehouse": [-78.7618, -2.8808], "network_high": [-78.7640, -2.8820], "network_low": [-78.7680, -2.8860],
            "toilets_school": [-78.7660, -2.8840], "grease_trap": [-78.7662, -2.8842], "box_school": [-78.7665, -2.8845],
            "sewer": [-78.7690, -2.8860], "septic": [-78.7700, -2.8870], "wetland": [-78.7720, -2.8890],
            "discharge": [-78.7740, -2.8900],
        },
    },
}


def _execute(conn: psycopg.Connection, tenant_id: str, sql: str, params: tuple) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(sql, params)


def _backdate_run(conn, tenant_id, run_id, when) -> None:
    _execute(conn, tenant_id, "UPDATE checklist_run SET performed_at = %s WHERE id = %s AND tenant_id = %s", (when, run_id, tenant_id))
    _execute(conn, tenant_id, "UPDATE finding SET created_at = %s WHERE source_ref LIKE %s AND tenant_id = %s",
             (when, f"{run_id}:%", tenant_id))


def _backdate_finding(conn, tenant_id, finding_id, created, closed=None) -> None:
    _execute(conn, tenant_id, "UPDATE finding SET created_at = %s, closed_at = COALESCE(%s, closed_at) WHERE id = %s AND tenant_id = %s",
             (created, closed, finding_id, tenant_id))


def _backdate_order(conn, tenant_id, order_id, **cols) -> None:
    sets = ", ".join(f"{k} = %s" for k in cols)
    _execute(conn, tenant_id, f"UPDATE maintenance_order SET {sets} WHERE id = %s AND tenant_id = %s",
             (*cols.values(), order_id, tenant_id))


def _run(conn, tenant_id, template_id, answers, when, notes) -> dict:
    run = submit_checklist_run(conn, tenant_id, template_id, answers, ACTOR, notes=notes)
    _backdate_run(conn, tenant_id, run["run_id"], when)
    return run


def main(dsn: str, tenant_id: str, profile: str = "san_jose") -> None:
    prof = PROFILES[profile]
    system = prof["system"]

    def asset(key: str, asset_type: str, default_name: str, status: str = "operational") -> str:
        coords = prof["coords"].get(key)
        return register_asset(
            conn, tenant_id, asset_type, status=status,
            attributes={"name": prof["names"].get(key, default_name), "system": system},
            geometry={"type": "Point", "coordinates": coords} if coords else None,
        )["asset_id"]

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM tenant WHERE id = %s", (tenant_id,))
            row = cur.fetchone()
        if row is None:
            print(f"No existe el tenant {tenant_id}")
            sys.exit(1)
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM checklist_run WHERE tenant_id = %s", (tenant_id,))
                    if cur.fetchone()[0] > 0:
                        print(f"El tenant '{row[0]}' ya tiene revisiones aplicadas -- no se modifica.")
                        return
        print(f"Tenant: {row[0]}")

        adopt_pack(conn, tenant_id, "EC-ARCA")
        adopt_pack(conn, tenant_id, "EC-MUNICIPIOS-AZULES")

        # ── Actividad 1: componentes encadenados ──────────────────────────
        ids: dict[str, str] = {}
        for route in (WATER, SANITATION):
            previous = None
            for key, asset_type, name, status in route:
                ids[key] = asset(key, asset_type, name, status)
                if previous:
                    connect_assets(conn, tenant_id, ids[previous], ids[key], "flow")
                previous = key
        for key, asset_type, name, status, upstream in WATER_EXTRA:
            ids[key] = asset(key, asset_type, name, status)
            if upstream:
                connect_assets(conn, tenant_id, ids[upstream], ids[key], "flow")
        ids["warehouse"] = asset("warehouse", "warehouse", "Bodega de la junta")
        print(f"Componentes: {len(ids)}")

        # ── Hallazgos: actividades 1, 3 y 5 + insumos 7G.2 ───────────────
        def finding(desc, priority, days_ago, **kw):
            f = create_finding(conn, tenant_id, desc, priority, ACTOR, **kw)
            _backdate_finding(conn, tenant_id, f["finding_id"], NOW - timedelta(days=days_ago))
            return f["finding_id"]

        f_leak = finding("La tubería pierde agua y deja al sector alto con baja presión.", "high", 88,
                         source_kind="critical_point", asset_id=ids["conveyance"],
                         location_text="Cruce de la quebrada, antes del reservorio", support_level="local_government")
        finding("El agua llega café y el desarenador acumula lodo.", "high", 88, source_kind="critical_point",
                asset_id=ids["sand_trap"], location_text="Entrada del desarenador, después de lluvias", support_level="community")
        f_box = finding("La caja está tapada, produce mal olor y descarga hacia la calle.", "high", 88,
                        source_kind="critical_point", asset_id=ids["box_school"],
                        location_text="Caja de revisión junto a la escuela", support_level="local_government")
        finding("El sedimentador acumula lodos y el agua sale todavía turbia.", "medium", 85,
                asset_id=ids["sedimentation"], support_level="community")
        f_filter = finding("El filtro no recibe retrolavado y pierde caudal.", "high", 85,
                           asset_id=ids["filtration"], support_level="specialized")
        finding("El agua presenta olor metálico en ciertos meses; no existe etapa de aireación. Evaluar hierro y manganeso.",
                "medium", 85, support_level="specialized")
        finding("En invierno el agua llega muy turbia; no existe coagulación ni floculación. Requiere prueba de jarras y diseño técnico.",
                "medium", 85, support_level="specialized")
        finding("El dosificador funciona, pero no se mide cloro residual todos los días.", "high", 85,
                asset_id=ids["disinfection"], support_level="community")
        f_septic = finding("La fosa séptica se llena rápidamente y presenta humedad alrededor.", "high", 60,
                           asset_id=ids["septic"], location_text="Centro comunitario", support_level="specialized")
        f_cheese = finding("El suero de una quesera entra a la red comunitaria y genera olores.", "high", 60,
                           asset_id=ids["sewer"], location_text="Quesera del sector bajo", support_level="local_government")
        f_chlorine = finding("Cloro residual bajo en el punto más lejano: tres mediciones de 0,15, 0,18 y 0,17 mg/L.", "high", 12,
                             asset_id=ids["network_high"], location_text="Vivienda del extremo de la red, sector alto",
                             support_level="specialized")
        f_grille = finding("Rejilla de la captación rota; ingresan hojas y animales.", "medium", 80,
                           asset_id=ids["intake"], support_level="community")
        update_finding(conn, tenant_id, f_grille, status="closed")
        _backdate_finding(conn, tenant_id, f_grille, NOW - timedelta(days=80), NOW - timedelta(days=74))
        for fid in (f_leak, f_box, f_filter, f_septic, f_cheese, f_chlorine):
            update_finding(conn, tenant_id, fid, to_improvement_plan=True)
        update_finding(conn, tenant_id, f_leak, status="in_progress")

        # ── Verificaciones iniciales (hace 90 dias) ───────────────────────
        _run(conn, tenant_id, "MA-G3-START", [
            {"item_key": "operator_assigned", "answer_code": "somewhat"},
            {"item_key": "daily_review", "answer_code": "no"},
            {"item_key": "chlorination_measured", "answer_code": "somewhat"},
            {"item_key": "quality_analysis", "answer_code": "no"},
            {"item_key": "maintenance_mingas", "answer_code": "yes"},
            {"item_key": "wastewater_known", "answer_code": "somewhat"},
            {"item_key": "sanitation_maintained", "answer_code": "no"},
            {"item_key": "knows_when_to_ask", "answer_code": "no"},
        ], NOW - timedelta(days=90), "Verificación inicial al iniciar el taller de la Guía 3.")
        _run(conn, tenant_id, "MA-G4-START", [
            {"item_key": "knows_monthly_cost", "answer_code": "no"},
            {"item_key": "cash_book_updated", "answer_code": "somewhat"},
            {"item_key": "payments_with_receipts", "answer_code": "somewhat"},
            {"item_key": "tariff_covers_costs", "answer_code": "no"},
            {"item_key": "accountability_yearly", "answer_code": "yes"},
        ], NOW - timedelta(days=90), "Verificación inicial al iniciar el taller de la Guía 4.")

        # ── Semaforo inicial (hace 90 dias) y actual (actividad 2) ────────
        initial_light = _run(conn, tenant_id, "MA-AP2", [
            {"item_key": "intake", "answer_code": "red", "action": "Reparar la rejilla rota y el cerco.", "asset_id": ids["intake"]},
            {"item_key": "conveyance", "answer_code": "red", "action": "Cerrar la válvula del tramo y gestionar reparación de la fuga con apoyo del GAD.", "asset_id": ids["conveyance"]},
            {"item_key": "treatment", "answer_code": "red", "action": "Limpiar el desarenador y revisar el estado del filtro."},
            {"item_key": "storage", "answer_code": "yellow", "action": "Programar el lavado del reservorio.", "asset_id": ids["tank"]},
            {"item_key": "network", "answer_code": "yellow", "action": "Revisar dos sectores con baja presión y purgar el punto bajo."},
            {"item_key": "sanitation", "answer_code": "red", "action": "Señalizar el rebose y solicitar destape y revisión técnica.", "asset_id": ids["box_school"]},
            {"item_key": "warehouse_ppe", "answer_code": "red", "action": "Separar el cloro de otros materiales y comprar gafas y guantes.", "asset_id": ids["warehouse"]},
            {"item_key": "logbooks", "answer_code": "red", "action": "Empezar el registro diario y designar al operador como responsable."},
        ], NOW - timedelta(days=90), "Semáforo inicial (actividad participativa 2).")
        _run(conn, tenant_id, "MA-AP2", [
            {"item_key": "intake", "answer_code": "green", "action": "Mantener la limpieza semanal y después de lluvias.", "asset_id": ids["intake"]},
            {"item_key": "conveyance", "answer_code": "red", "action": "Reparación de la fuga en curso con apoyo del GAD.", "asset_id": ids["conveyance"]},
            {"item_key": "treatment", "answer_code": "yellow", "action": "Retrolavar el filtro y pedir evaluación técnica."},
            {"item_key": "storage", "answer_code": "green", "action": "Mantener la revisión semanal y registrar el nivel del tanque.", "asset_id": ids["tank"]},
            {"item_key": "network", "answer_code": "yellow", "action": "Cloro bajo en el extremo del sector alto: revisar fugas y dosificación."},
            {"item_key": "sanitation", "answer_code": "red", "action": "Destape de la caja de la escuela y solución para la descarga de la quesera.", "asset_id": ids["box_school"]},
            {"item_key": "warehouse_ppe", "answer_code": "yellow", "action": "Comprar gafas y delantal antes de la siguiente preparación de cloro.", "asset_id": ids["warehouse"]},
            {"item_key": "logbooks", "answer_code": "green", "action": "Bitácora diaria al día; la directiva la revisa cada semana."},
        ], NOW - timedelta(days=2), "Semáforo actual, revisión mensual.")
        # Los hallazgos del semaforo inicial se atendieron o quedaron recogidos
        # en las revisiones posteriores: se cierran con fecha, como lo haria
        # la junta, para que no dupliquen a los vigentes.
        for fid in initial_light["findings_created"]:
            update_finding(conn, tenant_id, fid, status="closed")
            _backdate_finding(conn, tenant_id, fid, NOW - timedelta(days=90), NOW - timedelta(days=31))

        # ── Inspecciones 7A, 7E, 7G.1 ─────────────────────────────────────
        def due(days):
            return (NOW + timedelta(days=days)).date().isoformat()

        _run(conn, tenant_id, "MA-7A", [
            {"item_key": "source_protected", "answer_code": "in_progress", "observation": "Falta cercar parte de la zona de recarga.", "action": "Reforestar y cercar en la minga de mayo.", "responsible": "Directiva y comunidad", "due_date": due(45)},
            {"item_key": "intake_condition", "answer_code": "yes"},
            {"item_key": "conveyance_no_leaks", "answer_code": "no", "observation": "Fuga en el cruce de la quebrada.", "action": "Reparación con apoyo del GAD.", "responsible": "Presidencia", "due_date": due(10), "asset_id": ids["conveyance"]},
            {"item_key": "main_valves_work", "answer_code": "yes"},
            {"item_key": "treatment_works", "answer_code": "no", "observation": "El sedimentador y el filtro no funcionan según su diseño.", "action": "Solicitar evaluación técnica del filtro.", "responsible": "Presidencia", "due_date": due(30)},
            {"item_key": "filters_cleaned", "answer_code": "no", "observation": "El filtro no recibe retrolavado.", "action": "Capacitar al operador en retrolavado.", "responsible": "Operador/a", "due_date": due(14), "asset_id": ids["filtration"]},
            {"item_key": "doser_works", "answer_code": "in_progress", "observation": "Funciona, pero el goteo es irregular.", "action": "Limpiar la manguera y calibrar el goteo.", "responsible": "Operador/a", "due_date": due(3), "asset_id": ids["disinfection"]},
            {"item_key": "tank_sealed", "answer_code": "yes"},
            {"item_key": "tank_washed_6m", "answer_code": "yes"},
            {"item_key": "network_pressure", "answer_code": "no", "observation": "Baja presión en el sector alto.", "action": "Purgar el punto bajo y revisar fugas.", "responsible": "Operador/a + vocal", "due_date": due(7), "asset_id": ids["network_high"]},
            {"item_key": "no_unauthorized_connections", "answer_code": "in_progress", "observation": "Dos conexiones por verificar en el sector bajo.", "action": "Verificar con el padrón y aplicar el reglamento.", "responsible": "Secretaría", "due_date": due(20)},
        ], NOW - timedelta(days=30), "Inspección trimestral de agua potable.")
        _run(conn, tenant_id, "MA-7E", [
            {"item_key": "wastewater_destination_known", "answer_code": "yes"},
            {"item_key": "boxes_covered", "answer_code": "no", "observation": "La caja junto a la escuela rebosa.", "action": "Destape y revisión de la red.", "responsible": "Presidencia + GAD", "due_date": due(5), "asset_id": ids["box_school"]},
            {"item_key": "no_discharge_near_source", "answer_code": "yes"},
            {"item_key": "septic_maintenance_scheduled", "answer_code": "in_progress", "observation": "Se programó la extracción de lodos pero falta proveedor.", "action": "Cotizar la succión con un proveedor autorizado.", "responsible": "Tesorería", "due_date": due(21), "asset_id": ids["septic"]},
            {"item_key": "sludge_removed_safely", "answer_code": "in_progress", "action": "Definir destino seguro de los lodos con el GAD.", "responsible": "Presidencia", "due_date": due(21)},
            {"item_key": "plant_has_manual", "answer_code": "no", "observation": "El humedal no tiene manual de operación.", "action": "Pedir el manual al proveedor que lo construyó.", "responsible": "Presidencia", "due_date": due(30), "asset_id": ids["wetland"]},
            {"item_key": "operator_uses_ppe", "answer_code": "no", "observation": "No hay overol ni gafas para saneamiento.", "action": "Incluir EPP de saneamiento en la compra del mes.", "responsible": "Tesorería", "due_date": due(15)},
            {"item_key": "productive_discharges_controlled", "answer_code": "no", "observation": "Suero de la quesera entra a la red.", "action": "Acordar tratamiento previo con el propietario y avisar al GAD.", "responsible": "Directiva", "due_date": due(15), "asset_id": ids["sewer"]},
            {"item_key": "sanitation_maintenance_logged", "answer_code": "in_progress", "action": "Llevar el registro de limpieza y lodos.", "responsible": "Operador/a", "due_date": due(7)},
        ], NOW - timedelta(days=20), "Inspección mensual de saneamiento.")
        _run(conn, tenant_id, "MA-7G1", [
            {"item_key": "chemicals_labeled", "answer_code": "yes", "action": "Mantener orden y revisar fecha de vencimiento cada mes.", "responsible": "Operador/a"},
            {"item_key": "warehouse_conditions", "answer_code": "in_progress", "observation": "Existe ventilación, pero falta un letrero de acceso restringido.", "action": "Colocar señal y mantener la puerta con llave.", "responsible": "Presidencia", "due_date": due(10), "asset_id": ids["warehouse"]},
            {"item_key": "no_foreign_items", "answer_code": "yes"},
            {"item_key": "ppe_available", "answer_code": "no", "observation": "Hay guantes y botas; faltan gafas y delantal impermeable.", "action": "Comprar gafas y delantal antes de la siguiente preparación de cloro.", "responsible": "Tesorería", "due_date": due(5)},
            {"item_key": "ppe_good_condition", "answer_code": "in_progress", "action": "Reponer guantes rotos.", "responsible": "Tesorería", "due_date": due(5)},
            {"item_key": "tools_organized", "answer_code": "yes"},
            {"item_key": "inventory_updated", "answer_code": "in_progress", "observation": "Se registran químicos, pero no repuestos ni herramientas.", "action": "Completar inventario único y registrar entradas y salidas.", "responsible": "Operador/a + tesorería", "due_date": due(3)},
            {"item_key": "emergency_numbers_visible", "answer_code": "no", "action": "Pegar en la bodega los números del GAD, MSP, ARCA y ECU 911.", "responsible": "Secretaría", "due_date": due(3)},
        ], NOW - timedelta(days=7), "Revisión mensual de bodega y EPP (primer viernes del mes).")

        # ── Guia 4: 4A y 4B ───────────────────────────────────────────────
        _run(conn, tenant_id, "MA-4A", [
            {"item_key": "bank_account_active", "answer_code": "yes"},
            {"item_key": "cash_book_updated", "answer_code": "in_progress", "action": "Registrar todos los movimientos del trimestre.", "responsible": "Tesorería", "due_date": due(15)},
            {"item_key": "movements_with_receipts", "answer_code": "in_progress", "observation": "Faltan comprobantes de dos compras de cloro.", "action": "Pedir copia de las facturas al proveedor.", "responsible": "Tesorería", "due_date": due(10)},
            {"item_key": "numbered_receipts", "answer_code": "yes"},
            {"item_key": "payment_roll_updated", "answer_code": "in_progress", "action": "Actualizar el padrón con conexiones nuevas y suspendidas.", "responsible": "Secretaría", "due_date": due(20)},
            {"item_key": "budget_approved", "answer_code": "no", "action": "Presentar el presupuesto anual en la próxima asamblea.", "responsible": "Tesorería", "due_date": due(40)},
            {"item_key": "real_costs_calculated", "answer_code": "in_progress", "action": "Completar la planilla de costos con mantenimiento y saneamiento.", "responsible": "Tesorería + operador/a", "due_date": due(20)},
            {"item_key": "tariff_covers_operation", "answer_code": "no", "observation": "La tarifa actual de USD 3 no cubre los costos.", "action": "Preparar propuesta de ajuste gradual para la asamblea.", "responsible": "Directiva", "due_date": due(40)},
            {"item_key": "reserve_fund_active", "answer_code": "no", "action": "Separar un porcentaje mensual para el fondo de reserva.", "responsible": "Tesorería", "due_date": due(40)},
        ], NOW - timedelta(days=15), "Lista 4A de la Guía 4.")
        _run(conn, tenant_id, "MA-4B", [
            {"item_key": "accountability_12m", "answer_code": "yes"},
            {"item_key": "report_includes_reserve", "answer_code": "no", "action": "Incluir el fondo de reserva en el próximo informe.", "responsible": "Tesorería", "due_date": due(60)},
            {"item_key": "members_can_review_books", "answer_code": "in_progress", "action": "Aprobar en asamblea el día de revisión de libros.", "responsible": "Presidencia", "due_date": due(40)},
            {"item_key": "oversight_reviews_receipts", "answer_code": "in_progress", "action": "Revisión trimestral de comprobantes por el vocal de fiscalización.", "responsible": "Vocal de fiscalización", "due_date": due(30)},
            {"item_key": "assembly_approves_finance", "answer_code": "yes"},
            {"item_key": "minutes_signed_archived", "answer_code": "in_progress", "action": "Firmar y archivar las actas pendientes.", "responsible": "Secretaría", "due_date": due(15)},
        ], NOW - timedelta(days=15), "Lista 4B de la Guía 4.")

        # ── Mantenimiento: cuadrillas, codigos de falla, calendario 7G ────
        crews = {c["name"]: c["crew_id"] for c in list_crews(conn, tenant_id)}
        for name in ("Operador/a de la junta", "Minga comunitaria", "Operador/a + vocal"):
            if name not in crews:
                crews[name] = create_crew(conn, tenant_id, name)["crew_id"]
        codes = {c["code"]: c["failure_code_id"] for c in list_failure_codes(conn, tenant_id, include_inactive=True)}
        for code, label in (("SAN-OVERFLOW", "Rebose de aguas residuales"), ("DOSER-FAIL", "Falla del dosificador de cloro"),
                            ("SLUDGE-FULL", "Lodos acumulados"), ("TURBIDITY", "Agua turbia por lluvias")):
            if code not in codes:
                codes[code] = create_failure_code(conn, tenant_id, code, label)["failure_code_id"]

        # Frecuencias de la tabla de la seccion 3.6 y del calendario 7G.
        plans = [
            ("intake", "preventive", "medium", 7, -1),        # limpieza semanal (vencida: se ve "generar vencidas")
            ("sand_trap", "preventive", "medium", 7, 2),
            ("conveyance", "inspection", "medium", 30, 12),   # recorrido mensual de la linea
            ("sedimentation", "preventive", "medium", 15, 4),
            ("filtration", "preventive", "high", 7, -2),      # retrolavado (vencido)
            ("disinfection", "inspection", "high", 7, 1),     # dosificador semanal
            ("tank", "inspection", "low", 30, 20),            # revision mensual
            ("network_high", "inspection", "medium", 30, 8),
            ("network_low", "inspection", "low", 30, 15),
            ("box_school", "inspection", "medium", 30, 10),
            ("grease_trap", "preventive", "low", 30, 18),
            ("septic", "preventive", "medium", 365, 25),      # extraccion de lodos anual
            ("warehouse", "inspection", "low", 30, 26),       # bodega y EPP, primer viernes
        ]
        for key, order_type, priority, interval, offset in plans:
            create_pm_plan(conn, tenant_id, ids[key], order_type, priority, interval, NOW + timedelta(days=offset))
        wash = create_pm_plan(conn, tenant_id, ids["tank"], "preventive", "medium", 182, NOW + timedelta(days=160))

        # ── Ordenes (7D, 7F) en todo el ciclo de vida ─────────────────────
        def lifecycle(key, order_type, priority, reason, crew, created_days_ago, hours_to_close=None, **close):
            o = generate_order(conn, tenant_id, ids[key], order_type, "manual", priority, reason)
            created = NOW - timedelta(days=created_days_ago)
            schedule_order(conn, tenant_id, o["order_id"], created + timedelta(hours=2))
            assign_order(conn, tenant_id, o["order_id"], crews[crew])
            start_order(conn, tenant_id, o["order_id"])
            cols = {"created_at": created, "scheduled_at": created + timedelta(hours=2)}
            if hours_to_close is not None:
                close_order(conn, tenant_id, o["order_id"], "completed", **close)
                cols["closed_at"] = created + timedelta(hours=hours_to_close)
            _backdate_order(conn, tenant_id, o["order_id"], **cols)
            return o["order_id"]

        lifecycle("tank", "preventive", "medium", "Lavado y desinfección semestral del reservorio, con aviso a la comunidad.",
                  "Minga comunitaria", 22, 7, labor_hours=14, materials_used="Hipoclorito para desinfección, escobas, baldes, EPP",
                  root_cause="Mantenimiento semestral programado")
        _execute(conn, tenant_id, "UPDATE maintenance_pm_plan SET last_generated_at = %s WHERE id = %s AND tenant_id = %s",
                 (NOW - timedelta(days=22), wash["pm_plan_id"], tenant_id))
        lifecycle("sand_trap", "corrective", "high", "Limpieza del desarenador y la captación después de lluvias fuertes.",
                  "Minga comunitaria", 6, 5, labor_hours=10, materials_used="Palas, carretilla, baldes",
                  root_cause="Arrastre de arena por lluvias", failure_code_id=codes["TURBIDITY"])
        lifecycle("disinfection", "inspection", "high", "Goteo irregular del hipoclorador.", "Operador/a de la junta", 3, 2,
                  labor_hours=1.5, materials_used="Manguera de repuesto", root_cause="Manguera obstruida por sedimento",
                  failure_code_id=codes["DOSER-FAIL"])
        lifecycle("conveyance", "corrective", "high", "Reparar la fuga del cruce de la quebrada (punto crítico de la actividad 1).",
                  "Operador/a + vocal", 9)

        overflow = generate_order(conn, tenant_id, ids["box_school"], "corrective", "manual", "emergency",
                                  "Rebose de aguas residuales junto a la escuela: aislar la zona, evitar contacto y destapar.")
        _backdate_order(conn, tenant_id, overflow["order_id"], created_at=NOW - timedelta(days=2),
                        sla_due_at=NOW - timedelta(days=2) + timedelta(hours=2))
        sludge = generate_order(conn, tenant_id, ids["septic"], "preventive", "manual", "medium",
                                "Extracción de lodos de la fosa séptica con proveedor autorizado y destino seguro.")
        schedule_order(conn, tenant_id, sludge["order_id"], NOW + timedelta(days=12))
        generate_order(conn, tenant_id, ids["filtration"], "preventive", "manual", "high",
                       "Retrolavado del filtro lento y revisión del medio filtrante.")

        print("Listo: componentes, hallazgos, 9 revisiones, 14 planes y 7 órdenes.")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], *(sys.argv[3:]))
