"""Motor VEE -- Validacion (F14/F15, Sprint 3) + deteccion de intervalos
faltantes y estimacion (F16/F17, Sprint 4).

Logica pura, sin BD ni I/O -- toda regla llega ya cargada (desde el cache de
`vee_rules_cache.py`, patron config cacheada, ver docs/03-diseno.md SS2).
Nada de umbral fijo en codigo: `vee_rule.params` (BD) es la unica fuente de
los limites/intervalos/metodo por canal (docs/02-arquitectura-general.md,
principio "cero hardcode").

F15 (coherencia entre canales, Sprint C11): `03-diseno.md` SS5 pide
"coherencia entre canales (activa/reactiva)" -- diferido en Sprint 3 porque
el piloto de entonces solo tenia un canal mapeado por medidor (ya no, desde
que Sprint C10 dejo el editor de mapeo OBIS soportar varios canales por
marca/modelo). Regla nueva `vee_rule.type = 'channel_consistency'`:
compara `channel` contra `params.reference_channel` del MISMO medidor en el
MISMO instante -- `validate_reading` recibe `reference_value` ya resuelto
por el llamador (`run_vee_pass.py`, que va a `raw_reading` a buscarlo),
nunca toca BD el mismo.

F17 (estimacion): el diseno (docs/03-diseno.md SS5) pide que el metodo sea
"un parametro de vee_rule.params, no un if en el codigo". Los 3 metodos
mencionados alli:
  - `linear_interpolation` (Sprint 4): solo necesita los dos extremos del
    hueco -- no requiere historial.
  - `customer_historical_average` (Sprint C11): promedio de las lecturas
    REALES de ESTE MISMO medidor/canal en la misma hora del dia (across
    dias distintos) -- "que consume tipicamente este cliente a esta hora".
  - `similar_customers_average` (Sprint C11): promedio de las lecturas de
    OTROS medidores del mismo canal, cerca del mismo instante -- "que
    consumieron clientes similares en ese momento".
`estimate_gap` nunca inventa un promedio con datos que no existen: si el
metodo pide historial y no hay ninguna lectura que matchee, levanta
`InsufficientHistoryError` (distinto de `NotImplementedError`, que es para
un metodo que ni siquiera esta reconocido) -- el llamador (`run_vee_estimation.py`)
decide que hacer con un hueco que no se puede estimar todavia (no rellenarlo
con un valor inventado).

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


def channel_consistency_rule_for(rules: list[dict], channel: str) -> dict | None:
    """La regla `type == 'channel_consistency'` activa para ese canal (F15,
    Sprint C11) -- compara `channel` contra `params.reference_channel` del
    MISMO medidor en el MISMO instante (ej. reactiva vs. activa, `03-diseno.md`
    SS5). `params`: `reference_channel`, `min_ratio`, `max_ratio`. Publica
    (sin `_`) porque `run_vee_pass.py` la necesita para decidir si vale la
    pena ir a buscar la lectura del canal de referencia."""
    candidates = [
        rule
        for rule in rules
        if rule["type"] == "channel_consistency" and rule["params"].get("channel") == channel
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda rule: rule["priority"])


def validate_reading(
    value: Any, channel: str, rules: list[dict], reference_value: Any | None = None
) -> ValidationResult:
    """`rules` es la lista ya cacheada de `vee_rule` activas para el tenant
    (ver `vee_rules_cache.py`). `reference_value` es la lectura del
    `reference_channel` del MISMO medidor en el MISMO instante, si el
    llamador la trae (solo hace falta cuando hay una regla `channel_consistency`
    para este canal -- ver `run_vee_pass.py`). Devuelve siempre un
    `ValidationResult` -- nunca lanza, para que un valor raro en una lectura
    no tumbe el resto del pase de validacion."""
    if not _is_well_formed_number(value):
        return ValidationResult(is_valid=False, vee_rule_id=None, notes="formato invalido: valor no numerico finito")
    value_f = float(value)

    range_rule = _active_range_rule(rules, channel)
    if range_rule is not None:
        min_value = range_rule["params"].get("min")
        max_value = range_rule["params"].get("max")
        if min_value is not None and value_f < min_value:
            return ValidationResult(
                is_valid=False, vee_rule_id=range_rule["id"], notes=f"{value_f} < min configurado ({min_value})"
            )
        if max_value is not None and value_f > max_value:
            return ValidationResult(
                is_valid=False, vee_rule_id=range_rule["id"], notes=f"{value_f} > max configurado ({max_value})"
            )

    consistency_rule = channel_consistency_rule_for(rules, channel)
    if consistency_rule is not None:
        if reference_value is None or not _is_well_formed_number(reference_value):
            # No hay con que comparar todavia (el canal de referencia no
            # reporto en el mismo instante) -- no se adivina un ratio, se
            # deja sin evaluar (no invalida por esto).
            return ValidationResult(
                is_valid=True,
                vee_rule_id=range_rule["id"] if range_rule else None,
                notes="sin lectura del canal de referencia en el mismo instante -- coherencia no evaluada",
            )
        reference_f = float(reference_value)
        if reference_f == 0:
            return ValidationResult(
                is_valid=True,
                vee_rule_id=range_rule["id"] if range_rule else None,
                notes="canal de referencia en 0 -- ratio indefinido, coherencia no evaluada",
            )
        ratio = value_f / reference_f
        min_ratio = consistency_rule["params"].get("min_ratio")
        max_ratio = consistency_rule["params"].get("max_ratio")
        if (min_ratio is not None and ratio < min_ratio) or (max_ratio is not None and ratio > max_ratio):
            return ValidationResult(
                is_valid=False,
                vee_rule_id=consistency_rule["id"],
                notes=(
                    f"{channel}/{consistency_rule['params']['reference_channel']} = {ratio:.4f} "
                    f"fuera de [{min_ratio}, {max_ratio}]"
                ),
            )
        return ValidationResult(is_valid=True, vee_rule_id=consistency_rule["id"], notes=None)

    if range_rule is None:
        # Sin ninguna regla configurada para este canal: no se rechaza (no
        # hay con que comparar), pero SIN vee_rule_id -- distinto de "paso
        # una regla real" (ver docs/05-ejecucion.md F19, trazabilidad).
        return ValidationResult(is_valid=True, vee_rule_id=None, notes="sin regla de rango configurada para este canal")
    return ValidationResult(is_valid=True, vee_rule_id=range_rule["id"], notes=None)


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


_SUPPORTED_METHODS = ("linear_interpolation", "customer_historical_average", "similar_customers_average")


class InsufficientHistoryError(RuntimeError):
    """El metodo pedido (`customer_historical_average`/`similar_customers_average`)
    necesita lecturas historicas reales para promediar y no encontro ninguna
    que matchee -- nunca se inventa un promedio con datos que no existen."""


def _time_of_day_seconds(timestamp: datetime) -> float:
    midnight = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    return (timestamp - midnight).total_seconds()


def _average_by_time_of_day(
    historical_readings: list[tuple[datetime, float]], target: datetime, tolerance_seconds: float
) -> float:
    """`customer_historical_average`: lecturas historicas (de ESTE medidor,
    responsabilidad del llamador filtrarlas asi) cuya hora del dia cae
    dentro de `tolerance_seconds` de la hora del punto a estimar --
    sin importar de que dia sean."""
    target_tod = _time_of_day_seconds(target)
    matches = [
        value
        for timestamp, value in historical_readings
        if abs(_time_of_day_seconds(timestamp) - target_tod) <= tolerance_seconds
    ]
    if not matches:
        raise InsufficientHistoryError(
            f"Sin historial propio del medidor a la hora de {target} (tolerancia {tolerance_seconds}s) -- "
            "no se inventa un promedio."
        )
    return sum(matches) / len(matches)


def _average_near(
    historical_readings: list[tuple[datetime, float]], target: datetime, tolerance_seconds: float
) -> float:
    """`similar_customers_average`: lecturas de OTROS medidores (mismo canal,
    responsabilidad del llamador filtrarlas asi) cuyo timestamp cae dentro
    de `tolerance_seconds` del instante a estimar."""
    matches = [
        value
        for timestamp, value in historical_readings
        if abs((timestamp - target).total_seconds()) <= tolerance_seconds
    ]
    if not matches:
        raise InsufficientHistoryError(
            f"Sin lecturas de otros medidores cerca de {target} (tolerancia {tolerance_seconds}s) -- "
            "no se inventa un promedio."
        )
    return sum(matches) / len(matches)


def estimate_gap(
    gap: Gap,
    expected_interval_seconds: float,
    method: str,
    historical_readings: list[tuple[datetime, float]] | None = None,
    historical_tolerance_seconds: float | None = None,
) -> list[EstimatedPoint]:
    """Genera los puntos estimados dentro de un `Gap`, con el metodo
    configurado (ver docstring del modulo). `historical_readings` solo lo
    usan los dos metodos que lo necesitan -- `linear_interpolation` lo
    ignora (los dos extremos del propio `gap` bastan)."""
    if method not in _SUPPORTED_METHODS:
        raise NotImplementedError(f"Metodo de estimacion '{method}' no reconocido (soportados: {_SUPPORTED_METHODS}).")

    total_seconds = (gap.before_timestamp - gap.after_timestamp).total_seconds()
    tolerance = (
        historical_tolerance_seconds if historical_tolerance_seconds is not None else expected_interval_seconds / 2
    )

    points = []
    for i in range(1, gap.missing_count + 1):
        timestamp = gap.after_timestamp + timedelta(seconds=expected_interval_seconds * i)
        if method == "linear_interpolation":
            fraction = (timestamp - gap.after_timestamp).total_seconds() / total_seconds
            value = gap.after_value + (gap.before_value - gap.after_value) * fraction
        elif method == "customer_historical_average":
            value = _average_by_time_of_day(historical_readings or [], timestamp, tolerance)
        else:  # similar_customers_average
            value = _average_near(historical_readings or [], timestamp, tolerance)
        points.append(EstimatedPoint(timestamp=timestamp, value=value))
    return points
