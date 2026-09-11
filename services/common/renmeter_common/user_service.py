"""Alta y autenticación de usuarios reales (`app_user`, F47, Sprint C1).

Vive en `renmeter_common` (no en `portal-api`) porque tanto el Portal Web
(login) como `infra/onboarding/onboard_tenant.py` (alta de usuarios al dar
de alta un tenant piloto) lo necesitan -- mismo criterio que
`renmeter_common.db`/`config_cache`.
"""

from __future__ import annotations

import psycopg

from renmeter_common.db import tenant_scope
from renmeter_common.passwords import hash_password, verify_password


class InvalidCredentialsError(RuntimeError):
    """Email/tenant/contraseña no coinciden con ningún usuario activo --
    mensaje deliberadamente genérico (no distingue "no existe" de
    "contraseña incorrecta") para no ayudar a enumerar emails válidos."""


def create_app_user(
    conn: psycopg.Connection, tenant_id: str, email: str, password: str, role: str
) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO app_user (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
                    (tenant_id, email, hash_password(password), role),
                )
                (user_id,) = cur.fetchone()
                return str(user_id)


def authenticate(conn: psycopg.Connection, tenant_id: str, email: str, password: str) -> dict:
    """Devuelve `{user_id, role}` si las credenciales son válidas y el
    usuario está activo. Lanza `InvalidCredentialsError` en cualquier otro
    caso -- nunca revela si el problema fue el email, la contraseña, o que
    el usuario está desactivado."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, password_hash, role, is_active FROM app_user WHERE tenant_id = %s AND email = %s",
                    (tenant_id, email),
                )
                row = cur.fetchone()

    if row is None:
        raise InvalidCredentialsError("Credenciales inválidas")
    user_id, password_hash, role, is_active = row
    if not is_active or not verify_password(password, password_hash):
        raise InvalidCredentialsError("Credenciales inválidas")
    return {"user_id": str(user_id), "role": role}
