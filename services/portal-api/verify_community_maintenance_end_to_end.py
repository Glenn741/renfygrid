"""Verificacion end-to-end real de Track D, Sprint D3.1 (mantenimiento
comunitario sobre el CMMS, migracion 0035) -- HTTP real (FastAPI
TestClient), JWT real, Postgres real con el rol de aplicacion (RLS activo).

Que prueba, en espanol llano (Guia 3 §3.6 y ficha 7D):
  1. Catalogo del paquete: los 5 pasos del mantenimiento y los eventos que
     disparan planes (lluvias, deslizamientos, quejas).
  2. Orden EMERGENTE (rotura principal): se crea, se ejecuta y se cierra con
     los 5 pasos, responsable, materiales, pendiente y la minga
     (participantes y horas donadas). Paso inexistente u horas negativas ->
     422.
  3. Plan "semanal y despues de lluvias": registrar una lluvia fuerte genera
     una orden extraordinaria ligada al plan y al evento; un plan que no
     espera lluvias no genera nada; el plan conserva su frecuencia.
  4. Evento inexistente -> 404; plan con evento inventado -> 422.
  5. KPIs del ano: mingas, personas, horas donadas y % de cierres con los
     5 pasos.
  6. Permisos: el operador registra el evento y cierra ordenes; aislamiento
     entre juntas.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_community_maintenance_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d31-secret"
ORDER_SIGNING_SECRET = "e2e-d31-order-secret"


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
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D3.1 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D3.1 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "admin@d31.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d31.test", "clave-oper-1", "operator")
            create_app_user(conn, other_id, "admin@otra-d31.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d31.test", "clave-admin-1")
            op = login(tenant_id, "operador@d31.test", "clave-oper-1")
            other = login(other_id, "admin@otra-d31.test", "clave-admin-2")
            intake = client.post("/network-assets", headers=h, json={"type": "intake", "status": "operational"}).json()["asset_id"]
            conduction = client.post("/network-assets", headers=h, json={"type": "pipe", "status": "operational"}).json()["asset_id"]
            tank = client.post("/network-assets", headers=h, json={"type": "tank", "status": "operational"}).json()["asset_id"]
            crew = client.post("/maintenance/crews", headers=h, json={"name": "Operador y minga"}).json()["crew_id"]

            def run_to_progress(order_id):
                client.post(f"/maintenance-orders/{order_id}/schedule", headers=h, json={"scheduled_at": now.isoformat()})
                client.post(f"/maintenance-orders/{order_id}/assign", headers=h, json={"crew_id": crew})
                return client.post(f"/maintenance-orders/{order_id}/start", headers=op)

            print("1. Catalogo")
            cat = client.get("/maintenance/community-catalog", headers=h).json()
            check([s["step_no"] for s in cat["steps"]] == [1, 2, 3, 4, 5] and cat["steps"][0]["label"] == "Revisar el estado.",
                  "los 5 pasos de la Guía 3")
            check([e["code"] for e in cat["event_types"]] == ["heavy_rain", "ground_movement", "user_complaints"],
                  "eventos: lluvias, deslizamientos, quejas")

            print("2. Orden emergente con minga")
            r = client.post("/maintenance-orders", headers=h, json={
                "asset_id": conduction, "type": "emergency", "source": "manual", "priority": "emergency",
                "reason": "Rotura de la conducción principal en el cruce de la quebrada"})
            check(r.status_code == 201 and r.json()["type"] == "emergency", "orden emergente creada")
            em = r.json()["order_id"]
            check(run_to_progress(em).status_code == 200, "el operador la inicia")
            bad = client.post(f"/maintenance-orders/{em}/close", headers=op, json={"status": "completed", "steps_done": [1, 7]})
            check(bad.status_code == 422 and "Pasos desconocidos" in bad.json()["detail"], "paso inexistente -> 422")
            check(client.post(f"/maintenance-orders/{em}/close", headers=op, json={"status": "completed", "volunteer_hours": -2}).status_code == 422,
                  "horas negativas -> 422")
            r = client.post(f"/maintenance-orders/{em}/close", headers=op, json={
                "status": "completed", "steps_done": [1, 2, 3, 4, 5], "labor_hours": 6, "materials_used": "Tubo PVC 63 mm x 6 m, 2 uniones",
                "responsible": "Operador + vocal de operación", "pending_notes": "Proteger el cruce con gavión antes de lluvias",
                "community_participants": 14, "volunteer_hours": 42})
            o = r.json()
            check(r.status_code == 200 and o["status"] == "completed" and o["steps_done"] == [1, 2, 3, 4, 5]
                  and o["community_participants"] == 14 and o["volunteer_hours"] == 42.0 and o["pending_notes"].startswith("Proteger"),
                  "cerrada con los 5 pasos, ficha 7D y la minga")

            print("3. Planes por evento")
            r = client.post("/maintenance/pm-plans", headers=h, json={
                "asset_id": intake, "order_type": "preventive", "priority": "medium", "interval_days": 7,
                "next_due_at": (now + timedelta(days=7)).isoformat(), "title": "Limpieza de captación y desarenador",
                "responsible": "Operador + minga", "trigger_events": ["heavy_rain"]})
            check(r.status_code == 201 and r.json()["trigger_events"] == ["heavy_rain"] and r.json()["title"].startswith("Limpieza"),
                  "plan semanal y después de lluvias")
            plan = r.json()
            client.post("/maintenance/pm-plans", headers=h, json={
                "asset_id": tank, "order_type": "inspection", "priority": "low", "interval_days": 30,
                "next_due_at": (now + timedelta(days=30)).isoformat(), "title": "Revisión mensual del reservorio"})
            check(client.post("/maintenance/pm-plans", headers=h, json={
                "asset_id": tank, "order_type": "preventive", "priority": "low", "interval_days": 30,
                "next_due_at": now.isoformat(), "trigger_events": ["terremoto"]}).status_code == 422, "evento inventado en el plan -> 422")
            ev = client.post("/maintenance/events", headers=op, json={"event_type_code": "heavy_rain", "notes": "Aguacero de 3 horas"})
            check(ev.status_code == 201 and len(ev.json()["orders"]) == 1, "lluvia fuerte: 1 orden (solo el plan que la espera)")
            eo = ev.json()["orders"][0]
            check(eo["source"] == "event" and eo["pm_plan_id"] == plan["pm_plan_id"] and eo["event_id"] == ev.json()["event_id"]
                  and eo["reason"].startswith("Después de: Lluvias fuertes"), "orden ligada al plan y al evento")
            plans = {p["pm_plan_id"]: p for p in client.get("/maintenance/pm-plans", headers=h).json()}
            check(plans[plan["pm_plan_id"]]["next_due_at"] == plan["next_due_at"], "el plan conserva su frecuencia normal")
            events = client.get("/maintenance/events", headers=h).json()
            check(events[0]["label"] == "Lluvias fuertes" and events[0]["orders_generated"] == 1, "historial de eventos")
            check(client.post("/maintenance/events", headers=h, json={"event_type_code": "granizo"}).status_code == 404, "evento inexistente -> 404")
            check(client.post("/maintenance/events", headers=h, json={"event_type_code": "heavy_rain",
                                                                      "occurred_at": "2026-10-05T07:00:00"}).status_code == 422, "fecha sin zona -> 422")
            check(run_to_progress(eo["order_id"]).status_code == 200, "la orden del evento se ejecuta")
            client.post(f"/maintenance-orders/{eo['order_id']}/close", headers=op, json={
                "status": "completed", "steps_done": [1, 2, 4, 5], "community_participants": 6, "volunteer_hours": 12})

            print("4. KPIs del ano")
            k = client.get("/maintenance/kpis", headers=h).json()["community"]
            check(k == {"year": now.year, "mingas": 2, "participants": 20, "volunteer_hours": 54.0, "all_steps_pct": 50.0},
                  f"2 mingas, 20 personas, 54 horas donadas, 50 % con los 5 pasos ({k})")

            print("5. Aislamiento")
            check(client.get("/maintenance/events", headers=other).json() == [], "la otra junta no ve los eventos")
            check(client.get("/maintenance/kpis", headers=other).json()["community"]["mingas"] == 0, "ni las mingas")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("maintenance_order", "maintenance_event", "maintenance_pm_plan", "maintenance_crew",
                                      "network_asset", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D3.1 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
