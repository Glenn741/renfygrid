"""Roles y permisos reales (Track D, D1.4b, migracion 0033).

Hasta 0033 todo usuario era `supervisor` y ninguna escritura revisaba
permisos. Ahora:
  - El catalogo (`app_permission`, `app_role`, `role_default_permission`)
    dice que puede hacer cada rol por defecto; una junta puede reemplazar los
    permisos de un rol (`tenant_role_override`), incluso dejarlo vacio.
  - El Portal/API revisa CADA escritura (POST/PUT/PATCH/DELETE) con
    `required_permission`: la tabla de rutas de abajo dice que permiso pide
    cada una, y una escritura que no este en la tabla exige `settings.manage`
    (lo nuevo nunca queda abierto por olvido).
  - El rol se lee de la BD en cada escritura, no del token: quitar un
    permiso o desactivar un usuario rige de inmediato, sin esperar a que su
    sesion venza.
  - Nunca queda una junta sin nadie que pueda administrar usuarios.
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.passwords import hash_password  # noqa: E402

MIN_PASSWORD_LENGTH = 8  # limite de validacion, no un valor de uso
USERS_PERMISSION = "users.manage"
FALLBACK_PERMISSION = "settings.manage"

_ID = r"[^/]+"
# (metodos, ruta, permiso). None = cualquier usuario autenticado (escrituras
# que no cambian nada: evaluar una regla, calcular una dosis).
ROUTE_RULES: list[tuple[frozenset[str] | None, re.Pattern, str | None]] = [
    (None, re.compile(r"^/auth/login$"), None),
    (None, re.compile(r"^/parameter-rules/evaluate$"), None),
    (None, re.compile(r"^/dosing/calculate$"), None),
    (None, re.compile(r"^/(field-readings|operation-log|manual-reading)$"), "operations.record"),
    (None, re.compile(rf"^/(sampling-points|chemical-products)(/{_ID})?$"), "operations.manage"),
    (None, re.compile(r"^/checklist-runs$"), "checklists.apply"),
    (frozenset({"POST"}), re.compile(r"^/findings$"), "findings.report"),
    (None, re.compile(rf"^/findings/{_ID}$"), "findings.manage"),
    (None, re.compile(r"^/(passport|follow-up)(/.*)?$"), "program.manage"),
    (None, re.compile(r"^/maintenance-orders/bayforce-webhook$"), "maintenance.webhook"),
    (None, re.compile(r"^/maintenance/events$"), "maintenance.manage"),
    (None, re.compile(r"^/maintenance-orders(/.*)?$"), "maintenance.manage"),
    (None, re.compile(r"^/maintenance/(sla-policies|failure-codes|crews|pm-plans)(/.*)?$"), "maintenance.configure"),
    (None, re.compile(r"^/(network-zones|network-models|network-assets|asset-connectivity)(/.*)?$"), "network.manage"),
    (None, re.compile(rf"^/meters/{_ID}/(reads|ping)$"), "metering.operate"),
    (None, re.compile(r"^/meters/(.*/)?protection(/bulk)?$"), "metering.manage"),
    (None, re.compile(r"^/(vee/invalid-readings/edit|consumption/resolve)$"), "metering.manage"),
    (frozenset({"POST"}), re.compile(r"^/control-orders$"), "control.request"),
    (None, re.compile(rf"^/control-orders/{_ID}/approve$"), "control.approve"),
    (None, re.compile(r"^/quality/samples$"), "quality.record"),
    (None, re.compile(r"^/quality/plan(/.*)?$"), "quality.plan"),
    (None, re.compile(r"^/emergencies/activations(/.*)?$"), "emergency.activate"),
    (None, re.compile(r"^/emergencies/(plan|contacts|reviews)(/.*)?$"), "emergency.plan"),
    (None, re.compile(r"^/warehouse/movements$"), "warehouse.record"),
    (None, re.compile(r"^/warehouse/items(/.*)?$"), "warehouse.manage"),
    (None, re.compile(r"^/sanitation/discharges(/.*)?$"), "sanitation.record"),
    (None, re.compile(rf"^/sanitation/register/{_ID}/verify$"), "sanitation.verify"),
    (frozenset({"DELETE"}), re.compile(rf"^/improvement/inputs/{_ID}$"), "improvement.manage"),
    (None, re.compile(r"^/improvement/(minimum-plan|inputs)(/.*)?$"), "improvement.record"),
    (None, re.compile(r"^/group/members(/.*)?$"), "group.manage"),
    (None, re.compile(rf"^/group/memberships/{_ID}$"), "group.consent"),
    (None, re.compile(r"^/(users|roles)(/.*)?$"), USERS_PERMISSION),
    (None, re.compile(r"^/(settings|packs|vee-rules|consumption-anomaly-rules|control-approval-levels|obis-mappings)(/.*)?$"),
     "settings.manage"),
]
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class PermissionAdminError(ValueError):
    """Cambio de usuarios o roles que no se permite (dejaria la junta sin
    administrador, rol no asignable, correo invalido...)."""


class UserNotFoundError(LookupError):
    """Usuario o rol inexistente para esta junta."""


# Lecturas que piden permiso (D12): por defecto una lectura solo pide el
# token; estas exponen datos que no son de la propia junta.
READ_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/group/dashboard$"), "group.view"),
]


def required_permission(method: str, path: str) -> str | None:
    """Permiso que pide una escritura. Lecturas: ninguno (basta el token),
    salvo las de READ_RULES. Escritura fuera de la tabla: `settings.manage`."""
    method = method.upper()
    if method not in WRITE_METHODS:
        return next((perm for pattern, perm in READ_RULES if pattern.match(path)), None)
    for methods, pattern, permission in ROUTE_RULES:
        if (methods is None or method in methods) and pattern.match(path):
            return permission
    return FALLBACK_PERMISSION


# ── Permisos efectivos ────────────────────────────────────────────────

def _role_permissions(conn: psycopg.Connection, tenant_id: str, role: str) -> tuple[set[str], bool]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT permissions FROM tenant_role_override WHERE tenant_id = %s AND role_code = %s",
                            (tenant_id, role))
                row = cur.fetchone()
    if row is not None:
        return set(row[0]), True
    with conn.cursor() as cur:
        cur.execute("SELECT permission_code FROM role_default_permission WHERE role_code = %s", (role,))
        return {r[0] for r in cur.fetchall()}, False


def current_role(conn: psycopg.Connection, tenant_id: str, user_id: str | None, token_role: str | None) -> str | None:
    """Rol vigente del usuario segun la BD (None si esta desactivado o no
    existe). Un token sin `user_id` (anterior a C1) usa el rol del token."""
    if not user_id:
        return token_role
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        return None
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT role, is_active FROM app_user WHERE id = %s AND tenant_id = %s", (user_id, tenant_id))
                row = cur.fetchone()
    return row[0] if row and row[1] else None


def effective_permissions(conn: psycopg.Connection, tenant_id: str, role: str | None) -> set[str]:
    if not role:
        return set()
    return _role_permissions(conn, tenant_id, role)[0]


# ── Roles ─────────────────────────────────────────────────────────────

def list_permissions(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT code, area, label FROM app_permission ORDER BY sort_order")
        return [{"code": r[0], "area": r[1], "label": r[2]} for r in cur.fetchall()]


def list_roles(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT code, label, description, assignable FROM app_role ORDER BY sort_order")
        roles = cur.fetchall()
        cur.execute("SELECT role_code, permission_code FROM role_default_permission")
        defaults: dict[str, set[str]] = {}
        for role, perm in cur.fetchall():
            defaults.setdefault(role, set()).add(perm)
    out = []
    for code, label, description, assignable in roles:
        effective, overridden = _role_permissions(conn, tenant_id, code)
        out.append({"code": code, "label": label, "description": description, "assignable": assignable,
                    "default_permissions": sorted(defaults.get(code, set())), "permissions": sorted(effective),
                    "overridden": overridden})
    return out


def _admins_left(conn: psycopg.Connection, tenant_id: str, overrides: dict[str, set[str]] | None = None,
                 user_changes: dict[str, tuple[str, bool]] | None = None) -> int:
    """Usuarios activos que podrian administrar usuarios despues de un cambio
    (rol de un usuario, activo/inactivo o permisos de un rol)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id, role, is_active FROM app_user WHERE tenant_id = %s", (tenant_id,))
                users = {str(r[0]): (r[1], r[2]) for r in cur.fetchall()}
    users.update(user_changes or {})
    cache: dict[str, set[str]] = dict(overrides or {})
    count = 0
    for role, active in users.values():
        if not active:
            continue
        if role not in cache:
            cache[role] = _role_permissions(conn, tenant_id, role)[0]
        count += USERS_PERMISSION in cache[role]
    return count


def set_role_permissions(conn: psycopg.Connection, tenant_id: str, role: str, permissions: list[str], actor: str) -> dict:
    roles = {r["code"]: r for r in list_roles(conn, tenant_id)}
    if role not in roles:
        raise UserNotFoundError(f"No existe el rol {role!r}")
    valid = {p["code"] for p in list_permissions(conn)}
    unknown = sorted(set(permissions) - valid)
    if unknown:
        raise PermissionAdminError(f"Permisos desconocidos: {unknown}")
    if _admins_left(conn, tenant_id, overrides={role: set(permissions)}) == 0:
        raise PermissionAdminError("La organización quedaría sin nadie que pueda administrar usuarios")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            conn.execute(
                "INSERT INTO tenant_role_override (tenant_id, role_code, permissions, updated_by) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (tenant_id, role_code) DO UPDATE SET permissions = EXCLUDED.permissions, "
                "updated_by = EXCLUDED.updated_by, updated_at = now()",
                (tenant_id, role, sorted(set(permissions)), actor),
            )
    return next(r for r in list_roles(conn, tenant_id) if r["code"] == role)


def reset_role_permissions(conn: psycopg.Connection, tenant_id: str, role: str) -> dict:
    roles = {r["code"]: r for r in list_roles(conn, tenant_id)}
    if role not in roles:
        raise UserNotFoundError(f"No existe el rol {role!r}")
    if _admins_left(conn, tenant_id, overrides={role: set(roles[role]["default_permissions"])}) == 0:
        raise PermissionAdminError("La organización quedaría sin nadie que pueda administrar usuarios")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            conn.execute("DELETE FROM tenant_role_override WHERE tenant_id = %s AND role_code = %s", (tenant_id, role))
    return next(r for r in list_roles(conn, tenant_id) if r["code"] == role)


# ── Usuarios ──────────────────────────────────────────────────────────

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _user_row(r: tuple) -> dict:
    return {"user_id": str(r[0]), "email": r[1], "role": r[2], "is_active": r[3], "created_at": r[4].isoformat()}


def list_users(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, role, is_active, created_at FROM app_user WHERE tenant_id = %s "
                            "ORDER BY is_active DESC, email", (tenant_id,))
                return [_user_row(r) for r in cur.fetchall()]


def _assignable_role(conn: psycopg.Connection, role: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT assignable FROM app_role WHERE code = %s", (role,))
        row = cur.fetchone()
    if row is None:
        raise UserNotFoundError(f"No existe el rol {role!r}")
    if not row[0]:
        raise PermissionAdminError(f"El rol {role!r} es de una cuenta de servicio y no se asigna desde el Portal")


def _check_password(password: str) -> None:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise PermissionAdminError(f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres")


def create_user(conn: psycopg.Connection, tenant_id: str, email: str, password: str, role: str) -> dict:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email):
        raise PermissionAdminError("El usuario debe ser un correo (nombre@dominio)")
    _assignable_role(conn, role)
    _check_password(password)
    try:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO app_user (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) "
                        "RETURNING id, email, role, is_active, created_at",
                        (tenant_id, email, hash_password(password), role),
                    )
                    return _user_row(cur.fetchone())
    except psycopg.errors.UniqueViolation:
        raise PermissionAdminError(f"Ya existe un usuario {email!r} en esta organización") from None


def update_user(
    conn: psycopg.Connection, tenant_id: str, user_id: str, actor_user_id: str | None,
    role: str | None = None, is_active: bool | None = None, password: str | None = None,
) -> dict:
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        raise UserNotFoundError(f"No existe el usuario {user_id!r}") from None
    current = {u["user_id"]: u for u in list_users(conn, tenant_id)}.get(str(user_id))
    if current is None:
        raise UserNotFoundError(f"No existe el usuario {user_id} en esta organización")
    if role is not None and role != current["role"]:
        _assignable_role(conn, role)
    if is_active is False and str(user_id) == str(actor_user_id):
        raise PermissionAdminError("No puede desactivar su propio usuario")
    new_role = role if role is not None else current["role"]
    new_active = is_active if is_active is not None else current["is_active"]
    if _admins_left(conn, tenant_id, user_changes={str(user_id): (new_role, new_active)}) == 0:
        raise PermissionAdminError("La organización quedaría sin nadie que pueda administrar usuarios")
    sets, params = [], []
    if role is not None:
        sets.append("role = %s")
        params.append(role)
    if is_active is not None:
        sets.append("is_active = %s")
        params.append(is_active)
    if password is not None:
        _check_password(password)
        sets.append("password_hash = %s")
        params.append(hash_password(password))
    if sets:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                conn.execute(f"UPDATE app_user SET {', '.join(sets)} WHERE id = %s AND tenant_id = %s",
                             (*params, user_id, tenant_id))
    return {u["user_id"]: u for u in list_users(conn, tenant_id)}[str(user_id)]
