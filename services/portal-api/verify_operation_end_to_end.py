"""Verificacion end-to-end real de Track D, Sprint D1.1 (operacion diaria:
puntos de medicion, cloro residual 7B y bitacora 7C, migracion 0030) --
HTTP real (FastAPI TestClient), JWT real, Postgres real con el rol de
aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. Sin zona horaria la vista "Hoy" responde 409 (no usa el dia UTC).
  2. Catalogo: 4 tipos de punto (core), 5 momentos de la rutina (Guia 3
     §3.3) y parametros de campo con su regla y su "que hacer".
  3. Puntos de medicion: alta, nombre repetido -> 409, tipo inventado -> 404,
     activo ajeno -> 404; la salida del tanque toca cada dia.
  4. Mediciones con el ejemplo de la Actividad participativa 4 (15/07/2026):
     0,8 y 0,5 adecuado; 0,2 bajo -> hallazgo de prioridad alta; repetir la
     medicion en el mismo punto se suma al mismo hallazgo; mismo client_id
     -> no duplica; E. coli (laboratorio) -> 422; hora sin zona -> 422.
  5. Bitacora 7C: con el cloro bajo la toma queda en Alerta aunque el
     operador marque Bueno; agua turbia -> Alerta; validaciones -> 422/404.
  6. Vista "Hoy": rutina con sus tomas, puntos medidos, resumen del dia.
  7. Aislamiento: otra junta no ve puntos, mediciones ni bitacora.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_operation_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d1-secret"
ORDER_SIGNING_SECRET = "e2e-d1-order-secret"
EMAIL = "operador@junta-e2e-d1.test"
OTHER_EMAIL = "operador@otra-junta-e2e-d1.test"


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
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E Track D1.1 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E Track D1.1 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, EMAIL, "clave-junta-1", "supervisor")
            create_app_user(conn, other_id, OTHER_EMAIL, "clave-junta-2", "supervisor")

            def login(tid: str, email: str, pwd: str) -> dict:
                token = client.post("/auth/login", json={"tenant_id": tid, "email": email, "password": pwd}).json()["access_token"]
                return {"Authorization": f"Bearer {token}"}

            h = login(tenant_id, EMAIL, "clave-junta-1")
            other = login(other_id, OTHER_EMAIL, "clave-junta-2")

            print("1. Zona horaria")
            check(client.get("/operations/today", headers=h).status_code == 409, "sin zona horaria -> 409")
            for hh in (h, other):
                check(client.put("/settings/timezone", headers=hh, json={"timezone": "America/Guayaquil"}).status_code == 200,
                      "zona horaria de la junta fijada")

            print("2. Catalogo")
            cat = client.get("/operations/catalog", headers=h).json()
            check([k["code"] for k in cat["point_kinds"]] == ["tank_outlet", "network_mid", "network_far", "critical"],
                  "4 tipos de punto en el orden de la ficha 7B")
            check([m["code"] for m in cat["moments"]] == ["start", "morning", "day", "afternoon", "close"],
                  "rutina de 5 momentos (Guía 3 §3.3)")
            params = {p["code"]: p for p in cat["parameters"]}
            check(set(params) == {"free_chlorine", "turbidity", "ph"}, "solo parámetros de campo (E. coli es de laboratorio)")
            check(params["free_chlorine"]["bands"][0]["action"].startswith("Protección insuficiente"), "la regla trae qué hacer")
            ev = client.post("/parameter-rules/evaluate", headers=h, json={"parameter_code": "turbidity", "value": 9}).json()
            check(ev["result"]["code"] == "high" and "No compensar agua turbia" in ev["action"], "evaluar devuelve la acción de la guía")

            print("3. Puntos de medicion")
            r = client.post("/network-assets", headers=h, json={"type": "tank", "status": "operational"})
            tank_asset = r.json()["asset_id"]
            points = {}
            for kind, name, extra in (("tank_outlet", "Salida del reservorio", {"asset_id": tank_asset}),
                                      ("network_mid", "Punto medio de la red", {"frequency_days": 7}),
                                      ("network_far", "Vivienda del extremo de la red", {"frequency_days": 7}),
                                      ("critical", "Escuela", {})):
                r = client.post("/sampling-points", headers=h, json={"kind_code": kind, "name": name, **extra})
                check(r.status_code == 201, f"punto {name}")
                points[kind] = r.json()["point_id"]
            check(client.post("/sampling-points", headers=h, json={"kind_code": "critical", "name": "Escuela"}).status_code == 409,
                  "nombre repetido -> 409")
            check(client.post("/sampling-points", headers=h, json={"kind_code": "rio", "name": "x"}).status_code == 404,
                  "tipo inventado -> 404")
            check(client.post("/sampling-points", headers=h, json={"kind_code": "critical", "name": "y",
                                                                   "asset_id": str(uuid.uuid4())}).status_code == 404,
                  "componente ajeno o inexistente -> 404")
            check(client.post("/sampling-points", headers=h, json={"kind_code": "critical", "name": " "}).status_code == 422,
                  "punto sin nombre -> 422")
            r = client.patch(f"/sampling-points/{points['critical']}", headers=h, json={"frequency_days": 14})
            check(r.status_code == 200 and r.json()["frequency_days"] == 14 and r.json()["name"] == "Escuela",
                  "cambiar frecuencia sin tocar el resto")
            listed = {p["point_id"]: p for p in client.get("/sampling-points", headers=h).json()}
            check(listed[points["tank_outlet"]]["effective_frequency_days"] == 1 and listed[points["tank_outlet"]]["status"] == "never",
                  "salida del tanque: cada día, todavía sin medir")

            print("4. Mediciones 7B (Actividad participativa 4)")
            now = datetime.now(timezone.utc)

            def reading(kind, value, **extra):
                return client.post("/field-readings", headers=h, json={
                    "parameter_code": "free_chlorine", "value": value, "sampling_point_id": points[kind],
                    "measured_at": (now - timedelta(minutes=1)).isoformat(), **extra})

            r = reading("tank_outlet", 0.8)
            check(r.status_code == 201 and r.json()["result_label"] == "Adecuado" and not r.json()["finding_created"],
                  "salida del reservorio 0,8 -> Adecuado")
            check(reading("network_mid", 0.5).json()["result_code"] == "adequate", "punto medio 0,5 -> Adecuado")
            client_id = str(uuid.uuid4())
            far = reading("network_far", 0.2, action_taken="Repetir la muestra, revisar fugas y dosificador; informar a la directiva",
                          client_id=client_id).json()
            check(far["result_code"] == "low" and far["severity"] == "alert" and far["finding_created"],
                  "vivienda del extremo 0,2 -> Bajo, abre hallazgo")
            check(far["interpretation"]["finding_priority"] == "high" and "Repetir medición" in far["interpretation"]["action"],
                  "prioridad y acción salen del paquete")
            again = reading("network_far", 0.2, client_id=client_id).json()
            check(again["duplicate"] and again["reading_id"] == far["reading_id"], "mismo client_id -> no duplica")
            repeat = reading("network_far", 0.25).json()
            check(repeat["finding_id"] == far["finding_id"] and not repeat["finding_created"],
                  "repetir la medición se suma al mismo hallazgo")
            findings = client.get("/findings", headers=h).json()
            fin = next(f for f in findings if f["finding_id"] == far["finding_id"])
            check(fin["priority"] == "high" and "Vivienda del extremo" in fin["description"], "hallazgo con punto y prioridad")
            check(client.post("/field-readings", headers=h, json={"parameter_code": "e_coli", "value": 1}).status_code == 422,
                  "E. coli es de laboratorio -> 422")
            check(client.post("/field-readings", headers=h, json={"parameter_code": "free_chlorine", "value": 1,
                                                                  "measured_at": "2026-10-05T07:00:00"}).status_code == 422,
                  "hora sin zona -> 422")
            check(client.post("/field-readings", headers=h, json={"parameter_code": "free_chlorine", "value": 1,
                                                                  "sampling_point_id": "x"}).status_code == 404,
                  "punto mal formado -> 404")
            turb = client.post("/field-readings", headers=h, json={"parameter_code": "turbidity", "value": 2,
                                                                   "sampling_point_id": points["tank_outlet"]}).json()
            check(turb["result_code"] == "adequate", "turbiedad 2 UTN -> Adecuado")
            history = client.get(f"/field-readings?point_id={points['network_far']}", headers=h).json()
            check(len(history) == 2 and history[0]["value"] == 0.25, "historial del punto, la más reciente primero")

            print("5. Bitacora 7C")
            r = client.post("/operation-log", headers=h, json={
                "moment_code": "afternoon", "tank_level_pct": 80, "chlorine_applied": 20, "chlorine_applied_unit": "g",
                "reading_id": far["reading_id"], "appearance": "clear", "status": "good", "notes": "Repetir mañana"})
            check(r.status_code == 201 and r.json()["status"] == "alert" and r.json()["residual_chlorine"] == 0.2,
                  "cloro bajo -> la toma queda en Alerta aunque se marque Bueno")
            r = client.post("/operation-log", headers=h, json={"moment_code": "start", "tank_level_pct": 95, "appearance": "clear"})
            check(r.status_code == 201 and r.json()["status"] == "good" and r.json()["moment_label"] == "Inicio del día",
                  "inicio del día sin novedad -> Bueno")
            r = client.post("/operation-log", headers=h, json={"moment_code": "morning", "appearance": "turbid"})
            check(r.json()["status"] == "alert", "agua turbia -> Alerta")
            for body, msg in (({"chlorine_applied": 20}, "cloro aplicado sin unidad -> 422"),
                              ({"tank_level_pct": 120}, "nivel 120 % -> 422"),
                              ({"appearance": "verde"}, "aspecto inventado -> 422"),
                              ({"status": "regular"}, "estado inventado -> 422")):
                check(client.post("/operation-log", headers=h, json=body).status_code == 422, msg)
            check(client.post("/operation-log", headers=h, json={"moment_code": "siesta"}).status_code == 404, "momento inexistente -> 404")
            check(client.post("/operation-log", headers=h, json={"reading_id": str(uuid.uuid4())}).status_code == 404,
                  "medición inexistente -> 404")
            cid = str(uuid.uuid4())
            a = client.post("/operation-log", headers=h, json={"moment_code": "close", "client_id": cid}).json()
            b = client.post("/operation-log", headers=h, json={"moment_code": "close", "client_id": cid}).json()
            check(b["duplicate"] and a["entry_id"] == b["entry_id"], "bitácora: mismo client_id -> no duplica")

            print("6. Vista Hoy")
            today = client.get("/operations/today", headers=h).json()
            moments = {m["code"]: m for m in today["moments"]}
            check(len(moments["afternoon"]["entries"]) == 1 and len(moments["day"]["entries"]) == 0, "tomas por momento de la rutina")
            pts = {p["point_id"]: p for p in today["points"]}
            check(pts[points["tank_outlet"]]["status"] == "ok" and pts[points["critical"]]["status"] == "never",
                  "tanque medido hoy; escuela sin medir")
            check(pts[points["network_far"]]["last_chlorine"]["value"] == 0.25, "última medición de cloro del punto")
            s = today["summary"]
            check(s["readings_today"] == 5 and s["out_of_range_today"] == 2 and s["open_reading_findings"] == 1,
                  f"resumen: 5 mediciones, 2 fuera de rango, 1 hallazgo abierto ({s})")
            check(s["entries_today"] == 4 and s["alerts_today"] == 2, "4 tomas, 2 en alerta")

            print("7. Aislamiento")
            check(client.get("/sampling-points", headers=other).json() == [], "la otra junta no ve los puntos")
            check(client.get("/field-readings", headers=other).json() == [], "ni las mediciones")
            check(client.get("/operation-log", headers=other).json() == [], "ni la bitácora")
            check(client.post("/field-readings", headers=other, json={"parameter_code": "free_chlorine", "value": 1,
                                                                      "sampling_point_id": points["tank_outlet"]}).status_code == 404,
                  "no puede medir en un punto ajeno")
            check(client.post("/operation-log", headers=other, json={"reading_id": far["reading_id"]}).status_code == 404,
                  "no puede usar una medición ajena")
            check(client.patch(f"/sampling-points/{points['tank_outlet']}", headers=other, json={"name": "x"}).status_code == 404,
                  "no puede editar un punto ajeno")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("operation_log_entry", "field_reading", "sampling_point", "finding",
                                      "network_asset", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D1.1 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
