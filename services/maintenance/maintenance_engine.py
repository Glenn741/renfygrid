"""Logica pura del CMMS de Mantenimiento (sin BD ni I/O) -- SLA, mora y
KPIs. Mismo principio que `network_balance_engine.py`: la capa de
servicio (`order_service.py`) arma los datos desde filas reales y llama
aca, nunca calcula una formula ella misma.

Grounded en el estandar real de la industria (Cityworks -- referencia
dominante en CMMS de acueducto/alcantarillado -- y las metricas
MTTR/MTBF/% cumplimiento PM, ver docs/05-ejecucion.md 2026-09-14):
- MTTR (Mean Time To Repair) = tiempo promedio entre generar una orden y
  cerrarla como completada.
- Backlog = ordenes abiertas (no completadas/canceladas) + su antiguedad.
- % cumplimiento PM = de las ordenes de mantenimiento preventivo
  programado (fuente 'pm_schedule') que ya se cerraron, cuantas se
  cerraron dentro de su SLA -- solo cuenta las que SI tenian un SLA
  configurado (nunca se inventa un cumplimiento sobre ordenes sin tope
  real que cumplir).
"""

from __future__ import annotations

from datetime import datetime, timedelta

TERMINAL_STATUSES = {"completed", "cancelled"}


def compute_sla_due_at(created_at: datetime, target_hours: float | None) -> datetime | None:
    """`created_at + target_hours` -- `None` si no hay politica de SLA
    configurada para esa prioridad en este tenant (nunca una fecha
    fabricada sin un target real detras)."""
    if target_hours is None:
        return None
    return created_at + timedelta(hours=float(target_hours))


def is_overdue(sla_due_at: datetime | None, status: str, now: datetime) -> bool:
    """Una orden esta vencida si tiene un SLA real, sigue abierta, y ya
    paso su fecha limite. Sin SLA configurado -> nunca "vencida" (no hay
    limite real contra el cual estarlo)."""
    if sla_due_at is None or status in TERMINAL_STATUSES:
        return False
    return now > sla_due_at


def compute_mttr_hours(completed_orders: list[dict]) -> float | None:
    """`completed_orders`: dicts con `created_at`/`closed_at` reales
    (ambos datetime). `None` si no hay ninguna orden completada todavia
    (nunca un MTTR de 0 fabricado)."""
    durations = [
        (o["closed_at"] - o["created_at"]).total_seconds() / 3600.0
        for o in completed_orders
        if o.get("closed_at") is not None and o.get("created_at") is not None
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 1)


def compute_backlog(open_orders: list[dict], now: datetime) -> dict:
    """`open_orders`: ordenes con `status` fuera de `TERMINAL_STATUSES`.
    Devuelve conteo + antiguedad promedio en horas (`None` si no hay
    ninguna abierta -- no 0, que implicaria "sin atraso")."""
    if not open_orders:
        return {"count": 0, "avg_age_hours": None}
    ages = [(now - o["created_at"]).total_seconds() / 3600.0 for o in open_orders if o.get("created_at") is not None]
    return {
        "count": len(open_orders),
        "avg_age_hours": round(sum(ages) / len(ages), 1) if ages else None,
    }


def compute_pm_compliance_pct(closed_pm_orders: list[dict]) -> float | None:
    """`closed_pm_orders`: ordenes `source == 'pm_schedule'` ya
    cerradas, con `closed_at`/`sla_due_at`. Solo cuentan las que SI
    tenian `sla_due_at` real (una politica de SLA configurada) -- si
    ninguna la tiene, `None` (nada que medir, no 100%)."""
    with_sla = [o for o in closed_pm_orders if o.get("sla_due_at") is not None and o.get("closed_at") is not None]
    if not with_sla:
        return None
    on_time = sum(1 for o in with_sla if o["closed_at"] <= o["sla_due_at"])
    return round(100.0 * on_time / len(with_sla), 1)


def pm_plan_is_due(next_due_at: datetime, now: datetime) -> bool:
    return now >= next_due_at


def advance_pm_plan(next_due_at: datetime, interval_days: int, now: datetime) -> datetime:
    """Siguiente vencimiento real -- desde `next_due_at` (no desde `now`,
    para no ir corriendo el plan si se genera tarde) avanzando de a
    `interval_days` hasta quedar en el futuro."""
    new_due = next_due_at
    while new_due <= now:
        new_due = new_due + timedelta(days=interval_days)
    return new_due
