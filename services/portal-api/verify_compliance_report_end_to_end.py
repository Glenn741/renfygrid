"""Verificacion end-to-end real de Track D, Sprint D12.3 (informe de
cumplimiento al ente rector, migracion 0044) -- HTTP real (FastAPI
TestClient), JWT real, Postgres real con el rol de aplicacion (RLS activo),
sin mocks.

Que prueba, en espanol llano:
  1. La junta genera el informe de un periodo: las 6 secciones del paquete
     con lo del periodo (y nada de fuera): laboratorio con la fuente de la
     regla, cloro por tipo de punto, plan de muestreo, alertas y emergencias,
     calendario y saneamiento (7F). Declara que el formato es provisional.
  2. Validaciones y permisos: el operador no genera; periodo futuro o al
     reves; plantilla inexistente; organizacion sin zona horaria.
  3. Foto inmutable: un dato nuevo no cambia el informe ya generado (ni
     siquiera con un UPDATE directo en la base); otro informe si lo ve.
  4. Envio: a quien y cuando, una sola vez.
  5. Aislamiento.
Al final borra SOLO las organizaciones de prueba y lo que crearon.

Uso:
    python verify_compliance_report_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from e2e_packs import adopt_program_packs  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d123-secret"
ORDER_SIGNING_SECRET = "e2e-d123-order-secret"
TZ = "America/Guayaquil"


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
    today = datetime.now(ZoneInfo(TZ)).date()

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D12.3 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D12.3 otra') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            adopt_program_packs(conn, tenant_id, other_id)
            create_app_user(conn, tenant_id, "directiva@d123.test", "clave-dir-1", "board")
            create_app_user(conn, tenant_id, "operador@d123.test", "clave-oper-1", "operator")
            create_app_user(conn, tenant_id, "admin@d123.test", "clave-admin-1", "supervisor")
            create_app_user(conn, other_id, "admin@otra-d123.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            bd = login(tenant_id, "directiva@d123.test", "clave-dir-1")
            op = login(tenant_id, "operador@d123.test", "clave-oper-1")
            h = login(tenant_id, "admin@d123.test", "clave-admin-1")
            other = login(other_id, "admin@otra-d123.test", "clave-admin-2")
            client.put("/settings/timezone", headers=h, json={"timezone": TZ})

            tank = client.post("/sampling-points", headers=h, json={"kind_code": "tank_outlet", "name": "Salida del tanque"}).json()["point_id"]
            far = client.post("/sampling-points", headers=h, json={"kind_code": "network_far", "name": "Escuela"}).json()["point_id"]
            for point, v, ago in ((tank, 1.0, 1), (far, 0.15, 1), (far, 0.5, 2), (far, 0.1, 40)):
                client.post("/field-readings", headers=op, json={"parameter_code": "free_chlorine", "value": v, "sampling_point_id": point,
                                                                  "measured_at": (now - timedelta(days=ago)).isoformat()})
            plan = client.post("/quality/plan", headers=h, json={"name": "Microbiológico mensual", "parameters": ["e_coli"],
                                                                 "frequency_days": 30, "sampling_point_id": far}).json()["plan_item_id"]
            client.post("/quality/samples", headers=op, json={
                "sampled_at": (now - timedelta(hours=20)).isoformat(), "laboratory": "Laboratorio del GAD", "report_ref": "INF-077",
                "sampling_point_id": far, "plan_item_id": plan, "reason": "plan", "results": [{"parameter_code": "e_coli", "value": 0}]})
            client.post("/emergencies/activations", headers=op, json={"type_code": "main_break", "notes": "Rotura en la conducción"})
            septic = client.post("/network-assets", headers=h, json={"type": "septic_tank", "status": "operational"}).json()["asset_id"]
            crew = client.post("/maintenance/crews", headers=h, json={"name": "Operador"}).json()["crew_id"]
            o = client.post("/maintenance-orders", headers=h, json={"asset_id": septic, "type": "preventive", "source": "manual",
                                                                   "priority": "medium", "reason": "Retiro de lodos"}).json()["order_id"]
            client.post(f"/maintenance-orders/{o}/schedule", headers=h, json={"scheduled_at": now.isoformat()})
            client.post(f"/maintenance-orders/{o}/assign", headers=h, json={"crew_id": crew})
            client.post(f"/maintenance-orders/{o}/start", headers=op)
            r = client.post(f"/maintenance-orders/{o}/close", headers=op, json={"status": "completed", "sludge_volume_m3": 3.5,
                                                                              "waste_handler": "GAD", "waste_destination": "Planta de lodos"})
            assert r.status_code == 200, r.text

            print("1. Generar el informe")
            lst = client.get("/reports/compliance", headers=bd).json()
            tpl = lst["templates"][0]
            check(tpl["code"] == "compliance" and len(tpl["sections"]) == 6 and lst["reports"] == [], "plantilla con 6 secciones, sin informes")
            body = {"report_code": "compliance", "period_from": (today - timedelta(days=7)).isoformat(), "period_to": today.isoformat()}
            r = client.post("/reports/compliance", headers=bd, json=body)
            check(r.status_code == 201 and r.json()["generated_by"] == "portal:directiva@d123.test", "la directiva genera el informe")
            rep = r.json()
            c = rep["content"]
            sec = {s["code"]: s["data"] for s in c["sections"]}
            check([s["code"] for s in c["sections"]] == ["lab", "chlorine", "sampling_plan", "alerts", "maintenance", "sanitation"],
                  "secciones en el orden del paquete")
            check("provisional" in c["template"]["format_note"] and c["organization"] == "E2E D12.3 junta", "declara el formato provisional")
            lab = sec["lab"]
            check(lab["summary"]["samples"] == 1 and lab["samples"][0]["report_ref"] == "INF-077"
                  and lab["samples"][0]["results"][0]["rule_source"], "laboratorio con la fuente de la regla")
            ch = {k["kind"]: k for k in sec["chlorine"]["by_point_kind"]}
            check(sec["chlorine"]["total"] == 3 and ch["tank_outlet"]["in_range"] == 1 and ch["network_far"]["n"] == 2
                  and ch["network_far"]["min"] == 0.15, "cloro del periodo por tipo de punto (la medición de hace 40 días no cuenta)")
            check(sec["sampling_plan"]["items"][0]["taken"] == 1 and sec["sampling_plan"]["compliance_pct"] == 100.0,
                  "plan de muestreo cumplido")
            check(sec["alerts"]["out_of_range_alerts"] >= 1 and len(sec["alerts"]["emergencies"]) == 1, "alertas y la emergencia")
            check(sec["sanitation"]["interventions"] == 1 and sec["sanitation"]["sludge_m3"] == 3.5
                  and sec["sanitation"]["pending_verification"] == 1, "7F: 3,5 m³ de lodos, destino por verificar")
            check("compliance_pct" in sec["maintenance"], "calendario anual")

            print("2. Validaciones y permisos")
            check(client.post("/reports/compliance", headers=op, json=body).status_code == 403, "el operador no genera informes")
            check(client.post("/reports/compliance", headers=bd, json={**body, "period_to": (today + timedelta(days=1)).isoformat()}).status_code == 422,
                  "periodo futuro -> 422")
            check(client.post("/reports/compliance", headers=bd, json={**body, "period_from": today.isoformat(),
                                                                        "period_to": (today - timedelta(days=3)).isoformat()}).status_code == 422,
                  "periodo al revés -> 422")
            check(client.post("/reports/compliance", headers=bd, json={**body, "report_code": "inventado"}).status_code == 404,
                  "plantilla inexistente -> 404")
            r = client.post("/reports/compliance", headers=other, json=body)
            check(r.status_code == 422 and "zona horaria" in r.json()["detail"], "sin zona horaria -> 422")

            print("3. Foto inmutable")
            client.post("/field-readings", headers=op, json={"parameter_code": "free_chlorine", "value": 0.8, "sampling_point_id": tank,
                                                             "measured_at": (now - timedelta(hours=1)).isoformat()})
            again = client.get(f"/reports/compliance/{rep['report_id']}", headers=h).json()
            check({s["code"]: s["data"] for s in again["content"]["sections"]}["chlorine"]["total"] == 3, "el informe generado no cambia")
            try:
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        conn.execute("UPDATE compliance_report SET content = '{}'::jsonb WHERE id = %s", (rep["report_id"],))
                blocked = False
            except psycopg.Error:
                blocked = True
            check(blocked, "ni con un UPDATE directo en la base")
            r2 = client.post("/reports/compliance", headers=bd, json=body).json()
            check({s["code"]: s["data"] for s in r2["content"]["sections"]}["chlorine"]["total"] == 4, "un informe nuevo sí ve el dato")
            check(len(client.get("/reports/compliance", headers=bd).json()["reports"]) == 2, "dos informes en el historial")

            print("4. Envío")
            check(client.post(f"/reports/compliance/{rep['report_id']}/sent", headers=bd, json={"sent_to": " ", "sent_on": today.isoformat()}).status_code == 422,
                  "sin destinatario -> 422")
            check(client.post(f"/reports/compliance/{rep['report_id']}/sent", headers=bd,
                              json={"sent_to": "ARCA", "sent_on": (today - timedelta(days=30)).isoformat()}).status_code == 422,
                  "enviado antes de generarlo -> 422")
            r = client.post(f"/reports/compliance/{rep['report_id']}/sent", headers=bd,
                            json={"sent_to": "ARCA — Dirección Zonal 6", "sent_on": today.isoformat(), "note": "Oficio JAAS-2026-031"})
            check(r.status_code == 200 and r.json()["sent_to"].startswith("ARCA") and r.json()["sent_by"] == "portal:directiva@d123.test",
                  "registrado como enviado")
            check(client.post(f"/reports/compliance/{rep['report_id']}/sent", headers=bd,
                              json={"sent_to": "GAD", "sent_on": today.isoformat()}).status_code == 409, "una sola vez -> 409")

            print("5. Aislamiento")
            check(client.get(f"/reports/compliance/{rep['report_id']}", headers=other).status_code == 404, "otra junta no lo ve")
            check(client.get("/reports/compliance", headers=other).json()["reports"] == [], "ni en su lista")
            check(client.post(f"/reports/compliance/{r2['report_id']}/sent", headers=other,
                              json={"sent_to": "x", "sent_on": today.isoformat()}).status_code == 404, "ni lo marca enviado")
            check(client.get(f"/reports/compliance/{uuid.uuid4()}", headers=bd).status_code == 404, "informe inexistente -> 404")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        conn.execute("UPDATE field_reading SET finding_id = NULL WHERE tenant_id = %s", (tid,))
                        conn.execute("UPDATE lab_result SET finding_id = NULL WHERE tenant_id = %s", (tid,))
                        for table in ("lab_result", "lab_sample", "lab_plan_item", "emergency_activation", "emergency_plan_entry",
                                      "field_reading", "finding", "sampling_point", "maintenance_order", "maintenance_crew",
                                      "network_asset", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                # compliance_report no tiene DELETE para la aplicacion (registro de envio): cae con el tenant (ON DELETE CASCADE)
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: organizaciones de prueba y sus datos borrados")
    print("SPRINT D12.3 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
