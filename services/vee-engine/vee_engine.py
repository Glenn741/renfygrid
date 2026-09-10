"""Motor VEE -- Validacion (F14/F15, Sprint 3) + deteccion de intervalos
faltantes y estimacion (F16/F17, Sprint 4).

Logica pura, sin BD ni I/O -- toda regla llega ya cargada (desde el cache de
`vee_rules_cache.py`, patron config cacheada, ver docs/03-diseno.md SS2).
Nada de umbral fijo en codigo: `vee_rule.params` (BD) es la unica fuente de
los limites/intervalos/metodo por canal (docs/02-arquitectura-general.md,
principio "cero hardcode").

F17 (estimacion): el diseno (docs/03-diseno.md SS5) pide que el metodo sea
"un parametro de vee_rule.params, no un if en el codigo" -- de los 3 metodos
mencionados alli (`linear_interpolation`, `customer_historical_average`,
`similar_customers_average`), Sprint 4 implementa solo el primero. Los otros
dos necesitan agregados historicos por cliente/grupo de clientes que no
existen todavia (series de tiempo mas largas que las del piloto actual) --
`estimate_gap` levanta `NotImplementedError` para un metodo no soportado en
vez de fallar silenciosamente o adivinar, para que quede visible cuando haga
falta agregar el que sigue.

Edicion manual auditada (F18) vive en `manual_edit.py`, no aca -- toca BD
(la auditoria tiene que ser transaccional con el UPDATE), asi que no es
logica pura.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
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


@dataclass
class Gap:
    """Un hueco detectado entre dos lecturas consecutivas conocidas."""

    after_timestamp: datetime
    before_timestamp: datetime
    after_value: float
    before_value: float
    missing_count: int


@dataclass
class EstimatedPoint:
    timestamp: datetime
    value: float


def missing_interval_rule_for(rules: list[dict], channel: str) -> dict | None:
    """La regla `type == 'missing_interval'` activa para ese canal -- sus
    `params` traen `expected_interval_seconds`, `tolerance_seconds` y
    `estimation_method` (ver docstring del modulo)."""
    candidates = [
        rule
        for rule in rules
        if rule["type"] == "missing_interval" and rule["params"].get("channel") == channel
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda rule: rule["priority"])


def detect_gaps(
    readings: list[tuple[datetime, float]],
    expected_interval_seconds: float,
    tolerance_seconds: float,
) -> list[Gap]:
    """`readings`: pares (timestamp, value) YA ORDENADOS por timestamp
    ascendente (el llamador es responsable del orden -- ver `run_vee_estimation.py`,
    que los trae de una consulta `ORDER BY`). Un hueco es un salto entre dos
    lecturas consecutivas mayor que el intervalo esperado mas la tolerancia."""
    gaps: list[Gap] = []
    for (prev_ts, prev_value), (next_ts, next_value) in zip(readings, readings[1:]):
        delta_seconds = (next_ts - prev_ts).total_seconds()
        if delta_seconds <= expected_interval_seconds + tolerance_seconds:
            continue
        missing_count = round(delta_seconds / expected_interval_seconds) - 1
        if missing_count > 0:
            gaps.append(
                Gap(
                    after_timestamp=prev_ts,
                    before_timestamp=next_ts,
                    after_value=prev_value,
                    before_value=next_value,
                    missing_count=missing_count,
                )
            )
    return gaps


def estimate_gap(gap: Gap, expected_interval_seconds: float, method: str) -> list[EstimatedPoint]:
    """Genera los puntos estimados dentro de un `Gap`, con el metodo
    configurado (ver docstring del modulo: solo `linear_interpolation`
    implementado en Sprint 4)."""
    if method != "linear_interpolation":
        raise NotImplementedError(
            f"Metodo de estimacion '{method}' no soportado todavia (solo linear_interpolation, Sprint 4)."
        )
    total_seconds = (gap.before_timestamp - gap.after_timestamp).total_seconds()
    points = []
    for i in range(1, gap.missing_count + 1):
        timestamp = gap.after_timestamp + timedelta(seconds=expected_interval_seconds * i)
        fraction = (timestamp - gap.after_timestamp).total_seconds() / total_seconds
        value = gap.after_value + (gap.before_value - gap.after_value) * fraction
        points.append(EstimatedPoint(timestamp=timestamp, value=value))
    return points
