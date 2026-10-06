"""Verificacion end-to-end real de Track D, Sprint D1.4b (roles y permisos,
migracion 0033) -- HTTP real (FastAPI TestClient), JWT real, Postgres real
con el rol de aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. La tabla de rutas: lecturas libres, escrituras con su permiso, y una
     escritura que no esta en la tabla pide settings.manage.
  2. Administracion crea operador y directiva; correo sin @, rol de servicio,
     clave corta o usuario repetido -> 422.
  3. Operador: mide y lleva bitacora; no crea puntos ni toca configuracion
     ni usuarios (403). Directiva: crea puntos y gestiona hallazgos; no mide.
  4. Cambiar los permisos de un rol rige de inmediato, sin volver a ingresar;
     volver a los de defecto tambien.
  5. Cambiar el rol o desactivar a un usuario rige de inmediato (un usuario
     desactivado ya no lee ni escribe).
  6. Nunca queda la organizacion sin administrador: no se puede desactivar
     a uno mismo, ni quitar el ultimo administrador, ni quitarle users.manage
     al unico rol que lo tiene.
  7. Aislamiento: otra organizacion no ve ni toca estos usuarios.
Al final borra SOLO las organizaciones de prueba y lo que ellas crearon.

Uso:
    python verify_roles_permissions_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from e2e_packs import adopt_program_packs  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-d14b-secret"
ORDER_SIGNING_SECRET = "e2e-d14b-order-secret"


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
    from permissions import FALLBACK_PERMISSION, required_permission

    client = TestClient(main.app)

    print("1. Tabla de rutas")
    check(required_permission("GET", "/users") is None, "lecturas: sin permiso extra")
    check(required_permission("POST", "/field-readings") == "operations.record", "medir -> operations.record")
    check(required_permission("PATCH", "/sampling-points/abc") == "operations.manage", "editar punto -> operations.manage")
    check(required_permission("POST", "/findings") == "findings.report" and required_permission("PATCH", "/findings/x") == "findings.manage",
          "reportar vs. gestionar hallazgos")
    check(required_permission("PUT", "/follow-up/cycles/x/milestones/D7/review") == "program.manage", "seguimiento -> program.manage")
    check(required_permission("POST", "/maintenance-orders/bayforce-webhook") == "maintenance.webhook", "webhook antes que órdenes")
    check(required_permission("POST", "/dosing/calculate") is None, "calcular dosis no cambia nada")
    check(required_permission("POST", "/algo-nuevo-sin-mapear") == FALLBACK_PERMISSION, "escritura no mapeada -> settings.manage")

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D1.4b junta') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E D1.4b otra junta') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            adopt_program_packs(conn, tenant_id, other_id)
            admin_id = create_app_user(conn, tenant_id, "admin@junta-d14b.test", "clave-admin-1", "supervisor")
            create_app_user(conn, other_id, "admin@otra-d14b.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                r = client.post("/auth/login", json={"tenant_id": tid, "email": email, "password": pwd})
                assert r.status_code == 200, r.text
                return {"Authorization": f"Bearer {r.json()['access_token']}"}

            adm = login(tenant_id, "admin@junta-d14b.test", "clave-admin-1")
            other = login(other_id, "admin@otra-d14b.test", "clave-admin-2")

            print("2. Alta de usuarios")
            r = client.post("/users", headers=adm, json={"email": "Operador@Junta-D14b.test", "password": "clave-oper-1", "role": "operator"})
            check(r.status_code == 201 and r.json()["email"] == "operador@junta-d14b.test", "operador creado (correo en minúsculas)")
            op_id = r.json()["user_id"]
            r = client.post("/users", headers=adm, json={"email": "directiva@junta-d14b.test", "password": "clave-dir-1", "role": "board"})
            check(r.status_code == 201, "directiva creada")
            board_id = r.json()["user_id"]
            for body, msg in (({"email": "operador2", "password": "clave-oper-1", "role": "operator"}, "usuario sin @ -> 422"),
                              ({"email": "cis@junta.test", "password": "clave-cis-12", "role": "integration"}, "rol de servicio -> 422"),
                              ({"email": "x@junta.test", "password": "corta", "role": "operator"}, "clave corta -> 422"),
                              ({"email": "operador@junta-d14b.test", "password": "clave-oper-1", "role": "operator"}, "repetido -> 422")):
                check(client.post("/users", headers=adm, json=body).status_code == 422, msg)
            check(client.post("/users", headers=adm, json={"email": "y@junta.test", "password": "clave-y-123", "role": "rey"}).status_code == 404,
                  "rol inexistente -> 404")
            roles = {r["code"]: r for r in client.get("/roles", headers=adm).json()["roles"]}
            check(roles["operator"]["label"] == "Operador" and "operations.record" in roles["operator"]["permissions"],
                  "catálogo de roles con sus permisos")

            print("3. Operador y directiva")
            op = login(tenant_id, "operador@junta-d14b.test", "clave-oper-1")
            bd = login(tenant_id, "directiva@junta-d14b.test", "clave-dir-1")
            me = client.get("/auth/me", headers=op).json()
            check(me["role"] == "operator" and me["role_label"] == "Operador" and "operations.record" in me["permissions"]
                  and "settings.manage" not in me["permissions"], "/auth/me dice rol y permisos")
            check(client.post("/field-readings", headers=op, json={"parameter_code": "free_chlorine", "value": 0.8}).status_code == 201,
                  "operador mide")
            r = client.post("/sampling-points", headers=op, json={"kind_code": "tank_outlet", "name": "Tanque"})
            check(r.status_code == 403 and "operations.manage" in r.json()["detail"], "operador no crea puntos (403)")
            check(client.put("/settings/timezone", headers=op, json={"timezone": "America/Guayaquil"}).status_code == 403,
                  "operador no toca configuración")
            check(client.post("/users", headers=op, json={"email": "z@junta.test", "password": "clave-z-123", "role": "supervisor"}).status_code == 403,
                  "operador no crea usuarios")
            check(client.get("/operations/catalog", headers=op).status_code == 200, "operador lee")
            check(client.post("/sampling-points", headers=bd, json={"kind_code": "tank_outlet", "name": "Tanque"}).status_code == 201,
                  "directiva crea puntos")
            check(client.post("/field-readings", headers=bd, json={"parameter_code": "free_chlorine", "value": 0.8}).status_code == 403,
                  "directiva no mide (es del operador)")
            f = client.post("/findings", headers=op, json={"description": "Fuga en la conducción", "priority": "high"})
            check(f.status_code == 201, "operador reporta un hallazgo")
            check(client.patch(f"/findings/{f.json()['finding_id']}", headers=op, json={"status": "closed"}).status_code == 403,
                  "operador no lo cierra")
            check(client.patch(f"/findings/{f.json()['finding_id']}", headers=bd, json={"status": "closed"}).status_code == 200,
                  "directiva lo cierra")
            check(client.post("/algo-nuevo-sin-mapear", headers=op).status_code == 403, "escritura no mapeada: 403 sin settings.manage")

            print("4. Permisos de un rol por organizacion")
            r = client.put("/roles/operator/permissions", headers=adm, json={"permissions": ["operations.record", "operations.manage"]})
            check(r.status_code == 200 and r.json()["overridden"], "la junta amplía al operador")
            check(client.post("/sampling-points", headers=op, json={"kind_code": "network_far", "name": "Lejano"}).status_code == 201,
                  "rige de inmediato, sin volver a ingresar")
            check(client.post("/findings", headers=op, json={"description": "x", "priority": "low"}).status_code == 403,
                  "lo que no se incluyó ya no lo tiene")
            check(client.put("/roles/operator/permissions", headers=adm, json={"permissions": ["volar"]}).status_code == 422,
                  "permiso inventado -> 422")
            r = client.delete("/roles/operator/permissions", headers=adm)
            check(r.status_code == 200 and not r.json()["overridden"], "vuelve a los permisos por defecto")
            check(client.post("/sampling-points", headers=op, json={"kind_code": "critical", "name": "Escuela"}).status_code == 403,
                  "y rige de inmediato")

            print("5. Cambios de usuario")
            r = client.patch(f"/users/{op_id}", headers=adm, json={"role": "board"})
            check(r.status_code == 200 and r.json()["role"] == "board", "operador pasa a directiva")
            check(client.post("/sampling-points", headers=op, json={"kind_code": "critical", "name": "Escuela"}).status_code == 201,
                  "con el mismo token ya tiene los permisos nuevos")
            client.patch(f"/users/{op_id}", headers=adm, json={"is_active": False})
            r = client.get("/operations/catalog", headers=op)
            check(r.status_code == 403 and "desactivado" in r.json()["detail"], "desactivado: ya no lee con su token")
            check(client.post("/auth/login", json={"tenant_id": tenant_id, "email": "operador@junta-d14b.test",
                                                   "password": "clave-oper-1"}).status_code == 401, "ni ingresa")
            r = client.patch(f"/users/{board_id}", headers=adm, json={"password": "clave-nueva-9"})
            check(r.status_code == 200 and login(tenant_id, "directiva@junta-d14b.test", "clave-nueva-9"), "cambio de clave")

            print("6. Nunca sin administrador")
            check(client.patch(f"/users/{admin_id}", headers=adm, json={"is_active": False}).status_code == 422, "no se desactiva a sí mismo")
            check(client.patch(f"/users/{admin_id}", headers=adm, json={"role": "board"}).status_code == 422, "no se quita el último administrador")
            check(client.put("/roles/supervisor/permissions", headers=adm, json={"permissions": ["settings.manage"]}).status_code == 422,
                  "no se quita users.manage al único rol que lo tiene")
            check(client.patch(f"/users/{admin_id}", headers=adm, json={"role": "integration"}).status_code == 422,
                  "no se asigna el rol de servicio")

            print("7. Aislamiento")
            check([u["email"] for u in client.get("/users", headers=other).json()] == ["admin@otra-d14b.test"],
                  "la otra organización solo ve sus usuarios")
            check(client.patch(f"/users/{board_id}", headers=other, json={"is_active": False}).status_code == 404,
                  "ni puede tocar los de esta")
            check(all(not r["overridden"] for r in client.get("/roles", headers=other).json()["roles"]),
                  "los ajustes de roles de una junta no afectan a otra")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        for table in ("tenant_role_override", "field_reading", "sampling_point", "finding", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: organizaciones de prueba y sus datos borrados")
    print("SPRINT D1.4b E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
