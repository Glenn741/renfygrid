"""Verificacion end-to-end real de Track D, Sprint D12.2 (T-06, T-08 y T-10
de la Guia 7, migracion 0043) -- HTTP real (FastAPI TestClient), JWT real,
Postgres real con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. T-06 Evaluacion diaria: una respuesta por participante y jornada, con
     las preguntas abiertas; el analisis por tipo compara el dia 1 con el 2.
  2. T-08 Rubrica de microfacilitacion: pide la persona facilitadora; el
     puntaje y la observacion por criterio.
  3. T-10 Consolidado: la CAP propone como observacion la guia que quedo en
     el rango mas bajo; se registra, deja de proponerse, cambia de estado;
     validaciones y permisos.
  4. Aislamiento.
Al final borra SOLO las organizaciones de prueba y lo que crearon.

Uso:
    python verify_facilitation_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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

JWT_SECRET = "e2e-d122-secret"
ORDER_SIGNING_SECRET = "e2e-d122-order-secret"
T06 = ["learn_explain", "learn_tool", "fac_clear", "fac_participation", "app_useful"]
T08 = ["purpose", "experience", "language", "participation", "dynamic", "technical", "time", "closure", "feedback"]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  OK  {message}")


def run(dsn: str) -> None:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main  # despues de fijar el entorno
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D12.2 programa') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D12.2 otro') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "admin@d122.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d122.test", "clave-oper-1", "operator")
            create_app_user(conn, other_id, "admin@otro-d122.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d122.test", "clave-admin-1")
            op = login(tenant_id, "operador@d122.test", "clave-oper-1")
            other = login(other_id, "admin@otro-d122.test", "clave-admin-2")

            print("1. T-06 Evaluación diaria")
            day1 = [("yes", "partly", "no", "no", "yes"), ("partly", "partly", "no", "partly", "yes"), ("yes", "yes", "partly", "no", "yes")]
            for i, ans in enumerate(day1):
                r = client.post("/checklist-runs", headers=op, json={
                    "template_id": "MA-T06", "answers": [{"item_key": k, "answer_code": a} for k, a in zip(T06, ans)],
                    "context": {"day": "D1", "facilitator": "Facilitadora GAD",
                                **({"to_clarify": "Cómo se calcula la dosis de cloro"} if i == 0 else {})}})
                assert r.status_code == 201, r.text
            for ans in (("yes", "yes", "yes", "partly", "yes"), ("yes", "partly", "yes", "yes", "yes")):
                client.post("/checklist-runs", headers=op, json={
                    "template_id": "MA-T06", "answers": [{"item_key": k, "answer_code": a} for k, a in zip(T06, ans)],
                    "context": {"day": "D2"}})
            check(client.post("/checklist-runs", headers=op, json={"template_id": "MA-T06",
                                                                   "answers": [{"item_key": k, "answer_code": "yes"} for k in T06],
                                                                   "context": {"day": "D9"}}).status_code == 422, "jornada inexistente -> 422")
            check(client.post("/checklist-runs", headers=op, json={"template_id": "MA-T06",
                                                                   "answers": [{"item_key": k, "answer_code": "yes"} for k in T06]}).status_code == 422,
                  "sin jornada -> 422")
            a = client.get("/checklist-templates/MA-T06/analysis", headers=h).json()
            rows = {r["code"]: r for r in a["groupings"][0]["rows"]}
            check(a["participants"]["D1"] == 3 and a["participants"]["D2"] == 2, "3 respuestas el día 1 y 2 el día 2")
            check(rows["facilitation"]["moments"]["D1"]["pct"] == 16.7 and rows["facilitation"]["moments"]["D2"]["pct"] == 87.5,
                  "facilitación: 16,7 % el día 1, 87,5 % el día 2")
            check(rows["facilitation"]["difference_pct"] is None, "la diferencia se mide entre el primer y el último día (el 8 aún no)")
            runs = client.get("/checklist-runs?template_id=MA-T06", headers=h).json()
            check(any(r["context"].get("to_clarify") == "Cómo se calcula la dosis de cloro" for r in runs), "la pregunta abierta queda guardada")

            print("2. T-08 Rúbrica de microfacilitación")
            ans = [{"item_key": k, "answer_code": "achieved"} for k in T08]
            ans[6] = {"item_key": "time", "answer_code": "reinforce", "observation": "Se pasó 20 minutos en la dinámica"}
            check(client.post("/checklist-runs", headers=h, json={"template_id": "MA-T08", "answers": ans}).status_code == 422,
                  "sin persona facilitadora -> 422")
            r = client.post("/checklist-runs", headers=h, json={"template_id": "MA-T08", "answers": ans, "context": {
                "facilitator": "Técnico de la asociación", "strength": "Parte de la experiencia del grupo",
                "priority_adjustment": "Administrar el tiempo de la dinámica", "next_step": "Practicar con cronómetro"}})
            check(r.status_code == 201 and r.json()["score"]["score"] == 16 and r.json()["score"]["max_score"] == 18
                  and r.json()["findings_created"] == [], "16 de 18, sin hallazgos (es retroalimentación, no inspección)")

            print("3. T-10 Consolidado de observaciones")
            cap = next(t for t in client.get("/checklist-templates", headers=h).json() if t["id"] == "MA-CAP")
            for pid in ("P01", "P02"):
                answers = []
                for it in cap["items"]:
                    best = max(it["options"], key=lambda o: o["score"])["code"]
                    worst = min(it["options"], key=lambda o: o["score"])["code"]
                    answers.append({"item_key": it["key"], "answer_code": worst if it["groups"]["guide"] == "G3" else best})
                assert client.post("/checklist-runs", headers=h, json={"template_id": "MA-CAP", "answers": answers,
                                                                       "context": {"moment": "initial", "participant_code": pid}}).status_code == 201
            o = client.get("/program/observations", headers=h).json()
            check([s["code"] for s in o["sources"]] == ["application", "cap", "follow_up"] and len(o["stages"]) == 7, "fuentes y guías del paquete")
            sug = [s for s in o["suggestions"] if s["stage_code"] == "G3"]
            check(len(sug) == 1 and "0 %" in sug[0]["finding"] and "Bajo" in sug[0]["finding"] and "Inicial" in sug[0]["finding"]
                  and not any(s["stage_code"] == "G2" for s in o["suggestions"]), "la CAP propone la Guía 3 (0 %, Bajo, inicial); no la 2")
            check(client.post("/program/observations", headers=op, json={"stage_code": "G3", "source_code": "cap", "finding": "x",
                                                                          "priority": "high"}).status_code == 403, "el operador no registra T-10")
            check(client.post("/program/observations", headers=h, json={"stage_code": "G9", "source_code": "cap", "finding": "x",
                                                                         "priority": "high"}).status_code == 404, "guía inexistente -> 404")
            check(client.post("/program/observations", headers=h, json={"stage_code": "G3", "source_code": "rumor", "finding": "x",
                                                                         "priority": "high"}).status_code == 404, "fuente inexistente -> 404")
            check(client.post("/program/observations", headers=h, json={"stage_code": "G3", "source_code": "cap",
                                                                         "priority": "high"}).status_code == 422, "sin hallazgo -> 422")
            r = client.post("/program/observations", headers=h, json={
                "stage_code": "G3", "source_code": "cap", "finding": sug[0]["finding"], "priority": "high",
                "proposed_change": "Simplificar el ejemplo de cloración y agregar práctica con comparador",
                "reviewer": "Equipo técnico del programa", "community": "Gualaceo"})
            check(r.status_code == 201 and r.json()["status"] == "open" and r.json()["pack_id"] == "EC-MUNICIPIOS-AZULES", "observación registrada")
            obs = r.json()["observation_id"]
            check(not any(s["stage_code"] == "G3" for s in client.get("/program/observations", headers=h).json()["suggestions"]),
                  "la Guía 3 deja de proponerse")
            r = client.post("/program/observations", headers=h, json={
                "stage_code": "G1", "source_code": "application", "finding": "La dinámica del mapa parlante toma el doble del tiempo previsto",
                "priority": "medium"})
            check(r.status_code == 201, "observación de aplicación")
            r = client.patch(f"/program/observations/{obs}", headers=h, json={"status": "in_review"})
            check(r.status_code == 200 and r.json()["status"] == "in_review" and r.json()["proposed_change"].startswith("Simplificar"),
                  "en revisión, sin tocar lo demás")
            check(client.patch(f"/program/observations/{obs}", headers=h, json={"status": "olvidada"}).status_code == 422, "estado inventado -> 422")
            o = client.get("/program/observations", headers=h).json()
            check(o["summary"]["total"] == 2 and o["summary"]["open"] == 1 and o["summary"]["in_review"] == 1, "2 observaciones: 1 abierta, 1 en revisión")

            print("4. Aislamiento")
            oo = client.get("/program/observations", headers=other).json()
            check(oo["observations"] == [] and oo["suggestions"] == [], "otra organización no ve nada")
            check(client.patch(f"/program/observations/{obs}", headers=other, json={"status": "discarded"}).status_code == 404,
                  "ni cambia una observación ajena")
            check(client.get("/checklist-templates/MA-T06/analysis", headers=other).json()["participants"]["D1"] == 0,
                  "ni ve las evaluaciones diarias ajenas")
            check(client.patch(f"/program/observations/{uuid.uuid4()}", headers=h, json={"status": "open"}).status_code == 404,
                  "observación inexistente -> 404")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("program_observation", "checklist_answer", "checklist_run", "finding", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: organizaciones de prueba y sus datos borrados")
    print("SPRINT D12.2 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
