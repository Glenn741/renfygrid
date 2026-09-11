"""Motor de Control (SCR: Suspensión/Corte/Reconexión) -- reglas de
aprobación (F27), Sprint 6. Logica pura, sin BD -- igual principio que
vee_engine.py/consumption_engine.py.

Nada fijo en codigo: `control_approval_level` (BD, cacheada) decide, por
tenant y por tipo de orden, si hace falta aprobacion humana y que rol minimo
la puede dar (docs/03-diseno.md SS6).

Decision de alcance explicita: `min_required_role` se compara por IGUALDAD
EXACTA, no por jerarquia de roles (ej. "supervisor > operador") -- el diseno
no define ninguna tabla de rangos entre roles, e inventar una jerarquia no
pedida seria alcance no solicitado. Si en el futuro hace falta "cualquier
rol de rango >= X", eso necesita una tabla de jerarquia nueva, no una
suposicion aca.

Fail-safe: si no hay ninguna `control_approval_level` configurada para un
tipo de orden, se EXIGE aprobacion humana por defecto (nunca se auto-aprueba
por ausencia de configuracion -- ver docs/02-arquitectura-general.md SS6,
"el canal de control es el punto de mayor impacto si falla").
"""

from __future__ import annotations

from dataclasses import dataclass

VALID_ORDER_TYPES = {"suspension", "reconnection", "disconnection"}


@dataclass
class ApprovalLevel:
    requires_human_approval: bool
    min_required_role: str


def approval_level_for(order_type: str, levels: list[dict]) -> ApprovalLevel:
    matches = [level for level in levels if level["order_type"] == order_type]
    if not matches:
        return ApprovalLevel(requires_human_approval=True, min_required_role="operator")
    row = matches[0]  # UNIQUE (tenant_id, order_type, valid_from); el cache ya trae solo vigentes
    return ApprovalLevel(
        requires_human_approval=row["requires_human_approval"],
        min_required_role=row["min_required_role"],
    )


def status_after_request(approval: ApprovalLevel) -> str:
    """Toda orden nace `requested` (F26) -- esto decide a donde transiciona
    inmediatamente despues (F27): `pending_approval` si hace falta un humano,
    o directo a `approved` (auto-aprobada, sin humano) si el tenant configuro
    que este tipo de orden no lo necesita."""
    return "pending_approval" if approval.requires_human_approval else "approved"


def can_approve(actor_role: str, approval: ApprovalLevel) -> bool:
    return actor_role == approval.min_required_role
