"""Fichas y tablas de las guias con BD (Track E, E1, migracion 0047).

Una ficha o tabla es un documento vivo: hay un solo contenido vigente por
organizacion (o por operador asesorado dentro de la ONG) y cada guardado deja
una version (`form_entry_version`) con quien, cuando, desde donde (Portal,
archivo o traspaso) y en que taller. Se puede guardar a medias: el estado
dice si ya esta completa. La logica de validacion vive en `form_engine.py`.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from form_engine import FORM_KINDS, InvalidFormError, clean_form, completeness  # noqa: E402
from pack_service import TemplateNotAvailableError, list_checklist_templates  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

SOURCES = ("portal", "import", "transfer")


def form_template(conn: psycopg.Connection, tenant_id: str, template_id: str) -> dict:
    for t in list_checklist_templates(conn, tenant_id):
        if t["id"] == template_id:
            if t["kind"] not in FORM_KINDS:
                raise InvalidFormError(f"{template_id} es una lista: se aplica como revisión, no como ficha o tabla")
            return t
    raise TemplateNotAvailableError(f"El formulario {template_id!r} no existe o su paquete no está adoptado")


def _entry_row(conn: psycopg.Connection, tenant_id: str, template_id: str, operator_id: str | None) -> tuple | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, data, complete, updated_at, updated_by, workshop_id FROM form_entry "
            "WHERE tenant_id = %s AND template_id = %s AND advised_operator_id IS NOT DISTINCT FROM %s::uuid",
            (tenant_id, template_id, operator_id),
        )
        return cur.fetchone()


def get_form(conn: psycopg.Connection, tenant_id: str, template_id: str, advised_operator_id: str | None = None) -> dict:
    template = form_template(conn, tenant_id, template_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            row = _entry_row(conn, tenant_id, template_id, advised_operator_id)
            versions = 0
            if row:
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM form_entry_version WHERE entry_id = %s", (row[0],))
                    versions = cur.fetchone()[0]
    spec = template["form_spec"] or {}
    data = row[1] if row else ({"fields": {}} if template["kind"] == "record" else {"rows": []})
    return {
        "template": {k: template[k] for k in ("id", "pack_id", "kind", "title", "purpose", "stage_code", "form_spec")},
        "entry_id": str(row[0]) if row else None,
        "data": data,
        "progress": completeness(template["kind"], spec, data),
        "updated_at": row[3].isoformat() if row else None,
        "updated_by": row[4] if row else None,
        "workshop_id": str(row[5]) if row and row[5] else None,
        "versions": versions,
    }


def save_form(
    conn: psycopg.Connection,
    tenant_id: str,
    template_id: str,
    data: dict,
    actor: str,
    advised_operator_id: str | None = None,
    workshop_id: str | None = None,
    source: str = "portal",
) -> dict:
    """Reemplaza el contenido vigente por `data` (ya validado) y deja una
    version. Para cambiar un solo campo, la interfaz manda el contenido
    completo que esta viendo."""
    if source not in SOURCES:
        raise InvalidFormError(f"Origen desconocido: {source!r}")
    template = form_template(conn, tenant_id, template_id)
    spec = template["form_spec"] or {}
    clean = clean_form(template["kind"], spec, data)
    progress = completeness(template["kind"], spec, clean)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO form_entry (tenant_id, template_id, advised_operator_id, data, complete, workshop_id, updated_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id, template_id, coalesce(advised_operator_id, '00000000-0000-0000-0000-000000000000'::uuid)) "
                    "DO UPDATE SET data = EXCLUDED.data, complete = EXCLUDED.complete, "
                    "workshop_id = coalesce(EXCLUDED.workshop_id, form_entry.workshop_id), "
                    "updated_by = EXCLUDED.updated_by, updated_at = now() RETURNING id",
                    (tenant_id, template_id, advised_operator_id, Json(clean), progress["complete"], workshop_id, actor),
                )
                entry_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO form_entry_version (entry_id, tenant_id, data, complete, workshop_id, source, saved_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (entry_id, tenant_id, Json(clean), progress["complete"], workshop_id, source, actor),
                )
    return get_form(conn, tenant_id, template_id, advised_operator_id)


def merge_record(current: dict, incoming: dict) -> dict:
    """Ficha: lo que trae un archivo se suma a lo que ya hay, campo por campo
    (un archivo con solo dos campos no borra los demas)."""
    fields = dict((current or {}).get("fields") or {})
    fields.update((incoming or {}).get("fields") or {})
    return {"fields": fields}


def form_versions(conn: psycopg.Connection, tenant_id: str, template_id: str, advised_operator_id: str | None = None) -> list[dict]:
    form_template(conn, tenant_id, template_id)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            row = _entry_row(conn, tenant_id, template_id, advised_operator_id)
            if row is None:
                return []
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, saved_at, saved_by, source, complete, workshop_id FROM form_entry_version "
                    "WHERE entry_id = %s ORDER BY saved_at DESC",
                    (row[0],),
                )
                return [{"version_id": str(r[0]), "saved_at": r[1].isoformat(), "saved_by": r[2], "source": r[3],
                         "complete": r[4], "workshop_id": str(r[5]) if r[5] else None} for r in cur.fetchall()]


def entries_for(conn: psycopg.Connection, tenant_id: str, advised_operator_id: str | None = None) -> dict[str, dict[str, Any]]:
    """Contenido vigente de todas las fichas y tablas de un alcance."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT template_id, data, complete, updated_at FROM form_entry "
                    "WHERE tenant_id = %s AND advised_operator_id IS NOT DISTINCT FROM %s::uuid",
                    (tenant_id, advised_operator_id),
                )
                return {r[0]: {"data": r[1], "complete": r[2], "updated_at": r[3]} for r in cur.fetchall()}


def is_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False
