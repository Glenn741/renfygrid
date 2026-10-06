"""Verificacion end-to-end real de Track D, Sprint D5 (plan de emergencia,
migracion 0037) -- HTTP real (FastAPI TestClient), JWT real, Postgres real
con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano (Guia 3 §3.11 y Actividad participativa 6):
  1. El plan parte del catalogo: 6 emergencias con senales, primera accion y
     a quien avisar; donde la guia trae ejemplo, tambien el mensaje.
  2. La directiva ajusta una emergencia y agrega una propia; el operador no
     puede editar el plan (403). Validaciones 422/404.
  3. Contactos institucionales: alta, validacion y baja.
  4. Activacion manual (rotura principal); activarla otra vez no duplica,
     anota el nuevo disparo.
  5. Activacion AUTOMATICA: un analisis con E. coli presente activa
     "Contaminacion de agua"; otro positivo se suma a la misma. La vista Hoy
     cuenta las emergencias activas.
  6. Cierre, revision anual del plan y aislamiento entre juntas.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_emergencies_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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
from e2e_packs import adopt_program_packs  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d5-secret"
ORDER_SIGNING_SECRET = "e2e-d5-order-secret"


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
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D5 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D5 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            adopt_program_packs(conn, tenant_id, other_id)
            create_app_user(conn, tenant_id, "admin@d5.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d5.test", "clave-oper-1", "operator")
            create_app_user(conn, tenant_id, "directiva@d5.test", "clave-dir-1", "board")
            create_app_user(conn, other_id, "admin@otra-d5.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d5.test", "clave-admin-1")
            op = login(tenant_id, "operador@d5.test", "clave-oper-1")
            bd = login(tenant_id, "directiva@d5.test", "clave-dir-1")
            other = login(other_id, "admin@otra-d5.test", "clave-admin-2")
            for hh in (h, other):
                client.put("/settings/timezone", headers=hh, json={"timezone": "America/Guayaquil"})

            print("1. Plan desde el catalogo")
            plan = client.get("/emergencies", headers=h).json()
            entries = {e["type_code"]: e for e in plan["entries"]}
            check(list(entries) == ["heavy_rain", "drought", "main_break", "contamination", "sewage_overflow", "treatment_collapse"],
                  "las 6 emergencias de la Guía 3 en su orden")
            c = entries["contamination"]
            check(c["signals"].startswith("E. coli") and c["notify"] == "MSP, ARCA, GAD." and
                  c["community_message"].startswith("No consumir el agua") and not c["customized"], "textos de la guía y mensaje del ejemplo")
            check(entries["heavy_rain"]["community_message"] is None, "sin ejemplo en la guía: sin mensaje inventado")
            check(plan["review"]["period_days"] == 365 and plan["review"]["status"] == "never", "revisión anual, todavía sin revisar")

            print("2. Ajustes de la junta")
            r = client.put("/emergencies/plan", headers=bd, json={
                "type_code": "contamination", "responsible": "Presidencia y operador",
                "community_message": "No tome el agua de la llave hasta nuevo aviso. Hiérvala al menos 3 minutos.",
                "resources": "Bidones de 20 L en la casa comunal"})
            ce = {e["type_code"]: e for e in r.json()["entries"]}["contamination"]
            check(r.status_code == 200 and ce["customized"] and ce["responsible"] == "Presidencia y operador"
                  and ce["first_action"].startswith("Suspender"), "la directiva ajusta: lo no tocado conserva el texto de la guía")
            r = client.put("/emergencies/plan", headers=bd, json={"custom_label": "Incendio forestal en la microcuenca",
                                                                  "first_action": "Cerrar captación y avisar a bomberos"})
            check(len(r.json()["entries"]) == 7, "emergencia propia agregada")
            check(client.put("/emergencies/plan", headers=bd, json={"type_code": "drought", "custom_label": "x"}).status_code == 422,
                  "tipo y propia a la vez -> 422")
            check(client.put("/emergencies/plan", headers=bd, json={"type_code": "tsunami"}).status_code == 404, "tipo inexistente -> 404")
            check(client.put("/emergencies/plan", headers=op, json={"type_code": "drought", "responsible": "x"}).status_code == 403,
                  "el operador no edita el plan")

            print("3. Contactos")
            r = client.post("/emergencies/contacts", headers=bd, json={"institution": "MSP - Centro de salud", "phone": "07 222 0000",
                                                                      "person": "Médico de turno"})
            check(r.status_code == 201, "contacto agregado")
            check(client.post("/emergencies/contacts", headers=bd, json={"institution": "GAD", "phone": " "}).status_code == 422,
                  "sin teléfono -> 422")
            tmp = client.post("/emergencies/contacts", headers=bd, json={"institution": "Temporal", "phone": "1"}).json()["contact_id"]
            check(client.delete(f"/emergencies/contacts/{tmp}", headers=bd).status_code == 204, "contacto borrado")
            check(client.delete(f"/emergencies/contacts/{tmp}", headers=bd).status_code == 404, "borrar de nuevo -> 404")

            print("4. Activacion manual")
            r = client.post("/emergencies/activations", headers=op, json={"type_code": "main_break", "notes": "Fuga grande en la conducción"})
            check(r.status_code == 201 and r.json()["status"] == "active" and r.json()["trigger"] == "manual", "el operador activa la rotura principal")
            brk = r.json()["activation_id"]
            again = client.post("/emergencies/activations", headers=op, json={"type_code": "main_break", "notes": "Sigue la fuga"}).json()
            check(again["duplicate"] and again["activation_id"] == brk and "Sigue la fuga" in again["notes"], "activar otra vez no duplica")
            check(client.post("/emergencies/activations", headers=op, json={}).status_code == 422, "sin tipo -> 422")

            print("5. Activacion automatica por E. coli")
            school = client.post("/sampling-points", headers=h, json={"kind_code": "critical", "name": "Escuela"}).json()["point_id"]
            s1 = client.post("/quality/samples", headers=op, json={
                "sampled_at": (now - timedelta(hours=1)).isoformat(), "laboratory": "Lab GAD", "sampling_point_id": school,
                "results": [{"parameter_code": "e_coli", "value": 4}]}).json()
            check(len(s1["emergencies"]) == 1 and s1["emergencies"][0]["type_code"] == "contamination"
                  and s1["emergencies"][0]["trigger"] == "auto" and not s1["emergencies"][0]["duplicate"], "E. coli presente activa Contaminación")
            s2 = client.post("/quality/samples", headers=op, json={
                "sampled_at": now.isoformat(), "laboratory": "Lab GAD", "sampling_point_id": school,
                "results": [{"parameter_code": "e_coli", "value": 1}]}).json()
            check(s2["emergencies"][0]["duplicate"] and s2["emergencies"][0]["activation_id"] == s1["emergencies"][0]["activation_id"],
                  "otro positivo se suma a la misma emergencia")
            ok = client.post("/quality/samples", headers=op, json={"sampled_at": now.isoformat(), "laboratory": "Lab GAD",
                                                                   "results": [{"parameter_code": "e_coli", "value": 0}]}).json()
            check(ok["emergencies"] == [], "E. coli ausente no activa nada")
            active = client.get("/emergencies", headers=h).json()["active"]
            check({a["type_code"] for a in active} == {"main_break", "contamination"}, "2 emergencias activas")
            check(client.get("/operations/today", headers=h).json()["summary"]["active_emergencies"] == 2, "la vista Hoy las cuenta")

            print("6. Cierre, revision y aislamiento")
            r = client.post(f"/emergencies/activations/{brk}/close", headers=op, json={"notes": "Tubo reparado, servicio restablecido"})
            check(r.status_code == 200 and r.json()["status"] == "closed" and r.json()["closing_notes"].startswith("Tubo"), "emergencia cerrada")
            check(client.post(f"/emergencies/activations/{brk}/close", headers=op, json={}).status_code == 404, "cerrar otra vez -> 404")
            check(len(client.get("/emergencies/activations", headers=h).json()) == 2, "historial con abiertas y cerradas")
            rev = client.post("/emergencies/reviews", headers=bd, json={"reviewed_on": date.today().isoformat(), "notes": "Antes de lluvias"})
            check(rev.status_code == 201 and rev.json()["status"] == "ok", "revisión del plan registrada")
            o = client.get("/emergencies", headers=other).json()
            check(o["contacts"] == [] and o["active"] == [] and not any(e["customized"] for e in o["entries"]),
                  "la otra junta no ve contactos, activaciones ni ajustes")
            check(client.post(f"/emergencies/activations/{s1['emergencies'][0]['activation_id']}/close", headers=other,
                              json={}).status_code == 404, "ni puede cerrar una emergencia ajena")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("emergency_activation", "emergency_plan_review", "emergency_contact", "emergency_plan_entry",
                                      "lab_result", "lab_sample", "sampling_point", "finding", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D5 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
