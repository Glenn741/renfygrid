"""Verificacion end-to-end real de Track D, Sprint D12.1 (agrupacion de
juntas, migracion 0042) -- HTTP real (FastAPI TestClient), JWT real,
Postgres real con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. Una organizacion se declara agrupacion; invita juntas por su nombre
     (no a si misma, no a otra agrupacion, no dos veces).
  2. Consentimiento: el operador de la junta no decide; la directiva acepta
     eligiendo indicadores (no los no disponibles, como la tarifa), otra
     junta acepta solo uno y una tercera rechaza.
  3. Tablero: solo las juntas que aceptaron y solo lo que cada una compartio
     (la alerta de cloro de la junta que no compartio calidad no se cuenta);
     el operador de la agrupacion no lo ve; una junta no es agrupacion.
  4. La junta cambia lo que comparte o sale; la agrupacion retira a otra.
  5. Aislamiento: otra agrupacion no ve nada ni decide por nadie.
Al final borra SOLO las organizaciones de prueba y lo que crearon.

Uso:
    python verify_group_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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
from e2e_packs import adopt_program_packs  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d12-secret"
ORDER_SIGNING_SECRET = "e2e-d12-order-secret"
SUFFIX = uuid.uuid4().hex[:6]
NAMES = {k: f"E2E D12 {k} {SUFFIX}" for k in ("agrupacion", "junta A", "junta B", "junta C", "otra agrupacion")}


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
    ids: dict[str, str] = {}

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            for k, name in NAMES.items():
                cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", (name,))
                ids[k] = str(cur.fetchone()[0])
        try:
            adopt_program_packs(conn, *ids.values())
            users = {
                "g_admin": ("agrupacion", "admin@g.test", "supervisor"), "g_op": ("agrupacion", "tecnico@g.test", "operator"),
                "a_board": ("junta A", "directiva@a.test", "board"), "a_op": ("junta A", "operador@a.test", "operator"),
                "b_board": ("junta B", "directiva@b.test", "board"), "b_op": ("junta B", "operador@b.test", "operator"),
                "c_board": ("junta C", "directiva@c.test", "board"), "h_admin": ("otra agrupacion", "admin@h.test", "supervisor"),
            }
            for k, (t, email, role) in users.items():
                create_app_user(conn, ids[t], email, "clave-" + k, role)

            def login(k):
                t, email, _ = users[k]
                r = client.post("/auth/login", json={"tenant_id": NAMES[t], "email": email, "password": "clave-" + k})
                return {"Authorization": f"Bearer {r.json()['access_token']}"}

            hd = {k: login(k) for k in users}
            for k in ("g_admin", "a_board", "b_board", "c_board", "h_admin"):
                client.put("/settings/timezone", headers=hd[k], json={"timezone": "America/Guayaquil"})
            for k in ("a", "b"):
                p = client.post("/sampling-points", headers=hd[f"{k}_board"], json={"kind_code": "network_far", "name": "Extremo"}).json()
                client.post("/field-readings", headers=hd[f"{k}_op"], json={"parameter_code": "free_chlorine", "value": 0.1,
                                                                            "sampling_point_id": p["point_id"],
                                                                            "measured_at": (now - timedelta(hours=2)).isoformat()})
            client.post("/emergencies/activations", headers=hd["b_op"], json={"type_code": "main_break", "notes": "Fuga en la conducción"})

            print("1. Agrupación e invitaciones")
            check(client.put("/settings/organization-kind", headers=hd["g_admin"], json={"kind": "federacion"}).status_code == 422,
                  "tipo inventado -> 422")
            r = client.put("/settings/organization-kind", headers=hd["g_admin"], json={"kind": "group"})
            check(r.status_code == 200 and r.json()["kind"] == "group", "la organización se declara agrupación")
            client.put("/settings/organization-kind", headers=hd["h_admin"], json={"kind": "group"})
            check(client.post("/group/members", headers=hd["a_board"], json={"name": NAMES["junta B"]}).status_code == 403,
                  "una directiva de junta no invita (sin group.manage)")
            for k in ("junta A", "junta B", "junta C"):
                r = client.post("/group/members", headers=hd["g_admin"], json={"name": NAMES[k].upper()})
                assert r.status_code == 201 and r.json()["status"] == "invited", r.text
            check(True, "tres juntas invitadas por su nombre (sin distinguir mayúsculas)")
            check(client.post("/group/members", headers=hd["g_admin"], json={"name": NAMES["junta A"]}).status_code == 409, "dos veces -> 409")
            check(client.post("/group/members", headers=hd["g_admin"], json={"name": "no existe " + SUFFIX}).status_code == 404,
                  "organización inexistente -> 404")
            check(client.post("/group/members", headers=hd["g_admin"], json={"name": NAMES["agrupacion"]}).status_code == 409,
                  "no a sí misma -> 409")
            check(client.post("/group/members", headers=hd["g_admin"], json={"name": NAMES["otra agrupacion"]}).status_code == 409,
                  "no a otra agrupación -> 409")

            print("2. Consentimiento de cada junta")
            mine = client.get("/group", headers=hd["a_op"]).json()
            check(mine["organization"]["kind"] == "provider" and mine["groups"][0]["status"] == "invited"
                  and mine["groups"][0]["name"] == NAMES["agrupacion"], "la junta ve la invitación")
            g = ids["agrupacion"]
            check(client.post(f"/group/memberships/{g}", headers=hd["a_op"], json={"action": "accept", "shared": ["calendar"]}).status_code == 403,
                  "el operador no decide por la junta")
            check(client.post(f"/group/memberships/{g}", headers=hd["a_board"], json={"action": "accept", "shared": []}).status_code == 422,
                  "aceptar sin indicadores -> 422")
            r = client.post(f"/group/memberships/{g}", headers=hd["a_board"], json={"action": "accept", "shared": ["tariff_cost"]})
            check(r.status_code == 422 and "D9" in r.json()["detail"], "la tarifa todavía no se puede compartir (D9 en renfy_pool)")
            check(client.post(f"/group/memberships/{g}", headers=hd["a_board"], json={"action": "accept", "shared": ["secreto"]}).status_code == 422,
                  "indicador inventado -> 422")
            r = client.post(f"/group/memberships/{g}", headers=hd["a_board"],
                            json={"action": "accept", "shared": ["quality_alerts", "calendar", "products", "maturity"]})
            check(r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["decided_by"] == "portal:directiva@a.test",
                  "la directiva de A acepta y comparte 4 indicadores")
            check(client.post(f"/group/memberships/{g}", headers=hd["b_board"], json={"action": "accept", "shared": ["emergencies"]}).status_code == 200,
                  "B acepta y comparte solo emergencias")
            check(client.post(f"/group/memberships/{g}", headers=hd["c_board"], json={"action": "decline"}).status_code == 200,
                  "C rechaza")
            check(client.post(f"/group/memberships/{g}", headers=hd["c_board"], json={"action": "accept", "shared": ["calendar"]}).status_code == 409,
                  "C ya no puede aceptar sin una nueva invitación -> 409")

            print("3. Tablero")
            check(client.get("/group/dashboard", headers=hd["g_op"]).status_code == 403, "el técnico sin group.view no ve el tablero")
            check(client.get("/group/dashboard", headers=hd["a_board"]).status_code == 409, "una junta no es agrupación -> 409")
            d = client.get("/group/dashboard", headers=hd["g_admin"]).json()
            by = {m["name"]: m for m in d["members"]}
            check(set(by) == {NAMES["junta A"], NAMES["junta B"]} and d["pending_invitations"] == 0, "solo A y B, nada pendiente")
            check(set(by[NAMES["junta A"]]["indicators"]) == {"quality_alerts", "calendar", "products", "maturity"}
                  and set(by[NAMES["junta B"]]["indicators"]) == {"emergencies"}, "cada junta, solo lo que compartió")
            check(by[NAMES["junta A"]]["indicators"]["quality_alerts"] == {"open": 1, "critical": 0}
                  and d["rollup"]["quality_alerts"] == {"shared_by": 1, "open": 1, "critical": 0, "members_with_critical": 0},
                  "la alerta de cloro de B no se cuenta: B no compartió calidad")
            check(d["rollup"]["emergencies"] == {"shared_by": 1, "active": 1}, "la emergencia activa de B sí")
            check(by[NAMES["junta A"]]["indicators"]["products"]["total"] >= 13, "productos 7H de A")
            check(by[NAMES["junta A"]]["indicators"]["maturity"] == [], "A no aplicó verificaciones: sin índice")

            print("4. Cambiar, salir, retirar")
            r = client.post(f"/group/memberships/{g}", headers=hd["a_board"], json={"action": "share", "shared": ["calendar"]})
            check(r.status_code == 200 and r.json()["shared"] == ["calendar"], "A deja de compartir la calidad")
            d = client.get("/group/dashboard", headers=hd["g_admin"]).json()
            check("quality_alerts" not in {m["name"]: m for m in d["members"]}[NAMES["junta A"]]["indicators"]
                  and d["rollup"]["quality_alerts"]["shared_by"] == 0, "y el tablero deja de verla al instante")
            check(client.put("/settings/organization-kind", headers=hd["g_admin"], json={"kind": "provider"}).status_code == 409,
                  "la agrupación no deja de serlo con juntas activas -> 409")
            check(client.post(f"/group/memberships/{g}", headers=hd["a_board"], json={"action": "leave"}).status_code == 200, "A sale")
            r = client.delete(f"/group/members/{ids['junta B']}", headers=hd["g_admin"])
            check(r.status_code == 200 and r.json()["status"] == "removed" and r.json()["shared"] == [], "la agrupación retira a B")
            check(client.post(f"/group/memberships/{g}", headers=hd["b_board"], json={"action": "share", "shared": ["calendar"]}).status_code == 409,
                  "B retirada ya no comparte nada -> 409")
            check(client.get("/group/dashboard", headers=hd["g_admin"]).json()["members"] == [], "tablero vacío")
            r = client.post("/group/members", headers=hd["g_admin"], json={"name": NAMES["junta A"]})
            check(r.status_code == 201 and r.json()["status"] == "invited" and r.json()["shared"] == [], "se puede volver a invitar, desde cero")

            print("5. Aislamiento")
            h = client.get("/group", headers=hd["h_admin"]).json()
            check(h["members"] == [] and client.get("/group/dashboard", headers=hd["h_admin"]).json()["members"] == [],
                  "otra agrupación no ve juntas ajenas")
            check(client.post(f"/group/memberships/{g}", headers=hd["h_admin"], json={"action": "leave"}).status_code == 404,
                  "ni decide por ellas")
            check(client.delete(f"/group/members/{ids['junta A']}", headers=hd["h_admin"]).status_code == 404, "ni las retira")
            check(client.get("/group", headers=hd["c_board"]).json()["groups"][0]["status"] == "declined"
                  and client.get("/group", headers=hd["b_board"]).json()["groups"][0]["status"] == "removed",
                  "cada junta ve su propio estado")
        finally:
            for k, tid in ids.items():
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        conn.execute("DELETE FROM group_membership WHERE group_tenant_id = %s OR member_tenant_id = %s", (tid, tid))
                        conn.execute("UPDATE field_reading SET finding_id = NULL WHERE tenant_id = %s", (tid,))
                        for table in ("emergency_activation", "emergency_plan_entry", "field_reading", "finding", "sampling_point",
                                      "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: organizaciones de prueba y sus datos borrados")
    print("SPRINT D12.1 E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
