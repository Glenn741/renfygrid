"""Verificacion end-to-end real de Track D, Sprint D0.1 (motor de paquetes,
docs/04-plan-sprints.md SS11.4) -- Postgres real con el rol de aplicacion
(RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. Una junta nueva solo tiene el paquete `core`: no ve listas del
     programa y no tiene regla para el cloro (no se inventa un umbral).
  2. Adoptar un paquete inexistente falla; adoptar EC-ARCA y
     EC-MUNICIPIOS-AZULES los activa.
  3. Las lecturas del ejemplo de la Guia 3 se evaluan con la regla del
     paquete: 0,8 y 0,5 adecuado, 0,2 bajo; E. coli 1 es critico.
  4. `network_asset.type` ya es FK al catalogo: un tipo comunitario
     (captacion) entra, uno inventado no.
  5. Semaforo (MA-AP2) completo: crea un hallazgo por cada amarillo/rojo
     con la prioridad de la escala, y queda como semaforo vigente.
  6. Una aplicacion incompleta se rechaza.
  7. Aislamiento: la otra junta no ve la aplicacion ni los hallazgos.
  8. Tren de tratamiento: etapa en mantenimiento -> no funciona, con su
     hallazgo abierto; etapa no registrada -> no existe.
  9. Cerrar un hallazgo fija `closed_at`; una prioridad invalida falla.
 10. Nivel de instrumentacion: se guarda y se valida.
 11. El rol de aplicacion no puede escribir en los catalogos globales.
Al final borra SOLO las dos juntas de prueba y lo que ellas crearon.

Uso:
    python verify_pack_service_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import InvalidAnswersError, InvalidInstrumentationError  # noqa: E402
from pack_service import (  # noqa: E402
    unadopt_pack,
    AssetNotFoundError,
    InvalidFindingError,
    PackNotFoundError,
    RuleNotFoundError,
    RunNotFoundError,
    active_pack_ids,
    adopt_pack,
    create_finding,
    evaluate_parameter,
    get_checklist_run,
    get_instrumentation,
    latest_traffic_light,
    list_checklist_templates,
    list_component_types,
    list_findings,
    set_instrumentation,
    submit_checklist_run,
    treatment_train_report,
    update_finding,
)
from renmeter_common.db import tenant_scope  # noqa: E402

ACTOR = "portal:e2e-d0@renfygrid.test"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  OK  {message}")


def expect(exc_type: type[Exception], fn, message: str) -> None:
    try:
        fn()
    except exc_type:
        print(f"  OK  {message}")
        return
    raise AssertionError(f"Se esperaba {exc_type.__name__}: {message}")


def add_asset(conn: psycopg.Connection, tenant_id: str, asset_type: str, status: str = "operational") -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO network_asset (tenant_id, type, status) VALUES (%s, %s, %s) RETURNING id",
                    (tenant_id, asset_type, status),
                )
                return str(cur.fetchone()[0])


def main(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E Track D0 junta A') RETURNING id")
            tenant_a = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E Track D0 junta B') RETURNING id")
            tenant_b = str(cur.fetchone()[0])
        try:
            print("1. Junta nueva: nace con los paquetes base (0025)")
            check(sorted(active_pack_ids(conn, tenant_a)) == ["EC-ARCA", "EC-MUNICIPIOS-AZULES", "core"],
                  "paquetes base activos desde el alta (trigger en tenant)")
            check(sorted(active_pack_ids(conn, tenant_b)) == sorted(active_pack_ids(conn, tenant_a)),
                  "las dos juntas tienen el mismo modelo funcional")

            print("2. Desactivar y volver a activar un paquete")
            expect(PackNotFoundError, lambda: adopt_pack(conn, tenant_a, "NO-EXISTE"), "paquete inexistente rechazado")
            expect(PackNotFoundError, lambda: unadopt_pack(conn, tenant_a, "core"), "core no se desactiva")
            unadopt_pack(conn, tenant_a, "EC-ARCA")
            expect(RuleNotFoundError, lambda: evaluate_parameter(conn, tenant_a, "free_chlorine", 0.5),
                   "sin paquete normativo no hay regla de cloro (no se inventa un umbral)")
            result = adopt_pack(conn, tenant_a, "EC-ARCA")
            check(sorted(result["active_packs"]) == ["EC-ARCA", "EC-MUNICIPIOS-AZULES", "core"], "3 paquetes activos de nuevo")
            check(len(list_checklist_templates(conn, tenant_a)) == 24, "24 listas del programa visibles (G2-G6 y CAP, 0021+0024+0026)")

            print("3. Evaluacion con la regla del paquete")
            check(evaluate_parameter(conn, tenant_a, "free_chlorine", 0.8)["result"]["code"] == "adequate", "cloro 0,8 adecuado")
            check(evaluate_parameter(conn, tenant_a, "free_chlorine", 0.5)["result"]["code"] == "adequate", "cloro 0,5 adecuado")
            low = evaluate_parameter(conn, tenant_a, "free_chlorine", 0.2)
            check(low["result"] == {"code": "low", "label": "Bajo", "severity": "alert"}, "cloro 0,2 bajo (alerta)")
            check("NTE INEN 1108" in low["citation"], "la evaluacion trae la cita de la fuente")
            check(evaluate_parameter(conn, tenant_a, "e_coli", 1)["result"]["severity"] == "critical", "E. coli presente = critico")

            print("4. Catalogo de componentes como FK")
            codes = {t["code"] for t in list_component_types(conn, tenant_a)}
            check({"intake", "sand_trap", "septic_tank", "tank"} <= codes, "tipos comunitarios y urbanos en el catalogo")
            intake = add_asset(conn, tenant_a, "intake")
            add_asset(conn, tenant_a, "sand_trap")
            filtration = add_asset(conn, tenant_a, "filtration", status="maintenance")
            add_asset(conn, tenant_a, "tank")
            check(bool(intake), "captacion registrada")
            expect(psycopg.errors.ForeignKeyViolation, lambda: add_asset(conn, tenant_a, "teletransportador"),
                   "tipo inventado rechazado por la FK")

            print("5. Semaforo (MA-AP2)")
            answers = [
                {"item_key": "intake", "answer_code": "yellow", "action": "Limpiar rejilla en la minga del sábado", "asset_id": intake},
                {"item_key": "conveyance", "answer_code": "red", "observation": "Fuga en el cruce de la quebrada"},
                {"item_key": "treatment", "answer_code": "yellow"},
                {"item_key": "storage", "answer_code": "green"},
                {"item_key": "network", "answer_code": "yellow"},
                {"item_key": "sanitation", "answer_code": "red"},
                {"item_key": "warehouse_ppe", "answer_code": "yellow"},
                {"item_key": "logbooks", "answer_code": "red"},
            ]
            run = submit_checklist_run(conn, tenant_a, "MA-AP2", answers, ACTOR)
            check(len(run["findings_created"]) == 7, "7 hallazgos (4 amarillos + 3 rojos)")
            check(run["score"] == {"score": 6, "max_score": 16, "pct": 37.5}, "puntaje 6/16")
            findings = list_findings(conn, tenant_a)
            red = [f for f in findings if "Conducción" in f["description"]][0]
            check(red["priority"] == "high" and "Fuga en el cruce" in red["description"], "rojo -> prioridad alta con observacion")
            check(any(f["asset_id"] == intake for f in findings), "el hallazgo de la captacion queda ligado al activo")
            check(latest_traffic_light(conn, tenant_a)["run_id"] == run["run_id"], "es el semaforo vigente")

            print("6. Aplicacion incompleta")
            expect(InvalidAnswersError, lambda: submit_checklist_run(conn, tenant_a, "MA-AP2", answers[:3], ACTOR),
                   "faltan items -> rechazada")

            print("7. Aislamiento entre juntas")
            expect(RunNotFoundError, lambda: get_checklist_run(conn, tenant_b, run["run_id"]), "la junta B no ve la aplicacion de A")
            check(list_findings(conn, tenant_b) == [], "la junta B no ve hallazgos de A")
            expect(AssetNotFoundError, lambda: create_finding(conn, tenant_b, "x", "low", ACTOR, asset_id=intake),
                   "la junta B no puede ligar un hallazgo a un activo de A")

            print("8. Tren de tratamiento")
            create_finding(conn, tenant_a, "El filtro no recibe retrolavado y pierde caudal.", "high", ACTOR, asset_id=filtration)
            train = {row["type"]: row for row in treatment_train_report(conn, tenant_a)}
            check(train["sand_trap"]["exists"] and train["sand_trap"]["works"], "desarenador existe y funciona")
            check(train["filtration"]["works"] is False and len(train["filtration"]["open_findings"]) == 1,
                  "filtracion en mantenimiento, con su hallazgo abierto")
            check(train["coagulation"]["exists"] is False and train["coagulation"]["works"] is None, "coagulacion no registrada")

            print("9. Ciclo del hallazgo")
            closed = update_finding(conn, tenant_a, red["finding_id"], status="closed", to_improvement_plan=True)
            check(closed["status"] == "closed" and closed["closed_at"] and closed["to_improvement_plan"], "cerrado con fecha y marcado para el plan")
            expect(InvalidFindingError, lambda: update_finding(conn, tenant_a, red["finding_id"], priority="urgentisima"),
                   "prioridad invalida rechazada")

            print("10. Nivel de instrumentacion")
            set_instrumentation(conn, tenant_a, {"metering": "basic", "quality": "basic"})
            set_instrumentation(conn, tenant_a, {"metering": "intermediate"})
            check(get_instrumentation(conn, tenant_a) == {"metering": "intermediate", "quality": "basic"}, "niveles guardados y combinados")
            check(get_instrumentation(conn, tenant_b) == {}, "la junta B no tiene niveles asumidos")
            expect(InvalidInstrumentationError, lambda: set_instrumentation(conn, tenant_a, {"metering": "experto"}), "nivel invalido rechazado")

            print("11. Catalogos de solo lectura")
            expect(psycopg.errors.InsufficientPrivilege,
                   lambda: conn.execute("UPDATE checklist_template SET title = 'x' WHERE id = 'MA-7A'"),
                   "el rol de aplicacion no puede modificar listas del paquete")
        finally:
            for tenant_id in (tenant_a, tenant_b):
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        conn.execute("DELETE FROM finding WHERE tenant_id = %s", (tenant_id,))
                        conn.execute("DELETE FROM checklist_answer WHERE tenant_id = %s", (tenant_id,))
                        conn.execute("DELETE FROM checklist_run WHERE tenant_id = %s", (tenant_id,))
                        conn.execute("DELETE FROM tenant_pack WHERE tenant_id = %s", (tenant_id,))
                        conn.execute("DELETE FROM network_asset WHERE tenant_id = %s", (tenant_id,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D0.1 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1])
