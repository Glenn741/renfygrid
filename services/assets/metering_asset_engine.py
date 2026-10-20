"""Hoja de vida de los sistemas de medicion (Track F, Q2, migraciones 0049 y
0050) -- logica pura, sin BD.

Lo que decide aqui, siempre con los valores del paquete regulatorio (nunca
un numero fijo en el codigo):

- `point_class_for`: el tipo de punto que le corresponde a una frontera por
  su consumo mensual o su capacidad instalada (el mas exigente de los dos,
  CREG 038 art. 6).
- `periodic_status`: si la calibracion de un medidor o la prueba de rutina
  de un CT/PT esta al dia, por vencer, vencida o sin registro, a partir de
  su ultimo registro valido y la frecuencia del paquete para el tipo de
  punto donde esta instalado.
- `invalidates_calibration`: si un registro de la bitacora obliga a volver
  a calibrar (CREG 038 art. 11: retirar el sello de la tapa principal;
  art. 32: una parametrizacion que afecta la calibracion).
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any, Iterable


def add_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def point_class_for(consumption_mwh_month: float | None, capacity_mva: float | None, classes: Iterable[dict]) -> str | None:
    """`classes`: filas de `metering_point_class` ({code, min_mwh_month,
    min_mva, sort_order}). Gana el tipo mas exigente (menor `sort_order`)
    que cumpla cualquiera de los dos umbrales. Sin consumo ni capacidad no
    se puede decir."""
    if consumption_mwh_month is None and capacity_mva is None:
        return None
    for c in sorted(classes, key=lambda c: c["sort_order"]):
        by_energy = consumption_mwh_month is not None and consumption_mwh_month >= float(c["min_mwh_month"])
        by_capacity = capacity_mva is not None and capacity_mva >= float(c["min_mva"])
        if by_energy or by_capacity:
            return c["code"]
    return None


def _field(data: dict | None, key: str) -> Any:
    entry = ((data or {}).get("fields") or {}).get(key)
    return entry.get("value") if isinstance(entry, dict) else entry


def invalidates_calibration(rule: str | None, data: dict | None) -> bool:
    """`rule` = `metering_event_type.invalidates_calibration`: NULL (nunca),
    'always', o la clave de un campo booleano del registro que lo indica."""
    if not rule:
        return False
    if rule == "always":
        return True
    return _field(data, rule) is True


def event_passed(data: dict | None) -> bool:
    """Una calibracion o prueba con resultado "No conforme" no cuenta como
    vigente; sin resultado se toma como registrada."""
    return _field(data, "result") != "fail"


def periodic_status(
    *,
    activity: str | None,
    every_months: int | None,
    last_done: date | None,
    invalidated_after: date | None,
    today: date,
    due_soon_days: int | None,
) -> dict[str, Any]:
    """Estado de la actividad periodica de un equipo.

    - `activity` None (p. ej. un modem) o sin frecuencia (equipo sin
      instalar, o tipo de punto sin definir): `not_required`.
    - sin registro valido: `missing`.
    - un registro posterior que invalida la calibracion: `overdue` desde ese dia.
    - `due_soon_days` None (la organizacion no configuro la ventana de aviso):
      solo `ok` u `overdue`, nunca una ventana inventada.
    """
    if activity is None or every_months is None:
        return {"status": "not_required", "last_done": last_done.isoformat() if last_done else None, "due_on": None}
    if last_done is None:
        return {"status": "missing", "last_done": None, "due_on": None}
    due_on = add_months(last_done, every_months)
    if invalidated_after is not None and invalidated_after >= last_done:
        return {"status": "overdue", "last_done": last_done.isoformat(), "due_on": invalidated_after.isoformat(),
                "reason": "invalidated"}
    if due_on < today:
        status = "overdue"
    elif due_soon_days is not None and due_on <= today + timedelta(days=due_soon_days):
        status = "due_soon"
    else:
        status = "ok"
    return {"status": status, "last_done": last_done.isoformat(), "due_on": due_on.isoformat()}


STATUS_RANK = {"overdue": 0, "missing": 1, "due_soon": 2, "ok": 3, "not_required": 4}


def worst_status(statuses: Iterable[str]) -> str:
    """El estado de una frontera es el peor de sus equipos instalados."""
    ranked = sorted(statuses, key=lambda s: STATUS_RANK.get(s, 9))
    return ranked[0] if ranked else "not_required"
