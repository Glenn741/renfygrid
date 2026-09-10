"""Motor VEE -- etapa de Validacion (F14 rangos, F15 formato), Sprint 3.

Logica pura, sin BD ni I/O -- toda regla llega ya cargada (desde el cache de
`vee_rules_cache.py`, patron config cacheada, ver docs/03-diseno.md SS2).
Nada de umbral fijo en codigo: `vee_rule.params` (BD) es la unica fuente de
los limites min/max por canal (docs/02-arquitectura-general.md, principio
"cero hardcode").

Alcance explicito de Sprint 3, no mas: solo VALIDACION. Estimacion (F17,
metodo configurable) y edicion manual auditada (F18) son Sprint 4 a
proposito -- ver docs/05-ejecucion.md. "Coherencia entre canales" (activa vs
reactiva, mencionada en docs/03-diseno.md SS5) tampoco se implementa todavia
porque el piloto de referencia solo tiene un canal mapeado (ver Sprint 1-2);
queda para cuando haya un caso real con 2+ canales que validar entre si.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationResult:
    is_valid: bool
    vee_rule_id: str | None
    notes: str | None


def _is_well_formed_number(value: Any) -> bool:
    """F15 (formato): la BD ya garantiza `numeric NOT NULL` en raw_reading,
    pero un NaN/Infinity puede colarse igual desde ciertos drivers/DLMS --
    se rechaza explicito en vez de asumir que nunca puede pasar."""
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(as_float)


def _active_range_rule(rules: list[dict], channel: str) -> dict | None:
    """La regla `type == 'range'` activa para ese canal con mayor prioridad
    (menor `priority` = se evalua primero, ver `vee_rule.priority` en
    0001_init.sql) -- None si no hay ninguna configurada para ese canal."""
    candidates = [
        rule
        for rule in rules
        if rule["type"] == "range" and rule["params"].get("channel") == channel
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda rule: rule["priority"])


def validate_reading(value: Any, channel: str, rules: list[dict]) -> ValidationResult:
    """`rules` es la lista ya cacheada de `vee_rule` activas para el tenant
    (ver `vee_rules_cache.py`). Devuelve siempre un `ValidationResult` --
    nunca lanza, para que un valor raro en una lectura no tumbe el resto del
    pase de validacion (ver `run_vee_pass.py`)."""
    if not _is_well_formed_number(value):
        return ValidationResult(is_valid=False, vee_rule_id=None, notes="formato invalido: valor no numerico finito")

    rule = _active_range_rule(rules, channel)
    if rule is None:
        # Sin regla de rango configurada para este canal: no se rechaza por
        # rango (no hay con que comparar), pero SIN vee_rule_id -- distinto
        # de "paso una regla real" (ver docs/05-ejecucion.md F19, trazabilidad).
        return ValidationResult(is_valid=True, vee_rule_id=None, notes="sin regla de rango configurada para este canal")

    min_value = rule["params"].get("min")
    max_value = rule["params"].get("max")
    value_f = float(value)
    if min_value is not None and value_f < min_value:
        return ValidationResult(
            is_valid=False, vee_rule_id=rule["id"], notes=f"{value_f} < min configurado ({min_value})"
        )
    if max_value is not None and value_f > max_value:
        return ValidationResult(
            is_valid=False, vee_rule_id=rule["id"], notes=f"{value_f} > max configurado ({max_value})"
        )
    return ValidationResult(is_valid=True, vee_rule_id=rule["id"], notes=None)
