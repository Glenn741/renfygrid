"""Pruebas puras de pack_engine -- sin BD (docs/04-plan-sprints.md SS11.4).
Las bandas de prueba son copia de las semillas de 0021_community_packs.sql;
los casos de cloro son las mediciones del ejemplo de la Guia 3 (15/07/2026)."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pack_engine import (  # noqa: E402
    InvalidAnswersError,
    InvalidInstrumentationError,
    InvalidRecordError,
    InvalidRuleError,
    RegisterWentDownError,
    check_register,
    checklist_status,
    chlorine_product_per_day,
    dosing_guard_codes,
    evaluate_bands,
    findings_from_answers,
    follow_up_schedule,
    interpret_lab_result,
    interpret_reading,
    log_entry_status,
    passport_rows,
    passport_summary,
    sampling_points_status,
    maturity_score,
    questionnaire_analysis,
    stage_summary,
    system_route,
    treatment_train,
    validate_answers,
    validate_bands,
    validate_follow_up_item_status,
    validate_product_status,
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


PRODUCTS = [
    {"pack_id": "P", "code": "G1-P01", "stage_code": "G1", "sort_order": 1, "title": "Ficha territorial"},
    {"pack_id": "P", "code": "G1-P02", "stage_code": "G1", "sort_order": 2, "title": "Mapa del sistema"},
    {"pack_id": "P", "code": "G2-P01", "stage_code": "G2", "sort_order": 1, "title": "Acta de asamblea"},
]
MILESTONES = [
    {"code": "D30", "sort_order": 2, "offset_days": 30, "label": "30 días", "review": "r30", "evidence": "e30"},
    {"code": "D7", "sort_order": 1, "offset_days": 7, "label": "7 días", "review": "r7", "evidence": "e7"},
    {"code": "D90", "sort_order": 3, "offset_days": 90, "label": "90 días", "review": "r90", "evidence": "e90"},
]


class PassportTests(unittest.TestCase):
    def test_unregistered_product_counts_as_pending(self):
        rows = passport_rows(PRODUCTS, {("P", "G1-P01"): {"status": "complete", "evidence": "Carpeta", "to_improvement_plan": False},
                                        ("P", "G2-P01"): {"status": "to_validate", "to_improvement_plan": True}})
        self.assertEqual([r["status"] for r in rows], ["complete", "pending", "to_validate"])
        self.assertEqual([r["registered"] for r in rows], [True, False, True])
        self.assertEqual(passport_summary(rows),
                         {"total": 3, "to_improvement_plan": 1, "complete": 1, "to_validate": 1, "pending": 1})

    def test_statuses_validated(self):
        validate_product_status("to_validate")
        validate_follow_up_item_status("not_done")
        with self.assertRaises(InvalidRecordError):
            validate_product_status("listo")
        with self.assertRaises(InvalidRecordError):
            validate_follow_up_item_status("maybe")


class FollowUpScheduleTests(unittest.TestCase):
    def test_dates_from_anchor_and_status(self):
        items = [{"milestone_code": "D7", "status": "done"}, {"milestone_code": "D7", "status": "pending"},
                 {"milestone_code": "D30", "status": "pending"}]
        reviews = {"D7": {"reviewed_on": "2026-09-08", "summary": "Carpeta ordenada"}}
        sched = follow_up_schedule(MILESTONES, date(2026, 9, 1), reviews, items, today=date(2026, 10, 5))
        self.assertEqual([m["code"] for m in sched], ["D7", "D30", "D90"], "orden del catalogo")
        self.assertEqual([m["due_date"] for m in sched], ["2026-09-08", "2026-10-01", "2026-11-30"])
        self.assertEqual([m["status"] for m in sched], ["reviewed", "due", "upcoming"])
        self.assertEqual(sched[1]["days_to_due"], -4)
        self.assertEqual([m["pending_items"] for m in sched], [1, 1, 0])

    def test_due_on_the_day(self):
        sched = follow_up_schedule(MILESTONES, date(2026, 9, 1), {}, [], today=date(2026, 9, 8))
        self.assertEqual(sched[0]["status"], "due")
        self.assertEqual(sched[0]["days_to_due"], 0)


# Bandas de 0030 (cloro): con accion y prioridad del hallazgo.
CHLORINE_D1 = [
    {"upper": 0.3, "upper_inclusive": False, "code": "low", "label": "Bajo", "severity": "alert",
     "finding_priority": "high", "action": "Revisar dosificador"},
    {"upper": 1.5, "upper_inclusive": True, "code": "adequate", "label": "Adecuado", "severity": "ok", "action": "Registrar"},
    {"upper": None, "code": "high", "label": "Alto", "severity": "alert", "finding_priority": "medium", "action": "Revisar dosis"},
]


class ReadingInterpretationTests(unittest.TestCase):
    def test_guide_example_15_07_2026(self):
        # Actividad participativa 4: 0,8 y 0,5 adecuado; 0,2 bajo.
        self.assertEqual(interpret_reading(CHLORINE_D1, 0.8)["code"], "adequate")
        self.assertFalse(interpret_reading(CHLORINE_D1, 0.5)["out_of_range"])
        low = interpret_reading(CHLORINE_D1, 0.2)
        self.assertEqual((low["code"], low["out_of_range"], low["finding_priority"], low["action"]),
                         ("low", True, "high", "Revisar dosificador"))

    def test_in_range_has_no_finding_priority(self):
        self.assertIsNone(interpret_reading(CHLORINE_D1, 1.0)["finding_priority"])

    def test_out_of_range_band_without_priority_is_incomplete_rule(self):
        incomplete = [dict(b) for b in CHLORINE_D1]
        del incomplete[2]["finding_priority"]
        with self.assertRaises(InvalidRuleError):
            interpret_reading(incomplete, 2.0)


class OperationLogTests(unittest.TestCase):
    def test_low_chlorine_or_turbid_water_forces_alert(self):
        self.assertEqual(log_entry_status("good", "alert", "clear"), "alert")
        self.assertEqual(log_entry_status(None, "ok", "turbid"), "alert")
        self.assertEqual(log_entry_status("good", "ok", "clear"), "good")
        self.assertEqual(log_entry_status(None, None, None), "good")
        self.assertEqual(log_entry_status("alert", "ok", "clear"), "alert", "el operador puede marcar alerta")

    def test_invalid_values_rejected(self):
        with self.assertRaises(InvalidRecordError):
            log_entry_status("regular", None, None)
        with self.assertRaises(InvalidRecordError):
            log_entry_status(None, None, "verde")


class SamplingPointsTests(unittest.TestCase):
    def test_due_by_own_or_kind_frequency(self):
        points = [
            {"point_id": "t", "kind_frequency_days": 1, "frequency_days": None},
            {"point_id": "m", "kind_frequency_days": None, "frequency_days": 7},
            {"point_id": "f", "kind_frequency_days": None, "frequency_days": None},
            {"point_id": "c", "kind_frequency_days": None, "frequency_days": 7},
        ]
        today = date(2026, 10, 5)
        last = {"t": date(2026, 10, 4), "m": date(2026, 10, 1), "f": date(2026, 9, 1)}
        rows = {r["point_id"]: r for r in sampling_points_status(points, last, today)}
        self.assertEqual(rows["t"]["status"], "due", "salida del tanque: cada dia")
        self.assertEqual(rows["m"]["status"], "ok")
        self.assertEqual(rows["m"]["days_since"], 4)
        self.assertEqual(rows["f"]["status"], "ok", "sin frecuencia: solo se informa")
        self.assertEqual(rows["c"]["status"], "never")
        last["t"] = today
        self.assertEqual(sampling_points_status(points[:1], last, today)[0]["status"], "ok")



class DosingTests(unittest.TestCase):
    def test_guide_table_section_3_5(self):
        # Tabla de la Guia 3 §3.5, hipoclorito al 65 %: (caudal, g/dia a 1,5 mg/L, g/dia a 2,0 mg/L).
        # La guia a veces trunca a un decimal (26,58 -> 26,5; 39,88 -> 39,8): tolerancia 0,1.
        table = [(0.1, 19.9, 26.5), (0.2, 39.8, 53.1), (0.5, 99.7, 132.9), (1.0, 199.4, 265.8), (2.0, 398.8, 531.7)]
        for flow, at_15, at_20 in table:
            self.assertAlmostEqual(chlorine_product_per_day(flow, 1.5, 65), at_15, delta=0.1)
            self.assertAlmostEqual(chlorine_product_per_day(flow, 2.0, 65), at_20, delta=0.1)
        self.assertAlmostEqual(chlorine_product_per_day(5.0, 1.5, 65), 997.0, delta=0.1)

    def test_invalid_inputs(self):
        for args in ((0, 1.5, 65), (0.1, 0, 65), (0.1, 1.5, 0), (0.1, 1.5, 120)):
            with self.assertRaises(InvalidRecordError):
                chlorine_product_per_day(*args)

    def test_guards(self):
        always = ["orientative", "verify_after", "safety"]
        self.assertEqual(dosing_guard_codes("disinfection", "adequate", True, False), always)
        self.assertEqual(dosing_guard_codes("disinfection", "high", True, True), ["turbid_water", "high_residual"] + always)
        self.assertEqual(dosing_guard_codes("disinfection", "low", False, False), ["low_residual", "no_reading_today"] + always)
        self.assertEqual(dosing_guard_codes("disinfection", None, False, False), ["no_reading_today"] + always)
        self.assertEqual(dosing_guard_codes("coagulation", "adequate", True, False), ["not_disinfectant", "safety"])


class RegisterTests(unittest.TestCase):
    def test_consumption_since_previous(self):
        self.assertEqual(check_register(100, 105.5, False), {"delta": 5.5, "went_down": False})
        self.assertEqual(check_register(None, 12, False), {"delta": None, "went_down": False})
        self.assertEqual(check_register(100, 100, False)["delta"], 0)

    def test_register_going_down_needs_confirmation(self):
        with self.assertRaises(RegisterWentDownError):
            check_register(100, 3, False)
        self.assertEqual(check_register(100, 3, True), {"delta": None, "went_down": True})

    def test_negative_rejected(self):
        with self.assertRaises(InvalidRecordError):
            check_register(None, -1, True)


# Tramos de E. coli de 0030 y un limite quimico de prueba (no es la norma).
E_COLI_D2 = [
    {"upper": 0, "upper_inclusive": True, "code": "absent", "label": "Ausente", "severity": "ok", "action": "Archivar"},
    {"upper": None, "code": "present", "label": "Presente", "severity": "critical", "finding_priority": "high", "action": "Alerta"},
]
LIMIT_TEST = [
    {"upper": 0.01, "upper_inclusive": True, "code": "ok", "label": "Cumple", "severity": "ok"},
    {"upper": None, "code": "over", "label": "No cumple", "severity": "alert", "finding_priority": "high"},
]


class LabResultTests(unittest.TestCase):
    def test_exact_values(self):
        self.assertEqual(interpret_lab_result(E_COLI_D2, 0, "=")["code"], "absent")
        present = interpret_lab_result(E_COLI_D2, 3, "=")
        self.assertEqual((present["severity"], present["finding_priority"]), ("critical", "high"))

    def test_below_detection_limit(self):
        self.assertEqual(interpret_lab_result(LIMIT_TEST, 0.005, "<")["code"], "ok", "<0,005 con limite 0,01: cumple")
        self.assertIsNone(interpret_lab_result(LIMIT_TEST, 0.05, "<"), "<0,05 con limite 0,01: no concluyente")

    def test_above_range(self):
        self.assertEqual(interpret_lab_result(LIMIT_TEST, 0.02, ">")["code"], "over")
        self.assertIsNone(interpret_lab_result(LIMIT_TEST, 0.001, ">"))

    def test_invalid(self):
        with self.assertRaises(InvalidRecordError):
            interpret_lab_result(LIMIT_TEST, 1, "~")
        with self.assertRaises(InvalidRecordError):
            interpret_lab_result(LIMIT_TEST, -1, "=")


if __name__ == "__main__":
    unittest.main()
