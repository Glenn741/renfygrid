"""Verificacion end-to-end real de Track D, Sprint D1.4a (lectura manual de
micro y macromedidor, migracion 0032) -- HTTP real (FastAPI TestClient), JWT
real, Postgres real con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. Buscar medidores por cuenta: trae sus canales con la ultima lectura;
     un medidor que nunca reporto ofrece los canales de los de su tipo
     (micro -> los de micro, macro -> los de macro). Nada de canales fijos.
  2. Lectura manual: entra a raw_reading con source_quality 'manual', da el
     consumo desde la anterior y el pase VEE la encuentra para validarla.
  3. Registro que baja: 422 sin confirmar; con confirmacion (medidor cambiado
     o reiniciado) entra sin consumo calculado.
  4. Mismo client_id -> no duplica; mismo instante -> 409; canal ajeno al
     medidor, medidor inexistente o mal formado -> 404; hora sin zona -> 422.
  5. Aislamiento: otra junta no ve ni lee los medidores.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_manual_meter_reading_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vee-engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d14-secret"
ORDER_SIGNING_SECRET = "e2e-d14-order-secret"


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
    from run_vee_pass import unvalidated_readings

    client = TestClient(main.app)
    t0 = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D1.4a junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D1.4a otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "operador@d14.test", "clave-1", "supervisor")
            create_app_user(conn, other_id, "operador@otra-d14.test", "clave-2", "supervisor")
            meters = {}
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        for key, account, mtype in (("micro", "GUA-0001", "micro"), ("micro_new", "GUA-0002", "micro"),
                                                    ("macro", "MACRO-TANQUE", "macro"), ("macro_new", "MACRO-SECTOR-2", "macro")):
                            cur.execute(
                                "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol, meter_type) "
                                "VALUES (%s, %s, %s, 'Zenner', 'MANUAL', %s) RETURNING id",
                                (tenant_id, account, f"SN-{account}", mtype),
                            )
                            meters[key] = str(cur.fetchone()[0])
                        cur.execute("INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES "
                                    "(%s, %s, %s, 'volume_m3', 100), (%s, %s, %s, 'volume_m3_bulk', 5000)",
                                    (tenant_id, meters["micro"], t0, tenant_id, meters["macro"], t0))

            def login(tid, email, pwd):
                token = client.post("/auth/login", json={"tenant_id": tid, "email": email, "password": pwd}).json()["access_token"]
                return {"Authorization": f"Bearer {token}"}

            h = login(tenant_id, "operador@d14.test", "clave-1")
            other = login(other_id, "operador@otra-d14.test", "clave-2")

            print("1. Buscar medidores y canales")
            found = client.get("/manual-reading/meters?search=GUA-0001", headers=h).json()
            check(len(found) == 1 and found[0]["channels"][0] == {
                "channel": "volume_m3", "last_value": 100.0, "last_at": found[0]["channels"][0]["last_at"], "last_source": "real"},
                  "el micro trae su canal y su última lectura")
            new_micro = client.get("/manual-reading/meters?search=GUA-0002", headers=h).json()[0]
            check([c["channel"] for c in new_micro["channels"]] == ["volume_m3"], "micro sin lecturas: canales de los micro de la junta")
            new_macro = client.get("/manual-reading/meters?search=SECTOR-2", headers=h).json()[0]
            check([c["channel"] for c in new_macro["channels"]] == ["volume_m3_bulk"], "macro sin lecturas: canales de los macro")
            check(len(client.get("/manual-reading/meters?meter_type=macro", headers=h).json()) == 2, "filtro por tipo")

            print("2. Lectura manual")
            read_at = t0 + timedelta(days=1)
            r = client.post("/manual-reading", headers=h, json={
                "meter_id": meters["micro"], "channel": "volume_m3", "value": 105.5, "read_at": read_at.isoformat(),
                "notes": "Lectura de ruta"})
            check(r.status_code == 201 and r.json()["delta"] == 5.5 and r.json()["previous_value"] == 100.0,
                  "105,5 contra 100: 5,5 m³ consumidos")
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    src = conn.execute("SELECT source_quality FROM raw_reading WHERE meter_id = %s AND \"timestamp\" = %s",
                                       (meters["micro"], read_at)).fetchone()[0]
            check(src == "manual", "entra a raw_reading como 'manual'")
            pending = unvalidated_readings(conn, tenant_id)
            check(any(p["meter_id"] == meters["micro"] and p["timestamp"] == read_at for p in pending),
                  "el pase VEE la encuentra para validarla (mismo camino que la telemetría)")
            r = client.post("/manual-reading", headers=h, json={
                "meter_id": meters["micro_new"], "channel": "volume_m3", "value": 12, "read_at": read_at.isoformat()})
            check(r.status_code == 201 and r.json()["delta"] is None, "primera lectura de un medidor nuevo: sin consumo calculable")
            r = client.post("/manual-reading", headers=h, json={
                "meter_id": meters["macro"], "channel": "volume_m3_bulk", "value": 5230, "read_at": read_at.isoformat()})
            check(r.status_code == 201 and r.json()["delta"] == 230, "macro: 230 m³ entregados al sector")

            print("3. Registro que baja")
            later = (read_at + timedelta(days=1)).isoformat()
            r = client.post("/manual-reading", headers=h, json={"meter_id": meters["micro"], "channel": "volume_m3", "value": 3, "read_at": later})
            check(r.status_code == 422 and "menor que la anterior" in r.json()["detail"], "baja sin confirmar -> 422")
            r = client.post("/manual-reading", headers=h, json={"meter_id": meters["micro"], "channel": "volume_m3", "value": 3,
                                                                 "read_at": later, "lower_confirmed": True, "notes": "Medidor cambiado"})
            check(r.status_code == 201 and r.json()["lower_confirmed"] and r.json()["delta"] is None, "medidor cambiado: entra sin consumo")

            print("4. Idempotencia y validaciones")
            cid = str(uuid.uuid4())
            body = {"meter_id": meters["micro_new"], "channel": "volume_m3", "value": 14,
                    "read_at": (read_at + timedelta(days=2)).isoformat(), "client_id": cid}
            a = client.post("/manual-reading", headers=h, json=body).json()
            b = client.post("/manual-reading", headers=h, json=body).json()
            check(b["duplicate"] and a["manual_reading_id"] == b["manual_reading_id"], "mismo client_id -> no duplica")
            same = {**body, "client_id": None}
            check(client.post("/manual-reading", headers=h, json=same).status_code == 409, "mismo medidor, canal e instante -> 409")
            check(client.post("/manual-reading", headers=h, json={**same, "channel": "volume_m3_bulk"}).status_code == 404,
                  "canal de macro en un micro -> 404")
            check(client.post("/manual-reading", headers=h, json={**same, "meter_id": str(uuid.uuid4())}).status_code == 404,
                  "medidor inexistente -> 404")
            check(client.post("/manual-reading", headers=h, json={**same, "meter_id": "x"}).status_code == 404, "medidor mal formado -> 404")
            check(client.post("/manual-reading", headers=h, json={**same, "read_at": "2026-10-05T07:00:00"}).status_code == 422,
                  "hora sin zona -> 422")
            check(client.post("/manual-reading", headers=h, json={**same, "value": -1}).status_code == 422, "lectura negativa -> 422")
            hist = client.get(f"/manual-reading?meter_id={meters['micro']}", headers=h).json()
            check(len(hist) == 2 and hist[0]["lower_confirmed"] and hist[0]["account_number"] == "GUA-0001",
                  "historial de lecturas manuales del medidor")

            print("5. Aislamiento")
            check(client.get("/manual-reading/meters", headers=other).json() == [], "la otra junta no ve los medidores")
            check(client.post("/manual-reading", headers=other, json={**same, "read_at": later}).status_code == 404,
                  "ni puede leer uno ajeno")
            check(client.get("/manual-reading", headers=other).json() == [], "ni ve las lecturas")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("manual_meter_reading", "validated_reading", "raw_reading", "meter", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D1.4a E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
