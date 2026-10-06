"""Verificacion end-to-end real de Track D, Sprint D6 (saneamiento, migracion
0039) -- HTTP real (FastAPI TestClient), JWT real, Postgres real con el rol
de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano (Guia 3 §3.7-3.8, AP5, ficha 7F):
  1. Componentes de saneamiento: la fosa (acumula lodos) aparece "sin retiro"
     frente al plazo anual del paquete; los de agua potable no aparecen.
  2. Ficha 7F: una extraccion de lodos sin destino seguro se rechaza; con
     gestor y destino se cierra, la fosa queda al dia y la intervencion espera
     la verificacion de la directiva (el operador no puede verificar).
  3. Descargas productivas: alta, validaciones, seguimiento con acuerdo.
  4. DBO y DQO de la descarga por laboratorio, con su relacion.
  5. Aislamiento entre juntas.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_sanitation_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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

JWT_SECRET = "e2e-d6-secret"
ORDER_SIGNING_SECRET = "e2e-d6-order-secret"


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
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D6 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D6 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "admin@d6.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d6.test", "clave-oper-1", "operator")
            create_app_user(conn, tenant_id, "directiva@d6.test", "clave-dir-1", "board")
            create_app_user(conn, other_id, "admin@otra-d6.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d6.test", "clave-admin-1")
            op = login(tenant_id, "operador@d6.test", "clave-oper-1")
            bd = login(tenant_id, "directiva@d6.test", "clave-dir-1")
            other = login(other_id, "admin@otra-d6.test", "clave-admin-2")
            for hh in (h, other):
                client.put("/settings/timezone", headers=hh, json={"timezone": "America/Guayaquil"})
            septic = client.post("/network-assets", headers=h, json={"type": "septic_tank", "status": "operational"}).json()["asset_id"]
            client.post("/network-assets", headers=h, json={"type": "inspection_box", "status": "operational"})
            sand = client.post("/network-assets", headers=h, json={"type": "sand_trap", "status": "operational"}).json()["asset_id"]
            crew = client.post("/maintenance/crews", headers=h, json={"name": "Operador"}).json()["crew_id"]

            def to_progress(asset, why):
                o = client.post("/maintenance-orders", headers=h, json={"asset_id": asset, "type": "preventive", "source": "manual",
                                                                        "priority": "medium", "reason": why}).json()["order_id"]
                client.post(f"/maintenance-orders/{o}/schedule", headers=h, json={"scheduled_at": now.isoformat()})
                client.post(f"/maintenance-orders/{o}/assign", headers=h, json={"crew_id": crew})
                client.post(f"/maintenance-orders/{o}/start", headers=op)
                return o

            print("1. Componentes de saneamiento")
            s = client.get("/sanitation", headers=h).json()
            comps = {c["type"]: c for c in s["components"]}
            check(set(comps) == {"septic_tank", "inspection_box"}, "solo componentes de saneamiento")
            check(comps["septic_tank"]["sludge"]["status"] == "never" and comps["inspection_box"]["sludge"] is None,
                  "la fosa acumula lodos y no tiene retiro; la caja no aplica")
            check(s["sludge_rule"]["max_days"] == 365 and s["summary"]["sludge_overdue"] == 1, "plazo anual del paquete")

            print("2. Ficha 7F")
            o = to_progress(septic, "Extracción anual de lodos")
            r = client.post(f"/maintenance-orders/{o}/close", headers=op, json={"status": "completed", "sludge_volume_m3": 3.5})
            check(r.status_code == 422 and "destino seguro" in r.json()["detail"], "lodos sin destino seguro -> 422")
            r = client.post(f"/maintenance-orders/{o}/close", headers=op, json={
                "status": "completed", "steps_done": [1, 2, 4, 5], "sludge_volume_m3": 3.5,
                "waste_handler": "Gestor autorizado del GAD", "waste_destination": "Planta de lodos del GAD municipal"})
            check(r.status_code == 200 and r.json()["sludge_volume_m3"] == 3.5, "extracción cerrada con gestor y destino")
            s = client.get("/sanitation", headers=h).json()
            check({c["type"]: c for c in s["components"]}["septic_tank"]["sludge"]["status"] == "ok", "la fosa queda al día")
            entry = next(e for e in s["register_7f"] if e["order_id"] == o)
            check(entry["needs_verification"] and s["summary"]["pending_verification"] == 1, "espera la verificación de la directiva")
            check(client.post(f"/sanitation/register/{o}/verify", headers=op).status_code == 403, "el operador no verifica")
            check(client.post(f"/sanitation/register/{o}/verify", headers=bd).status_code == 200, "la directiva verifica el destino")
            check(client.get("/sanitation", headers=h).json()["summary"]["pending_verification"] == 0, "nada pendiente de verificar")
            water = to_progress(sand, "Limpieza del desarenador")
            client.post(f"/maintenance-orders/{water}/close", headers=op, json={"status": "completed"})
            check(client.post(f"/sanitation/register/{water}/verify", headers=bd).status_code == 404, "una orden de agua potable no es 7F -> 404")

            print("3. Descargas productivas")
            r = client.post("/sanitation/discharges", headers=op, json={
                "activity_code": "cheese_factory", "name": "Quesera El Rocío", "owner": "Familia Ordóñez",
                "location_text": "Sector alto, junto a la caja de revisión 4",
                "problem": "El suero entra a la red comunitaria y genera olores."})
            check(r.status_code == 201 and r.json()["status"] == "identified" and r.json()["activity_label"] == "Quesera", "quesera registrada")
            d = r.json()["discharge_id"]
            check(client.post("/sanitation/discharges", headers=op, json={"activity_code": "mina", "name": "x"}).status_code == 404,
                  "actividad inexistente -> 404")
            check(client.post("/sanitation/discharges", headers=op, json={"activity_code": "laundry", "name": " "}).status_code == 422,
                  "sin nombre -> 422")
            r = client.post(f"/sanitation/discharges/{d}/followups", headers=bd, json={
                "note": "Reunión con el propietario", "new_status": "agreement",
                "agreement": "Separar el suero y entregarlo para alimento animal; no descargar a la red."})
            check(r.status_code == 201 and r.json()["status"] == "agreement" and r.json()["agreement"].startswith("Separar")
                  and len(r.json()["followups"]) == 1, "seguimiento con acuerdo")
            check(client.post(f"/sanitation/discharges/{d}/followups", headers=bd, json={"note": "x", "new_status": "olvidada"}).status_code == 422,
                  "estado inventado -> 422")

            print("4. DBO y DQO")
            r = client.post("/quality/samples", headers=op, json={
                "sampled_at": (now - timedelta(hours=2)).isoformat(), "laboratory": "Lab GAD", "discharge_id": d, "reason": "other",
                "results": [{"parameter_code": "bod5", "value": 450}, {"parameter_code": "cod", "value": 900}]})
            check(r.status_code == 201 and all(x["interpretation"] == "no_rule" for x in r.json()["results"]),
                  "DBO y DQO guardados sin interpretación automática (los interpreta personal técnico)")
            disc = next(x for x in client.get("/sanitation", headers=h).json()["discharges"] if x["discharge_id"] == d)
            check(disc["samples"][0]["bod5"] == 450 and disc["samples"][0]["bod_cod_ratio"] == 0.5, "relación DBO/DQO de la descarga")
            check(client.post("/quality/samples", headers=op, json={"sampled_at": now.isoformat(), "laboratory": "Lab",
                                                                    "discharge_id": str(uuid.uuid4()),
                                                                    "results": [{"parameter_code": "cod", "value": 1}]}).status_code == 404,
                  "descarga ajena -> 404")

            print("5. Aislamiento")
            o2 = client.get("/sanitation", headers=other).json()
            check(o2["components"] == [] and o2["discharges"] == [] and o2["register_7f"] == [], "la otra junta no ve nada")
            check(client.post(f"/sanitation/discharges/{d}/followups", headers=other, json={"note": "x"}).status_code == 404,
                  "ni puede seguir una descarga ajena")
            check(client.post(f"/sanitation/register/{o}/verify", headers=other).status_code == 404, "ni verificar una 7F ajena")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("lab_result", "lab_sample", "productive_discharge_followup", "productive_discharge",
                                      "maintenance_order", "maintenance_crew", "network_asset", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D6 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
