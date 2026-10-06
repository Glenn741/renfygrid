-- RenfyGrid -- 0040_improvement_plan.sql
-- Track D, D7 (2026-10-06): plan minimo de O&M, ficha 7G.2 (insumos para el
-- Plan de Mejora) y tablero 7H de productos finales de la Guia 3.
--
-- Guia 3 seccion 4: "Al finalizar esta guia, la JAAPS debe salir con un plan
-- minimo. No es un documento complejo. Es una hoja de ruta inmediata para
-- ordenar la operacion, el mantenimiento y los primeros problemas que pasaran
-- a la Guia 6." (8 filas: componente, decision, responsable, plazo).
-- Ficha 7G.2: problema priorizado, evidencia o formato donde se identifico,
-- accion propuesta, accion que puede ejecutar la JAAPS, apoyo tecnico o
-- institucional, costo estimado, plazo/prioridad. "No reemplaza el Plan de
-- Mejora: organiza la evidencia producida en esta guia."
-- Ficha 7H: productos de la guia, donde se generan, completo/pendiente.
--
-- Generico: las filas del plan minimo, las etiquetas de evidencia y los
-- productos 7H son CATALOGO del paquete; los detectores de evidencia son
-- capacidades del motor que cualquier paquete referencia por codigo.

-- ── Catalogo: filas del plan minimo ───────────────────────────────────
-- `suggestion_source`: que evidencia viva del sistema se muestra como
-- sugerencia al llenar la fila (detector del motor).
CREATE TABLE minimum_plan_row (
    pack_id             text NOT NULL REFERENCES pack(id),
    code                text NOT NULL,
    sort_order          integer NOT NULL,
    component           text NOT NULL,
    guidance            text NOT NULL,    -- la pregunta de la tabla en blanco
    example_decision    text,             -- ejemplo de referencia de la guia
    example_responsible text,
    example_term        text,
    suggestion_source   text NOT NULL CHECK (suggestion_source IN (
        'daily_routine', 'chlorine_points', 'monthly_maintenance', 'sanitation_priority',
        'warehouse_ppe', 'likely_emergency', 'technical_support', 'improvement_inputs')),
    PRIMARY KEY (pack_id, code)
);
INSERT INTO minimum_plan_row (pack_id, code, sort_order, component, guidance, example_decision, example_responsible, example_term, suggestion_source) VALUES
('EC-MUNICIPIOS-AZULES', 'daily_routine', 1, 'Rutina diaria del operador',
 'Qué se revisará cada día: captación, tanque, cloro, red, bitácora.',
 'Revisar captación, nivel del reservorio, funcionamiento del dosificador, cloro residual y novedades de la red; registrar en bitácora.',
 'Operador/a', 'Desde mañana, todos los días', 'daily_routine'),
('EC-MUNICIPIOS-AZULES', 'chlorine_points', 2, 'Puntos de cloro residual',
 'Dónde se medirá: salida de tanque, punto medio, punto lejano o crítico.',
 'Medir en la salida del reservorio cada día y rotar semanalmente el punto medio y el extremo de la red.',
 'Operador/a y vocal de calidad', 'Inicio: 20/07/2026', 'chlorine_points'),
('EC-MUNICIPIOS-AZULES', 'monthly_maintenance', 3, 'Mantenimiento preventivo del mes',
 'Qué tarea se realizará primero: limpieza, revisión, retrolavado, reservorio u otra.',
 'Limpiar captación y desarenador; recorrer la conducción y reparar una fuga menor.',
 'Operador/a + minga', 'Último sábado del mes', 'monthly_maintenance'),
('EC-MUNICIPIOS-AZULES', 'sanitation_priority', 4, 'Problema de saneamiento prioritario',
 'Qué se atenderá primero: fosa, caja, rebose, descarga, lodos o planta.',
 'Destapar y reparar la caja de revisión junto a la escuela; verificar que no exista descarga hacia la calle.',
 'Presidencia + GAD', 'Dentro de 10 días', 'sanitation_priority'),
('EC-MUNICIPIOS-AZULES', 'warehouse_ppe', 5, 'Bodega y EPP',
 'Qué se debe comprar, ordenar o reponer.',
 'Separar el cloro, rotular productos y adquirir gafas, guantes y mascarillas.',
 'Tesorería y operador/a', 'En 2 semanas', 'warehouse_ppe'),
('EC-MUNICIPIOS-AZULES', 'likely_emergency', 6, 'Emergencia más probable',
 'Qué riesgo se preparará primero: sequía, rotura, contaminación, rebose o inundación.',
 'Preparar respuesta ante agua turbia por lluvias: cierre de captación, aviso, hervido y muestreo.',
 'Presidencia y operador/a', 'Antes de la temporada de lluvias', 'likely_emergency'),
('EC-MUNICIPIOS-AZULES', 'technical_support', 7, 'Apoyo técnico requerido',
 'Qué tema supera la capacidad de la JAAPS y a quién se pedirá apoyo.',
 'Solicitar evaluación del filtro y apoyo para definir el plan de muestreo.',
 'Presidencia', 'Durante el próximo mes', 'technical_support'),
('EC-MUNICIPIOS-AZULES', 'improvement_inputs', 8, 'Insumos para la Guía 6',
 'Qué problema pasará al Plan de Mejora.',
 'Incorporar la rehabilitación del filtro y la reparación de la red sanitaria como prioridades del Plan de Mejora.',
 'Directiva', 'Próxima sesión de planificación', 'improvement_inputs');

-- ── Catalogo: como se cita la evidencia en la 7G.2 ───────────────────
-- Una por tipo de origen; las listas se citan con su propio titulo.
CREATE TABLE evidence_label (
    pack_id      text NOT NULL REFERENCES pack(id),
    source_kind  text NOT NULL CHECK (source_kind IN ('reading', 'lab', 'checklist', 'critical_point', 'manual', 'sludge', 'discharge')),
    label        text NOT NULL,
    PRIMARY KEY (pack_id, source_kind)
);
INSERT INTO evidence_label (pack_id, source_kind, label) VALUES
('EC-MUNICIPIOS-AZULES', 'reading', 'Registro 7B'),
('EC-MUNICIPIOS-AZULES', 'lab', 'Análisis de laboratorio (calendario 7G)'),
('EC-MUNICIPIOS-AZULES', 'checklist', 'Lista'),
('EC-MUNICIPIOS-AZULES', 'critical_point', 'Mapa técnico (Actividad 1)'),
('EC-MUNICIPIOS-AZULES', 'manual', 'Registro de la junta'),
('EC-MUNICIPIOS-AZULES', 'sludge', 'Registro de lodos 7F'),
('EC-MUNICIPIOS-AZULES', 'discharge', 'Registro de descargas productivas (§3.8)');

GRANT SELECT ON minimum_plan_row, evidence_label TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON minimum_plan_row, evidence_label FROM renfygrid_app;

-- ── Por junta: plan minimo ────────────────────────────────────────────
CREATE TABLE minimum_plan_entry (
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id      text NOT NULL,
    row_code     text NOT NULL,
    decision     text NOT NULL,
    responsible  text,
    term         text,          -- como lo dice la junta ("último sábado del mes")
    due_date     date,          -- opcional, para el seguimiento
    updated_at   timestamptz NOT NULL DEFAULT now(),
    updated_by   text NOT NULL,
    PRIMARY KEY (tenant_id, pack_id, row_code),
    FOREIGN KEY (pack_id, row_code) REFERENCES minimum_plan_row(pack_id, code)
);

-- ── Por junta: ficha 7G.2 ─────────────────────────────────────────────
-- `source_ref`: de donde salio (hallazgo, fosa, descarga); evita trasladar
-- dos veces la misma evidencia. Una fila manual no tiene origen.
CREATE TABLE improvement_input (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    source_kind       text NOT NULL CHECK (source_kind IN ('reading', 'lab', 'checklist', 'critical_point', 'manual', 'sludge', 'discharge')),
    source_ref        text,
    finding_id        uuid REFERENCES finding(id),
    problem           text NOT NULL,
    evidence          text,
    proposed_action   text,
    community_action  text,
    support_required  text,
    support_level     text CHECK (support_level IN ('community', 'local_government', 'specialized')),
    cost_estimate     numeric CHECK (cost_estimate IS NULL OR cost_estimate >= 0),
    cost_note         text,     -- "por cotizar", "estimación inicial"
    term              text,
    priority          text NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_ref)
);
CREATE INDEX improvement_input_tenant_idx ON improvement_input (tenant_id, priority, created_at);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['minimum_plan_entry', 'improvement_input'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL '
            'USING (tenant_id = current_setting(''app.tenant_id'', true)::uuid) '
            'WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true)::uuid)',
            t || '_tenant_isolation', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO renfygrid_app', t);
    END LOOP;
END $$;

-- ── Ficha 7H de la Guia 3 ─────────────────────────────────────────────
-- Mismo patron que la 7H de las Guias 2 y 6 (lista de tipo `products`).
-- `evidence`: detector del motor que muestra si el registro existe en el
-- sistema; marcarlo completo sigue siendo decision de quien verifica.
INSERT INTO checklist_template (id, pack_id, kind, title, purpose, scale, items, stage_code, frequency_days) VALUES
('MA-G3-7H', 'EC-MUNICIPIOS-AZULES', 'products', '7H. Productos finales — Guía 3',
 'Se usa al cierre de la guía y en cada visita de seguimiento hasta cerrar los pendientes. Marque cada producto después de verificar que el formato fue elaborado, revisado por la directiva y archivado.',
 '[{"code": "complete", "label": "Completo", "finding": false, "score": 2},
   {"code": "pending", "label": "Pendiente", "finding": false, "ask_note": true, "score": 0}]',
 '[{"key": "technical_map", "text": "Mapa técnico de agua potable y saneamiento (Actividad participativa 1)", "evidence": {"kind": "assets_mapped"}},
   {"key": "traffic_light", "text": "Semáforo técnico del sistema (Actividad participativa 2)", "evidence": {"kind": "checklist_runs", "ref": "MA-AP2"}},
   {"key": "treatment_train", "text": "Revisión del tren de tratamiento (Actividad participativa 3)", "evidence": {"kind": "treatment_stages"}},
   {"key": "chlorine_register", "text": "Registro e interpretación de cloro residual (Actividad 4 · formato 7B)", "evidence": {"kind": "field_readings", "ref": "free_chlorine"}},
   {"key": "operation_log", "text": "Bitácora diaria de operación (Sección 3.10 · formato 7C)", "evidence": {"kind": "operation_log"}},
   {"key": "maintenance_plan", "text": "Plan de mantenimiento (Sección 3.6 · formato 7D y calendario 7G)", "evidence": {"kind": "pm_plans"}},
   {"key": "sanitation_checklist", "text": "Lista de inspección de saneamiento (Actividad 5 · formato 7E)", "evidence": {"kind": "checklist_runs", "ref": "MA-7E"}},
   {"key": "sludge_register", "text": "Registro de lodos o fosas (formato 7F)", "evidence": {"kind": "sanitation_register"}},
   {"key": "warehouse_ppe", "text": "Bodega y EPP revisados (Sección 3.9 · lista 7G.1)", "evidence": {"kind": "checklist_runs", "ref": "MA-7G1"}},
   {"key": "emergency_plan", "text": "Plan básico de emergencia (Actividad participativa 6)", "evidence": {"kind": "emergency_plan"}},
   {"key": "minimum_plan", "text": "Plan mínimo de operación y mantenimiento (Sección 4: acción transformadora final)", "evidence": {"kind": "minimum_plan"}},
   {"key": "improvement_inputs", "text": "Insumos para la Guía 6 (ficha 7G.2)", "evidence": {"kind": "improvement_inputs"}},
   {"key": "quality_calendar", "text": "Calendario de control y análisis de calidad del agua (calendario 7G)", "evidence": {"kind": "lab_plan"}}]',
 'G3', NULL);

-- ── Permisos ──────────────────────────────────────────────────────────
-- La 7G.2 "la completa la directiva, la persona operadora y la facilitación".
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('improvement.record', 25, 'Plan de Mejora', 'Llenar el plan mínimo y la ficha de insumos 7G.2'),
('improvement.manage', 26, 'Plan de Mejora', 'Quitar filas de la ficha 7G.2');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'improvement.record'), ('supervisor', 'improvement.manage'),
('board', 'improvement.record'), ('board', 'improvement.manage'),
('operator', 'improvement.record');
