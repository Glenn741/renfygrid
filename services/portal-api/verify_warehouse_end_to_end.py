"""Verificacion end-to-end real de Track D, Sprint D4 (bodega y EPP,
migracion 0038) -- HTTP real (FastAPI TestClient), JWT real, Postgres real
con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano (Guia 3 §3.9-3.10, lista 7G.1):
  1. Catalogo: 5 categorias de la bodega basica y EPP minimo por tarea.
  2. Articulos: alta con su unidad y stock minimo (la directiva); validaciones;
     el operador no crea articulos (403).
  3. Movimientos: entradas con vencimiento, salidas (no pueden dejar el stock
     negativo), ajuste por conteo, idempotencia por client_id.
  4. Alertas: bajo el minimo y lotes (FIFO) que vencen antes de la proxima
     revision 7G.1 (30 dias, frecuencia del paquete).
  5. Cruce del cloro: aplicado segun la bitacora 7C vs. salido de bodega.
  6. Aislamiento entre juntas.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_warehouse_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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

JWT_SECRET = "e2e-d4-secret"
ORDER_SIGNING_SECRET = "e2e-d4-order-secret"


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
    today = date.today()

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D4 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D4 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "admin@d4.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d4.test", "clave-oper-1", "operator")
            create_app_user(conn, other_id, "admin@otra-d4.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d4.test", "clave-admin-1")
            op = login(tenant_id, "operador@d4.test", "clave-oper-1")
            other = login(other_id, "admin@otra-d4.test", "clave-admin-2")
            for hh in (h, other):
                client.put("/settings/timezone", headers=hh, json={"timezone": "America/Guayaquil"})

            print("1. Catalogo")
            w = client.get("/warehouse", headers=h).json()
            check([c["code"] for c in w["categories"]] == ["chemicals", "spare_parts", "tools", "control", "ppe"],
                  "las 5 categorías de la bodega básica")
            check(len(w["ppe_tasks"]) == 4 and w["ppe_tasks"][0]["task"] == "Preparar cloro o químicos", "EPP mínimo por tarea")

            print("2. Articulos")
            chem = client.post("/chemical-products", headers=h, json={"name": "Hipoclorito de calcio 65 %", "purpose": "disinfection",
                                                                    "form": "solid", "active_pct": 65}).json()["product_id"]
            r = client.post("/warehouse/items", headers=h, json={"name": "Hipoclorito de calcio 65 %", "category_code": "chemicals",
                                                                 "unit": "kg", "min_stock": 5, "chemical_product_id": chem})
            check(r.status_code == 201 and r.json()["stock"] == 0 and r.json()["below_min"], "hipoclorito en kg, ligado al producto")
            hypo = r.json()["item_id"]
            gloves = client.post("/warehouse/items", headers=h, json={"name": "Guantes de nitrilo", "category_code": "ppe",
                                                                      "unit": "pair", "min_stock": 4}).json()["item_id"]
            for body, code, msg in (({"name": "x", "category_code": "chemicals", "unit": "galón"}, 422, "unidad inválida -> 422"),
                                    ({"name": "Guantes de nitrilo", "category_code": "ppe", "unit": "pair"}, 409, "nombre repetido -> 409"),
                                    ({"name": "y", "category_code": "juguetes", "unit": "unit"}, 404, "categoría inexistente -> 404"),
                                    ({"name": "z", "category_code": "chemicals", "unit": "kg", "chemical_product_id": str(uuid.uuid4())}, 404,
                                     "producto químico ajeno -> 404")):
                check(client.post("/warehouse/items", headers=h, json=body).status_code == code, msg)
            check(client.post("/warehouse/items", headers=op, json={"name": "w", "category_code": "tools", "unit": "unit"}).status_code == 403,
                  "el operador no crea artículos")

            print("3. Movimientos")
            soon = (today + timedelta(days=20)).isoformat()
            r = client.post("/warehouse/movements", headers=op, json={"item_id": hypo, "kind": "in", "quantity": 20, "expires_on": soon,
                                                                      "reason": "Compra al proveedor del GAD"})
            check(r.status_code == 201 and r.json()["stock"] == 20, "entrada de 20 kg con vencimiento")
            client.post("/warehouse/movements", headers=op, json={"item_id": hypo, "kind": "in", "quantity": 10,
                                                                  "expires_on": (today + timedelta(days=200)).isoformat()})
            cid = str(uuid.uuid4())
            r = client.post("/warehouse/movements", headers=op, json={"item_id": hypo, "kind": "out", "quantity": 0.4, "client_id": cid,
                                                                      "reason": "Dosificación de la semana"})
            check(r.json()["stock"] == 29.6, "salida de 0,4 kg")
            check(client.post("/warehouse/movements", headers=op, json={"item_id": hypo, "kind": "out", "quantity": 0.4,
                                                                        "client_id": cid}).json()["duplicate"], "mismo client_id -> no duplica")
            r = client.post("/warehouse/movements", headers=op, json={"item_id": hypo, "kind": "out", "quantity": 100})
            check(r.status_code == 409 and "supera la existencia" in r.json()["detail"], "salida mayor que la existencia -> 409")
            check(client.post("/warehouse/movements", headers=op, json={"item_id": hypo, "kind": "adjust", "quantity": -0.1,
                                                                        "reason": "Conteo mensual"}).json()["stock"] == 29.5, "ajuste por conteo")
            for body, msg in (({"item_id": hypo, "kind": "in", "quantity": -1}, "entrada negativa -> 422"),
                              ({"item_id": hypo, "kind": "out", "quantity": 1, "expires_on": soon}, "vencimiento en una salida -> 422"),
                              ({"item_id": hypo, "kind": "regalo", "quantity": 1}, "movimiento inventado -> 422"),
                              ({"item_id": hypo, "kind": "in", "quantity": 1, "moved_at": "2026-10-05T07:00:00"}, "fecha sin zona -> 422")):
                check(client.post("/warehouse/movements", headers=op, json=body).status_code == 422, msg)
            check(client.post("/warehouse/movements", headers=op, json={"item_id": str(uuid.uuid4()), "kind": "in", "quantity": 1}).status_code == 404,
                  "artículo inexistente -> 404")
            client.post("/warehouse/movements", headers=op, json={"item_id": gloves, "kind": "in", "quantity": 2})

            print("4. Alertas")
            w = client.get("/warehouse", headers=h).json()
            items = {i["item_id"]: i for i in w["items"]}
            exp = items[hypo]["expiring"]
            check(len(exp) == 1 and exp[0]["remaining"] == 19.5 and exp[0]["days_left"] == 20,
                  "lote que vence en 20 días (antes de la próxima 7G.1), con lo que queda según FIFO")
            check(items[gloves]["below_min"] and not items[hypo]["below_min"], "guantes bajo el mínimo")
            check(w["alerts"] == {"below_min": 1, "expiring": 1}, "resumen de alertas")

            print("5. Cruce del cloro")
            for g in (180, 120):
                client.post("/operation-log", headers=op, json={"chlorine_applied": g, "chlorine_applied_unit": "g", "status": "good"})
            cc = client.get("/warehouse", headers=h).json()["chlorine_check"]
            check(len(cc) == 1 and cc[0]["unit"] == "g" and cc[0]["applied"] == 300.0 and cc[0]["issued"] == 400.0
                  and cc[0]["difference"] == 100.0 and cc[0]["difference_pct"] == 25.0,
                  "bitácora 300 g aplicados vs 400 g salidos de bodega: 100 g sin registrar (25 %)")
            hist = client.get(f"/warehouse/movements?item_id={hypo}", headers=h).json()
            check(len(hist) == 4 and hist[0]["kind"] == "adjust", "historial del artículo")

            print("6. Aislamiento")
            ow = client.get("/warehouse", headers=other).json()
            check(ow["items"] == [] and ow["chlorine_check"] == [], "la otra junta no ve artículos ni cruce")
            check(client.post("/warehouse/movements", headers=other, json={"item_id": hypo, "kind": "in", "quantity": 1}).status_code == 404,
                  "ni puede mover un artículo ajeno")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("warehouse_movement", "warehouse_item", "chemical_product", "operation_log_entry",
                                      "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D4 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
