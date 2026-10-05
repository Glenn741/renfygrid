"""Pruebas puras de pack_engine -- sin BD (docs/04-plan-sprints.md SS11.4).
Las bandas de prueba son copia de las semillas de 0021_community_packs.sql;
los casos de cloro son las mediciones del ejemplo de la Guia 3 (15/07/2026)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pack_engine import (  # noqa: E402
    InvalidAnswersError,
    InvalidInstrumentationError,
    InvalidRuleError,
    evaluate_bands,
    findings_from_answers,
    maturity_score,
    system_route,
    treatment_train,
    validate_answers,
    validate_bands,
    validate_instrumentation,
)

CHLORINE = [
    {"upper": 0.3, "upper_inclusive": False, "code": "low", "label": "Bajo", "severity": "alert"},
    {"upper": 1.5, "upper_inclusive": True, "code": "adequate", "label": "Adecuado", "severity": "ok"},
    {"upper": None, "code": "high", "label": "Alto", "severity": "alert"},
]
E_COLI = [
    {"upper": 0, "upper_inclusive": True, "code": "absent", "label": "Ausente", "severity": "ok"},
    {"upper": None, "code": "present", "label": "Presente", "severity": "critical"},
]
PH = [
    {"upper": 6.5, "upper_inclusive": False, "code": "low", "label": "Bajo", "severity": "alert"},
    {"upper": 8.5, "upper_inclusive": True, "code": "adequate", "label": "Adecuado", "severity": "ok"},
    {"upper": None, "code": "high", "label": "Alto", "severity": "alert"},
]

INSPECTION = {
    "id": "TEST-7A",
    "scale": [
        {"code": "yes", "label": "Sí", "finding": False, "score": 2},
        {"code": "in_progress", "label": "En proceso", "finding": True, "finding_priority": "medium", "score": 1},
        {"code": "no", "label": "No", "finding": True, "finding_priority": "high", "score": 0},
    ],
    "items": [
        {"key": "intake_condition", "text": "La captación tiene tapa, cerco y rejilla en buen estado."},
        {"key": "doser_works", "text": "El dosificador funciona y se controla."},
        {"key": "tank_sealed", "text": "El reservorio tiene tapa sellada y no presenta grietas."},
    ],
}


class EvaluateBandsTests(unittest.TestCase):
    def test_guide_example_readings(self):
        self.assertEqual(evaluate_bands(CHLORINE, 0.8)["code"], "adequate")
        self.assertEqual(evaluate_bands(CHLORINE, 0.5)["code"], "adequate")
        self.assertEqual(evaluate_bands(CHLORINE, 0.2)["code"], "low")

    def test_exclusive_lower_limit(self):
        self.assertEqual(evaluate_bands(CHLORINE, 0.29)["code"], "low")
        self.assertEqual(evaluate_bands(CHLORINE, 0.3)["code"], "adequate")

    def test_inclusive_upper_limit(self):
        self.assertEqual(evaluate_bands(CHLORINE, 1.5)["code"], "adequate")
        self.assertEqual(evaluate_bands(CHLORINE, 1.51)["code"], "high")

    def test_result_carries_label_and_severity(self):
        self.assertEqual(evaluate_bands(CHLORINE, 0.2), {"code": "low", "label": "Bajo", "severity": "alert"})

    def test_e_coli_presence_is_critical(self):
        self.assertEqual(evaluate_bands(E_COLI, 0)["code"], "absent")
        self.assertEqual(evaluate_bands(E_COLI, 1)["severity"], "critical")

    def test_ph_both_sides(self):
        self.assertEqual(evaluate_bands(PH, 6.4)["code"], "low")
        self.assertEqual(evaluate_bands(PH, 7.2)["code"], "adequate")
        self.assertEqual(evaluate_bands(PH, 9)["code"], "high")


class ValidateBandsTests(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(InvalidRuleError):
            validate_bands([])

    def test_last_band_must_be_open(self):
        with self.assertRaises(InvalidRuleError):
            validate_bands([{"upper": 1, "code": "a", "label": "A", "severity": "ok"}])

    def test_limits_must_grow(self):
        bands = [
            {"upper": 2, "code": "a", "label": "A", "severity": "ok"},
            {"upper": 1, "code": "b", "label": "B", "severity": "ok"},
            {"upper": None, "code": "c", "label": "C", "severity": "ok"},
        ]
        with self.assertRaises(InvalidRuleError):
            validate_bands(bands)

    def test_band_needs_code_label_severity(self):
        with self.assertRaises(InvalidRuleError):
            validate_bands([{"upper": None, "code": "a"}])


class ValidateAnswersTests(unittest.TestCase):
    def _all(self, code="yes"):
        return [{"item_key": i["key"], "answer_code": code} for i in INSPECTION["items"]]

    def test_complete_answers_pass(self):
        validate_answers(INSPECTION, self._all())

    def test_missing_item_rejected(self):
        with self.assertRaises(InvalidAnswersError):
            validate_answers(INSPECTION, self._all()[:2])

    def test_unknown_item_rejected(self):
        answers = self._all() + [{"item_key": "invented", "answer_code": "yes"}]
        with self.assertRaises(InvalidAnswersError):
            validate_answers(INSPECTION, answers)

    def test_duplicate_item_rejected(self):
        answers = self._all() + [{"item_key": "doser_works", "answer_code": "no"}]
        with self.assertRaises(InvalidAnswersError):
            validate_answers(INSPECTION, answers)

    def test_code_outside_scale_rejected(self):
        answers = self._all()
        answers[0]["answer_code"] = "maybe"
        with self.assertRaises(InvalidAnswersError):
            validate_answers(INSPECTION, answers)


class FindingsFromAnswersTests(unittest.TestCase):
    def test_only_flagged_answers_create_findings_with_scale_priority(self):
        answers = [
            {"item_key": "intake_condition", "answer_code": "yes"},
            {"item_key": "doser_works", "answer_code": "in_progress", "observation": "Gotea de forma irregular"},
            {"item_key": "tank_sealed", "answer_code": "no", "action": "Sellar grieta", "responsible": "Operador/a"},
        ]
        findings = findings_from_answers(INSPECTION, answers)
        self.assertEqual([f["item_key"] for f in findings], ["doser_works", "tank_sealed"])
        self.assertEqual(findings[0]["priority"], "medium")
        self.assertEqual(findings[1]["priority"], "high")
        self.assertEqual(
            findings[0]["description"],
            "El dosificador funciona y se controla. — En proceso. Gotea de forma irregular",
        )
        self.assertEqual(findings[1]["action"], "Sellar grieta")

    def test_scale_without_priority_is_rejected(self):
        template = {**INSPECTION, "scale": [{"code": "no", "label": "No", "finding": True, "score": 0}]}
        with self.assertRaises(InvalidAnswersError):
            findings_from_answers(template, [{"item_key": "doser_works", "answer_code": "no"}])


class MaturityScoreTests(unittest.TestCase):
    def test_score_over_best_possible(self):
        answers = [
            {"item_key": "intake_condition", "answer_code": "yes"},
            {"item_key": "doser_works", "answer_code": "in_progress"},
            {"item_key": "tank_sealed", "answer_code": "no"},
        ]
        self.assertEqual(maturity_score(INSPECTION, answers), {"score": 3, "max_score": 6, "pct": 50.0})


COMPONENT_TYPES = [
    {"code": "intake", "label": "Captación", "service": "water", "stage_order": 20, "is_treatment_stage": False},
    {"code": "sand_trap", "label": "Desarenador", "service": "water", "stage_order": 30, "is_treatment_stage": True},
    {"code": "filtration", "label": "Filtración", "service": "water", "stage_order": 90, "is_treatment_stage": True},
    {"code": "disinfection", "label": "Desinfección", "service": "water", "stage_order": 100, "is_treatment_stage": True},
    {"code": "tank", "label": "Reservorio o tanque", "service": "water", "stage_order": 110, "is_treatment_stage": False},
    {"code": "valve", "label": "Válvula", "service": "water", "stage_order": None, "is_treatment_stage": False},
    {"code": "inspection_box", "label": "Caja de revisión", "service": "sanitation", "stage_order": 30, "is_treatment_stage": False},
]

ASSETS = [
    {"asset_id": "a-tank", "type": "tank", "status": "operational"},
    {"asset_id": "a-intake", "type": "intake", "status": "operational"},
    {"asset_id": "a-sand", "type": "sand_trap", "status": "operational"},
    {"asset_id": "a-filter", "type": "filtration", "status": "maintenance"},
    {"asset_id": "a-valve", "type": "valve", "status": "operational"},
    {"asset_id": "a-box", "type": "inspection_box", "status": "out_of_service"},
]


class SystemRouteTests(unittest.TestCase):
    def test_stages_ordered_and_accessories_apart(self):
        route = system_route(COMPONENT_TYPES, ASSETS)
        self.assertEqual([s["type"] for s in route["services"]["water"]], ["intake", "sand_trap", "filtration", "tank"])
        self.assertEqual([s["type"] for s in route["services"]["sanitation"]], ["inspection_box"])
        self.assertEqual([s["type"] for s in route["accessories"]], ["valve"])


class TreatmentTrainTests(unittest.TestCase):
    def test_every_stage_listed_even_if_missing(self):
        findings = [{"finding_id": "f1", "asset_id": "a-filter", "description": "No recibe retrolavado", "priority": "high"}]
        rows = treatment_train(COMPONENT_TYPES, ASSETS, findings)
        self.assertEqual([r["type"] for r in rows], ["sand_trap", "filtration", "disinfection"])
        sand, filt, disinf = rows
        self.assertTrue(sand["exists"])
        self.assertTrue(sand["works"])
        self.assertFalse(filt["works"])
        self.assertEqual(filt["open_findings"][0]["finding_id"], "f1")
        self.assertFalse(disinf["exists"])
        self.assertIsNone(disinf["works"])


class InstrumentationTests(unittest.TestCase):
    def test_valid_levels_pass(self):
        validate_instrumentation({"metering": "basic", "quality": "intermediate"})

    def test_unknown_module_rejected(self):
        with self.assertRaises(InvalidInstrumentationError):
            validate_instrumentation({"teleporting": "basic"})

    def test_unknown_level_rejected(self):
        with self.assertRaises(InvalidInstrumentationError):
            validate_instrumentation({"metering": "expert"})


if __name__ == "__main__":
    unittest.main()
