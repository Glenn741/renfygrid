"""Logica pura del motor de paquetes (Track D, Sprint D0.1, sin BD ni I/O).
Ver docs/04-plan-sprints.md SS11.3-SS11.4.

El motor no sabe de ningun pais ni programa: evalua reglas, escalas e
items que vienen de los catalogos globales (`parameter_rule`,
`checklist_template`, `component_type`). Todo umbral, etiqueta o prioridad
sale de esos datos -- si una funcion de aca necesitara saber que es "7A" o
que el cloro en Ecuador es 0,3-1,5 mg/L, estaria mal ubicada.

La capa de servicio (`pack_service.py`) arma los datos desde filas reales
y llama aca, igual que `order_service.py` con `maintenance_engine.py`.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

INSTRUMENTATION_MODULES = ("metering", "water_balance", "quality", "maintenance", "network", "billing")
INSTRUMENTATION_LEVELS = ("basic", "intermediate", "advanced")


class InvalidRuleError(ValueError):
    """Bandas de una regla mal formadas (vacias, sin tramo final abierto o
    con limites que no crecen)."""


class InvalidAnswersError(ValueError):
    """Respuestas que no calzan con la plantilla: item desconocido o
    repetido, codigo fuera de la escala, o items sin responder."""


class InvalidInstrumentationError(ValueError):
    """Modulo o nivel de instrumentacion fuera de los definidos."""


# ── Reglas de parametros ───────────────────────────────────────────────

def validate_bands(bands: list[dict]) -> None:
    """Una regla valida: al menos un tramo, el ultimo sin limite (`upper`
    None, para que todo valor caiga en algun tramo) y limites crecientes."""
    if not bands:
        raise InvalidRuleError("La regla no tiene tramos")
    if bands[-1].get("upper") is not None:
        raise InvalidRuleError("El ultimo tramo debe quedar abierto (upper = null)")
    previous = None
    for band in bands[:-1]:
        upper = band.get("upper")
        if upper is None:
            raise InvalidRuleError("Solo el ultimo tramo puede quedar abierto")
        if previous is not None and upper < previous:
            raise InvalidRuleError("Los limites de los tramos deben crecer")
        previous = upper
    for band in bands:
        if not band.get("code") or not band.get("label") or not band.get("severity"):
            raise InvalidRuleError("Cada tramo necesita code, label y severity")


def matching_band(bands: list[dict], value: float) -> dict[str, Any]:
    """El primer tramo cuyo limite cubre el valor. Con `upper_inclusive`
    falso el limite se excluye (cloro 0,29 -> bajo; 0,3 -> adecuado)."""
    validate_bands(bands)
    for band in bands:
        upper = band.get("upper")
        if upper is None:
            return band
        if band.get("upper_inclusive", True):
            if value <= upper:
                return band
        elif value < upper:
            return band
    raise InvalidRuleError("Ningun tramo cubre el valor")  # inalcanzable si validate_bands paso


def evaluate_bands(bands: list[dict], value: float) -> dict[str, Any]:
    return _band_result(matching_band(bands, value))


def interpret_reading(bands: list[dict], value: float) -> dict[str, Any]:
    """Interpretacion completa de una medicion (7B): resultado, que hacer y
    con que prioridad se abre un hallazgo si esta fuera de rango. Todo sale
    del tramo del paquete; un tramo fuera de rango sin `finding_priority` es
    una regla incompleta, no un valor a inventar."""
    band = matching_band(bands, value)
    out_of_range = band["severity"] != "ok"
    if out_of_range and not band.get("finding_priority"):
        raise InvalidRuleError(f"El tramo {band['code']!r} esta fuera de rango y no define finding_priority")
    return {
        **_band_result(band),
        "action": band.get("action"),
        "out_of_range": out_of_range,
        "finding_priority": band.get("finding_priority") if out_of_range else None,
    }


def _band_result(band: dict) -> dict[str, Any]:
    return {"code": band["code"], "label": band["label"], "severity": band["severity"]}


# ── Listas de verificacion ─────────────────────────────────────────────

def item_scale(template: dict, item: dict) -> list[dict]:
    """Escala de un item: la propia si la trae (`options`, p. ej. las
    preguntas de opcion multiple de la CAP, cada opcion con su puntaje de la
    clave) o la comun de la lista."""
    return item.get("options") or template["scale"]


def answer_label(template: dict, item: dict, code: str) -> str:
    return {e["code"]: e["label"] for e in item_scale(template, item)}[code]


def validate_answers(template: dict, answers: list[dict]) -> None:
    """Toda aplicacion de una lista es completa: cada item respondido una
    sola vez con un codigo de su escala. Una inspeccion a medias no deja
    ver que quedo sin revisar."""
    items = {item["key"]: item for item in template["items"]}
    seen: set[str] = set()
    for answer in answers:
        key = answer.get("item_key")
        if key not in items:
            raise InvalidAnswersError(f"Item desconocido para {template['id']}: {key!r}")
        if key in seen:
            raise InvalidAnswersError(f"Item respondido dos veces: {key!r}")
        codes = {entry["code"] for entry in item_scale(template, items[key])}
        if answer.get("answer_code") not in codes:
            raise InvalidAnswersError(
                f"Respuesta {answer.get('answer_code')!r} fuera de la escala de {key!r} (validas: {sorted(codes)})"
            )
        seen.add(key)
    missing = [key for key in items if key not in seen]
    if missing:
        raise InvalidAnswersError(f"Faltan items por responder: {missing}")


def validate_run_context(template: dict, context: dict | None) -> dict:
    """Datos de la aplicacion que define la plantilla (`run_fields`): p. ej.
    momento inicial/final y codigo de participante de la CAP. Devuelve solo
    los campos declarados, sin espacios sobrantes; un campo con `options`
    acepta solo esos codigos."""
    context = context or {}
    fields = {f["key"]: f for f in template.get("run_fields") or []}
    unknown = sorted(set(context) - set(fields))
    if unknown:
        raise InvalidAnswersError(f"Datos de la aplicacion no definidos para {template['id']}: {unknown}")
    clean: dict[str, str] = {}
    for key, field in fields.items():
        value = context.get(key)
        value = value.strip() if isinstance(value, str) else value
        if value in (None, ""):
            if field.get("required"):
                raise InvalidAnswersError(f"Falta {field['label']!r}")
            continue
        options = field.get("options")
        if options and value not in {o["code"] for o in options}:
            raise InvalidAnswersError(f"{field['label']}: {value!r} no es una opcion valida")
        clean[key] = value
    return clean


def findings_from_answers(template: dict, answers: list[dict]) -> list[dict[str, Any]]:
    """Un hallazgo por cada respuesta cuya entrada de la escala tiene
    `finding` verdadero. La prioridad sale de la escala del paquete. La
    descripcion junta el texto del item, la respuesta y la observacion."""
    items = {item["key"]: item for item in template["items"]}
    findings = []
    for answer in answers:
        item = items[answer["item_key"]]
        entry = {e["code"]: e for e in item_scale(template, item)}[answer["answer_code"]]
        if not entry.get("finding"):
            continue
        if not entry.get("finding_priority"):
            raise InvalidAnswersError(
                f"La escala de {template['id']} marca {entry['code']!r} como hallazgo sin finding_priority"
            )
        description = f"{item['text']} — {entry['label']}"
        if answer.get("observation"):
            description += f". {answer['observation']}"
        findings.append({
            "item_key": answer["item_key"],
            "description": description,
            "priority": entry["finding_priority"],
            "action": answer.get("action"),
            "responsible": answer.get("responsible"),
            "due_date": answer.get("due_date"),
        })
    return findings


def _item_points(template: dict, items: list[dict], answers: list[dict]) -> tuple[int, int]:
    """Puntos obtenidos y maximo posible sobre `items` (cada item con el
    mejor puntaje de su propia escala)."""
    by_key = {a["item_key"]: a["answer_code"] for a in answers}
    total = maximum = 0
    for item in items:
        scale = {e["code"]: e.get("score", 0) for e in item_scale(template, item)}
        maximum += max(scale.values(), default=0)
        if item["key"] in by_key:
            total += scale.get(by_key[item["key"]], 0)
    return total, maximum


def maturity_score(template: dict, answers: list[dict]) -> dict[str, Any]:
    """Puntaje sobre el maximo posible. Sirve para la verificacion inicial y
    final, 4A/4B (indice de madurez) y la CAP (clave de T-05).
    `answers`: [{item_key, answer_code}]."""
    total, maximum = _item_points(template, template["items"], answers)
    pct = round(100.0 * total / maximum, 1) if maximum else None
    return {"score": total, "max_score": maximum, "pct": pct}


def _level(levels: list[dict], pct: float | None) -> str | None:
    if pct is None:
        return None
    for band in sorted(levels, key=lambda b: b["min_pct"], reverse=True):
        if pct >= band["min_pct"]:
            return band["label"]
    return None


def questionnaire_analysis(template: dict, runs: list[dict]) -> dict[str, Any]:
    """Matriz de analisis de un cuestionario (p. ej. T-05 de la CAP): por
    cada agrupacion que declara la plantilla (guia, dimension) y por cada
    momento a comparar (inicial, final), el puntaje promedio, el porcentaje,
    el nivel segun los rangos del paquete y la diferencia entre el primer y
    el ultimo momento. `runs`: [{context, answers: [{item_key, answer_code}]}].
    Todo nombre de grupo, momento y rango sale de `template["analysis"]`."""
    spec = template.get("analysis")
    if not spec:
        raise InvalidAnswersError(f"{template['id']} no define analisis")
    compare_by = spec["compare_by"]
    moments = [m["code"] for m in spec["compare"]]
    levels = spec.get("levels") or []
    by_moment = {m: [r for r in runs if (r.get("context") or {}).get(compare_by) == m] for m in moments}

    def cell(items: list[dict], moment: str) -> dict[str, Any]:
        maximum = _item_points(template, items, [])[1]
        points = [_item_points(template, items, r["answers"])[0] for r in by_moment[moment]]
        if not points:
            return {"n": 0, "avg_score": None, "max_score": maximum, "pct": None, "level": None}
        avg = sum(points) / len(points)
        pct = round(100.0 * avg / maximum, 1) if maximum else None
        return {"n": len(points), "avg_score": round(avg, 2), "max_score": maximum, "pct": pct, "level": _level(levels, pct)}

    def row(code: str, label: str, items: list[dict]) -> dict[str, Any]:
        cells = {m: cell(items, m) for m in moments}
        first, last = cells[moments[0]]["pct"], cells[moments[-1]]["pct"]
        return {
            "code": code, "label": label, "items": [i["key"] for i in items], "moments": cells,
            "difference_pct": round(last - first, 1) if first is not None and last is not None else None,
        }

    groupings = []
    for g in spec.get("group_by") or []:
        # `values` es una LISTA [{code, label}]: el orden es el de la guia (un
        # objeto jsonb no conserva el orden de sus claves).
        rows = [
            row(v["code"], v["label"], [i for i in template["items"] if (i.get("groups") or {}).get(g["key"]) == v["code"]])
            for v in g["values"]
        ]
        groupings.append({"key": g["key"], "label": g["label"], "rows": rows})
    return {
        "template_id": template["id"], "compare_by": compare_by, "moments": spec["compare"], "levels": levels,
        "groupings": groupings, "total": row("total", "Total", template["items"]),
        "participants": {m: len(by_moment[m]) for m in moments},
    }


# ── Recorrido del sistema y tren de tratamiento ────────────────────────

def system_route(component_types: list[dict], assets: list[dict]) -> dict[str, Any]:
    """Componentes registrados ordenados por su lugar en el recorrido, por
    servicio. Los tipos sin `stage_order` (tuberia, valvula...) van como
    accesorios. Solo aparecen tramos con algo registrado."""
    types = {t["code"]: t for t in component_types}
    by_type: dict[str, list[dict]] = {}
    for asset in assets:
        by_type.setdefault(asset["type"], []).append(asset)

    services: dict[str, list[dict]] = {}
    accessories: list[dict] = []
    for code, group in by_type.items():
        ctype = types.get(code)
        if ctype is None:
            continue
        entry = {"type": code, "label": ctype["label"], "stage_order": ctype["stage_order"], "assets": group}
        if ctype["stage_order"] is None:
            accessories.append(entry)
        else:
            services.setdefault(ctype["service"], []).append(entry)
    for stages in services.values():
        stages.sort(key=lambda s: s["stage_order"])
    accessories.sort(key=lambda s: s["label"])
    return {"services": services, "accessories": accessories}


def treatment_train(component_types: list[dict], assets: list[dict], open_findings: list[dict]) -> list[dict[str, Any]]:
    """Una fila por cada etapa de tratamiento del catalogo, exista o no
    (que una etapa falte es informacion, igual que en la actividad de la
    guia). `works`: todos los componentes de la etapa operativos; `None`
    si la etapa no existe."""
    stages = sorted(
        (t for t in component_types if t["is_treatment_stage"]),
        key=lambda t: t["stage_order"] if t["stage_order"] is not None else 10**6,
    )
    rows = []
    for stage in stages:
        stage_assets = [a for a in assets if a["type"] == stage["code"]]
        asset_ids = {a["asset_id"] for a in stage_assets}
        stage_findings = [f for f in open_findings if f.get("asset_id") in asset_ids]
        exists = bool(stage_assets)
        rows.append({
            "type": stage["code"],
            "label": stage["label"],
            "exists": exists,
            "works": all(a["status"] == "operational" for a in stage_assets) if exists else None,
            "asset_count": len(stage_assets),
            "open_findings": [
                {"finding_id": f["finding_id"], "description": f["description"], "priority": f["priority"]}
                for f in stage_findings
            ],
        })
    return rows


# ── Ruta del programa (0023) ───────────────────────────────────────────

def checklist_status(frequency_days: int | None, last_run_at: datetime | None, now: datetime) -> dict[str, Any]:
    """Estado de una lista en la ruta. La frecuencia sale del catalogo del
    paquete; sin frecuencia, la lista se aplica cuando corresponde y basta
    con saber si ya se aplico.
      never    -- nunca se aplico
      done     -- aplicada, sin frecuencia definida
      ok       -- aplicada y todavia dentro de su frecuencia
      overdue  -- ya paso su proxima fecha
    """
    if last_run_at is None:
        return {"status": "never", "next_due_at": None, "days_to_due": None}
    if frequency_days is None:
        return {"status": "done", "next_due_at": None, "days_to_due": None}
    next_due = last_run_at + timedelta(days=frequency_days)
    days = (next_due - now).total_seconds() / 86400
    # Negativo = dias de atraso (medio dia vencida cuenta como 1 dia de atraso).
    return {"status": "overdue" if days < 0 else "ok", "next_due_at": next_due, "days_to_due": math.floor(days)}


def stage_summary(lists: list[dict]) -> dict[str, int]:
    """Conteo por estado de las listas de una etapa (para el paso de la ruta)."""
    counts = {"total": len(lists), "never": 0, "done": 0, "ok": 0, "overdue": 0}
    for item in lists:
        counts[item["status"]] += 1
    counts["applied"] = counts["done"] + counts["ok"] + counts["overdue"]
    return counts


# ── Pasaporte de productos y seguimiento (0028) ────────────────────────

PRODUCT_STATUSES = ("complete", "to_validate", "pending")
FOLLOW_UP_ITEM_STATUSES = ("pending", "done", "not_done")


class InvalidRecordError(ValueError):
    """Estado de producto o de compromiso fuera de los definidos, o fecha
    de cierre que no calza."""


def validate_product_status(status: str) -> None:
    if status not in PRODUCT_STATUSES:
        raise InvalidRecordError(f"Estado de producto invalido: {status!r} (validos: {list(PRODUCT_STATUSES)})")


def validate_follow_up_item_status(status: str) -> None:
    if status not in FOLLOW_UP_ITEM_STATUSES:
        raise InvalidRecordError(f"Estado de compromiso invalido: {status!r} (validos: {list(FOLLOW_UP_ITEM_STATUSES)})")


def passport_rows(products: list[dict], records: dict[tuple[str, str], dict]) -> list[dict[str, Any]]:
    """Una fila por producto del catalogo (T-07), en el orden de la ruta. Un
    producto sin registro cuenta como pendiente: que falte es informacion.
    `records`: {(pack_id, product_code): {status, evidence, to_improvement_plan, updated_at, updated_by}}."""
    rows = []
    for p in products:
        rec = records.get((p["pack_id"], p["code"]))
        rows.append({
            "pack_id": p["pack_id"], "code": p["code"], "stage_code": p["stage_code"], "title": p["title"],
            "registered": rec is not None,
            "status": rec["status"] if rec else "pending",
            "evidence": rec.get("evidence") if rec else None,
            "to_improvement_plan": bool(rec and rec.get("to_improvement_plan")),
            "updated_at": rec.get("updated_at") if rec else None,
            "updated_by": rec.get("updated_by") if rec else None,
        })
    return rows


def passport_summary(rows: list[dict]) -> dict[str, int]:
    counts = {"total": len(rows), "to_improvement_plan": sum(1 for r in rows if r["to_improvement_plan"])}
    for status in PRODUCT_STATUSES:
        counts[status] = sum(1 for r in rows if r["status"] == status)
    return counts


def follow_up_schedule(
    milestones: list[dict], anchor: date, reviews: dict[str, dict], items: list[dict], today: date,
) -> list[dict[str, Any]]:
    """Momentos del seguimiento de un ciclo con su fecha (cierre + dias del
    catalogo) y su estado:
      reviewed -- ya se registro la revision del momento
      due      -- llego la fecha y falta revisarlo
      upcoming -- todavia no llega la fecha
    Cada momento trae sus compromisos y cuantos siguen pendientes."""
    result = []
    for m in sorted(milestones, key=lambda m: m["sort_order"]):
        due = anchor + timedelta(days=m["offset_days"])
        review = reviews.get(m["code"])
        status = "reviewed" if review else ("due" if today >= due else "upcoming")
        own = [i for i in items if i["milestone_code"] == m["code"]]
        result.append({
            "code": m["code"], "label": m["label"], "offset_days": m["offset_days"],
            "review_guide": m["review"], "evidence_guide": m["evidence"],
            "due_date": due.isoformat(), "days_to_due": (due - today).days, "status": status,
            "review": review, "items": own,
            "pending_items": sum(1 for i in own if i["status"] == "pending"),
        })
    return result


# ── Operacion diaria: 7B y 7C (0030) ───────────────────────────────────

APPEARANCES = ("clear", "turbid", "colored")
LOG_STATUSES = ("good", "alert")


def log_entry_status(operator_status: str | None, reading_severity: str | None, appearance: str | None) -> str:
    """Estado de una toma de la bitacora 7C (Bueno / Alerta). El operador
    puede marcar alerta por cualquier novedad; nunca puede quedar "Bueno"
    si el cloro esta fuera de rango o el agua se ve turbia o con color."""
    if operator_status is not None and operator_status not in LOG_STATUSES:
        raise InvalidRecordError(f"Estado invalido: {operator_status!r} (validos: {list(LOG_STATUSES)})")
    if appearance is not None and appearance not in APPEARANCES:
        raise InvalidRecordError(f"Aspecto invalido: {appearance!r} (validos: {list(APPEARANCES)})")
    if reading_severity in ("alert", "critical") or appearance in ("turbid", "colored"):
        return "alert"
    return operator_status or "good"


def sampling_points_status(points: list[dict], last_reading_on: dict[str, date], today: date) -> list[dict[str, Any]]:
    """Que puntos toca medir hoy. Frecuencia: la del punto o, si no tiene,
    la de su tipo (catalogo). Sin frecuencia, el punto rota cuando la junta
    lo decide y solo se informa su ultima medicion.
      never -- nunca se midio
      due   -- ya paso su frecuencia
      ok    -- medido dentro de su frecuencia (o sin frecuencia definida)"""
    rows = []
    for p in points:
        freq = p.get("frequency_days") or p.get("kind_frequency_days")
        last = last_reading_on.get(p["point_id"])
        if last is None:
            status = "never"
        elif freq and (today - last).days >= freq:
            status = "due"
        else:
            status = "ok"
        rows.append({**p, "effective_frequency_days": freq, "last_reading_on": last.isoformat() if last else None,
                     "days_since": (today - last).days if last else None, "status": status})
    return rows


# ── Saneamiento (D6, 0039) ─────────────────────────────────────────────

def bod_cod_ratio(bod: float | None, cod: float | None) -> float | None:
    """Relacion DBO/DQO de una muestra. Solo el dato: la guia pide que la
    interprete personal tecnico; aqui no se clasifica."""
    if bod is None or cod is None or cod <= 0:
        return None
    return round(bod / cod, 2)


def sludge_status(last_extraction: date | None, max_days: int | None, today: date) -> dict[str, Any]:
    """Estado del retiro de lodos de una fosa o planta frente al plazo del
    paquete (al menos una vez al ano)."""
    if max_days is None:
        return {"status": None, "days_since": None, "due_on": None}
    if last_extraction is None:
        return {"status": "never", "days_since": None, "due_on": None}
    due = last_extraction + timedelta(days=max_days)
    return {"status": "overdue" if today > due else "ok", "days_since": (today - last_extraction).days, "due_on": due.isoformat()}


# ── Bodega (D4, 0038) ──────────────────────────────────────────────────

# Unidades de bodega y su equivalencia en la unidad base de masa (g) o
# volumen (ml); las demas no se convierten.
UNIT_BASE = {"g": ("g", 1.0), "kg": ("g", 1000.0), "ml": ("ml", 1.0), "l": ("ml", 1000.0)}


def to_base_unit(quantity: float, unit: str) -> tuple[str, float] | None:
    """Cantidad en g o ml; None si la unidad no es de masa ni volumen."""
    if unit not in UNIT_BASE:
        return None
    base, factor = UNIT_BASE[unit]
    return base, quantity * factor


def stock_level(movements: list[dict]) -> float:
    """Existencia: entradas - salidas + ajustes (con signo)."""
    total = 0.0
    for m in movements:
        q = float(m["quantity"])
        total += q if m["kind"] in ("in", "adjust") else -q
    return round(total, 3)


def chlorine_reconciliation(applied: float, applied_unit: str, issued: float, issued_unit: str) -> dict[str, Any]:
    """Cruce del cloro aplicado (bitacora 7C) con lo que salio de bodega en el
    mismo periodo. Diferencia positiva: salio mas de lo que se registro como
    aplicado (producto sin registrar o perdido); negativa: se registro mas de
    lo que salio (falta registrar salidas). Unidades incompatibles -> None."""
    a, i = to_base_unit(applied, applied_unit), to_base_unit(issued, issued_unit)
    if a is None or i is None or a[0] != i[0]:
        return {"comparable": False, "unit": None, "applied": None, "issued": None, "difference": None, "difference_pct": None}
    diff = round(i[1] - a[1], 1)
    return {"comparable": True, "unit": a[0], "applied": round(a[1], 1), "issued": round(i[1], 1), "difference": diff,
            "difference_pct": round(100.0 * diff / i[1], 1) if i[1] else None}


def fifo_remaining_lots(ins: list[dict], consumed: float) -> list[dict]:
    """Lotes (entradas) que siguen en bodega si lo consumido salio primero de
    los mas antiguos. `ins`: [{quantity, moved_at, expires_on}]; devuelve los
    lotes con su `remaining`."""
    left = max(consumed, 0.0)
    out = []
    for lot in sorted(ins, key=lambda x: x["moved_at"]):
        q = float(lot["quantity"])
        used = min(q, left)
        left -= used
        if q - used > 0:
            out.append({**lot, "remaining": round(q - used, 3)})
    return out


def expiring_lots(lots: list[dict], today: date, horizon_days: int) -> list[dict]:
    """Lotes vencidos o que vencen antes de la proxima revision (horizonte en
    dias, la frecuencia de la lista 7G.1 del paquete)."""
    out = []
    for lot in lots:
        if lot.get("expires_on") is None:
            continue
        days = (lot["expires_on"] - today).days
        if days <= horizon_days:
            out.append({**lot, "days_left": days, "expired": days < 0})
    return sorted(out, key=lambda x: x["days_left"])


# ── Calendario anual 7G (D3.2) ─────────────────────────────────────────

def periods_elapsed(days_elapsed: float, frequency_days: int) -> int:
    """Cuantas veces debio hacerse una actividad con frecuencia N dias en
    los dias transcurridos del periodo (la primera vence al empezar)."""
    if frequency_days <= 0:
        raise InvalidRecordError("La frecuencia debe ser positiva")
    if days_elapsed <= 0:
        return 0
    return math.ceil(days_elapsed / frequency_days)


def compliance_pct(done: int, expected: int) -> float | None:
    """% de cumplimiento: lo hecho (sin pasar de lo esperado) sobre lo
    esperado. Nada esperado todavia -> None (no 100 %)."""
    if expected <= 0:
        return None
    return round(100.0 * min(done, expected) / expected, 1)


# ── Laboratorio (0034) ─────────────────────────────────────────────────

QUALIFIERS = ("=", "<", ">")


def interpret_lab_result(bands: list[dict], value: float, qualifier: str) -> dict[str, Any] | None:
    """Interpretacion de un resultado de laboratorio. Con '<' (bajo el limite
    de deteccion) o '>' (sobre el rango) el valor real es un intervalo: se
    interpreta solo si TODO el intervalo cae en el mismo tramo; si no, el
    resultado no es concluyente (None) y no se inventa una interpretacion.
      '<X' -> [0, X)      '>X' -> (X, infinito)"""
    if qualifier not in QUALIFIERS:
        raise InvalidRecordError(f"Calificador invalido: {qualifier!r} (validos: {list(QUALIFIERS)})")
    if value < 0:
        raise InvalidRecordError("El resultado no puede ser negativo")
    if qualifier == "=":
        return interpret_reading(bands, value)
    if qualifier == "<":
        low, high = 0.0, math.nextafter(value, -math.inf) if value > 0 else 0.0
    else:
        low, high = math.nextafter(value, math.inf), math.inf
    first, last = matching_band(bands, low), matching_band(bands, high)
    if first["code"] != last["code"]:
        return None
    return interpret_reading(bands, low)


# ── Lectura manual de medidor (0032) ───────────────────────────────────

class RegisterWentDownError(InvalidRecordError):
    """El registro acumulado quedo por debajo de la lectura anterior y el
    operador no confirmo cambio o reinicio del medidor."""


def check_register(previous_value: float | None, value: float, lower_confirmed: bool) -> dict[str, Any]:
    """Un medidor acumula: la lectura nueva no puede ser menor que la anterior
    salvo que el operador confirme que el medidor se cambio o se reinicio
    (en ese caso no hay consumo calculable contra la anterior)."""
    if value < 0:
        raise InvalidRecordError("La lectura no puede ser negativa")
    if previous_value is None:
        return {"delta": None, "went_down": False}
    if value < previous_value:
        if not lower_confirmed:
            raise RegisterWentDownError(
                f"La lectura {value:g} es menor que la anterior ({previous_value:g}). Si el medidor se cambió o se "
                "reinició, confírmelo; si no, revise el número leído."
            )
        return {"delta": None, "went_down": True}
    return {"delta": round(value - previous_value, 3), "went_down": False}


# ── Dosificacion (0031) ────────────────────────────────────────────────

SECONDS_PER_DAY = 86_400


def chlorine_product_per_day(flow_lps: float, dose_mg_l: float, active_pct: float) -> float:
    """Guia 3 §3.5: gramos de producto por dia = (caudal L/s x 86.400 x dosis
    mg/L) / (% de cloro activo x 10). Para un liquido con % peso/volumen el
    resultado son mililitros por dia."""
    if flow_lps <= 0:
        raise InvalidRecordError("El caudal debe ser mayor que cero (L/s)")
    if dose_mg_l <= 0:
        raise InvalidRecordError("La dosis debe ser mayor que cero (mg/L)")
    if not 0 < active_pct <= 100:
        raise InvalidRecordError("La concentración del producto va de más de 0 a 100 %")
    return flow_lps * SECONDS_PER_DAY * dose_mg_l / (active_pct * 10)


def dosing_guard_codes(
    product_purpose: str,
    last_residual_code: str | None,
    residual_measured_today: bool,
    turbid_today: bool,
) -> list[str]:
    """Que guardas aplican al calculo (los textos son del paquete):
      not_disinfectant -- la formula es solo para cloro; otros productos van
                          con prueba de jarras y apoyo tecnico
      turbid_water     -- turbiedad fuera de rango o agua turbia/con color hoy
      high_residual    -- el ultimo cloro en la salida del tanque esta alto
      low_residual     -- esta bajo: revisar causas antes de subir
      no_reading_today -- no se midio hoy en la salida del tanque
      orientative, verify_after, safety -- siempre."""
    if product_purpose != "disinfection":
        return ["not_disinfectant", "safety"]
    codes = []
    if turbid_today:
        codes.append("turbid_water")
    if last_residual_code == "high":
        codes.append("high_residual")
    elif last_residual_code == "low":
        codes.append("low_residual")
    if not residual_measured_today:
        codes.append("no_reading_today")
    return codes + ["orientative", "verify_after", "safety"]


# ── Nivel de instrumentacion ───────────────────────────────────────────

def validate_instrumentation(levels: dict[str, str]) -> None:
    for module, level in levels.items():
        if module not in INSTRUMENTATION_MODULES:
            raise InvalidInstrumentationError(f"Modulo desconocido: {module!r} (validos: {list(INSTRUMENTATION_MODULES)})")
        if level not in INSTRUMENTATION_LEVELS:
            raise InvalidInstrumentationError(f"Nivel invalido para {module}: {level!r} (validos: {list(INSTRUMENTATION_LEVELS)})")



# ── Plan minimo, ficha 7G.2 y tablero 7H (D7) ──────────────────────────

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def minimum_plan_view(rows: list[dict], entries: dict[tuple[str, str], dict],
                      suggestions: dict[str, list[str]]) -> dict[str, Any]:
    """Une las filas del catalogo con lo que decidio la junta y la evidencia
    viva de cada fila. `entries`: {(pack_id, row_code): entrada}.
    `suggestions`: {suggestion_source: [hechos]}."""
    out = []
    for r in rows:
        e = entries.get((r["pack_id"], r["code"]))
        out.append({**r, "entry": e, "suggestions": suggestions.get(r["suggestion_source"], [])})
    done = sum(1 for x in out if x["entry"] and (x["entry"].get("decision") or "").strip())
    return {"rows": out, "summary": {"total": len(out), "decided": done, "complete": bool(out) and done == len(out)}}


def improvement_candidates(findings: list[dict], derived: list[dict], taken_refs: set[str]) -> list[dict[str, Any]]:
    """Lo que la evidencia propone llevar a la 7G.2 y aun no se llevo.
    `findings`: hallazgos abiertos (source_ref del candidato = id del
    hallazgo). `derived`: evidencia que no es hallazgo (fosa sin retiro,
    descarga abierta), ya con su `source_ref`. Orden: prioridad, luego lo
    mas antiguo primero (lleva mas tiempo sin resolverse)."""
    out = []
    for f in findings:
        if f["status"] == "closed" or f["finding_id"] in taken_refs:
            continue
        out.append({**f, "source_ref": f["finding_id"]})
    out += [d for d in derived if d["source_ref"] not in taken_refs]
    return sorted(out, key=lambda c: (PRIORITY_ORDER.get(c.get("priority") or "", 3), c.get("since") or ""))


def products_board(items: list[dict], answers: dict[str, dict], evidence: dict[str, dict]) -> dict[str, Any]:
    """Tablero 7H: cada producto con su ultimo estado verificado (de la
    ultima aplicacion de la lista) y lo que el sistema tiene registrado.
    `answers`: {item_key: {answer_code, observation}}; `evidence`:
    {item_key: {count, last_at}}. "Sin evidencia" con "completo" se marca
    para que quien verifica lo revise; no cambia la decision."""
    rows = []
    for it in items:
        a = answers.get(it["key"])
        ev = evidence.get(it["key"]) or {"count": 0, "last_at": None}
        status = a["answer_code"] if a else None
        rows.append({
            "key": it["key"], "text": it["text"], "status": status, "note": a.get("observation") if a else None,
            "evidence": ev, "has_evidence": ev["count"] > 0,
            "check": status == "complete" and ev["count"] == 0 and "evidence" in it,
        })
    return {
        "items": rows,
        "summary": {"total": len(rows), "complete": sum(1 for r in rows if r["status"] == "complete"),
                    "pending": sum(1 for r in rows if r["status"] != "complete"),
                    "with_evidence": sum(1 for r in rows if r["has_evidence"])},
    }



# ── Tablero de la agrupacion (D12) ─────────────────────────────────────

def maturity_progress(runs: list[dict]) -> dict[str, Any]:
    """Primera aplicacion frente a la ultima de una verificacion.
    `runs`: [{performed_at, score: {pct}}] en cualquier orden."""
    scored = sorted((r for r in runs if r.get("score") and r["score"].get("pct") is not None), key=lambda r: r["performed_at"])
    if not scored:
        return {"runs": 0, "initial_pct": None, "current_pct": None, "change": None}
    first, last = scored[0]["score"]["pct"], scored[-1]["score"]["pct"]
    return {"runs": len(scored), "initial_pct": first, "current_pct": last,
            "change": round(last - first, 1) if len(scored) > 1 else None}


def group_rollup(members: list[dict]) -> dict[str, Any]:
    """Totales de la agrupacion solo con lo que cada junta compartio.
    `members`: [{indicators: {code: valor}}]; un indicador no compartido no
    esta en el dict y no cuenta (ni como cero). Para cada indicador dice
    cuantas juntas lo comparten, para leer los totales con su base."""
    def shared(code):
        return [m["indicators"][code] for m in members if code in m["indicators"] and m["indicators"][code] is not None]

    out: dict[str, Any] = {"members": len(members)}
    q = shared("quality_alerts")
    out["quality_alerts"] = {"shared_by": len(q), "open": sum(x["open"] for x in q), "critical": sum(x["critical"] for x in q),
                             "members_with_critical": sum(1 for x in q if x["critical"])}
    c = [x for x in shared("calendar") if x.get("compliance_pct") is not None]
    out["calendar"] = {"shared_by": len(c),
                       "average_pct": round(sum(x["compliance_pct"] for x in c) / len(c), 1) if c else None,
                       "lowest_pct": min((x["compliance_pct"] for x in c), default=None)}
    p = shared("products")
    out["products"] = {"shared_by": len(p), "complete": sum(x["complete"] for x in p), "total": sum(x["total"] for x in p)}
    i = shared("improvement")
    out["improvement"] = {"shared_by": len(i), "inputs": sum(x["inputs"] for x in i),
                          "cost_estimate_total": sum(x["cost_estimate_total"] for x in i), "to_quote": sum(x["to_quote"] for x in i)}
    s = shared("sanitation")
    out["sanitation"] = {"shared_by": len(s), "sludge_overdue": sum(x["sludge_overdue"] for x in s),
                         "open_discharges": sum(x["open_discharges"] for x in s)}
    e = shared("emergencies")
    out["emergencies"] = {"shared_by": len(e), "active": sum(x["active"] for x in e)}
    m = shared("maturity")
    changes = [t["change"] for x in m for t in x if t["change"] is not None]
    out["maturity"] = {"shared_by": len(m), "evaluations_with_progress": len(changes),
                       "average_change": round(sum(changes) / len(changes), 1) if changes else None}
    return out
