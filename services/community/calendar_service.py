"""Calendario anual de mantenimiento, control y analisis de calidad (Guia 3,
ficha 7G; Track D, D3.2): "reune las tareas de mantenimiento, el control
operativo y los analisis de calidad del agua... La directiva y el operador
deben acordar fechas concretas y revisar mensualmente su cumplimiento."

No es una tabla nueva: se arma con lo que la junta ya definio en la
plataforma, cada actividad con su frecuencia y responsable:
  - mantenimiento: planes del CMMS (0019/0035). Esperadas = ordenes que el
    plan genero este ano + periodos vencidos que todavia no se generaron;
    cumplidas = las completadas. Las extraordinarias por evento se cuentan
    aparte (no cambian el cumplimiento del calendario).
  - listas de revision con frecuencia del paquete (7A, 7E, 7G.1...).
  - plan de muestreo de laboratorio de la junta (0034).
El % de cumplimiento es lo hecho (sin pasar de lo esperado) sobre lo
esperado en lo que va del ano. Lo esperado se cuenta desde que la actividad
existe en la junta (adopcion del paquete de la lista, alta de la parte del
plan de muestreo), no desde el 1 de enero: una junta que empezo en octubre no
debe aparecer con nueve meses de incumplimiento.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_engine import checklist_status, compliance_pct, periods_elapsed  # noqa: E402
from pack_service import list_checklist_templates  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def annual_calendar(conn: psycopg.Connection, tenant_id: str, year_start: datetime, now: datetime) -> dict:
    """`year_start` y `now` con la zona horaria de la organizacion."""
    def days_since(start: datetime | None) -> float:
        start = max(year_start, start) if start else year_start
        return (now - start).total_seconds() / 86400

    items: list[dict] = []
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT p.id, coalesce(p.title, a.type), p.interval_days, p.responsible, p.next_due_at, p.trigger_events, "
                    "count(o.id) FILTER (WHERE o.source = 'pm_schedule'), "
                    "count(o.id) FILTER (WHERE o.source = 'pm_schedule' AND o.status = 'completed'), "
                    "count(o.id) FILTER (WHERE o.source = 'event'), "
                    "count(o.id) FILTER (WHERE o.source = 'event' AND o.status = 'completed') "
                    "FROM maintenance_pm_plan p JOIN network_asset a ON a.id = p.asset_id "
                    "LEFT JOIN maintenance_order o ON o.pm_plan_id = p.id AND o.created_at >= %s "
                    "WHERE p.tenant_id = %s AND p.is_active GROUP BY p.id, a.type ORDER BY p.interval_days, 2",
                    (year_start, tenant_id),
                )
                plans = cur.fetchall()
                cur.execute(
                    "SELECT template_id, count(*), max(performed_at) FROM checklist_run "
                    "WHERE tenant_id = %s AND performed_at >= %s GROUP BY template_id",
                    (tenant_id, year_start),
                )
                runs = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
                cur.execute("SELECT template_id, max(performed_at) FROM checklist_run WHERE tenant_id = %s GROUP BY template_id",
                            (tenant_id,))
                last_run = {r[0]: r[1] for r in cur.fetchall()}
                cur.execute("SELECT pack_id, adopted_at FROM tenant_pack WHERE tenant_id = %s", (tenant_id,))
                adopted = {r[0]: r[1] for r in cur.fetchall()}
                cur.execute(
                    "SELECT p.id, p.name, p.frequency_days, count(s.id), p.created_at, "
                    "(SELECT max(s2.sampled_at) FROM lab_sample s2 WHERE s2.plan_item_id = p.id) "
                    "FROM lab_plan_item p LEFT JOIN lab_sample s ON s.plan_item_id = p.id AND s.sampled_at >= %s "
                    "WHERE p.tenant_id = %s AND p.active GROUP BY p.id, p.created_at ORDER BY p.name",
                    (year_start, tenant_id),
                )
                lab = cur.fetchall()

    for pid, title, interval, responsible, next_due, events, generated, done, ev_total, ev_done in plans:
        # Periodos ya vencidos que no generaron orden (el generador no corrio).
        missed = math.floor((now - next_due).total_seconds() / 86400 / interval) + 1 if next_due <= now else 0
        expected = generated + missed
        items.append({
            "kind": "maintenance", "ref": str(pid), "activity": title, "frequency_days": interval,
            "responsible": responsible, "trigger_events": list(events or []),
            "expected": expected, "done": done, "compliance_pct": compliance_pct(done, expected),
            "not_generated": missed, "extraordinary": ev_total, "extraordinary_done": ev_done,
            "next_due_at": next_due.isoformat(), "overdue": next_due <= now,
        })
    for t in list_checklist_templates(conn, tenant_id):
        if not t["frequency_days"]:
            continue
        count, _ = runs.get(t["id"], (0, None))
        expected = periods_elapsed(days_since(adopted.get(t["pack_id"])), t["frequency_days"])
        st = checklist_status(t["frequency_days"], last_run.get(t["id"]), now)
        items.append({
            "kind": "checklist", "ref": t["id"], "activity": t["title"], "frequency_days": t["frequency_days"],
            "responsible": None, "trigger_events": [],
            "expected": expected, "done": count, "compliance_pct": compliance_pct(count, expected),
            "not_generated": 0, "extraordinary": 0, "extraordinary_done": 0,
            "next_due_at": st["next_due_at"].isoformat() if st["next_due_at"] else None,
            "overdue": st["status"] in ("overdue", "never"),
        })
    for pid, name, freq, count, created_at, last_any in lab:
        expected = periods_elapsed(days_since(created_at), freq)
        st = checklist_status(freq, last_any, now)
        items.append({
            "kind": "lab", "ref": str(pid), "activity": f"Análisis de laboratorio: {name}", "frequency_days": freq,
            "responsible": None, "trigger_events": [],
            "expected": expected, "done": count, "compliance_pct": compliance_pct(count, expected),
            "not_generated": 0, "extraordinary": 0, "extraordinary_done": 0,
            "next_due_at": st["next_due_at"].isoformat() if st["next_due_at"] else None,
            "overdue": st["status"] in ("overdue", "never"),
        })
    expected_total = sum(i["expected"] for i in items)
    done_total = sum(min(i["done"], i["expected"]) for i in items)
    return {
        "year": year_start.year, "as_of": now.isoformat(), "items": items,
        "summary": {"activities": len(items), "expected": expected_total, "done": done_total,
                    "compliance_pct": compliance_pct(done_total, expected_total),
                    "overdue": sum(1 for i in items if i["overdue"])},
    }
