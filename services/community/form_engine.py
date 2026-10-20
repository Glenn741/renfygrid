"""Fichas y tablas de las guias (Track E, E1, migracion 0047) -- logica pura,
sin BD.

Dos tipos de formulario genericos, definidos por el paquete en
`checklist_template.form_spec` (ningun formato se programa como pantalla
propia, docs/04-plan-sprints.md §11.3):

- ficha (`record`): `{"fields": [{key, label, type, required?, options?,
  verify?, group?}]}`. Contenido: `{"fields": {key: {"value", "estimated",
  "note"}}}`. "estimated" y "note" son lo que pide la Guia 1: si no hay dato
  exacto se usa una estimacion marcada para verificar, y se anota quien puede
  ayudar a conseguirlo.
- tabla (`table`): `{"columns": [...], "min_rows"?, "max_rows"?,
  "preset_rows"?}`. Contenido: `{"rows": [{col: value}]}`.

Una ficha o tabla se puede guardar a medias (se completa en varias
sesiones o semanas); `completeness` dice si ya esta completa.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any

FIELD_TYPES = ("text", "textarea", "integer", "number", "choice", "multi", "geo", "list", "date", "boolean")
FORM_KINDS = ("record", "table")


class InvalidFormError(ValueError):
    """Contenido que no corresponde a la definicion del formulario."""


def _options(defn: dict) -> dict[str, str]:
    return {o["code"]: o["label"] for o in defn.get("options") or []}


def _norm(text: str) -> str:
    """Sin mayusculas, comas ni espacios repetidos: el desplegable de Excel no
    admite comas dentro de una opcion, asi que alli se cambian por espacios."""
    return re.sub(r"[,\s]+", " ", str(text)).strip().lower()


def _by_label(defn: dict, raw: str) -> str | None:
    """Codigo de una opcion a partir de su codigo o su etiqueta (sin
    distinguir mayusculas): en un Excel la gente escribe la etiqueta."""
    text = _norm(raw)
    for o in defn.get("options") or []:
        if text in (o["code"].lower(), _norm(o["label"])):
            return o["code"]
    # "Agua potable" para "Agua potable (tratada y desinfectada)"
    matches = [o["code"] for o in defn.get("options") or [] if _norm(o["label"]).startswith(text)]
    return matches[0] if len(matches) == 1 else None


def excel_serial_to_date(value: float) -> date:
    return date(1899, 12, 30) + timedelta(days=int(value))


def coerce_value(defn: dict, raw: Any) -> Any:
    """Valor limpio de un campo o columna, o None si esta vacio. Acepta lo
    que llega de la interfaz (ya tipado) y de un archivo (texto, numeros de
    Excel). Lanza InvalidFormError con un mensaje para la persona."""
    label = defn.get("label", defn["key"])
    kind = defn["type"]
    if raw is None or (isinstance(raw, str) and raw.strip() == "") or raw == [] or raw == {}:
        return None
    if kind in ("text", "textarea"):
        return str(raw).strip() if not isinstance(raw, float) or not raw.is_integer() else str(int(raw))
    if kind in ("integer", "number"):
        if isinstance(raw, bool):
            raise InvalidFormError(f"{label}: se espera un número")
        if isinstance(raw, str):
            text = raw.strip().replace(" ", "")
            # 1.250 o 1,250 como separador de miles; 2,5 como decimal.
            if kind == "integer":
                text = text.replace(".", "").replace(",", "")
            elif text.count(",") == 1 and "." not in text:
                text = text.replace(",", ".")
            try:
                raw = float(text)
            except ValueError:
                raise InvalidFormError(f"{label}: {raw!r} no es un número") from None
        value = float(raw)
        if math.isnan(value) or math.isinf(value):
            raise InvalidFormError(f"{label}: número inválido")
        # Por defecto una cantidad no es negativa; el campo que si puede serlo
        # (p. ej. el error de un medidor en su calibracion) lo declara.
        if value < 0 and not defn.get("signed"):
            raise InvalidFormError(f"{label}: no puede ser negativo")
        if kind == "integer":
            if not value.is_integer():
                raise InvalidFormError(f"{label}: se espera un número entero")
            return int(value)
        return value
    if kind == "choice":
        code = raw if isinstance(raw, str) and raw in _options(defn) else _by_label(defn, str(raw))
        if code is None:
            raise InvalidFormError(f"{label}: {raw!r} no es una opción válida ({', '.join(_options(defn).values())})")
        return code
    if kind == "multi":
        parts = raw if isinstance(raw, list) else [p for p in str(raw).replace(";", ",").split(",")]
        codes = []
        for part in parts:
            if str(part).strip() == "":
                continue
            code = part if part in _options(defn) else _by_label(defn, str(part))
            if code is None:
                raise InvalidFormError(f"{label}: {part!r} no es una opción válida ({', '.join(_options(defn).values())})")
            if code not in codes:
                codes.append(code)
        return codes or None
    if kind == "list":
        items = raw if isinstance(raw, list) else str(raw).replace("\r", "").split("\n")
        clean = [str(i).strip().lstrip("-•").strip() for i in items if str(i).strip().lstrip("-•").strip()]
        return clean or None
    if kind == "geo":
        if isinstance(raw, dict):
            lat, lon = raw.get("lat"), raw.get("lon")
        else:
            parts = str(raw).replace(";", ",").split(",")
            if len(parts) != 2:
                raise InvalidFormError(f"{label}: escriba latitud y longitud separadas por coma (p. ej. -2.89, -78.77)")
            lat, lon = parts
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            raise InvalidFormError(f"{label}: latitud y longitud deben ser números") from None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise InvalidFormError(f"{label}: coordenadas fuera de rango")
        return {"lat": round(lat, 6), "lon": round(lon, 6)}
    if kind == "date":
        if isinstance(raw, datetime):
            return raw.date().isoformat()
        if isinstance(raw, date):
            return raw.isoformat()
        if isinstance(raw, (int, float)):
            return excel_serial_to_date(raw).isoformat()
        text = str(raw).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        raise InvalidFormError(f"{label}: {raw!r} no es una fecha (use dd/mm/aaaa)")
    if kind == "boolean":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in ("si", "sí", "s", "yes", "true", "1", "x"):
            return True
        if text in ("no", "n", "false", "0"):
            return False
        raise InvalidFormError(f"{label}: responda Sí o No")
    raise InvalidFormError(f"Tipo de campo desconocido: {kind!r}")


def _flag(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("si", "sí", "s", "yes", "true", "1", "x")


def clean_record(spec: dict, data: dict | None) -> dict:
    """Contenido limpio de una ficha. Campos desconocidos = error (un archivo
    con una columna mal escrita no se pierde en silencio)."""
    fields = {f["key"]: f for f in spec.get("fields") or []}
    incoming = (data or {}).get("fields") or {}
    unknown = sorted(set(incoming) - set(fields))
    if unknown:
        raise InvalidFormError(f"Campos que no existen en la ficha: {unknown}")
    out: dict[str, dict] = {}
    for key, defn in fields.items():
        entry = incoming.get(key)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            entry = {"value": entry}
        value = coerce_value(defn, entry.get("value"))
        note = (str(entry.get("note") or "").strip()) or None
        estimated = _flag(entry.get("estimated"))
        if value is None and note is None:
            continue
        out[key] = {"value": value, "estimated": estimated and value is not None, "note": note}
    return {"fields": out}


def clean_table(spec: dict, data: dict | None) -> dict:
    columns = {c["key"]: c for c in spec.get("columns") or []}
    rows_in = (data or {}).get("rows") or []
    if not isinstance(rows_in, list):
        raise InvalidFormError("Las filas deben ser una lista")
    rows: list[dict] = []
    for n, row in enumerate(rows_in, start=1):
        if not isinstance(row, dict):
            raise InvalidFormError(f"Fila {n}: formato inválido")
        unknown = sorted(set(row) - set(columns))
        if unknown:
            raise InvalidFormError(f"Fila {n}: columnas que no existen en la tabla: {unknown}")
        clean = {}
        for key, defn in columns.items():
            try:
                value = coerce_value(defn, row.get(key))
            except InvalidFormError as exc:
                raise InvalidFormError(f"Fila {n}: {exc}") from None
            if value is not None:
                clean[key] = value
        if clean:
            rows.append(clean)
    max_rows = spec.get("max_rows")
    if max_rows and len(rows) > max_rows:
        raise InvalidFormError(f"La tabla admite como máximo {max_rows} filas")
    return {"rows": rows}


def clean_form(kind: str, spec: dict, data: dict | None) -> dict:
    if kind == "record":
        return clean_record(spec, data)
    if kind == "table":
        return clean_table(spec, data)
    raise InvalidFormError(f"El formulario de tipo {kind!r} no es ficha ni tabla")


def completeness(kind: str, spec: dict, data: dict) -> dict[str, Any]:
    """Avance de una ficha o tabla. Ficha: campos con dato sobre el total; esta
    completa cuando tiene todos los obligatorios. Tabla: completa con el minimo
    de filas y cada fila con sus columnas obligatorias."""
    if kind == "record":
        fields = spec.get("fields") or []
        filled = {k for k, v in (data.get("fields") or {}).items() if v.get("value") is not None}
        required = [f["key"] for f in fields if f.get("required")]
        missing = [f["label"] for f in fields if f.get("required") and f["key"] not in filled]
        estimated = sum(1 for v in (data.get("fields") or {}).values() if v.get("estimated"))
        return {"filled": len(filled), "total": len(fields), "required": len(required), "missing_required": missing,
                "estimated": estimated, "complete": not missing and bool(filled)}
    rows = data.get("rows") or []
    columns = spec.get("columns") or []
    required = [c["key"] for c in columns if c.get("required")]
    incomplete_rows = [i + 1 for i, r in enumerate(rows) if any(k not in r for k in required)]
    min_rows = spec.get("min_rows") or 1
    missing = []
    if len(rows) < min_rows:
        missing.append(f"al menos {min_rows} fila{'s' if min_rows > 1 else ''}")
    if incomplete_rows:
        missing.append(f"columnas obligatorias en la{'s' if len(incomplete_rows) > 1 else ''} fila{'s' if len(incomplete_rows) > 1 else ''} {', '.join(map(str, incomplete_rows))}")
    return {"rows": len(rows), "min_rows": min_rows, "missing_required": missing, "complete": not missing}


def field_value(data: dict | None, key: str) -> Any:
    entry = ((data or {}).get("fields") or {}).get(key)
    return entry.get("value") if entry else None


def option_label(spec: dict, key: str, code: str | None) -> str | None:
    for f in (spec.get("fields") or []) + (spec.get("columns") or []):
        if f["key"] == key:
            return _options(f).get(code) if code else None
    return None


def guide_coverage(stages: list[dict]) -> dict[str, Any]:
    """Resumen de avance por guia para el tablero de la ONG: formularios
    con contenido (aplicados o con algo llenado) y completos, por etapa.
    `stages`: salida de la ruta del operador."""
    out = {}
    for s in stages:
        lists = s.get("lists") or []
        total = len(lists)
        started = sum(1 for item in lists if item["status"] != "never")
        complete = sum(1 for item in lists if item["status"] in ("done", "ok", "overdue"))
        out[s["code"]] = {"total": total, "started": started, "complete": complete,
                          "pct": round(100.0 * complete / total, 1) if total else None}
    return out
