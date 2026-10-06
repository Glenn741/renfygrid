"""Verificacion end-to-end real de Track D, Sprint D2 (calidad del agua y
laboratorio, migracion 0034) -- HTTP real (FastAPI TestClient), JWT real,
Postgres real con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. Catalogo: parametros de laboratorio sin regla (sus limites son de la
     NTE INEN 1108, no estan en las guias); E. coli con regla.
  2. Plan de muestreo de la junta: alta con su frecuencia (la fija la
     junta), validaciones, estado "sin muestra" y revision anual (plazo del
     paquete).
  3. Muestra con E. coli presente -> alerta critica con hallazgo de
     prioridad alta; coliformes y arsenico sin regla se guardan sin
     interpretar; "<" no concluyente no se interpreta; repetir en el mismo
     punto se suma al mismo hallazgo; E. coli 0 -> ausente.
  4. La muestra del plan pone el plan al dia; la vista "Hoy" y el resumen de
     calidad muestran la alerta critica.
  5. Validaciones (422/404) y permisos: el operador registra resultados pero
     no define el plan.
  6. Aislamiento entre juntas.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_water_quality_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d2-secret"
ORDER_SIGNING_SECRET = "e2e-d2-order-secret"


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
    now = datetime.now(timezone.utc)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D2 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D2 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "admin@d2.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d2.test", "clave-oper-1", "operator")
            create_app_user(conn, other_id, "admin@otra-d2.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d2.test", "clave-admin-1")
            op = login(tenant_id, "operador@d2.test", "clave-oper-1")
            other = login(other_id, "admin@otra-d2.test", "clave-admin-2")
            client.put("/settings/timezone", headers=h, json={"timezone": "America/Guayaquil"})
            tank = client.post("/sampling-points", headers=h, json={"kind_code": "tank_outlet", "name": "Salida del tanque"}).json()["point_id"]
            school = client.post("/sampling-points", headers=h, json={"kind_code": "critical", "name": "Escuela"}).json()["point_id"]

            print("1. Catalogo")
            params = {p["code"]: p for p in client.get("/quality/parameters", headers=h).json()}
            check({"total_coliforms", "nitrate", "fluoride", "arsenic", "iron", "manganese"} <= set(params), "parámetros de laboratorio")
            check(params["arsenic"]["bands"] is None and params["arsenic"]["measured_by"] == "lab", "arsénico sin regla (norma no cargada)")
            check(params["e_coli"]["bands"] is not None, "E. coli con regla")

            print("2. Plan de muestreo")
            r = client.post("/quality/plan", headers=h, json={
                "name": "Microbiológico mensual", "parameters": ["e_coli", "total_coliforms"], "frequency_days": 30,
                "sampling_point_id": school, "source_note": "Oficio ARCA (frecuencia según la categoría de la junta)"})
            check(r.status_code == 201 and r.json()["status"] == "never", "plan creado, sin muestra todavía")
            plan_id = r.json()["plan_item_id"]
            for body, code, msg in (({"name": "Microbiológico mensual", "parameters": ["e_coli"], "frequency_days": 30}, 409, "nombre repetido -> 409"),
                                    ({"name": "x", "parameters": [], "frequency_days": 30}, 422, "sin parámetros -> 422"),
                                    ({"name": "x", "parameters": ["oro"], "frequency_days": 30}, 404, "parámetro inexistente -> 404"),
                                    ({"name": "x", "parameters": ["e_coli"], "frequency_days": 0}, 422, "frecuencia 0 -> 422"),
                                    ({"name": "x", "parameters": ["e_coli"], "frequency_days": 30, "sampling_point_id": str(uuid.uuid4())}, 404,
                                     "punto inexistente -> 404")):
                check(client.post("/quality/plan", headers=h, json=body).status_code == code, msg)
            plan = client.get("/quality/plan", headers=h).json()
            check(plan["review"]["period_days"] == 365 and plan["review"]["status"] == "never" and "una vez al año" in plan["review"]["source"],
                  "revisión anual del plan (plazo del paquete), todavía sin revisar")
            rev = client.post("/quality/plan/reviews", headers=h, json={"reviewed_on": date.today().isoformat(), "notes": "Revisado con el GAD"})
            check(rev.status_code == 201 and rev.json()["status"] == "ok", "revisión registrada: al día")
            r = client.patch(f"/quality/plan/{plan_id}", headers=h, json={"frequency_days": 60})
            check(r.status_code == 200 and r.json()["frequency_days"] == 60 and r.json()["name"] == "Microbiológico mensual",
                  "cambiar la frecuencia sin tocar el resto")

            print("3. Muestras y resultados")
            sampled = (now - timedelta(hours=2)).isoformat()
            r = client.post("/quality/samples", headers=h, json={
                "sampled_at": sampled, "laboratory": "Laboratorio del GAD Gualaceo", "report_ref": "INF-2026-118",
                "sampling_point_id": school, "plan_item_id": plan_id, "reason": "plan",
                "results": [{"parameter_code": "e_coli", "value": 3}, {"parameter_code": "total_coliforms", "value": 12},
                            {"parameter_code": "arsenic", "value": 0.005, "qualifier": "<"}]})
            check(r.status_code == 201 and r.json()["critical"] and r.json()["findings_created"] == 1, "E. coli presente: alerta crítica con 1 hallazgo")
            res = {x["parameter_code"]: x for x in r.json()["results"]}
            check(res["e_coli"]["severity"] == "critical" and res["e_coli"]["result_label"] == "Presente", "E. coli 3 -> Presente (crítico)")
            check(res["total_coliforms"]["interpretation"] == "no_rule" and res["arsenic"]["interpretation"] == "no_rule"
                  and res["arsenic"]["qualifier"] == "<", "coliformes y arsénico sin regla: guardados sin interpretar")
            findings = client.get("/findings", headers=h).json()
            f = next(x for x in findings if x["finding_id"] == res["e_coli"]["finding_id"])
            check(f["priority"] == "high" and f["description"].startswith("ALERTA CRÍTICA") and "Escuela" in f["description"],
                  "hallazgo de prioridad alta con punto y acción")
            r2 = client.post("/quality/samples", headers=h, json={
                "sampled_at": (now - timedelta(hours=1)).isoformat(), "laboratory": "Laboratorio del GAD Gualaceo", "reason": "alert",
                "sampling_point_id": school, "results": [{"parameter_code": "e_coli", "value": 1}]})
            check(r2.json()["findings_created"] == 0 and r2.json()["results"][0]["finding_id"] == res["e_coli"]["finding_id"],
                  "repetir en el mismo punto se suma al mismo hallazgo")
            field = client.post("/field-readings", headers=h, json={"parameter_code": "turbidity", "value": 8, "sampling_point_id": tank}).json()
            check(field["finding_created"], "turbiedad 8 UTN medida en campo abre hallazgo")
            r3 = client.post("/quality/samples", headers=h, json={
                "sampled_at": sampled, "laboratory": "Laboratorio del GAD Gualaceo", "sampling_point_id": tank,
                "results": [{"parameter_code": "e_coli", "value": 0}, {"parameter_code": "free_chlorine", "value": 0.8},
                            {"parameter_code": "turbidity", "value": 9, "qualifier": ">"}]})
            res3 = {x["parameter_code"]: x for x in r3.json()["results"]}
            check(res3["e_coli"]["result_label"] == "Ausente" and not r3.json()["critical"], "E. coli 0 en el tanque -> Ausente")
            check(res3["free_chlorine"]["result_code"] == "adequate", "parámetros de campo también por laboratorio")
            check(res3["turbidity"]["result_code"] == "high", "turbiedad >9: todo el intervalo es Alto")
            check(res3["turbidity"]["finding_id"] == field["finding_id"], "el laboratorio se suma al hallazgo abierto por la medición de campo")
            r4 = client.post("/quality/samples", headers=h, json={
                "sampled_at": sampled, "laboratory": "Lab", "sampling_point_id": tank,
                "results": [{"parameter_code": "free_chlorine", "value": 1, "qualifier": "<"}]})
            check(r4.json()["results"][0]["interpretation"] == "inconclusive", "cloro <1: no concluyente (puede ser bajo o adecuado)")

            print("4. Plan al dia y alertas")
            item = next(p for p in client.get("/quality/plan", headers=h).json()["items"] if p["plan_item_id"] == plan_id)
            check(item["status"] == "ok" and item["last_sample_id"] == r.json()["sample_id"], "la muestra del plan lo pone al día")
            ov = client.get("/quality/overview", headers=h).json()
            check(ov["critical_open"] == 1 and any(a["critical"] for a in ov["alerts"]), "resumen: 1 alerta crítica abierta")
            today = client.get("/operations/today", headers=h).json()
            check(today["summary"]["critical_quality_open"] == 1, "la vista Hoy avisa la alerta crítica")
            samples = client.get(f"/quality/samples?point_id={school}", headers=h).json()
            check(len(samples) == 2 and samples[0]["reason"] == "alert", "historial del punto, la más reciente primero")

            print("5. Validaciones y permisos")
            base = {"sampled_at": sampled, "laboratory": "Lab", "results": [{"parameter_code": "e_coli", "value": 0}]}
            for body, code, msg in ((dict(base, laboratory=" "), 422, "sin laboratorio -> 422"),
                                    (dict(base, results=[]), 422, "sin resultados -> 422"),
                                    (dict(base, results=[{"parameter_code": "e_coli", "value": 0}] * 2), 422, "parámetro repetido -> 422"),
                                    (dict(base, results=[{"parameter_code": "e_coli", "value": 0, "qualifier": "~"}]), 422, "calificador inválido -> 422"),
                                    (dict(base, results=[{"parameter_code": "oro", "value": 1}]), 404, "parámetro inexistente -> 404"),
                                    (dict(base, reason="capricho"), 422, "motivo inválido -> 422"),
                                    (dict(base, sampled_at="2026-10-05T07:00:00"), 422, "fecha sin zona -> 422"),
                                    (dict(base, sampling_point_id=str(uuid.uuid4())), 404, "punto ajeno -> 404"),
                                    (dict(base, plan_item_id="x"), 404, "plan mal formado -> 404")):
                check(client.post("/quality/samples", headers=h, json=body).status_code == code, msg)
            check(client.post("/quality/samples", headers=op, json=base).status_code == 201, "el operador registra resultados")
            check(client.post("/quality/plan", headers=op, json={"name": "y", "parameters": ["nitrate"], "frequency_days": 180}).status_code == 403,
                  "pero no define el plan (403)")

            print("6. Aislamiento")
            ov2 = client.get("/quality/overview", headers=other).json()
            check(ov2["alerts"] == [] and ov2["plan"]["items"] == [], "la otra junta no ve alertas ni plan")
            check(client.get(f"/quality/samples/{r.json()['sample_id']}", headers=other).status_code == 404, "ni la muestra")
            check(client.post("/quality/samples", headers=other, json=dict(base, sampling_point_id=school)).status_code == 404,
                  "ni puede usar un punto ajeno")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("lab_result", "lab_sample", "lab_plan_review", "lab_plan_item", "field_reading",
                                      "sampling_point", "finding", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D2 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
