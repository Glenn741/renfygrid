"""Informe de cumplimiento al ente rector (Track D, D12.3, migracion 0044).

La junta elige el periodo y genera el informe: queda una foto inmutable de
lo que el sistema tenia en ese momento (`compliance_report.content`). Luego
decide enviarlo y registra a quien y cuando. El ente rector no entra al
sistema. Las secciones y su orden son catalogo del paquete regulatorio; cada
una usa un detector del motor (abajo).
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from calendar_service import annual_calendar  # noqa: E402
from pack_engine import InvalidRecordError, field_reading_summary, sampling_plan_compliance  # noqa: E402
from pack_service import active_pack_ids  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from sanitation_service import sanitation_overview  # noqa: E402


class ReportNotFoundError(LookupError):
    """Informe o plantilla inexistente para esta junta."""


class ReportConflictError(RuntimeError):
    """El informe ya fue registrado como enviado."""


def _num(v: Any) -> float | None:
    return float(v) if v is not None else None


def templates(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    packs = active_pack_ids(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute("SELECT pack_id, code, title, purpose, recipient, format_note FROM report_template WHERE pack_id = ANY(%s) "
                    "ORDER BY pack_id, code", (packs,))
        tpls = [{"pack_id": r[0], "code": r[1], "title": r[2], "purpose": r[3], "recipient": r[4], "format_note": r[5]}
                for r in cur.fetchall()]
        cur.execute("SELECT pack_id, report_code, code, title, description, detector, params FROM report_section "
                    "WHERE pack_id = ANY(%s) ORDER BY sort_order", (packs,))
        sections = cur.fetchall()
    for t in tpls:
        t["sections"] = [{"code": s[2], "title": s[3], "description": s[4], "detector": s[5], "params": s[6]}
                         for s in sections if (s[0], s[1]) == (t["pack_id"], t["code"])]
    return tpls


# ── Detectores ────────────────────────────────────────────────────────

def _lab_quality(cur: psycopg.Cursor, tid: str, start: datetime, end: datetime, **_: Any) -> dict:
    cur.execute(
        "SELECT s.id, s.sampled_at, s.laboratory, s.report_ref, s.reason, sp.name, p.label, p.unit, r.qualifier, r.value, "
        "r.result_label, r.severity, pr.citation FROM lab_sample s JOIN lab_result r ON r.sample_id = s.id "
        "JOIN parameter p ON p.code = r.parameter_code LEFT JOIN sampling_point sp ON sp.id = s.sampling_point_id "
        "LEFT JOIN parameter_rule pr ON pr.id = r.rule_id "
        "WHERE s.tenant_id = %s AND s.sampled_at >= %s AND s.sampled_at < %s ORDER BY s.sampled_at, p.label",
        (tid, start, end))
    samples: dict[str, dict] = {}
    for sid, at, lab, ref, reason, point, plabel, unit, q, v, rlabel, sev, cit in cur.fetchall():
        s = samples.setdefault(str(sid), {"sampled_at": at.isoformat(), "laboratory": lab, "report_ref": ref, "reason": reason,
                                          "point": point, "results": []})
        s["results"].append({"parameter": plabel, "unit": unit, "qualifier": q, "value": float(v), "interpretation": rlabel,
                             "severity": sev, "rule_source": cit})
    results = [r for s in samples.values() for r in s["results"]]
    return {"samples": list(samples.values()),
            "summary": {"samples": len(samples), "results": len(results),
                        "out_of_range": sum(1 for r in results if r["severity"] in ("alert", "critical")),
                        "critical": sum(1 for r in results if r["severity"] == "critical"),
                        "without_rule": sum(1 for r in results if r["severity"] is None)}}


def _field_readings(cur: psycopg.Cursor, tid: str, start: datetime, end: datetime, params: dict, **_: Any) -> dict:
    code = params.get("parameter_code")
    cur.execute("SELECT label, unit FROM parameter WHERE code = %s", (code,))
    p = cur.fetchone()
    if p is None:
        return {"parameter": None, "by_point_kind": [], "total": 0}
    cur.execute(
        "SELECT coalesce(k.code, 'none'), coalesce(k.label, 'Sin punto'), r.value, r.severity FROM field_reading r "
        "LEFT JOIN sampling_point sp ON sp.id = r.sampling_point_id LEFT JOIN sampling_point_kind k ON k.code = sp.kind_code "
        "WHERE r.tenant_id = %s AND r.parameter_code = %s AND r.measured_at >= %s AND r.measured_at < %s "
        "ORDER BY k.sort_order NULLS LAST, r.measured_at", (tid, code, start, end))
    rows = [{"kind": r[0], "kind_label": r[1], "value": float(r[2]), "severity": r[3]} for r in cur.fetchall()]
    return {"parameter": {"code": code, "label": p[0], "unit": p[1]}, "by_point_kind": field_reading_summary(rows), "total": len(rows)}


def _sampling_plan(cur: psycopg.Cursor, tid: str, start: datetime, end: datetime, **_: Any) -> dict:
    cur.execute("SELECT id, name, parameters, frequency_days, source_note, created_at FROM lab_plan_item "
                "WHERE tenant_id = %s AND active AND created_at < %s ORDER BY name", (tid, end))
    items = []
    for iid, name, params, freq, note, created in cur.fetchall():
        eff = max(start, created)
        items.append({"item_id": str(iid), "name": name, "parameters": list(params), "frequency_days": freq, "source_note": note,
                      "days": max((end - eff).total_seconds() / 86400, 0)})
    cur.execute("SELECT plan_item_id, count(*) FROM lab_sample WHERE tenant_id = %s AND plan_item_id IS NOT NULL "
                "AND sampled_at >= %s AND sampled_at < %s GROUP BY 1", (tid, start, end))
    taken = {str(r[0]): r[1] for r in cur.fetchall()}
    out = sampling_plan_compliance(items, taken, (end - start).days)
    for it in out["items"]:
        it.pop("days", None)
    return out


def _alerts(cur: psycopg.Cursor, tid: str, start: datetime, end: datetime, **_: Any) -> dict:
    # Por la fecha de la medicion o del analisis (no la del hallazgo): un
    # resultado de septiembre cargado en octubre es de septiembre.
    cur.execute(
        "SELECT count(*), count(*) FILTER (WHERE f.status = 'closed') FROM ("
        " SELECT r.finding_id FROM field_reading r WHERE r.tenant_id = %s AND r.severity IN ('alert', 'critical') "
        "   AND r.measured_at >= %s AND r.measured_at < %s "
        " UNION ALL SELECT l.finding_id FROM lab_result l JOIN lab_sample s ON s.id = l.sample_id WHERE l.tenant_id = %s "
        "   AND l.severity IN ('alert', 'critical') AND s.sampled_at >= %s AND s.sampled_at < %s"
        ") x LEFT JOIN finding f ON f.id = x.finding_id", (tid, start, end, tid, start, end))
    n, closed = cur.fetchone()
    cur.execute("SELECT label, trigger, activated_at, closed_at, status FROM emergency_activation "
                "WHERE tenant_id = %s AND activated_at >= %s AND activated_at < %s ORDER BY activated_at", (tid, start, end))
    acts = [{"label": r[0], "trigger": r[1], "activated_at": r[2].isoformat(), "closed_at": r[3].isoformat() if r[3] else None,
             "status": r[4]} for r in cur.fetchall()]
    return {"out_of_range_alerts": n, "alerts_closed": closed, "emergencies": acts}


def _detect(conn: psycopg.Connection, tid: str, section: dict, start: datetime, end: datetime, tz: ZoneInfo) -> dict:
    det = section["detector"]
    if det == "maintenance_calendar":
        now = min(end, datetime.now(tz))
        return annual_calendar(conn, tid, datetime(now.year, 1, 1, tzinfo=tz), now)["summary"]
    if det == "sanitation":
        s = sanitation_overview(conn, tid, (end - timedelta(seconds=1)).date())
        in_period = [e for e in s["register_7f"] if e["closed_at"] and start <= datetime.fromisoformat(e["closed_at"]) < end]
        return {"interventions": len(in_period),
                "sludge_m3": round(sum(e["sludge_volume_m3"] or 0 for e in in_period), 2),
                "destination_verified": sum(1 for e in in_period if e["verified_by"]),
                "pending_verification": sum(1 for e in in_period if e["needs_verification"]),
                "sludge_overdue": [c["type_label"] + (f" ({c['name']})" if c["name"] else "") for c in s["components"]
                                   if c["sludge"] and c["sludge"]["status"] in ("never", "overdue")],
                # Estado actual de las descargas registradas antes del cierre del periodo.
                "open_discharges": [f"{d['name']} ({d['activity_label']})" for d in s["discharges"]
                                    if d["status"] in ("identified", "agreement") and datetime.fromisoformat(d["created_at"]) < end]}
    fn = {"lab_quality": _lab_quality, "field_readings": _field_readings, "sampling_plan": _sampling_plan,
          "alerts_emergencies": _alerts}[det]
    with conn.transaction():
        with tenant_scope(conn, tid):
            with conn.cursor() as cur:
                return fn(cur, tid, start, end, params=section["params"])


# ── Informes ──────────────────────────────────────────────────────────

def _report_row(r: tuple, with_content: bool) -> dict:
    out = {"report_id": str(r[0]), "pack_id": r[1], "report_code": r[2], "period_from": r[3].isoformat(), "period_to": r[4].isoformat(),
           "generated_by": r[5], "generated_at": r[6].isoformat(), "sent_to": r[7], "sent_on": r[8].isoformat() if r[8] else None,
           "sent_by": r[9], "sent_note": r[10], "title": r[11]["template"]["title"]}
    if with_content:
        out["content"] = r[11]
    return out


_SELECT = ("SELECT id, pack_id, report_code, period_from, period_to, generated_by, generated_at, sent_to, sent_on, sent_by, "
           "sent_note, content FROM compliance_report ")


def list_reports(conn: psycopg.Connection, tenant_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_SELECT + "WHERE tenant_id = %s ORDER BY generated_at DESC", (tenant_id,))
                rows = [_report_row(r, False) for r in cur.fetchall()]
    return {"templates": templates(conn, tenant_id), "reports": rows}


def get_report(conn: psycopg.Connection, tenant_id: str, report_id: str) -> dict:
    try:
        uuid.UUID(str(report_id))
    except ValueError:
        raise ReportNotFoundError(f"No existe el informe {report_id!r}") from None
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(_SELECT + "WHERE id = %s AND tenant_id = %s", (report_id, tenant_id))
                r = cur.fetchone()
    if r is None:
        raise ReportNotFoundError(f"No existe el informe {report_id}")
    return _report_row(r, True)


def generate_report(conn: psycopg.Connection, tenant_id: str, actor: str, report_code: str, period_from: date,
                    period_to: date, pack_id: str | None = None) -> dict:
    tpl = next((t for t in templates(conn, tenant_id) if t["code"] == report_code and (pack_id is None or t["pack_id"] == pack_id)), None)
    if tpl is None:
        raise ReportNotFoundError(f"No hay un informe {report_code!r} en los paquetes adoptados")
    with conn.cursor() as cur:
        cur.execute("SELECT name, config->>'timezone' FROM tenant WHERE id = %s", (tenant_id,))
        name, tz_name = cur.fetchone()
    if not tz_name:
        raise InvalidRecordError("La organización no tiene zona horaria configurada (Configuración → Zona horaria)")
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    if period_from > period_to:
        raise InvalidRecordError("El periodo empieza después de terminar")
    if period_to > today:
        raise InvalidRecordError("El periodo no puede terminar en el futuro")
    start = datetime.combine(period_from, datetime.min.time(), tzinfo=tz)
    end = datetime.combine(period_to + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    content = {
        "template": {k: tpl[k] for k in ("pack_id", "code", "title", "purpose", "recipient", "format_note")},
        "organization": name, "timezone": tz_name,
        "period": {"from": period_from.isoformat(), "to": period_to.isoformat()},
        "generated_at": datetime.now(tz).isoformat(), "generated_by": actor,
        "sections": [{"code": s["code"], "title": s["title"], "description": s["description"], "detector": s["detector"],
                      "data": _detect(conn, tenant_id, s, start, end, tz)} for s in tpl["sections"]],
    }
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("INSERT INTO compliance_report (tenant_id, pack_id, report_code, period_from, period_to, content, generated_by) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
                            (tenant_id, tpl["pack_id"], tpl["code"], period_from, period_to, Json(content), actor))
                rid = cur.fetchone()[0]
    return get_report(conn, tenant_id, str(rid))


def mark_sent(conn: psycopg.Connection, tenant_id: str, report_id: str, actor: str, sent_to: str, sent_on: date,
              note: str | None = None) -> dict:
    sent_to = (sent_to or "").strip()
    if not sent_to:
        raise InvalidRecordError("Indique a quién se envió")
    current = get_report(conn, tenant_id, report_id)
    if current["sent_on"]:
        raise ReportConflictError("El informe ya fue registrado como enviado")
    if sent_on < date.fromisoformat(current["generated_at"][:10]):
        raise InvalidRecordError("No se puede enviar antes de generarlo")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("UPDATE compliance_report SET sent_to = %s, sent_on = %s, sent_by = %s, sent_note = %s "
                            "WHERE id = %s AND tenant_id = %s", (sent_to, sent_on, actor, (note or "").strip() or None, report_id, tenant_id))
    return get_report(conn, tenant_id, report_id)
