"""Genera la migracion 0050 (formularios de la hoja de vida) desde el formato
oficial de la Circular CREG 119 de 2014 (Track F, Q2, 2026-10-20).

La hoja "Definicion de campos" del Excel oficial trae cada campo de la hoja de
vida con su numeral, nombre, tipo de dato, si es obligatorio y su
descripcion. Este script la convierte en fichas del motor de formularios
(`asset_form.form_spec`, mismo formato que 0047), una por seccion:

- lo que RenfyGrid ya guarda como dato propio NO se repite en la ficha: la
  identificacion de la frontera y del equipo (columnas de `metering_point` y
  `equipment`), las fechas de instalacion y retiro (`equipment_installation`),
  los sellos, las calibraciones, las pruebas de rutina, los accesos de nivel
  2 y las novedades (registros de `metering_event`);
- las opciones de cada campo de seleccion salen de la hoja "Mod" del mismo
  Excel (o de la descripcion del campo cuando alli estan) y quedan en
  `CHOICES` con el numeral del que salen.

Uso:
    python infra/db/tools/build_creg_hoja_vida.py
    (lee docs/fuentes/creg/Circular119-2014-Anexo1-hoja-de-vida.xlsx y
     escribe infra/db/migrations/0050_co_creg_hoja_vida_forms.sql)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs" / "fuentes" / "creg" / "Circular119-2014-Anexo1-hoja-de-vida.xlsx"
TARGET = ROOT / "infra" / "db" / "migrations" / "0050_co_creg_hoja_vida_forms.sql"
PACK = "CO-CREG-038"


def opts(*labels: str) -> list[dict]:
    out = []
    for label in labels:
        code = re.sub(r"[^a-z0-9]+", "_", label.lower().translate(str.maketrans("áéíóúñ", "aeioun"))).strip("_")
        out.append({"code": code, "label": label})
    return out


CONFORMITY = opts("Conformidad", "Declaración de fabricante", "Informe de recepción", "No aplica")
# Opciones de los campos de seleccion, por numeral (hoja "Mod" del Excel oficial).
CHOICES: dict[str, list[dict]] = {
    "2.16": opts("Monofásica", "Bifásica", "Trifásica"),
    "2.17": opts("Residencial", "Comercial", "Industrial", "Provisional", "Oficial", "Alumbrado", "Otro"),
    "2.24": opts("Generación", "Comercialización", "Para agentes y usuarios", "Distribución", "Enlace internacional",
                 "Entre agentes", "Interconexión internacional", "Demanda desconectable", "Sin reporte al ASIC"),
    "3.1": opts("Poste", "Patio", "Interior", "Exterior"),
    "3.9": opts("Estático", "Electromecánico", "Híbrido"),
    "3.10": opts("Directa", "Semidirecta", "Indirecta"),
    "3.10.1": opts("1 elemento", "2 elementos", "2 1/2 elementos", "2 elementos (Aarón)", "3 elementos"),
    "3.11": opts("Unidireccional", "Bidireccional"),
    "3.14": opts("Ciclométrico", "Display"),
    "3.20": opts("kWh/rev", "rev/kWh", "kWh/imp", "imp/kWh"),
    "3.31": opts("No aplica", "Volátil", "No volátil"),
    "3.32.1": opts("No aplica", "Interno", "Externo"),
    "3.36": opts("Sí", "No", "No aplica"),
    "3.39": CONFORMITY,
    "8.1.2": opts("AWG", "mm2"),
    "8.2.2": opts("AWG", "mm2"),
    "8.1.5": opts("Monopolar", "Multiconductor"),
    "8.2.5": opts("Monopolar", "Multiconductor"),
    "9.1.1.4": CONFORMITY,
    "9.2.1.4": CONFORMITY,
    "9.3.1.4": CONFORMITY,
    "10.1": opts("Puentes", "Cuchillas", "Otras"),
    "10.3.4": CONFORMITY[:3],
    "11.8": opts("Movistar", "Claro", "Tigo", "Otros"),
    "11.9": opts("Sin telemedida", "GPRS", "3G", "4G", "Línea telefónica", "Fibra óptica", "Satelital", "Otra"),
    "11.10": opts("Horario", "Acumulativo", "No aplica"),
}
MULTI = {"3.37": opts("RS232", "RS485", "Óptico", "Ethernet", "Otro")}
BOOLEAN = {"2.22"}  # SI / NO
TEXTAREA = {"16"}
# Numeros de certificado, de documento y de telefono: son identificadores, no cantidades.
AS_TEXT = {"3.38.1", "17.2", "11.7"}
# El Excel deja sin tipo los datos de placa del CT (VA, Hz, %, V, kA): son cantidades.
AS_NUMBER = {"6.6", "6.6.1", "6.7", "6.8", "6.9", "6.10", "6.11", "7.10.1"}

# Lo que ya es dato propio de RenfyGrid (columnas o registros de la bitacora).
IN_COLUMNS = {
    "2.1", "2.2", "2.3", "2.5", "2.6", "2.7", "2.8", "2.13", "2.14", "2.15", "2.25",
    "3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.28", "3.29", "3.30", "3.33",
    "6.1", "6.2", "6.3", "6.5", "6.12", "6.13",
    "7.1", "7.2", "7.3", "7.5", "7.13", "7.14",
    "11.1", "11.2",
}
IN_EVENTS = ("2.26", "3.27", "3.40", "6.19", "6.20.1", "6.20.2", "6.20.3", "6.21", "7.15", "7.16.1", "7.16.2",
             "7.16.3", "7.17", "10.2", "1")
# El Excel repite 6.20.4: "Ente Emisor" del certificado de calibracion (va en la bitacora)
# y "Otras certificaciones" (titulo de 6.20.4.1 a 6.20.4.3, que si van en la ficha).
IN_EVENTS_EXACT = {"6.20.4"}
ANNEXES = {"2.27", "3.41", "6.22", "7.18", "8.3", "11.11"}  # adjuntos: van con los documentos, no en la ficha

# (id, alcance, tipo de equipo, orden, titulo, numerales de la seccion)
FORMS = [
    ("CO-HV-GENERAL", "point", None, 1, "Información general de la frontera", ("2.",)),
    ("CO-HV-CONDUCTORS", "point", None, 2, "Conductores", ("8.",)),
    ("CO-HV-PANELS", "point", None, 3, "Paneles o cajas de seguridad", ("9.",)),
    ("CO-HV-TEST-BLOCK", "point", None, 4, "Bornera de prueba", ("10.",)),
    ("CO-HV-OBSERVATIONS", "point", None, 5, "Observaciones y responsable de la hoja de vida", ("16", "17.")),
    ("CO-HV-METER", "equipment", "meter", 1, "Ficha técnica del medidor", ("3.",)),
    ("CO-HV-CT", "equipment", "ct", 2, "Ficha técnica del transformador de corriente", ("6.",)),
    ("CO-HV-PT", "equipment", "pt", 3, "Ficha técnica del transformador de tensión", ("7.",)),
    ("CO-HV-MODEM", "equipment", "modem", 4, "Ficha técnica del módem", ("11.",)),
]
TYPE_MAP = {"Texto": "text", "Fecha": "date", "Número": "number", "Numero": "number"}


def ref_of(raw: str) -> str:
    return raw.strip().rstrip(".")


def key_of(ref: str) -> str:
    return "c" + ref.replace(".", "_")


def read_definitions() -> list[dict]:
    """Un numeral es titulo si tiene sub-numerales (p. ej. 6.19 Sellos); el
    Excel deja sin tipo de dato a varios campos reales (6.4 a 6.11), asi que
    el tipo vacio no basta para decidirlo."""
    wb = openpyxl.load_workbook(SOURCE, read_only=True, data_only=True)
    ws = wb["Definición de campos"]
    raw = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        cells = [("" if c is None else str(c).strip()) for c in r[:6]]
        if cells[0]:
            raw.append(cells)
    refs = [ref_of(c[0]) for c in raw]
    parents = {ref for ref in refs if any(other.startswith(ref + ".") for other in refs)}
    rows = []
    group = None
    for num, name, _title_flag, kind, required, desc in raw:
        ref = ref_of(num)
        name = " ".join(name.split()).rstrip(":")
        # Un numeral con sub-numerales tambien es campo si tiene tipo de dato u
        # opciones (3.10 Conexion y su 3.10.1; 3.32 Capacidad y su 3.32.1).
        is_field = bool(kind) or ref in CHOICES or ref in MULTI or ref in AS_NUMBER
        if (ref in parents and not is_field) or ("." not in ref and ref not in TEXTAREA):
            group = name
            rows.append({"ref": ref, "name": name, "header": True, "group": group})
            continue
        rows.append({"ref": ref, "name": name, "kind": kind, "required": required == "1",
                     "desc": " ".join(desc.split()), "group": group, "header": False})
    return rows


def field_for(row: dict) -> dict:
    ref = row["ref"]
    field: dict = {"key": key_of(ref), "label": row["name"], "ref": ref}
    if ref in CHOICES:
        field.update(type="choice", options=CHOICES[ref])
    elif ref in MULTI:
        field.update(type="multi", options=MULTI[ref])
    elif ref in BOOLEAN:
        field["type"] = "boolean"
    elif ref in TEXTAREA:
        field["type"] = "textarea"
    elif ref in AS_TEXT:
        field["type"] = "text"
    elif ref in AS_NUMBER:
        field["type"] = "number"
    else:
        field["type"] = TYPE_MAP.get(row["kind"], "text")
    if row.get("required"):
        field["required"] = True
    if row.get("group") and row["group"] != row["name"]:
        field["group"] = row["group"]
    if row.get("desc"):
        field["verify"] = row["desc"]
    return field


def excluded(ref: str) -> bool:
    if ref in IN_COLUMNS or ref in ANNEXES or ref in IN_EVENTS_EXACT:
        return True
    return any(ref == p.rstrip(".") or ref.startswith(p if p.endswith(".") else p + ".") for p in IN_EVENTS)


def build() -> str:
    rows = read_definitions()
    seen: set[str] = set()
    statements = []
    for form_id, scope, eq_class, order, title, prefixes in FORMS:
        fields = []
        for row in rows:
            ref = row["ref"]
            in_section = any(ref == p.rstrip(".") or ref.startswith(p if p.endswith(".") else p + ".") for p in prefixes)
            if not in_section or row["header"] or excluded(ref):
                continue
            if "Sello" in row["name"] and row["name"].startswith("("):
                continue  # posiciones fijas de sellos: son registros de la bitacora
            field = field_for(row)
            if field["key"] in seen:
                continue  # el Excel repite numerales (6.20.4); se toma el primero
            seen.add(field["key"])
            fields.append(field)
        spec = json.dumps({"fields": fields}, ensure_ascii=False)
        statements.append(
            "INSERT INTO asset_form (id, pack_id, scope, equipment_class, sort_order, title, form_spec, source_ref) VALUES\n"
            f"({sql(form_id)}, {sql(PACK)}, {sql(scope)}, {sql(eq_class)}, {order}, {sql(title)},\n {sql(spec)}::jsonb,\n"
            f" {sql('Circular CREG 119 de 2014, hoja de vida, numerales ' + ', '.join(p.rstrip('.') for p in prefixes))});"
        )
    header = (
        "-- RenfyGrid -- 0050_co_creg_hoja_vida_forms.sql\n"
        "-- GENERADO por infra/db/tools/build_creg_hoja_vida.py desde el formato oficial de la\n"
        "-- Circular CREG 119 de 2014 (docs/fuentes/creg/). No editar a mano: cambiar el script y\n"
        "-- volver a generar. Track F, Q2 (2026-10-20), docs/10-caso-energia-fronteras.md.\n\n"
    )
    return header + "\n\n".join(statements) + "\n"


def sql(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    TARGET.write_text(build(), encoding="utf-8", newline="\n")
    print(f"escrito {TARGET.relative_to(ROOT)}")
