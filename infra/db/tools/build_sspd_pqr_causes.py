"""Genera la migracion 0052 (causales de PQR de la Superservicios) desde el
documento fuente (Track F, Q2.5, 2026-10-21).

Fuente: proyecto de resolucion de PQRS y canales de atencion publicado por la
Superservicios en abril de 2026 (docs/fuentes/sspd/), anexo 5 "Clasificacion
del detalle de causales": codigo de 3 digitos, detalle, tipo de tramite
(reclamacion o queja), causal (facturacion o prestacion) y descripcion. La
resolucion final es la SSPD 20261000681915 del 5 de agosto de 2026; si su
texto cambia algun codigo, se corrige la fuente y se vuelve a generar.

A que sectores aplica cada causal sale de su propia descripcion ("Aplica
para..."); las del servicio de aseo quedan con un arreglo vacio porque aseo no
es un sector de RenfyGrid.

Uso:
    python infra/db/tools/build_sspd_pqr_causes.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pypdf

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs" / "fuentes" / "sspd" / "Proyecto-resolucion-PQRS-canales-atencion-SUI-2026-04.pdf"
TARGET = ROOT / "infra" / "db" / "migrations" / "0052_sspd_pqr_causes.sql"
PACK = "CO-SSPD"

# Aplicacion por sector, leida de la descripcion de cada causal.
ONLY_SANITATION = {"100", "102", "112", "123", "129", "130", "131"}   # aforo, produccion, predio desocupado, multiusuario, frecuencias, complementarias: aseo
SECTORS = {"203": "{water}", "207": "{water}", "208": "{electricity}"}


def extract() -> list[tuple[str, str, str, str, str]]:
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(str(SOURCE)).pages)
    seg = text[text.index("5.1. RECLAMACIONES"):]
    seg = re.sub(r"RADS\s+Página \d+ de 33.*?sspd@superservicios\.gov\.co", " ", seg, flags=re.S)
    seg = re.sub(r"Código Detalle de la\s+Causal\s+Tipo de\s+trámite Causal Descripción resumida", " ", seg)
    flat = " ".join(seg.split())
    rows = []
    for part in re.split(r"\s(?=(?:1[0-3]\d|2\d\d)\s+[A-ZÁÉÍÓÚ])", flat):
        m = re.match(r"(\d{3})\s+(.*?)\s+(Reclamación|Queja)\s+(Facturación|Prestación)\s+(.*)", part)
        if not m:
            continue
        desc = re.split(r"\s(?:5\.2\.|Nota de unificación|Nota \d|ANEXO)", m.group(5))[0].strip()
        rows.append((m.group(1), m.group(2).strip(), m.group(3), m.group(4), desc.replace("Se re fiere", "Se refiere")))
    codes = [r[0] for r in rows]
    assert len(codes) == len(set(codes)) and len(rows) >= 40, f"extraccion incompleta: {len(rows)} causales"
    return rows


def sql(value: str | None) -> str:
    return "NULL" if value is None else "'" + value.replace("'", "''") + "'"


def build() -> str:
    lines = []
    for code, label, kind, group, desc in extract():
        sectors = "'{}'" if code in ONLY_SANITATION else (f"'{SECTORS[code]}'" if code in SECTORS else "NULL")
        lines.append(f"({sql(PACK)}, {sql(code)}, {sql('F' if group == 'Facturación' else 'P')}, "
                     f"{sql('claim' if kind == 'Reclamación' else 'complaint')}, {sql(label)}, {sql(desc)}, {sectors})")
    return ("-- RenfyGrid -- 0052_sspd_pqr_causes.sql\n"
            "-- GENERADO por infra/db/tools/build_sspd_pqr_causes.py desde docs/fuentes/sspd/. No editar a mano.\n"
            "-- Track F, Q2.5 (2026-10-21), docs/11-mapa-fronteras.md.\n\n"
            "INSERT INTO pqr_cause (pack_id, code, group_code, request_kind, label, description, sectors) VALUES\n"
            + ",\n".join(lines) + ";\n")


if __name__ == "__main__":
    TARGET.write_text(build(), encoding="utf-8", newline="\n")
    print(f"escrito {TARGET.relative_to(ROOT)}")
