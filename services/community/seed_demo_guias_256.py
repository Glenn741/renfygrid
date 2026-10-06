"""Respuestas de DEMOSTRACION de las listas de las Guias 2, 5 y 6 (migracion
0024) para una junta demo que ya tiene las Guias 3 y 4 cargadas
(`seed_demo_guias_tenant.py`), a pedido del usuario 2026-10-05. Historia
ilustrativa coherente con la de Gualaceo:
  G2 (hace ~70 dias): AUA vencida, reglamento interno desactualizado, padron
     sin las conexiones nuevas, tarifa sin sustento.
  G5 (hace ~40 dias): ganado y fumigacion cerca de la zona de recarga,
     descarga de la quesera, campanas de higiene pendientes.
  G6 (ultimos 14 dias): consolidado y diagnostico listos; plan, presupuesto
     y tablero pendientes. La lista de presentacion formal queda SIN aplicar
     a proposito: la junta todavia no llega a esa etapa.
Fechas en el pasado, mismo criterio que las otras semillas demo. Si el tenant
ya aplico la verificacion inicial de la Guia 2, no hace nada.

Uso:
    python seed_demo_guias_256.py "<DSN>" "<TENANT_ID>"
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from seed_demo_guias_tenant import NOW, _run  # noqa: E402


def due(days: int) -> str:
    return (NOW + timedelta(days=days)).date().isoformat()


def ans(key: str, code: str, observation: str | None = None, action: str | None = None,
        responsible: str | None = None, due_days: int | None = None) -> dict:
    a = {"item_key": key, "answer_code": code}
    if observation:
        a["observation"] = observation
    if action:
        a["action"] = action
    if responsible:
        a["responsible"] = responsible
    if due_days is not None:
        a["due_date"] = due(due_days)
    return a


def main(dsn: str, tenant_id: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM checklist_run WHERE tenant_id = %s AND template_id = 'MA-G2-START'",
                                (tenant_id,))
                    if cur.fetchone()[0] > 0:
                        print("La junta ya tiene la Guía 2 aplicada -- no se modifica.")
                        return

        def run(template_id: str, answers: list[dict], days_ago: int, notes: str) -> None:
            _run(conn, tenant_id, template_id, answers, NOW - timedelta(days=days_ago), notes)

        # ── Guia 2 · Gobernanza ───────────────────────────────────────────
        run("MA-G2-START", [
            ans("knows_who_decides", "yes"), ans("roles_known", "somewhat"), ans("legal_basics", "yes"),
            ans("aua_current", "no"), ans("yearly_accountability", "yes"), ans("knows_first_procedure", "no"),
        ], 75, "Verificación inicial al iniciar el taller de la Guía 2.")
        run("MA-G2-7B", [
            ans("call_complete", "yes"), ans("call_published", "yes"),
            ans("roll_signed", "missing", "El padrón usado en la asamblea no tenía firma de secretaría.",
                "Fechar y firmar el padrón antes de cada asamblea.", "Secretaría", 10),
            ans("quorum_checked", "yes"),
            ans("agreements_owned", "missing", "Dos acuerdos quedaron sin responsable ni plazo.",
                "Anotar responsable y plazo en cada acuerdo del acta.", "Secretaría", 10),
            ans("minutes_signed", "yes"),
        ], 70, "Simulacro de asamblea (actividad participativa 2).")
        run("MA-G2-7C", [
            ans("legal_personality", "yes"), ans("bylaws_current", "yes"),
            ans("internal_rules", "missing", "El reglamento interno es de 2012 y no incluye la escala de morosidad.",
                "Actualizar el reglamento y aprobarlo en asamblea.", "Directiva", 60),
            ans("board_registered", "unknown", "No se sabe si la directiva elegida este año quedó registrada en el MAE.",
                "Consultar el registro en el MAE.", "Presidencia", 20),
            ans("aua_current", "missing", "La autorización de uso del agua de la vertiente está vencida.",
                "Iniciar la renovación de la AUA ante el MAE.", "Presidencia", 30),
            ans("user_roll_updated", "missing", "El padrón no incluye cuatro conexiones nuevas del sector bajo.",
                "Actualizar el padrón con las conexiones nuevas y suspendidas.", "Secretaría", 15),
            ans("minutes_book", "yes"),
            ans("technical_archive", "missing", "No se encuentran los planos originales del sistema.",
                "Pedir copia de los planos al GAD municipal.", "Presidencia", 45),
            ans("budget_poa_approved", "missing", None, "Preparar POA y presupuesto para la asamblea.", "Tesorería", 40),
            ans("tariff_reviewed", "missing", "La tarifa de USD 3 no tiene sustento técnico.",
                "Calcular la tarifa con costos reales (Guía 4).", "Tesorería", 40),
            ans("accountability_presented", "yes"),
            ans("claims_register", "unknown", "Los reclamos se reciben de palabra; no hay registro.",
                "Abrir un cuaderno o registro de reclamos.", "Secretaría", 15),
        ], 68, "Revisión del archivo de la junta (actividad participativa 3).")
        run("MA-G2-7H", [
            ans("org_chart", "ready"), ans("assembly_minutes", "ready"), ans("legal_diagnosis", "ready"),
            ans("user_roll", "pending", "Falta incorporar las conexiones nuevas del sector bajo."),
            ans("update_route", "ready"), ans("alliance_proposal", "ready"),
            ans("transparency_plan", "pending", "Falta acordar cada cuánto se informa a la comunidad."),
            ans("governance_plan", "ready"),
            ans("adapted_models", "pending", "Falta adaptar el modelo de informe de rendición de cuentas."),
        ], 65, "Cierre del taller de la Guía 2.")

        # ── Guia 5 · Ambiente y WASH ──────────────────────────────────────
        run("MA-G5-START", [
            ans("knows_source", "yes"), ans("source_protected", "somewhat"), ans("home_treatment", "somewhat"),
            ans("handwashing", "somewhat"), ans("campaigns_done", "no"), ans("knows_diseases", "no"),
        ], 45, "Verificación inicial al iniciar el taller de la Guía 5.")
        run("MA-G5-5A", [
            ans("intake_fenced", "yes"),
            ans("protection_zone_clear", "in_progress", "Ganado sube a pastar en la zona alta de la microcuenca.",
                "Acordar con las familias un potrero alternativo.", "Directiva", 30),
            ans("native_reforestation", "in_progress", "Se sembraron 200 plantas nativas en la zona de recarga; faltan 300.",
                "Segunda minga de reforestación.", "Directiva y comunidad", 60),
            ans("no_agrochemicals", "no", "Cultivos de maíz con fumigación a menos de 100 m de la vertiente.",
                "Acordar una zona sin pesticidas y pedir apoyo al GAD.", "Presidencia", 30),
            ans("no_waste_burning", "yes"),
            ans("community_vigilance", "in_progress", None, "Turnos de vigilancia por sector.", "Vocal", 20),
        ], 40, "Recorrido por la fuente y la microcuenca.")
        run("MA-G5-5B", [
            ans("users_treat_water", "in_progress", None, "Repetir la demostración de agua segura en cada sector.", "Operador/a", 30),
            ans("covered_containers", "in_progress", "En el sector alto varias familias guardan agua destapada.",
                "Visitas casa por casa con la campaña.", "Promotora de salud", 30),
            ans("household_sanitation", "yes"),
            ans("no_discharge_to_streams", "no", "La quesera y dos viviendas del sector bajo descargan a la quebrada.",
                "Notificar a la quesera y coordinar con el GAD.", "Directiva", 15),
            ans("septic_far_from_sources", "yes"),
            ans("sanitation_maintained", "in_progress", None, "Programar la extracción de lodos de la fosa comunal.", "Tesorería", 25),
        ], 38, "Revisión de agua segura y saneamiento.")
        run("MA-G5-5C", [
            ans("handwashing_campaigns", "no", None, "Campaña de lavado de manos en la escuela.", "Promotora de salud", 20),
            ans("school_water_soap", "yes"),
            ans("families_know_dci", "no", None, "Charla con el centro de salud sobre agua, diarrea y DCI.", "Presidencia", 30),
            ans("quality_alerts_communicated", "in_progress", "Las alertas de cloro bajo solo llegan a la directiva.",
                "Avisar a la comunidad por WhatsApp.", "Secretaría", 10),
            ans("food_washed_safe_water", "in_progress"),
            ans("animals_out_of_kitchen", "no", "En varias casas los cuyes y gallinas están en la cocina.",
                "Incluir el tema en las visitas de la campaña.", "Promotora de salud", 30),
        ], 36, "Revisión de higiene y salud.")
        run("MA-G5-WASH", [
            ans("intake_protected", "4"),
            ans("waste_near_source", "3", "Algo de basura en el camino de acceso a la captación."),
            ans("animals_near_water", "2", "Ganado cerca de la quebrada en la zona alta.", "Cercar el tramo de la quebrada.", "Directiva", 45),
            ans("stored_water_covered", "3", "La mitad de las familias visitadas tapan el agua."),
            ans("handwashing", "2", "No se practica en los momentos críticos.", "Campaña de lavado de manos.", "Promotora de salud", 20),
            ans("wastewater_management", "2", "Descargas de la quesera a la red y a la quebrada.", "Tratamiento previo de la quesera.", "Directiva", 30),
        ], 35, "Ficha de diagnóstico ambiental y WASH.")
        run("MA-G5-HOME", [
            ans("boil", "yes"),
            ans("chlorinate", "no", "Las familias no conocen la dosis de gotas según el producto."),
            ans("filter_turbid", "yes"), ans("store_covered", "yes"),
        ], 33, "Demostración de agua segura en el hogar.")
        run("MA-G5-PRODUCTS", [
            ans("watershed_map", "complete"), ans("protection_actions", "complete"), ans("safe_water_demo", "complete"),
            ans("handwashing_practice", "complete"),
            ans("campaign_plan", "pending", "Falta definir responsables y fechas de la campaña escolar."),
        ], 30, "Cierre del taller de la Guía 5.")

        # ── Guia 6 · Plan de Mejora ───────────────────────────────────────
        run("MA-G6-START", [
            ans("has_products_g1_g5", "somewhat"), ans("knows_valid_data", "somewhat"), ans("knows_problems_causes", "yes"),
            ans("compares_alternatives", "no"), ans("goal_and_indicator", "no"), ans("knows_approval", "no"),
        ], 14, "Verificación inicial al iniciar el taller de la Guía 6.")
        req_yes = {"technical_memory", "surveys_user_roll", "water_quality_analysis", "legal_documentation",
                   "community_socialization", "community_minutes"}
        req_na = {"soil_studies": "La mejora de la red no requiere obra civil mayor.",
                  "materials_debris_plan": "No aplica para el cambio de tramos de tubería.",
                  "knowledge_transfer": "No hay tecnología nueva que transferir."}
        req_notes = {"enabling_documents": "La AUA está vencida; renovación en trámite.",
                     "tariff_study": "Pendiente del cálculo de tarifa de la Guía 4.",
                     "om_manual": "Existe el plan mínimo de O&M; falta el manual completo.",
                     "project_budget": "Cotizaciones solicitadas a dos proveedores."}
        reqs = ["environmental_regularization", "enabling_documents", "technical_memory", "surveys_user_roll",
                "water_quality_analysis", "soil_studies", "topography", "technical_calculations", "project_budget",
                "technical_specifications", "socioeconomic_study", "project_plans", "legal_documentation",
                "community_socialization", "community_minutes", "management_model", "community_development_plan",
                "tariff_study", "om_manual", "materials_debris_plan", "risk_management", "occupational_safety",
                "knowledge_transfer", "environmental_impacts", "executive_summary"]
        run("MA-G6-7F", [
            ans(k, "yes") if k in req_yes else ans(k, "na", req_na[k]) if k in req_na else ans(k, "no", req_notes.get(k))
            for k in reqs
        ], 10, "Requisitos del proyecto prioritario: mejoramiento de la red y reducción de pérdidas del sector alto.")
        run("MA-G6-7H", [
            ans("consolidated_inputs", "complete"), ans("diagnosis_prioritization", "complete"),
            ans("selected_alternatives", "complete"),
            ans("improvement_plan", "pending", "Falta completar metas e indicadores de dos componentes."),
            ans("budget_schedule", "pending", "Esperando cotizaciones."),
            ans("project_profile", "complete"),
            ans("tracking_board", "pending", "Se arma después de aprobar el plan."),
            ans("approval_minutes", "pending", "Asamblea de aprobación prevista para el próximo mes."),
            ans("requirements_checklist", "complete"),
        ], 7, "Avance del Plan de Mejora.")
        print("Listo: 4 listas de la Guía 2, 7 de la Guía 5 y 3 de la Guía 6 aplicadas (presentación formal sin aplicar).")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
