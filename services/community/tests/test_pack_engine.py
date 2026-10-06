"""Pruebas puras de pack_engine -- sin BD (docs/04-plan-sprints.md SS11.4).
Las bandas de prueba son copia de las semillas de 0021_community_packs.sql;
los casos de cloro son las mediciones del ejemplo de la Guia 3 (15/07/2026)."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pack_engine import (  # noqa: E402
    InvalidAnswersError,
    InvalidInstrumentationError,
    InvalidRuleError,
    checklist_status,
    evaluate_bands,
    findings_from_answers,
    maturity_score,
    questionnaire_analysis,
    stage_summary,
    system_route,
    treatment_train,
    validate_answers,
    validate_bands,
    validate_instrumentation,
    validate_run_context,
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


def _mc(key: str, guide: str, dimension: str, correct: str) -> dict:
    return {"key": key, "text": key, "groups": {"guide": guide, "dimension": dimension},
            "options": [{"code": c, "label": c, "score": 2 if c == correct else 0} for c in "abc"]}


# Recorte de la CAP de la Guia 7 (T-04/T-05): dos guias x dos dimensiones,
# clave 2 puntos / 0 puntos, rangos Alto 80 / Medio 50 / Bajo 0.
QUESTIONNAIRE = {
    "id": "Q-TEST", "kind": "questionnaire", "scale": [],
    "items": [_mc("q1", "G1", "knowledge", "b"), _mc("q2", "G1", "attitude", "b"),
              _mc("q3", "G2", "knowledge", "a"), _mc("q4", "G2", "attitude", "b")],
    "run_fields": [
        {"key": "moment", "label": "Momento", "required": True,
         "options": [{"code": "initial", "label": "Inicial"}, {"code": "final", "label": "Final"}]},
        {"key": "participant_code", "label": "Código de participante", "required": True},
    ],
    "analysis": {
        "compare_by": "moment",
        "compare": [{"code": "initial", "label": "Inicial"}, {"code": "final", "label": "Final"}],
        "group_by": [{"key": "guide", "label": "Guía", "values": [{"code": "G1", "label": "Guía 1"}, {"code": "G2", "label": "Guía 2"}]},
                     {"key": "dimension", "label": "Dimensión",
                      "values": [{"code": "knowledge", "label": "Conocimientos"}, {"code": "attitude", "label": "Actitudes"}]}],
        "levels": [{"min_pct": 80, "label": "Alto"}, {"min_pct": 50, "label": "Medio"}, {"min_pct": 0, "label": "Bajo"}],
    },
}


def _answers(**codes: str) -> list[dict]:
    return [{"item_key": k, "answer_code": v} for k, v in codes.items()]


class QuestionnaireTests(unittest.TestCase):
    def test_item_options_are_the_scale(self):
        validate_answers(QUESTIONNAIRE, _answers(q1="a", q2="b", q3="c", q4="b"))
        with self.assertRaises(InvalidAnswersError):
            validate_answers(QUESTIONNAIRE, _answers(q1="yes", q2="b", q3="c", q4="b"))

    def test_key_scores_two_points_only_for_expected_option(self):
        score = maturity_score(QUESTIONNAIRE, _answers(q1="b", q2="a", q3="a", q4="c"))
        self.assertEqual(score, {"score": 4, "max_score": 8, "pct": 50.0})

    def test_questionnaire_creates_no_findings(self):
        self.assertEqual(findings_from_answers(QUESTIONNAIRE, _answers(q1="a", q2="a", q3="b", q4="a")), [])

    def test_run_context_required_and_options_checked(self):
        ok = validate_run_context(QUESTIONNAIRE, {"moment": "initial", "participant_code": "  P-01 "})
        self.assertEqual(ok, {"moment": "initial", "participant_code": "P-01"})
        with self.assertRaises(InvalidAnswersError):
            validate_run_context(QUESTIONNAIRE, {"moment": "initial"})
        with self.assertRaises(InvalidAnswersError):
            validate_run_context(QUESTIONNAIRE, {"moment": "midterm", "participant_code": "P-01"})
        with self.assertRaises(InvalidAnswersError):
            validate_run_context(QUESTIONNAIRE, {"moment": "final", "participant_code": "P-01", "extra": "x"})

    def test_list_without_run_fields_accepts_empty_context(self):
        self.assertEqual(validate_run_context(INSPECTION, None), {})

    def test_analysis_by_group_moment_and_level(self):
        runs = [
            {"context": {"moment": "initial", "participant_code": "P1"}, "answers": _answers(q1="a", q2="b", q3="b", q4="a")},
            {"context": {"moment": "initial", "participant_code": "P2"}, "answers": _answers(q1="b", q2="b", q3="b", q4="a")},
            {"context": {"moment": "final", "participant_code": "P1"}, "answers": _answers(q1="b", q2="b", q3="a", q4="b")},
            {"context": {"moment": "final", "participant_code": "P2"}, "answers": _answers(q1="b", q2="b", q3="a", q4="a")},
        ]
        report = questionnaire_analysis(QUESTIONNAIRE, runs)
        guide = {r["code"]: r for r in report["groupings"][0]["rows"]}
        # G1 inicial: P1 2/4, P2 4/4 -> promedio 3/4 = 75 % (Medio); final 4/4 = 100 % (Alto).
        self.assertEqual(guide["G1"]["moments"]["initial"], {"n": 2, "avg_score": 3.0, "max_score": 4, "pct": 75.0, "level": "Medio"})
        self.assertEqual(guide["G1"]["moments"]["final"]["level"], "Alto")
        self.assertEqual(guide["G1"]["difference_pct"], 25.0)
        # G2 inicial 0 % (Bajo), final (4 + 2) / 2 = 3/4 = 75 %.
        self.assertEqual(guide["G2"]["moments"]["initial"]["level"], "Bajo")
        self.assertEqual(guide["G2"]["difference_pct"], 75.0)
        self.assertEqual(report["total"]["moments"]["final"]["pct"], 87.5)
        self.assertEqual(report["participants"], {"initial": 2, "final": 2})
        self.assertEqual([r["code"] for r in report["groupings"][1]["rows"]], ["knowledge", "attitude"], "orden de la guia")

    def test_analysis_without_final_has_no_difference(self):
        runs = [{"context": {"moment": "initial", "participant_code": "P1"}, "answers": _answers(q1="b", q2="b", q3="a", q4="b")}]
        report = questionnaire_analysis(QUESTIONNAIRE, runs)
        self.assertEqual(report["total"]["moments"]["final"]["n"], 0)
        self.assertIsNone(report["total"]["difference_pct"])

    def test_list_without_analysis_rejected(self):
        with self.assertRaises(InvalidAnswersError):
            questionnaire_analysis(INSPECTION, [])


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


NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)


class ChecklistStatusTests(unittest.TestCase):
    def test_never_applied(self):
        self.assertEqual(checklist_status(30, None, NOW)["status"], "never")

    def test_applied_without_frequency_is_done(self):
        self.assertEqual(checklist_status(None, NOW - timedelta(days=400), NOW)["status"], "done")

    def test_within_frequency_is_ok_with_days_left(self):
        s = checklist_status(90, NOW - timedelta(days=30), NOW)
        self.assertEqual((s["status"], s["days_to_due"]), ("ok", 60))

    def test_past_frequency_is_overdue_with_negative_days(self):
        s = checklist_status(30, NOW - timedelta(days=35), NOW)
        self.assertEqual((s["status"], s["days_to_due"]), ("overdue", -5))

    def test_half_day_late_counts_as_one_day(self):
        self.assertEqual(checklist_status(30, NOW - timedelta(days=30, hours=12), NOW)["days_to_due"], -1)

    def test_stage_summary_counts(self):
        lists = [{"status": "never"}, {"status": "ok"}, {"status": "overdue"}, {"status": "done"}]
        self.assertEqual(stage_summary(lists), {"total": 4, "never": 1, "done": 1, "ok": 1, "overdue": 1, "applied": 3})


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
