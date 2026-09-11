"""Lista de cuentas protegidas contra suspension/desconexion (Control/SCR,
Sprint C11-5) -- benchmark real (docs/05-ejecucion.md Sprint C11-5): ningun
MDM/CIS de referencia ejecuta un corte sin chequear si la cuenta es un
"usuario de proteccion especial"; en Colombia esto es requisito real (Ley
142 de 1994 + normas de la CRA/CREG posteriores -- Resolucion CREG
108/1997 exige considerar "sujetos de especial proteccion" antes de
suspender, con derecho a debido proceso).

Alcance deliberadamente acotado (confirmado con el usuario): esto es SOLO
la bandera de exclusion + quien/cuando/por-que-en-texto-libre la marco --
la clasificacion real del cliente (es un hospital, un colegio, tiene
tarifa especial...) es dato de CIS, fuera del alcance de un MDM como
RenfyGrid. Marcar la bandera es una decision operativa ya tomada (por
carga masiva desde una lista externa, o a mano), no una reimplementacion
del CIS.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


class MeterNotFoundError(LookupError):
    """No existe ese medidor (o esa cuenta) para este tenant."""


def is_protected(conn: psycopg.Connection, tenant_id: str, meter_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT protected_from_suspension, protection_reason, protection_marked_by, protection_marked_at "
                    "FROM meter WHERE id = %s AND tenant_id = %s",
                    (meter_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise MeterNotFoundError(f"No existe el medidor {meter_id} para este tenant")
    protected, reason, marked_by, marked_at = row
    return {
        "protected": protected,
        "reason": reason,
        "marked_by": marked_by,
        "marked_at": marked_at.isoformat() if marked_at else None,
    }


def mark_protection(
    conn: psycopg.Connection, tenant_id: str, meter_id: str, protected: bool, reason: str | None, marked_by: str
) -> None:
    """Marca (o quita) la proteccion de UN medidor/cuenta a mano -- deja
    quien y cuando, siempre (aunque se este desmarcando), para que la
    decision quede trazable igual que cualquier otra accion sobre una
    orden de control. Marcar SIN motivo no se permite -- mismo criterio
    que `bulk_mark_protection`, que ya exigia `reason`; desmarcar si lo
    permite (no hace falta justificar por que una cuenta deja de estar
    protegida, solo queda quien lo hizo)."""
    if protected and not reason:
        raise ValueError("No se puede marcar una cuenta como protegida sin `reason`")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE meter SET protected_from_suspension = %s, protection_reason = %s, "
                    "  protection_marked_by = %s, protection_marked_at = now() "
                    "WHERE id = %s AND tenant_id = %s",
                    (protected, reason, marked_by, meter_id, tenant_id),
                )
                if cur.rowcount == 0:
                    raise MeterNotFoundError(f"No existe el medidor {meter_id} para este tenant")


def bulk_mark_protection(
    conn: psycopg.Connection, tenant_id: str, account_numbers: list[str], reason: str, marked_by: str
) -> dict:
    """Carga masiva (ej. desde un archivo de cuentas excluidas de corte) --
    por `account_number`, no `meter_id` (el archivo externo no conoce los
    UUID internos). Cuentas que no existen en este tenant se reportan, no
    se inventan ni se descartan en silencio."""
    marked: list[str] = []
    not_found: list[str] = []
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                for account_number in account_numbers:
                    cur.execute(
                        "UPDATE meter SET protected_from_suspension = true, protection_reason = %s, "
                        "  protection_marked_by = %s, protection_marked_at = now() "
                        "WHERE account_number = %s AND tenant_id = %s",
                        (reason, marked_by, account_number, tenant_id),
                    )
                    (marked if cur.rowcount > 0 else not_found).append(account_number)
    return {"marked": marked, "not_found": not_found}


def list_protected_meters(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, account_number, brand, model, protection_reason, protection_marked_by, protection_marked_at "
                    "FROM meter WHERE tenant_id = %s AND protected_from_suspension = true "
                    "ORDER BY account_number",
                    (tenant_id,),
                )
                rows = cur.fetchall()
    return [
        {
            "meter_id": str(meter_id),
            "account_number": account_number,
            "brand": brand,
            "model": model,
            "reason": reason,
            "marked_by": marked_by,
            "marked_at": marked_at.isoformat() if marked_at else None,
        }
        for meter_id, account_number, brand, model, reason, marked_by, marked_at in rows
    ]
