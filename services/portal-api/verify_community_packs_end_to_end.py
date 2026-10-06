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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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

            print("2. Junta nueva: paquetes base desde el alta (0025)")
            packs = client.get("/packs", headers=h).json()
            check(sorted(packs["active"]) == ["EC-ARCA", "EC-MUNICIPIOS-AZULES", "core"], "nace con los paquetes base")
            check({p["pack_id"] for p in packs["packs"] if p["is_default"]} == {"EC-ARCA", "EC-MUNICIPIOS-AZULES"},
                  "el catálogo marca los paquetes base")

            print("3. Desactivar y activar")
            check(client.post("/packs/NO-EXISTE/adopt", headers=h).status_code == 404, "paquete inexistente -> 404")
            check(client.delete("/packs/core/adopt", headers=h).status_code == 404, "core no se desactiva -> 404")
            r = client.delete("/packs/EC-ARCA/adopt", headers=h)
            check(r.status_code == 200 and "EC-ARCA" not in r.json()["active_packs"], "desactivar EC-ARCA")
            r = client.post("/parameter-rules/evaluate", headers=h, json={"parameter_code": "free_chlorine", "value": 0.5})
            check(r.status_code == 404, "sin paquete normativo no hay regla de cloro -> 404")
            r = client.post("/packs/EC-ARCA/adopt", headers=h)
            check(r.status_code == 200 and len(r.json()["active_packs"]) == 3, "3 paquetes activos de nuevo")
            check(len(client.get("/checklist-templates", headers=h).json()) == 28, "28 listas disponibles (G2-G6, CAP, T-06, T-08, Evaluar antes de comprar y 7H de la Guía 3)")
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
            check([s["code"] for s in route["stages"]] == ["G1", "G2", "G3", "G4", "G5", "G6", "INT"], "7 etapas en orden")
            g3 = {i["template_id"]: i for i in route["stages"][2]["lists"]}
            check(set(g3) == {"MA-G3-START", "MA-AP2", "MA-7A", "MA-7E", "MA-7G1", "MA-G3-BUY", "MA-G3-7H"}, "la etapa G3 agrupa sus 7 listas")
            check(g3["MA-AP2"]["status"] == "done" and g3["MA-7A"]["status"] == "never", "semáforo aplicado, 7A sin aplicar")
            check(g3["MA-7A"]["frequency_days"] == 90 and g3["MA-7E"]["frequency_days"] == 30, "frecuencias del catálogo")
            check(route["stages"][2]["summary"]["applied"] == 1, "resumen de la etapa: 1 aplicada")
            check(route["stages"][0]["lists"] == [] and route["stages"][0]["products"], "etapa sin listas muestra sus productos")
            counts = {s["code"]: s["summary"]["total"] for s in route["stages"]}
            check(counts == {"G1": 0, "G2": 4, "G3": 7, "G4": 3, "G5": 7, "G6": 4, "INT": 3}, f"listas por etapa {counts}")

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

            print("6d. CAP como cuestionario (0026)")
            cap = next(t for t in client.get("/checklist-templates", headers=h).json() if t["id"] == "MA-CAP")
            check(cap["kind"] == "questionnaire" and len(cap["items"]) == 18 and cap["scale"] == [],
                  "CAP: 18 preguntas, cada una con sus opciones")
            key = {i["key"]: next(o["code"] for o in i["options"] if o["score"] == 2) for i in cap["items"]}
            check("".join(key.values()) == "bbabbabbbaaabbabba", "clave de T-05 tal cual la guía")
            wrong = {k: ("c" if v != "c" else "a") for k, v in key.items()}

            def cap_answers(correct_keys: set[str]) -> list[dict]:
                return [{"item_key": k, "answer_code": key[k] if k in correct_keys else wrong[k]} for k in key]

            all_keys = set(key)
            g1_g3 = {f"q{n:02d}" for n in range(1, 10)}
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-CAP", "answers": cap_answers(g1_g3)})
            check(r.status_code == 422, "sin momento ni participante -> 422")
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-CAP", "answers": cap_answers(g1_g3),
                                                                 "context": {"moment": "mitad", "participant_code": "P-01"}})
            check(r.status_code == 422, "momento fuera de las opciones -> 422")
            for code, moment, correct in (("P-01", "initial", g1_g3), ("P-02", "initial", set()),
                                          ("P-01", "final", all_keys), ("P-02", "final", g1_g3)):
                r = client.post("/checklist-runs", headers=h, json={
                    "template_id": "MA-CAP", "answers": cap_answers(correct),
                    "context": {"moment": moment, "participant_code": code}})
                check(r.status_code == 201 and r.json()["findings_created"] == [], f"CAP {moment} {code}: 201 sin hallazgos")
            check(r.json()["score"] == {"score": 18, "max_score": 36, "pct": 50.0}, "puntaje con la clave: 9 aciertos = 18/36")
            detail = client.get(f"/checklist-runs/{r.json()['run_id']}", headers=h).json()
            check(detail["context"] == {"moment": "final", "participant_code": "P-02"}, "la aplicación guarda momento y participante")
            check(detail["answers"][0]["answer_label"].startswith("b) "), "etiqueta de la opción del ítem")
            analysis = client.get("/checklist-templates/MA-CAP/analysis", headers=h).json()
            check(analysis["participants"] == {"initial": 2, "final": 2} and analysis["paired_participants"] == 2,
                  "2 participantes con inicial y final")
            guides = {row["code"]: row for row in analysis["groupings"][0]["rows"]}
            check(guides["G1"]["moments"]["initial"]["pct"] == 50.0 and guides["G1"]["moments"]["final"]["level"] == "Alto",
                  "Guía 1: inicial 50 %, final Alto")
            check(guides["G4"]["moments"]["initial"]["level"] == "Bajo" and guides["G4"]["difference_pct"] == 50.0,
                  "Guía 4: de Bajo a +50 puntos")
            dims = {row["code"]: row for row in analysis["groupings"][1]["rows"]}
            check(set(dims) == {"knowledge", "attitude", "practice"} and dims["knowledge"]["moments"]["final"]["max_score"] == 12,
                  "3 dimensiones, 12 puntos máximos cada una")
            check(analysis["total"]["moments"]["initial"]["avg_score"] == 9.0 and analysis["total"]["difference_pct"] == 50.0,
                  "total: 9/36 inicial, +50 puntos al final")
            check(client.get("/checklist-templates/MA-7A/analysis", headers=h).status_code == 404,
                  "una lista sin análisis -> 404")

            print("6e. Pasaporte de productos (T-07, 0028)")
            pp = client.get("/passport", headers=h).json()
            check([s["code"] for s in pp["stages"]] == ["G1", "G2", "G3", "G4", "G5", "G6", "INT"], "pasaporte por etapa")
            check(pp["summary"]["total"] == 42 and pp["summary"]["pending"] == 42,
                  "42 productos del catálogo, todos pendientes al empezar")
            first = pp["stages"][0]["products"][0]
            check(first["code"] == "G1-P01" and first["title"] == "Ficha territorial" and not first["registered"],
                  "producto sin registro = pendiente")
            r = client.put("/passport/EC-MUNICIPIOS-AZULES/G1-P01", headers=h,
                           json={"status": "complete", "evidence": "  Carpeta de la junta, folio 3 "})
            check(r.status_code == 200 and r.json()["evidence"] == "Carpeta de la junta, folio 3", "producto completo con evidencia")
            r = client.put("/passport/EC-MUNICIPIOS-AZULES/G2-P02", headers=h,
                           json={"status": "to_validate", "to_improvement_plan": True})
            check(r.status_code == 200, "acta por validar, pasa a G6")
            check(client.put("/passport/EC-MUNICIPIOS-AZULES/G1-P01", headers=h, json={"status": "listo"}).status_code == 422,
                  "estado inventado -> 422")
            check(client.put("/passport/EC-MUNICIPIOS-AZULES/G9-P99", headers=h, json={"status": "complete"}).status_code == 404,
                  "producto inexistente -> 404")
            check(client.put("/passport/NO-EXISTE/G1-P01", headers=h, json={"status": "complete"}).status_code == 404,
                  "paquete no activo -> 404")
            route = client.get("/process-route", headers=h).json()
            stages = {s["code"]: s for s in route["stages"]}
            check(stages["G1"]["products"][0]["status"] == "complete" and stages["G1"]["products_summary"]["complete"] == 1,
                  "la ruta muestra el estado del producto")
            check(stages["G2"]["products_summary"]["to_improvement_plan"] == 1, "la ruta cuenta lo que pasa a G6")
            check(stages["INT"]["has_follow_up"] and not stages["G1"]["has_follow_up"], "el seguimiento vive en la etapa INT")

            print("6f. Seguimiento 7-30-90 (T-09, 0028)")
            check(client.get("/follow-up", headers=h).status_code == 409, "sin zona horaria -> 409 (no se usa la fecha UTC)")
            check(client.put("/settings/timezone", headers=h, json={"timezone": "America/Atlantida"}).status_code == 422,
                  "zona inventada -> 422")
            r = client.put("/settings/timezone", headers=h, json={"timezone": "America/Guayaquil"})
            check(r.status_code == 200 and client.get("/settings/timezone", headers=h).json()["timezone"] == "America/Guayaquil",
                  "zona horaria de la junta guardada")
            local_today = datetime.now(ZoneInfo("America/Guayaquil")).date()
            fu = client.get("/follow-up", headers=h).json()
            check(fu["cycles"] == [] and [p["pack_id"] for p in fu["programs"]] == ["EC-MUNICIPIOS-AZULES"],
                  "sin ciclos; el programa define seguimiento")
            anchor = (local_today - timedelta(days=35)).isoformat()
            r = client.post("/follow-up/cycles", headers=h,
                            json={"pack_id": "EC-MUNICIPIOS-AZULES", "anchor_date": anchor, "title": "Taller E2E"})
            check(r.status_code == 201, "ciclo creado con fecha de cierre hace 35 días")
            cycle_id = r.json()["cycle_id"]
            check(client.post("/follow-up/cycles", headers=h, json={"pack_id": "EC-ARCA", "anchor_date": anchor,
                                                                    "title": "x"}).status_code == 404,
                  "paquete sin seguimiento -> 404")
            check(client.post("/follow-up/cycles", headers=h, json={"pack_id": "EC-MUNICIPIOS-AZULES", "anchor_date": anchor,
                                                                    "title": "  "}).status_code == 422, "ciclo sin nombre -> 422")
            r = client.post(f"/follow-up/cycles/{cycle_id}/items", headers=h, json={
                "milestone_code": "D7", "commitment": "Completar el padrón con cédulas faltantes", "responsible": "Secretaría"})
            check(r.status_code == 201 and r.json()["status"] == "pending", "compromiso a 7 días")
            item_id = r.json()["item_id"]
            r = client.post(f"/follow-up/cycles/{cycle_id}/items", headers=h, json={
                "milestone_code": "D30", "commitment": "Usar la bitácora de cloro todos los días"})
            check(r.status_code == 201, "compromiso a 30 días")
            check(client.post(f"/follow-up/cycles/{cycle_id}/items", headers=h,
                              json={"milestone_code": "D45", "commitment": "x"}).status_code == 404, "momento inexistente -> 404")
            check(client.post(f"/follow-up/cycles/{cycle_id}/items", headers=h,
                              json={"milestone_code": "D7", "commitment": " "}).status_code == 422, "compromiso vacío -> 422")
            check(client.post("/follow-up/cycles/no-es-uuid/items", headers=h,
                              json={"milestone_code": "D7", "commitment": "x"}).status_code == 404, "ciclo mal formado -> 404")
            r = client.patch(f"/follow-up/items/{item_id}", headers=h, json={
                "status": "done", "situation": "Padrón completo", "evidence": "Padrón firmado"})
            check(r.status_code == 200 and r.json()["status"] == "done" and r.json()["responsible"] == "Secretaría",
                  "compromiso cumplido; lo no enviado no cambia")
            check(client.patch(f"/follow-up/items/{item_id}", headers=h, json={"status": "quizas"}).status_code == 422,
                  "estado inventado -> 422")
            check(client.patch(f"/follow-up/items/{uuid.uuid4()}", headers=h, json={"status": "done"}).status_code == 404,
                  "compromiso inexistente -> 404")
            r = client.put(f"/follow-up/cycles/{cycle_id}/milestones/D7/review", headers=h,
                           json={"reviewed_on": local_today.isoformat(), "summary": "Carpeta ordenada"})
            check(r.status_code == 200, "revisión a 7 días registrada")
            cycle = client.get("/follow-up", headers=h).json()["cycles"][0]
            ms = {m["code"]: m for m in cycle["milestones"]}
            check([m["code"] for m in cycle["milestones"]] == ["D7", "D30", "D90"], "momentos en orden")
            check(ms["D7"]["status"] == "reviewed" and ms["D7"]["pending_items"] == 0, "7 días: revisado, sin pendientes")
            check(ms["D30"]["status"] == "due" and ms["D30"]["days_to_due"] == -5 and ms["D30"]["pending_items"] == 1,
                  "30 días: venció hace 5 días con 1 compromiso pendiente")
            check(ms["D90"]["status"] == "upcoming" and ms["D90"]["due_date"] == (local_today + timedelta(days=55)).isoformat(),
                  "90 días: faltan 55")
            check("bitácoras" in ms["D30"]["review_guide"], "qué revisar sale del catálogo de la guía")

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
                    for table in ("product_record", "follow_up_review", "follow_up_item", "follow_up_cycle",
                                  "finding", "checklist_answer", "checklist_run", "tenant_pack", "network_asset", "app_user"):
                        conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
            conn.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
            print("Limpieza: junta de prueba y sus datos borrados")
    print("SPRINT D0.2 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
