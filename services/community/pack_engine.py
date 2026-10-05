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


def evaluate_bands(bands: list[dict], value: float) -> dict[str, Any]:
    """El primer tramo cuyo limite cubre el valor. Con `upper_inclusive`
    falso el limite se excluye (cloro 0,29 -> bajo; 0,3 -> adecuado)."""
    validate_bands(bands)
    for band in bands:
        upper = band.get("upper")
        if upper is None:
            return _band_result(band)
        if band.get("upper_inclusive", True):
            if value <= upper:
                return _band_result(band)
        elif value < upper:
            return _band_result(band)
    raise InvalidRuleError("Ningun tramo cubre el valor")  # inalcanzable si validate_bands paso


def _band_result(band: dict) -> dict[str, Any]:
    return {"code": band["code"], "label": band["label"], "severity": band["severity"]}


# ── Listas de verificacion ─────────────────────────────────────────────

def validate_answers(template: dict, answers: list[dict]) -> None:
    """Toda aplicacion de una lista es completa: cada item respondido una
    sola vez con un codigo de la escala. Una inspeccion a medias no deja
    ver que quedo sin revisar."""
    item_keys = [item["key"] for item in template["items"]]
    scale_codes = {entry["code"] for entry in template["scale"]}
    seen: set[str] = set()
    for answer in answers:
        key = answer.get("item_key")
        if key not in item_keys:
            raise InvalidAnswersError(f"Item desconocido para {template['id']}: {key!r}")
        if key in seen:
            raise InvalidAnswersError(f"Item respondido dos veces: {key!r}")
        if answer.get("answer_code") not in scale_codes:
            raise InvalidAnswersError(
                f"Respuesta {answer.get('answer_code')!r} fuera de la escala (validas: {sorted(scale_codes)})"
            )
        seen.add(key)
    missing = [key for key in item_keys if key not in seen]
    if missing:
        raise InvalidAnswersError(f"Faltan items por responder: {missing}")


def findings_from_answers(template: dict, answers: list[dict]) -> list[dict[str, Any]]:
    """Un hallazgo por cada respuesta cuya entrada de la escala tiene
    `finding` verdadero. La prioridad sale de la escala del paquete. La
    descripcion junta el texto del item, la respuesta y la observacion."""
    scale = {entry["code"]: entry for entry in template["scale"]}
    items = {item["key"]: item for item in template["items"]}
    findings = []
    for answer in answers:
        entry = scale[answer["answer_code"]]
        if not entry.get("finding"):
            continue
        if not entry.get("finding_priority"):
            raise InvalidAnswersError(
                f"La escala de {template['id']} marca {entry['code']!r} como hallazgo sin finding_priority"
            )
        item = items[answer["item_key"]]
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


def maturity_score(template: dict, answers: list[dict]) -> dict[str, Any]:
    """Puntaje sobre el maximo posible con la escala de la plantilla. Sirve
    para la verificacion inicial y final y para 4A/4B (indice de madurez)."""
    scale = {entry["code"]: entry for entry in template["scale"]}
    best = max(entry.get("score", 0) for entry in template["scale"])
    total = sum(scale[a["answer_code"]].get("score", 0) for a in answers)
    maximum = best * len(template["items"])
    pct = round(100.0 * total / maximum, 1) if maximum else None
    return {"score": total, "max_score": maximum, "pct": pct}


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


# ── Nivel de instrumentacion ───────────────────────────────────────────

def validate_instrumentation(levels: dict[str, str]) -> None:
    for module, level in levels.items():
        if module not in INSTRUMENTATION_MODULES:
            raise InvalidInstrumentationError(f"Modulo desconocido: {module!r} (validos: {list(INSTRUMENTATION_MODULES)})")
        if level not in INSTRUMENTATION_LEVELS:
            raise InvalidInstrumentationError(f"Nivel invalido para {module}: {level!r} (validos: {list(INSTRUMENTATION_LEVELS)})")
