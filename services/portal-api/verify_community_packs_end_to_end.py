"""Verificacion end-to-end real de Track D, Sprint D0.2 (endpoints del motor
de paquetes, docs/04-plan-sprints.md SS11.4) -- HTTP real (FastAPI
TestClient), JWT real, Postgres real con el rol de aplicacion.

Que prueba, en espanol llano:
  1. Sin token -> 401.
  2. Junta nueva: `/packs` muestra solo `core` activo; evaluar cloro -> 404
     (no hay regla hasta adoptar el paquete normativo).
  3. Adoptar un paquete inexistente -> 404; adoptar los dos de Ecuador -> ok.
  4. `/parameter-rules/evaluate` con las lecturas de la Guia 3.
  5. `/network-assets` ya acepta tipos comunitarios del catalogo y sigue
     rechazando un tipo inventado (422).
  6. `/checklist-runs`: semaforo completo -> 201 con hallazgos; quien lo
     hizo sale del JWT; incompleto -> 422; lista de otro paquete o
     inexistente -> 404.
  7. `/reports/traffic-light`, `/reports/treatment-train`,
     `/reports/system-route` reflejan lo registrado.
  8. `/findings`: punto critico -> 201; PATCH a cerrado; prioridad
     invalida -> 422; hallazgo inexistente -> 404.
  9. `/settings/instrumentation`: guardar y validar.
Al final borra SOLO la junta de prueba y lo que ella creo.

Uso:
    python verify_community_packs_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d0-secret"
ORDER_SIGNING_SECRET = "e2e-d0-order-secret"
EMAIL = "operador@junta-e2e-d0.test"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  OK  {message}")


def run(dsn: str) -> None:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main  # despues de fijar el entorno (Settings.from_env corre al importar)
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E Track D0.2 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, EMAIL, "clave-junta-1", "supervisor")
            token = client.post(
                "/auth/login", json={"tenant_id": tenant_id, "email": EMAIL, "password": "clave-junta-1"}
            ).json()["access_token"]
            h = {"Authorization": f"Bearer {token}"}

            print("1. Autenticacion")
            check(client.get("/packs").status_code == 401, "sin token -> 401")

            print("2. Junta nueva")
            packs = client.get("/packs", headers=h).json()
            check(packs["active"] == ["core"], "solo core activo")
            check({p["pack_id"] for p in packs["packs"]} >= {"core", "EC-ARCA", "EC-MUNICIPIOS-AZULES"}, "catalogo con los 3 paquetes")
            r = client.post("/parameter-rules/evaluate", headers=h, json={"parameter_code": "free_chlorine", "value": 0.5})
            check(r.status_code == 404, "sin regla de cloro -> 404")

            print("3. Adopcion")
            check(client.post("/packs/NO-EXISTE/adopt", headers=h).status_code == 404, "paquete inexistente -> 404")
            client.post("/packs/EC-ARCA/adopt", headers=h)
            r = client.post("/packs/EC-MUNICIPIOS-AZULES/adopt", headers=h)
            check(r.status_code == 200 and len(r.json()["active_packs"]) == 3, "3 paquetes activos")
            check(len(client.get("/checklist-templates", headers=h).json()) == 23, "23 listas disponibles (G2-G6)")
            g6_req = next(t for t in client.get("/checklist-templates", headers=h).json() if t["id"] == "MA-G6-7F")
            check(len(g6_req["items"]) == 25 and g6_req["stage_code"] == "G6", "7F de la Guía 6: 25 requisitos en la etapa G6")
            check(len(client.get("/parameter-rules", headers=h).json()) == 4, "4 reglas vigentes")

            print("4. Evaluacion")
            for value, code in ((0.8, "adequate"), (0.5, "adequate"), (0.2, "low")):
                r = client.post("/parameter-rules/evaluate", headers=h, json={"parameter_code": "free_chlorine", "value": value})
                check(r.json()["result"]["code"] == code, f"cloro {value} -> {code}")

            print("5. Activos con tipos del catalogo")
            ids = {}
            for asset_type, status in (("intake", "operational"), ("sand_trap", "operational"),
                                       ("filtration", "maintenance"), ("disinfection", "operational"), ("tank", "operational")):
                r = client.post("/network-assets", headers=h, json={"type": asset_type, "status": status})
                check(r.status_code == 201, f"{asset_type} registrado")
                ids[asset_type] = r.json()["asset_id"]
            check(client.post("/network-assets", headers=h, json={"type": "teletransportador"}).status_code == 422,
                  "tipo inventado -> 422")

            print("6. Aplicacion de listas")
            items = ["intake", "conveyance", "treatment", "storage", "network", "sanitation", "warehouse_ppe", "logbooks"]
            codes = ["yellow", "red", "yellow", "green", "green", "red", "green", "yellow"]
            answers = [{"item_key": k, "answer_code": c} for k, c in zip(items, codes)]
            answers[0]["asset_id"] = ids["intake"]
            answers[0]["action"] = "Limpiar rejilla y reparar cerco en la minga del sábado"
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-AP2", "answers": answers})
            check(r.status_code == 201 and len(r.json()["findings_created"]) == 5, "semaforo -> 201 con 5 hallazgos")
            run_id = r.json()["run_id"]
            detail = client.get(f"/checklist-runs/{run_id}", headers=h).json()
            check(detail["performed_by"] == f"portal:{EMAIL}", "quien aplico sale del JWT")
            check(detail["answers"][0]["answer_label"] == "Amarillo", "respuesta con su etiqueta del paquete")
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-AP2", "answers": answers[:2]})
            check(r.status_code == 422, "incompleta -> 422")
            r = client.post("/checklist-runs", headers=h, json={"template_id": "NO-EXISTE", "answers": answers})
            check(r.status_code == 404, "lista inexistente -> 404")
            foreign = dict(answers[0], asset_id=str(uuid.uuid4()))
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-AP2", "answers": [foreign] + answers[1:]})
            check(r.status_code == 404, "activo ajeno o inexistente -> 404")
            history = client.get("/checklist-runs?template_id=MA-AP2", headers=h).json()
            check(len(history) == 1, "historial: 1 aplicacion")
            check(history[0]["findings_count"] == 5 and history[0]["score"]["max_score"] == 16,
                  "historial trae puntaje y cantidad de hallazgos")

            print("6b. Ruta del programa (0023)")
            route = client.get("/process-route", headers=h).json()
            check([s["code"] for s in route["stages"]] == ["G1", "G2", "G3", "G4", "G5", "G6"], "6 etapas en orden")
            g3 = {i["template_id"]: i for i in route["stages"][2]["lists"]}
            check(set(g3) == {"MA-G3-START", "MA-AP2", "MA-7A", "MA-7E", "MA-7G1"}, "la etapa G3 agrupa sus 5 listas")
            check(g3["MA-AP2"]["status"] == "done" and g3["MA-7A"]["status"] == "never", "semáforo aplicado, 7A sin aplicar")
            check(g3["MA-7A"]["frequency_days"] == 90 and g3["MA-7E"]["frequency_days"] == 30, "frecuencias del catálogo")
            check(route["stages"][2]["summary"]["applied"] == 1, "resumen de la etapa: 1 aplicada")
            check(route["stages"][0]["lists"] == [] and route["stages"][0]["products"], "etapa sin listas muestra sus productos")
            counts = {s["code"]: s["summary"]["total"] for s in route["stages"]}
            check(counts == {"G1": 0, "G2": 4, "G3": 5, "G4": 3, "G5": 7, "G6": 4}, f"listas por etapa {counts}")

            print("6c. Lista de productos (0024): 'Falta' no genera hallazgo")
            products = [{"item_key": k, "answer_code": "pending" if i % 2 else "ready"} for i, k in enumerate(
                ["org_chart", "assembly_minutes", "legal_diagnosis", "user_roll", "update_route", "alliance_proposal",
                 "transparency_plan", "governance_plan", "adapted_models"])]
            products[1]["observation"] = "Falta firmar el acta"
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-G2-7H", "answers": products})
            check(r.status_code == 201 and r.json()["findings_created"] == [], "productos: 201 y sin hallazgos")
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-G2-7C", "answers": [
                {"item_key": k, "answer_code": "missing" if k == "aua_current" else "yes"} for k in
                ["legal_personality", "bylaws_current", "internal_rules", "board_registered", "aua_current", "user_roll_updated",
                 "minutes_book", "technical_archive", "budget_poa_approved", "tariff_reviewed", "accountability_presented",
                 "claims_register"]]})
            check(r.status_code == 201 and len(r.json()["findings_created"]) == 1, "7C: AUA 'Falta' genera 1 hallazgo")

            print("7. Reportes")
            light = client.get("/reports/traffic-light", headers=h).json()["run"]
            check(light["run_id"] == run_id, "semaforo vigente = la aplicacion")
            train = {row["type"]: row for row in client.get("/reports/treatment-train", headers=h).json()}
            check(train["filtration"]["works"] is False and train["coagulation"]["exists"] is False,
                  "tren: filtracion no funciona, coagulacion no existe")
            route = client.get("/reports/system-route", headers=h).json()
            check([s["type"] for s in route["services"]["water"]] == ["intake", "sand_trap", "filtration", "disinfection", "tank"],
                  "recorrido en orden de la guia")

            print("8. Hallazgos")
            r = client.post("/findings", headers=h, json={
                "description": "La tubería pierde agua y deja al sector alto con baja presión.",
                "priority": "high", "source_kind": "critical_point",
                "location_text": "Cruce de la quebrada, antes del reservorio", "support_level": "local_government",
            })
            check(r.status_code == 201, "punto critico -> 201")
            finding_id = r.json()["finding_id"]
            check(len(client.get("/findings?status=open", headers=h).json()) == 7,
                  "7 hallazgos abiertos (5 del semáforo + 1 de 7C + el punto crítico)")
            r = client.patch(f"/findings/{finding_id}", headers=h, json={"status": "closed"})
            check(r.status_code == 200 and r.json()["closed_at"], "cerrado con fecha")
            check(client.patch(f"/findings/{finding_id}", headers=h, json={"priority": "x"}).status_code == 422, "prioridad invalida -> 422")
            check(client.patch(f"/findings/{uuid.uuid4()}", headers=h, json={"status": "closed"}).status_code == 404, "inexistente -> 404")
            check(client.get("/findings?status=raro", headers=h).status_code == 422, "filtro de estado invalido -> 422")

            print("9. Nivel de instrumentacion")
            r = client.put("/settings/instrumentation", headers=h, json={"levels": {"metering": "basic", "quality": "basic"}})
            check(r.json()["levels"] == {"metering": "basic", "quality": "basic"}, "niveles guardados")
            check(client.put("/settings/instrumentation", headers=h, json={"levels": {"x": "basic"}}).status_code == 422,
                  "modulo desconocido -> 422")
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    for table in ("finding", "checklist_answer", "checklist_run", "tenant_pack", "network_asset", "app_user"):
                        conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
            conn.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
            print("Limpieza: junta de prueba y sus datos borrados")
    print("SPRINT D0.2 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
