"""Pruebas puras de form_engine (Track E, E1, migracion 0047) -- sin BD.
Las definiciones de prueba son copia reducida de la ficha y la tabla de la
Guia 1 (MA-G1-PROFILE, MA-G1-PRIORITIES)."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from form_engine import (  # noqa: E402
    InvalidFormError,
    clean_record,
    clean_table,
    coerce_value,
    completeness,
    guide_coverage,
)

SUPPLY = {"key": "supply_type", "label": "Agua", "type": "choice", "required": True,
          "options": [{"code": "potable", "label": "Agua potable (tratada y desinfectada)"},
                      {"code": "raw", "label": "Agua cruda o entubada sin tratamiento"}, {"code": "none", "label": "Sin servicio de agua"}]}
SANITATION = {"key": "sanitation", "label": "Saneamiento", "type": "choice",
              "options": [{"code": "onsite", "label": "Saneamiento en sitio (pozo séptico, letrina, biodigestor)"}]}
PROFILE = {"fields": [
    {"key": "canton", "label": "Cantón", "type": "text", "required": True},
    {"key": "users", "label": "Usuarios", "type": "integer", "required": True},
    {"key": "location", "label": "Ubicación", "type": "geo"},
    {"key": "economy", "label": "Actividades", "type": "multi",
     "options": [{"code": "agriculture", "label": "Agricultura"}, {"code": "trade", "label": "Comercio"}]},
    {"key": "causes", "label": "Causas", "type": "list"},
    SUPPLY,
]}
PRIORITIES = {"min_rows": 1, "max_rows": 3, "columns": [
    {"key": "problem", "label": "Problema", "type": "text", "required": True},
    {"key": "families", "label": "Familias", "type": "integer"},
    {"key": "priority", "label": "Prioridad", "type": "choice", "required": True,
     "options": [{"code": "high", "label": "Alta"}, {"code": "low", "label": "Baja"}]},
]}


class CoerceValueTest(unittest.TestCase):
    def test_numbers_from_files(self):
        users = {"key": "u", "label": "Usuarios", "type": "integer"}
        self.assertEqual(coerce_value(users, "1.250"), 1250)
        self.assertEqual(coerce_value(users, 120.0), 120)
        self.assertEqual(coerce_value({"key": "n", "label": "n", "type": "number"}, "2,5"), 2.5)
        with self.assertRaises(InvalidFormError):
            coerce_value(users, "muchos")
        with self.assertRaises(InvalidFormError):
            coerce_value(users, -1)

    def test_choice_by_label_prefix_and_excel_dropdown(self):
        self.assertEqual(coerce_value(SUPPLY, "Agua potable"), "potable")
        self.assertEqual(coerce_value(SUPPLY, "raw"), "raw")
        # El desplegable de Excel cambia las comas por espacios.
        self.assertEqual(coerce_value(SANITATION, "Saneamiento en sitio (pozo séptico  letrina  biodigestor)"), "onsite")
        with self.assertRaises(InvalidFormError):
            coerce_value(SUPPLY, "Agua")  # ambiguo: tres opciones empiezan asi

    def test_geo_date_list(self):
        geo = {"key": "g", "label": "Ubicación", "type": "geo"}
        self.assertEqual(coerce_value(geo, "-2.8974, -78.7756"), {"lat": -2.8974, "lon": -78.7756})
        with self.assertRaises(InvalidFormError):
            coerce_value(geo, "-200, 0")
        when = {"key": "d", "label": "Fecha", "type": "date"}
        self.assertEqual(coerce_value(when, "22/10/2026"), "2026-10-22")
        self.assertEqual(coerce_value(when, 46317), "2026-10-22")  # serial de Excel
        self.assertEqual(coerce_value(when, date(2026, 10, 22)), "2026-10-22")
        self.assertEqual(coerce_value({"key": "l", "label": "l", "type": "list"}, "- tuberías antiguas\n- deslizamientos\n"),
                         ["tuberías antiguas", "deslizamientos"])

    def test_empty_is_none(self):
        self.assertIsNone(coerce_value(SUPPLY, "  "))
        self.assertIsNone(coerce_value({"key": "m", "label": "m", "type": "multi", "options": []}, []))


class RecordTest(unittest.TestCase):
    def test_partial_then_complete(self):
        data = clean_record(PROFILE, {"fields": {"canton": {"value": "Gualaceo"}, "users": {"value": "120", "estimated": "Sí"}}})
        progress = completeness("record", PROFILE, data)
        self.assertFalse(progress["complete"])
        self.assertEqual(progress["missing_required"], ["Agua"])
        self.assertEqual(progress["estimated"], 1)
        data["fields"]["supply_type"] = {"value": "potable", "estimated": False, "note": None}
        self.assertTrue(completeness("record", PROFILE, data)["complete"])

    def test_note_without_value_is_kept_and_estimated_needs_value(self):
        data = clean_record(PROFILE, {"fields": {"users": {"value": None, "estimated": True, "note": "Pedir al GAD"}}})
        self.assertEqual(data["fields"]["users"], {"value": None, "estimated": False, "note": "Pedir al GAD"})

    def test_unknown_field_is_an_error(self):
        with self.assertRaises(InvalidFormError):
            clean_record(PROFILE, {"fields": {"inventado": {"value": 1}}})


class TableTest(unittest.TestCase):
    def test_rows_required_columns_and_limits(self):
        data = clean_table(PRIORITIES, {"rows": [{"problem": "Fugas", "priority": "Alta", "families": "70"}, {"problem": "Morosidad"}, {}]})
        self.assertEqual(len(data["rows"]), 2)  # la fila vacia no cuenta
        progress = completeness("table", PRIORITIES, data)
        self.assertFalse(progress["complete"])
        self.assertIn("fila 2", progress["missing_required"][0])
        with self.assertRaises(InvalidFormError):
            clean_table(PRIORITIES, {"rows": [{"problem": str(i)} for i in range(4)]})
        with self.assertRaises(InvalidFormError):
            clean_table(PRIORITIES, {"rows": [{"problem": "x", "priority": "Urgentísima"}]})

    def test_empty_table_is_not_complete(self):
        self.assertFalse(completeness("table", PRIORITIES, {"rows": []})["complete"])


class CoverageTest(unittest.TestCase):
    def test_guide_coverage(self):
        stages = [{"code": "G1", "lists": [{"status": "done"}, {"status": "draft"}, {"status": "never"}, {"status": "ok"}]},
                  {"code": "G4", "lists": []}]
        cov = guide_coverage(stages)
        self.assertEqual(cov["G1"], {"total": 4, "started": 3, "complete": 2, "pct": 50.0})
        self.assertIsNone(cov["G4"]["pct"])


if __name__ == "__main__":
    unittest.main()
