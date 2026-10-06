-- RenfyGrid -- 0043_facilitation_tools.sql
-- Track D, D12.2 (2026-10-06): herramientas del programa de facilitacion de
-- la Guia 7 de Municipios Azules que faltaban.
--   T-06 Evaluacion diaria: "Conocer aprendizajes, calidad de facilitacion y
--        necesidad de refuerzo. Al cierre de cada jornada." Sí / Más o menos /
--        No por enunciado, dos preguntas abiertas.
--   T-08 Rubrica de microfacilitacion: "Dar retroalimentacion concreta a la
--        practica de facilitacion. Dia 8." Logrado / En proceso / Por
--        reforzar con observacion especifica; fortaleza, ajuste y proximo paso.
--   T-10 Consolidado de observaciones para mejora: "Priorizar cambios de
--        contenido, metodologia, formato o referencias de las seis guias."
--        Guia, hallazgo, fuente (aplicacion / CAP / seguimiento), cambio
--        propuesto, prioridad, responsable de revision, estado.
-- T-06 y T-08 son listas del paquete (tipos ya genericos: cuestionario con
-- analisis por momento, autoevaluacion con observacion por item). T-10 es una
-- tabla por organizacion: la usa el programa o la agrupacion que facilita.

INSERT INTO checklist_template (id, pack_id, kind, title, purpose, scale, items, stage_code, run_fields, analysis) VALUES
('MA-T06', 'EC-MUNICIPIOS-AZULES', 'questionnaire', 'T-06. Evaluación diaria',
 'Conocer aprendizajes, calidad de facilitación y necesidad de refuerzo. Se aplica al cierre de cada jornada; una respuesta por participante.',
 '[]',
 '[{"key": "learn_explain", "text": "Puedo explicar la idea principal de la jornada.", "groups": {"type": "learning"},
    "options": [{"code": "yes", "label": "Sí", "score": 2}, {"code": "partly", "label": "Más o menos", "score": 1}, {"code": "no", "label": "No", "score": 0}]},
   {"key": "learn_tool", "text": "Puedo usar al menos una herramienta trabajada.", "groups": {"type": "learning"},
    "options": [{"code": "yes", "label": "Sí", "score": 2}, {"code": "partly", "label": "Más o menos", "score": 1}, {"code": "no", "label": "No", "score": 0}]},
   {"key": "fac_clear", "text": "Las explicaciones fueron claras y respetuosas.", "groups": {"type": "facilitation"},
    "options": [{"code": "yes", "label": "Sí", "score": 2}, {"code": "partly", "label": "Más o menos", "score": 1}, {"code": "no", "label": "No", "score": 0}]},
   {"key": "fac_participation", "text": "Las actividades permitieron participar y practicar.", "groups": {"type": "facilitation"},
    "options": [{"code": "yes", "label": "Sí", "score": 2}, {"code": "partly", "label": "Más o menos", "score": 1}, {"code": "no", "label": "No", "score": 0}]},
   {"key": "app_useful", "text": "El producto construido es útil para la JAAPS.", "groups": {"type": "application"},
    "options": [{"code": "yes", "label": "Sí", "score": 2}, {"code": "partly", "label": "Más o menos", "score": 1}, {"code": "no", "label": "No", "score": 0}]}]',
 'INT',
 '[{"key": "day", "label": "Jornada", "required": true, "options": [{"code": "D1", "label": "Día 1"}, {"code": "D2", "label": "Día 2"}, {"code": "D3", "label": "Día 3"}, {"code": "D4", "label": "Día 4"}, {"code": "D5", "label": "Día 5"}, {"code": "D6", "label": "Día 6"}, {"code": "D7", "label": "Día 7"}, {"code": "D8", "label": "Día 8"}]},
   {"key": "facilitator", "label": "Persona facilitadora"},
   {"key": "to_clarify", "label": "¿Qué debemos aclarar o practicar en la próxima jornada?"},
   {"key": "most_useful", "label": "¿Qué actividad fue más útil y por qué?"}]',
 '{"source": "Guía 7, T-06 · Evaluación diaria", "compare_by": "day",
   "compare": [{"code": "D1", "label": "Día 1"}, {"code": "D2", "label": "Día 2"}, {"code": "D3", "label": "Día 3"}, {"code": "D4", "label": "Día 4"}, {"code": "D5", "label": "Día 5"}, {"code": "D6", "label": "Día 6"}, {"code": "D7", "label": "Día 7"}, {"code": "D8", "label": "Día 8"}],
   "group_by": [{"key": "type", "label": "Tipo", "values": [{"code": "learning", "label": "Aprendizaje"}, {"code": "facilitation", "label": "Facilitación"}, {"code": "application", "label": "Aplicación"}]}],
   "note": "Una jornada con aprendizaje o facilitación baja indica qué reforzar al día siguiente. Lea también las respuestas abiertas de esa jornada."}'),

('MA-T08', 'EC-MUNICIPIOS-AZULES', 'self_assessment', 'T-08. Rúbrica de microfacilitación',
 'Dar retroalimentación concreta a la práctica de facilitación (Día 8 y formación de personas facilitadoras). Debe centrarse en conductas observables y oportunidades de mejora; anote una observación específica por criterio.',
 '[{"code": "achieved", "label": "Logrado", "score": 2, "finding": false}, {"code": "in_progress", "label": "En proceso", "score": 1, "finding": false},
   {"code": "reinforce", "label": "Por reforzar", "score": 0, "finding": false, "ask_note": true}]',
 '[{"key": "purpose", "text": "Explica propósito y producto esperado"},
   {"key": "experience", "text": "Parte de la experiencia del grupo"},
   {"key": "language", "text": "Usa lenguaje claro y define términos"},
   {"key": "participation", "text": "Promueve participación equilibrada"},
   {"key": "dynamic", "text": "Aplica una dinámica con propósito"},
   {"key": "technical", "text": "Mantiene precisión técnica y reconoce límites"},
   {"key": "time", "text": "Administra el tiempo"},
   {"key": "closure", "text": "Cierra con producto o acción"},
   {"key": "feedback", "text": "Recoge dudas y observaciones para mejorar la guía"}]',
 'INT',
 '[{"key": "facilitator", "label": "Persona facilitadora observada", "required": true},
   {"key": "strength", "label": "Una fortaleza concreta"},
   {"key": "priority_adjustment", "label": "Un ajuste prioritario"},
   {"key": "next_step", "label": "Próximo paso de práctica"}]',
 NULL);

-- ── Catalogo: de donde sale una observacion de la T-10 ────────────────
CREATE TABLE observation_source (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO observation_source (pack_id, code, sort_order, label) VALUES
('EC-MUNICIPIOS-AZULES', 'application', 1, 'Aplicación'),
('EC-MUNICIPIOS-AZULES', 'cap', 2, 'CAP'),
('EC-MUNICIPIOS-AZULES', 'follow_up', 3, 'Seguimiento');
GRANT SELECT ON observation_source TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON observation_source FROM renfygrid_app;

-- ── Por organizacion: T-10 ────────────────────────────────────────────
CREATE TABLE program_observation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id          text NOT NULL,
    stage_code       text NOT NULL,          -- la guia observada (etapa de la ruta)
    source_code      text NOT NULL,
    finding          text NOT NULL,
    proposed_change  text,
    priority         text NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
    reviewer         text,
    status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_review', 'incorporated', 'discarded')),
    community        text,                   -- JAAPS o comunidad donde se observo
    created_by       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pack_id, stage_code) REFERENCES process_stage(pack_id, code),
    FOREIGN KEY (pack_id, source_code) REFERENCES observation_source(pack_id, code)
);
CREATE INDEX program_observation_tenant_idx ON program_observation (tenant_id, stage_code, status);
ALTER TABLE program_observation ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_observation FORCE ROW LEVEL SECURITY;
CREATE POLICY program_observation_tenant_isolation ON program_observation FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON program_observation TO renfygrid_app;

INSERT INTO app_permission (code, sort_order, area, label) VALUES
('program.observe', 30, 'Programa', 'Registrar observaciones para mejorar las guías (T-10)');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'program.observe'), ('board', 'program.observe');
