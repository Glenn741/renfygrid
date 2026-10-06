"""Verificacion end-to-end real de Track D, Sprint D7 (plan minimo, ficha
7G.2 y tablero 7H, migracion 0040) -- HTTP real (FastAPI TestClient), JWT
real, Postgres real con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano (Guia 3 seccion 4, fichas 7G.2 y 7H):
  1. Plan minimo: 8 filas del paquete con su ejemplo; cada fila muestra la
     evidencia viva (cloro bajo en el punto lejano); el operador anota las
     decisiones y el plan queda completo.
  2. Ficha 7G.2: el cloro bajo repetido, el "No" de la 7G.1, la fosa sin
     retiro de lodos y la descarga productiva aparecen como candidatos con la
     evidencia citada; trasladar uno marca el hallazgo para el Plan de Mejora
     y no se puede trasladar dos veces; filas manuales; quitar una fila es de
     la directiva y devuelve el candidato.
  3. Tablero 7H: 13 productos con la evidencia del sistema; un producto
     marcado completo sin evidencia queda senalado para revisar.
  4. Aislamiento entre juntas.
Al final borra SOLO las juntas de prueba y lo que ellas crearon.

Uso:
    python verify_improvement_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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

JWT_SECRET = "e2e-d7-secret"
ORDER_SIGNING_SECRET = "e2e-d7-order-secret"
G7_1 = ["chemicals_labeled", "warehouse_conditions", "no_foreign_items", "ppe_available", "ppe_good_condition",
        "tools_organized", "inventory_updated", "emergency_numbers_visible"]


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
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D7 junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D7 otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "admin@d7.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@d7.test", "clave-oper-1", "operator")
            create_app_user(conn, tenant_id, "directiva@d7.test", "clave-dir-1", "board")
            create_app_user(conn, other_id, "admin@otra-d7.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@d7.test", "clave-admin-1")
            op = login(tenant_id, "operador@d7.test", "clave-oper-1")
            bd = login(tenant_id, "directiva@d7.test", "clave-dir-1")
            other = login(other_id, "admin@otra-d7.test", "clave-admin-2")
            for hh in (h, other):
                client.put("/settings/timezone", headers=hh, json={"timezone": "America/Guayaquil"})
            far = client.post("/sampling-points", headers=h, json={"kind_code": "network_far", "name": "Casa de la familia Pérez"}).json()["point_id"]
            for i, v in enumerate((0.15, 0.18, 0.17)):
                client.post("/field-readings", headers=op, json={"parameter_code": "free_chlorine", "value": v, "sampling_point_id": far,
                                                                  "measured_at": (now - timedelta(days=3 - i)).isoformat()})
            client.post("/checklist-runs", headers=op, json={"template_id": "MA-7G1", "answers": [
                {"item_key": k, "answer_code": "no" if k == "ppe_available" else "yes",
                 **({"observation": "Faltan gafas y delantal para preparar cloro"} if k == "ppe_available" else {})} for k in G7_1]})
            client.post("/network-assets", headers=h, json={"type": "septic_tank", "status": "operational"})
            client.post("/sanitation/discharges", headers=op, json={"activity_code": "pig_farm", "name": "Chanchera La Loma",
                                                                    "problem": "Lavado de corrales hacia la quebrada."})

            print("1. Plan mínimo")
            p = client.get("/improvement/minimum-plan", headers=op).json()
            check(len(p["rows"]) == 8 and p["summary"] == {"total": 8, "decided": 0, "complete": False}, "8 filas del paquete, ninguna decidida")
            rows = {r["code"]: r for r in p["rows"]}
            check(rows["daily_routine"]["example_decision"].startswith("Revisar captación"), "con el ejemplo de referencia de la guía")
            check(any("Casa de la familia Pérez" in s for s in rows["chlorine_points"]["suggestions"])
                  and any(s.startswith("Sin cerrar:") for s in rows["chlorine_points"]["suggestions"]),
                  "puntos de cloro: el punto lejano y el cloro bajo sin cerrar")
            check(any("sin retiro de lodos" in s for s in rows["sanitation_priority"]["suggestions"])
                  and any("Chanchera La Loma" in s for s in rows["sanitation_priority"]["suggestions"]), "saneamiento: fosa y descarga")
            check(client.put("/improvement/minimum-plan/EC-MUNICIPIOS-AZULES/daily_routine", headers=op, json={"decision": " "}).status_code == 422,
                  "decisión vacía -> 422")
            check(client.put("/improvement/minimum-plan/EC-MUNICIPIOS-AZULES/inventada", headers=op, json={"decision": "x"}).status_code == 404,
                  "fila inexistente -> 404")
            for code in rows:
                r = client.put(f"/improvement/minimum-plan/EC-MUNICIPIOS-AZULES/{code}", headers=op,
                               json={"decision": f"Decisión de la junta para {code}", "responsible": "Operador/a", "term": "Este mes"})
                assert r.status_code == 200, r.text
            p = client.get("/improvement/minimum-plan", headers=h).json()
            check(p["summary"]["complete"] and p["rows"][0]["entry"]["updated_by"] == "portal:operador@d7.test", "plan mínimo completo")

            print("2. Ficha 7G.2")
            g = client.get("/improvement/inputs", headers=op).json()
            kinds = {c["source_kind"]: c for c in g["candidates"]}
            check(set(kinds) >= {"reading", "checklist", "sludge", "discharge"} and g["inputs"] == [], "cuatro tipos de evidencia candidatos")
            check(kinds["reading"]["evidence"] == "3 mediciones de Cloro residual en Casa de la familia Pérez: 0.15; 0.18; 0.17 mg/L. Registro 7B",
                  "cloro bajo repetido con sus tres mediciones citadas")
            check("7G.1" in kinds["checklist"]["evidence"] and "«No»" in kinds["checklist"]["evidence"], "el «No» de la 7G.1 citado")
            check(all(c["stage_code"] == "G3" for c in g["candidates"]), "cada candidato dice de qué guía viene (G3)")
            check(kinds["checklist"]["priority"] == "high", "la prioridad viene del paquete")
            r = client.post("/improvement/inputs", headers=op, json={
                "source_ref": kinds["reading"]["source_ref"], "proposed_action": "Revisar dosificador, tiempo de contacto y fugas.",
                "community_action": "Inspeccionar, limpiar, registrar y ajustar con orientación.",
                "support_required": "Asistencia técnica del GAD", "support_level": "local_government",
                "cost_estimate": 300, "cost_note": "estimación inicial", "term": "corto plazo"})
            check(r.status_code == 201 and r.json()["source_kind"] == "reading" and r.json()["evidence"].startswith("3 mediciones")
                  and r.json()["priority"] == kinds["reading"]["priority"], "trasladado con la evidencia y la prioridad del hallazgo")
            reading_input = r.json()["input_id"]
            fid = r.json()["finding_id"]
            check(next(f for f in client.get("/findings", headers=h).json() if f["finding_id"] == fid)["to_improvement_plan"],
                  "el hallazgo queda marcado para el Plan de Mejora")
            check(client.post("/improvement/inputs", headers=op, json={"source_ref": kinds["reading"]["source_ref"]}).status_code == 409,
                  "no se traslada dos veces -> 409")
            check(client.post("/improvement/inputs", headers=op, json={"source_ref": str(uuid.uuid4())}).status_code == 404,
                  "evidencia inexistente -> 404")
            r = client.post("/improvement/inputs", headers=op, json={"source_ref": kinds["sludge"]["source_ref"], "priority": "medium"})
            check(r.status_code == 201 and r.json()["finding_id"] is None and "lodos" in r.json()["problem"], "fosa sin retiro trasladada")
            check(client.post("/improvement/inputs", headers=op, json={"source_ref": kinds["discharge"]["source_ref"]}).status_code == 422,
                  "sin prioridad (la descarga no la trae) -> 422")
            check(client.post("/improvement/inputs", headers=op, json={"problem": "Red sanitaria", "priority": "urgente"}).status_code == 422,
                  "prioridad inventada -> 422")
            r = client.post("/improvement/inputs", headers=bd, json={
                "problem": "Rehabilitar el filtro lento", "priority": "high", "cost_note": "por cotizar",
                "support_level": "specialized"})
            check(r.status_code == 201 and r.json()["source_kind"] == "manual", "fila manual")
            r = client.patch(f"/improvement/inputs/{r.json()['input_id']}", headers=op, json={"cost_estimate": 1200, "term": "6 meses"})
            check(r.status_code == 200 and r.json()["cost_estimate"] == 1200 and r.json()["problem"] == "Rehabilitar el filtro lento",
                  "costo y plazo ajustados sin tocar lo demás")
            check(client.patch(f"/improvement/inputs/{reading_input}", headers=op, json={"cost_estimate": -5}).status_code == 422,
                  "costo negativo -> 422")
            g = client.get("/improvement/inputs", headers=h).json()
            check(g["summary"]["inputs"] == 3 and g["summary"]["cost_estimate_total"] == 1500 and g["summary"]["to_quote"] == 1,
                  "3 filas, USD 1500 estimados, 1 por cotizar")
            check(g["inputs"][0]["priority"] == "high", "ordenadas por prioridad")
            check(client.delete(f"/improvement/inputs/{reading_input}", headers=op).status_code == 403, "el operador no quita filas")
            check(client.delete(f"/improvement/inputs/{reading_input}", headers=bd).status_code == 204, "la directiva quita una fila")
            g = client.get("/improvement/inputs", headers=h).json()
            check(any(c["source_ref"] == fid for c in g["candidates"])
                  and not next(f for f in client.get("/findings", headers=h).json() if f["finding_id"] == fid)["to_improvement_plan"],
                  "el hallazgo vuelve a ser candidato y se desmarca")
            p = client.get("/improvement/minimum-plan", headers=op).json()
            check(any("Rehabilitar el filtro lento" in s for s in {r["code"]: r for r in p["rows"]}["improvement_inputs"]["suggestions"]),
                  "la fila 'Insumos para la Guía 6' muestra la 7G.2")

            print("3. Tablero 7H")
            b = client.get("/improvement/products/MA-G3-7H", headers=op).json()
            ev = {i["key"]: i for i in b["items"]}
            check(len(b["items"]) == 13 and b["last_run"] is None and b["summary"]["complete"] == 0 and b["stage_code"] == "G3",
                  "13 productos de la etapa G3, nada verificado")
            check(ev["chlorine_register"]["evidence"]["count"] == 3 and ev["minimum_plan"]["evidence"]["count"] == 8
                  and ev["improvement_inputs"]["evidence"]["count"] == 2 and ev["warehouse_ppe"]["has_evidence"]
                  and not ev["operation_log"]["has_evidence"], "evidencia del sistema por producto")
            r = client.post("/checklist-runs", headers=bd, json={"template_id": "MA-G3-7H", "answers": [
                {"item_key": i["key"], "answer_code": "complete" if i["key"] in ("chlorine_register", "minimum_plan", "operation_log") else "pending",
                 **({} if i["key"] in ("chlorine_register", "minimum_plan", "operation_log") else {"observation": "Falta archivar"})}
                for i in b["items"]]})
            check(r.status_code == 201, "la directiva verifica los productos (lista 7H)")
            b = client.get("/improvement/products/MA-G3-7H", headers=op).json()
            ev = {i["key"]: i for i in b["items"]}
            check(b["summary"]["complete"] == 3 and ev["technical_map"]["note"] == "Falta archivar", "3 completos, pendientes con nota")
            check(ev["operation_log"]["check"] and not ev["chlorine_register"]["check"], "completo sin bitácora registrada: señalado para revisar")
            check(client.get("/improvement/products/MA-7A", headers=op).status_code == 404, "una lista que no es de productos -> 404")

            print("4. Aislamiento")
            o = client.get("/improvement/inputs", headers=other).json()
            check(o["inputs"] == [] and o["candidates"] == [], "la otra junta no ve nada")
            check(client.get("/improvement/minimum-plan", headers=other).json()["summary"]["decided"] == 0, "ni el plan mínimo")
            any_input = client.get("/improvement/inputs", headers=h).json()["inputs"][0]["input_id"]
            check(client.patch(f"/improvement/inputs/{any_input}", headers=other, json={"term": "x"}).status_code == 404,
                  "ni puede editar una fila ajena")
            check(client.delete(f"/improvement/inputs/{any_input}", headers=other).status_code == 404, "ni quitarla")
            check(client.post("/improvement/inputs", headers=other, json={"source_ref": fid}).status_code == 404,
                  "ni trasladar evidencia ajena")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        conn.execute("UPDATE field_reading SET finding_id = NULL WHERE tenant_id = %s", (tid,))
                        for table in ("improvement_input", "minimum_plan_entry", "checklist_answer", "checklist_run",
                                      "productive_discharge_followup", "productive_discharge", "field_reading", "finding",
                                      "sampling_point", "network_asset", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: juntas de prueba y sus datos borrados")
    print("SPRINT D7 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
