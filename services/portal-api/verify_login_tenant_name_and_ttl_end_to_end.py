"""Verificacion end-to-end del login por nombre de tenant y de la duracion de
sesion como parametro de la organizacion (2026-10-05) -- HTTP real
(TestClient), Postgres real.

Que prueba:
  1. Login con el NOMBRE del tenant (sin distinguir mayusculas) -> 200, y el
     token trae el tenant_id real.
  2. Un tenant nuevo nace con la duracion de sesion del esquema (0022: 12 h)
     y el token vence a esa hora.
  3. /auth/me devuelve organizacion, usuario, rol, inicio y vencimiento.
  4. PUT /settings/session cambia la duracion; el siguiente login la usa.
     Menos de 5 minutos -> 422.
  5. Una organizacion sin el parametro -> 409 con mensaje claro (nunca una
     duracion inventada).
  6. Login con UUID sigue funcionando; nombre inexistente y clave incorrecta
     -> 401 con el mismo mensaje.
Crea y borra sus propios tenants de prueba.

Uso:
    python verify_login_tenant_name_and_ttl_end_to_end.py "<DSN rol de aplicacion>"
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

NAME = "E2E Login Por Nombre"
NAME_NO_TTL = "E2E Login Sin Duracion"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  OK  {message}")


def claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def login(client, org: str, user: str = "usr-e2e@renfygrid.test", password: str = "clave-e2e"):
    return client.post("/auth/login", json={"tenant_id": org, "email": user, "password": password})


def run(dsn: str) -> None:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = "e2e-login-secret"
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = "e2e-login-sign"

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    with psycopg.connect(dsn, autocommit=True) as conn:
        tenant_id = str(conn.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", (NAME,)).fetchone()[0])
        no_ttl_id = str(conn.execute("INSERT INTO tenant (name, config) VALUES (%s, '{}'::jsonb) RETURNING id",
                                     (NAME_NO_TTL,)).fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "usr-e2e@renfygrid.test", "clave-e2e", "supervisor")
            create_app_user(conn, no_ttl_id, "usr-e2e@renfygrid.test", "clave-e2e", "supervisor")

            r = login(client, NAME.upper())
            check(r.status_code == 200, "login por nombre (mayúsculas) -> 200")
            token = r.json()["access_token"]
            c = claims(token)
            check(c["tenant_id"] == tenant_id, "el token trae el tenant_id real")
            check(c["exp"] - c["iat"] == 43200 == r.json()["expires_in"], "tenant nuevo: sesión de 12 h desde el esquema (0022)")
            h = {"Authorization": f"Bearer {token}"}

            me = client.get("/auth/me", headers=h).json()
            check(me["tenant_name"] == NAME and me["email"] == "usr-e2e@renfygrid.test" and me["role"] == "supervisor",
                  "/auth/me devuelve organización, usuario y rol")
            check(me["expires_at"] > me["issued_at"], "/auth/me devuelve inicio y vencimiento")
            check(client.get("/auth/me").status_code == 401, "/auth/me sin token -> 401")

            check(client.get("/settings/session", headers=h).json() == {"session_ttl_seconds": 43200}, "GET /settings/session")
            r = client.put("/settings/session", headers=h, json={"session_ttl_seconds": 7200})
            check(r.status_code == 200 and r.json()["session_ttl_seconds"] == 7200, "PUT /settings/session = 2 h")
            c2 = claims(login(client, NAME).json()["access_token"])
            check(c2["exp"] - c2["iat"] == 7200, "el login siguiente usa la nueva duración")
            check(client.put("/settings/session", headers=h, json={"session_ttl_seconds": 60}).status_code == 422,
                  "menos de 5 minutos -> 422")

            r = login(client, NAME_NO_TTL)
            check(r.status_code == 409 and "Configuración" in r.json()["detail"],
                  "organización sin duración configurada -> 409 con mensaje claro")

            check(login(client, tenant_id).status_code == 200, "login por UUID sigue funcionando")
            bad_name = login(client, "no-existe-xyz")
            bad_pw = login(client, NAME, password="otra")
            check(bad_name.status_code == 401 and bad_pw.status_code == 401, "nombre inexistente y clave incorrecta -> 401")
            check(bad_name.json() == bad_pw.json(), "mismo mensaje en ambos casos (no ayuda a enumerar)")
        finally:
            for tid in (tenant_id, no_ttl_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        conn.execute("DELETE FROM app_user WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
    print("LOGIN POR NOMBRE + DURACION DE SESION POR ORGANIZACION E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
