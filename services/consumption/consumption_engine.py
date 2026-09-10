"""Motor de Gestion de Consumos -- agregacion de lecturas validadas en
consumo facturable (F21) y deteccion de desviacion vs. el periodo anterior
(F22), Sprint 5.

Logica pura, sin BD -- mismo principio que vee_engine.py: nada de umbral
fijo en codigo, `consumption_anomaly_rule.condition` (BD, cacheada) es la
unica fuente del porcentaje de desviacion que dispara una orden.

Por que "cierre menos apertura" y no una suma directa: un registro DLMS
tipico (OBIS 1.0.1.8.0.255, energia activa) es ACUMULATIVO desde la
instalacion del medidor, no ya viene como "consumo de este periodo" --
el consumo de un periodo es la lectura de cierre menos la de apertura,
igual que la lectura de un medidor de energia real.
"""

from __future__ import annotations

from dataclasses import dataclass


def compute_consumption(opening_value: float, closing_value: float) -> float:
    return closing_value - opening_value


@dataclass
class DeviationResult:
    is_anomalous: bool
    deviation_pct: float | None
    action: str | None
    rule_id: str | None


def detect_deviation(
    current_value: float, previous_value: float | None, rules: list[dict]
) -> DeviationResult:
    """`rules`: `consumption_anomaly_rule` activas ya cacheadas, cada una con
    `condition` (ej. `{"max_deviation_pct": 30}`) y `action`
    (`'inspection_order'`|`'reread_order'`). Sin consumo previo (primer
    periodo del medidor) no hay con que comparar -- no se adivina una
    anomalia, se devuelve sin ella. `consumption_anomaly_rule` no tiene
    columna `priority` (a diferencia de `vee_rule`): cuando hay mas de una
    regla de tipo desviacion activa, gana la mas estricta (menor
    `max_deviation_pct`), por convencion documentada aca, no en el codigo
    del llamador."""
    if previous_value in (None, 0):
        return DeviationResult(is_anomalous=False, deviation_pct=None, action=None, rule_id=None)

    deviation_pct = abs(current_value - previous_value) / abs(previous_value) * 100
    candidates = [rule for rule in rules if "max_deviation_pct" in rule["condition"]]
    if not candidates:
        return DeviationResult(is_anomalous=False, deviation_pct=deviation_pct, action=None, rule_id=None)

    rule = min(candidates, key=lambda rule: rule["condition"]["max_deviation_pct"])
    threshold = rule["condition"]["max_deviation_pct"]
    if deviation_pct > threshold:
        return DeviationResult(is_anomalous=True, deviation_pct=deviation_pct, action=rule["action"], rule_id=rule["id"])
    return DeviationResult(is_anomalous=False, deviation_pct=deviation_pct, action=None, rule_id=None)
