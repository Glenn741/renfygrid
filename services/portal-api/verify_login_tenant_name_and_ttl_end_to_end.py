"""Verificacion end-to-end del login por nombre de tenant y de la duracion de
sesion configurable (2026-10-05) -- HTTP real (TestClient), Postgres real.

Que prueba:
  1. Login con el NOMBRE del tenant (sin distinguir mayusculas) y un usuario
     que no es un correo -> 200, y el token trae el tenant_id real.
  2. Login con el UUID sigue funcionando.
  3. Nombre inexistente, o clave incorrecta -> 401 con el mismo mensaje.
  4. El token vence a los RENFYGRID_SESSION_TTL_SECONDS configurados.
Crea y borra su propio tenant de prueba.

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

TTL = 43200
NAME = "E2E Login Por Nombre"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  OK  {message}")


def claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def run(dsn: str) -> None:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = "e2e-login-secret"
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = "e2e-login-sign"
    os.environ["RENFYGRID_SESSION_TTL_SECONDS"] = str(TTL)

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    with psycopg.connect(dsn, autocommit=True) as conn:
        tenant_id = str(conn.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", (NAME,)).fetchone()[0])
        try:
            create_app_user(conn, tenant_id, "usr-e2e", "clave-e2e", "supervisor")

            r = client.post("/auth/login", json={"tenant_id": NAME.upper(), "email": "usr-e2e", "password": "clave-e2e"})
            check(r.status_code == 200, "login por nombre (mayúsculas) y usuario sin correo -> 200")
            token = r.json()["access_token"]
            c = claims(token)
            check(c["tenant_id"] == tenant_id and r.json()["tenant_id"] == tenant_id, "el token trae el tenant_id real")
            check(c["exp"] - c["iat"] == TTL and r.json()["expires_in"] == TTL, f"vence a los {TTL} s configurados")
            check(client.get("/packs", headers={"Authorization": f"Bearer {token}"}).status_code == 200, "el token sirve para la API")
            me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            check(me.status_code == 200 and me.json()["tenant_name"] == NAME and me.json()["email"] == "usr-e2e"
                  and me.json()["role"] == "supervisor", "/auth/me devuelve organización, usuario y rol")
            check(me.json()["expires_at"] > me.json()["issued_at"], "/auth/me devuelve inicio y vencimiento de la sesión")
            check(client.get("/auth/me").status_code == 401, "/auth/me sin token -> 401")

            r = client.post("/auth/login", json={"tenant_id": tenant_id, "email": "usr-e2e", "password": "clave-e2e"})
            check(r.status_code == 200, "login por UUID sigue funcionando")

            bad_name = client.post("/auth/login", json={"tenant_id": "no-existe-xyz", "email": "usr-e2e", "password": "clave-e2e"})
            bad_pw = client.post("/auth/login", json={"tenant_id": NAME, "email": "usr-e2e", "password": "otra"})
            check(bad_name.status_code == 401 and bad_pw.status_code == 401, "nombre inexistente y clave incorrecta -> 401")
            check(bad_name.json() == bad_pw.json(), "mismo mensaje en ambos casos (no ayuda a enumerar)")
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    conn.execute("DELETE FROM app_user WHERE tenant_id = %s", (tenant_id,))
            conn.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
    print("LOGIN POR NOMBRE + TTL E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
