"""Crea la junta de DEMOSTRACION del Track D (Sprint D0.4) con el caso
ficticio que la propia Guia 3 de Municipios Azules usa en sus actividades
1 y 2: una junta pequena con captacion, desarenador, conduccion con fuga,
sedimentador y filtro con problemas, reservorio, red, y una caja de
revision que rebosa junto a la escuela. Todo queda etiquetado como caso
ficticio en el nombre de la junta -- nunca presentado como una junta real.

Que crea (persistente, no se borra):
  1. La junta "Junta de Agua de ejemplo (caso ficticio Guía 3)" con los
     paquetes EC-ARCA y EC-MUNICIPIOS-AZULES activos y nivel basico.
  2. Un usuario con el correo y la clave que se pasen por argumento
     (nunca una clave fija en codigo).
  3. Los componentes del recorrido de agua y de saneamiento, encadenados.
  4. Los 3 puntos criticos de la actividad 1 de la guia.
  5. Un semaforo (actividad 2) con las acciones inmediatas de la guia.
  6. La verificacion inicial de la Guia 3.

Si la junta ya existe (mismo nombre), no hace nada y muestra su id.

Uso:
    python seed_demo_junta.py "<DSN rol de aplicacion>" "<correo>" "<clave>"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))

import psycopg  # noqa: E402

from asset_service import connect_assets, register_asset  # noqa: E402
from pack_service import adopt_pack, create_finding, set_instrumentation, submit_checklist_run  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

TENANT_NAME = "Junta de Agua de ejemplo (caso ficticio Guía 3)"

# (clave interna, tipo, nombre, estado)
WATER_ROUTE = [
    ("source", "water_source", "Vertiente El Molino", "operational"),
    ("intake", "intake", "Captación de la vertiente", "operational"),
    ("sand_trap", "sand_trap", "Desarenador", "maintenance"),
    ("conveyance", "conveyance", "Conducción principal", "maintenance"),
    ("sedimentation", "sedimentation", "Sedimentador", "maintenance"),
    ("filtration", "filtration", "Filtro lento", "maintenance"),
    ("disinfection", "disinfection", "Dosificador de cloro por goteo", "operational"),
    ("tank", "tank", "Reservorio de 40 m³", "operational"),
    ("network", "distribution_network", "Red de distribución", "operational"),
]
SANITATION_ROUTE = [
    ("box_school", "inspection_box", "Caja de revisión junto a la escuela", "out_of_service"),
    ("septic_center", "septic_tank", "Fosa séptica del centro comunitario", "maintenance"),
]


def main(dsn: str, email: str, password: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenant WHERE name = %s", (TENANT_NAME,))
            row = cur.fetchone()
            if row:
                print(f"La junta demo ya existe: {row[0]} -- no se modifica.")
                return
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", (TENANT_NAME,))
            tenant_id = str(cur.fetchone()[0])

        create_app_user(conn, tenant_id, email, password, "supervisor")
        actor = f"portal:{email}"
        adopt_pack(conn, tenant_id, "EC-ARCA")
        adopt_pack(conn, tenant_id, "EC-MUNICIPIOS-AZULES")
        set_instrumentation(conn, tenant_id, {
            "metering": "basic", "water_balance": "basic", "quality": "basic",
            "maintenance": "basic", "network": "basic", "billing": "basic",
        })

        ids: dict[str, str] = {}
        for route in (WATER_ROUTE, SANITATION_ROUTE):
            previous = None
            for key, asset_type, name, status in route:
                ids[key] = register_asset(conn, tenant_id, asset_type, attributes={"name": name}, status=status)["asset_id"]
                if previous:
                    connect_assets(conn, tenant_id, ids[previous], ids[key], "flow")
                previous = key

        # Actividad 1 (Guia 3): puntos criticos del ejemplo de referencia.
        create_finding(conn, tenant_id, "La tubería pierde agua y deja al sector alto con baja presión.", "high", actor,
                       source_kind="critical_point", asset_id=ids["conveyance"],
                       location_text="Cruce de la quebrada, antes del reservorio", support_level="local_government")
        create_finding(conn, tenant_id, "El agua llega café y el desarenador acumula lodo.", "high", actor,
                       source_kind="critical_point", asset_id=ids["sand_trap"],
                       location_text="Entrada del desarenador, después de lluvias", support_level="community")
        create_finding(conn, tenant_id, "La caja está tapada, produce mal olor y descarga hacia la calle.", "high", actor,
                       source_kind="critical_point", asset_id=ids["box_school"],
                       location_text="Caja de revisión junto a la escuela", support_level="local_government")
        # Actividad 3 (Guia 3): problemas del tren de tratamiento del ejemplo.
        create_finding(conn, tenant_id, "El sedimentador acumula lodos y el agua sale todavía turbia.", "medium", actor,
                       asset_id=ids["sedimentation"], support_level="community")
        create_finding(conn, tenant_id, "El filtro no recibe retrolavado y pierde caudal.", "medium", actor,
                       asset_id=ids["filtration"], support_level="specialized")

        # Actividad 2 (Guia 3): semaforo con las acciones inmediatas del ejemplo.
        traffic_light = [
            ("intake", "yellow", "Retirar hojas, limpiar la rejilla y reparar el cerco durante la minga del sábado.", ids["intake"]),
            ("conveyance", "red", "Cerrar la válvula del tramo y gestionar reparación de la fuga con apoyo del GAD.", ids["conveyance"]),
            ("treatment", "yellow", "Limpiar el desarenador y revisar el estado del filtro.", None),
            ("storage", "green", "Mantener la revisión semanal y registrar el nivel del tanque.", ids["tank"]),
            ("network", "yellow", "Revisar dos sectores con baja presión y purgar el punto bajo.", ids["network"]),
            ("sanitation", "red", "Señalizar el rebose y solicitar destape y revisión técnica.", ids["box_school"]),
            ("warehouse_ppe", "yellow", "Separar el cloro de otros materiales y comprar gafas y guantes.", None),
            ("logbooks", "red", "Empezar el registro diario y designar al operador como responsable.", None),
        ]
        submit_checklist_run(conn, tenant_id, "MA-AP2", [
            {"item_key": k, "answer_code": c, "action": a, "asset_id": asset}
            for k, c, a, asset in traffic_light
        ], actor, notes="Semáforo del caso ficticio de la Guía 3 (actividad participativa 2).")

        submit_checklist_run(conn, tenant_id, "MA-G3-START", [
            {"item_key": "operator_assigned", "answer_code": "yes"},
            {"item_key": "daily_review", "answer_code": "somewhat"},
            {"item_key": "chlorination_measured", "answer_code": "somewhat"},
            {"item_key": "quality_analysis", "answer_code": "no"},
            {"item_key": "maintenance_mingas", "answer_code": "yes"},
            {"item_key": "wastewater_known", "answer_code": "somewhat"},
            {"item_key": "sanitation_maintained", "answer_code": "no"},
            {"item_key": "knows_when_to_ask", "answer_code": "somewhat"},
        ], actor, notes="Verificación inicial del caso ficticio.")

        print(f"Junta demo creada: {tenant_id}")
        print(f"Usuario: {email}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
