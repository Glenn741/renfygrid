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
