-- RenfyGrid -- 0021_community_packs.sql
-- Track D, Sprint D0.1 (2026-10-05) -- motor de paquetes. Ver
-- docs/04-plan-sprints.md SS11.3 y SS11.4.
--
-- Principio: el motor no sabe de ningun pais. Lo que define un paquete
-- (tipos de componente, parametros y sus reglas, listas de verificacion) va
-- en catalogos GLOBALES, sin tenant_id y de solo lectura para el rol de
-- aplicacion -- una junta nunca puede alterar el paquete que usan otras.
-- Lo que hace cada junta (que paquetes adopta, que listas aplica, que
-- hallazgos tiene) va en tablas por tenant con RLS.
--
-- Paquetes cargados aqui:
--   core                  -- tipos de componente universales
--   EC-ARCA               -- normativo Ecuador: reglas de calidad de agua
--   EC-MUNICIPIOS-AZULES  -- programa: listas de verificacion de las Guias 3 y 4
-- Los textos de las listas son literales de las guias (Clientes\ARCA\Guia3_digital.pdf,
-- Guia4_digital.pdf). Los umbrales son los que la Guia 3 SS3.4 presenta como
-- "referencia operativa"; la norma completa es la NTE INEN 1108.

-- ── Catalogos globales ────────────────────────────────────────────────

CREATE TABLE pack (
    id           text PRIMARY KEY,
    kind         text NOT NULL CHECK (kind IN ('core', 'regulatory', 'program')),
    country      text,            -- ISO 3166-1 alfa-2; NULL para core
    name         text NOT NULL,
    version      text NOT NULL,
    source_note  text NOT NULL
);

CREATE TABLE component_type (
    code               text PRIMARY KEY,
    pack_id            text NOT NULL REFERENCES pack(id),
    service            text NOT NULL CHECK (service IN ('water', 'sanitation', 'support')),
    stage_order        integer,   -- posicion en el recorrido; NULL = accesorio de cualquier tramo
    is_treatment_stage boolean NOT NULL DEFAULT false,
    label              text NOT NULL,
    description        text
);

CREATE TABLE parameter (
    code         text PRIMARY KEY,
    label        text NOT NULL,
    unit         text NOT NULL,
    measured_by  text NOT NULL CHECK (measured_by IN ('field', 'lab'))
);

-- `bands`: lista ordenada de tramos, cada uno con su limite superior
-- (`upper`, NULL = sin limite) y si ese limite es inclusivo. El primer
-- tramo cuyo limite cubre el valor es el resultado. Ej. cloro (Ecuador):
-- [<0,3 bajo] [<=1,5 adecuado] [resto alto].
CREATE TABLE parameter_rule (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_id         text NOT NULL REFERENCES pack(id),
    parameter_code  text NOT NULL REFERENCES parameter(code),
    bands           jsonb NOT NULL,
    citation        text NOT NULL,
    valid_from      date,
    valid_to        date,
    UNIQUE (pack_id, parameter_code, valid_from)
);

-- `scale`: respuestas posibles, cada una con `finding` (si genera
-- hallazgo), `finding_priority` (prioridad de ese hallazgo, la define el
-- paquete, nunca el codigo) y `score` (aporte al indice de madurez).
-- `items`: [{key, text, component_service?}] en el orden de la guia.
CREATE TABLE checklist_template (
    id         text PRIMARY KEY,
    pack_id    text NOT NULL REFERENCES pack(id),
    kind       text NOT NULL CHECK (kind IN ('inspection', 'traffic_light', 'self_assessment')),
    title      text NOT NULL,
    purpose    text NOT NULL,
    scale      jsonb NOT NULL,
    items      jsonb NOT NULL
);

-- GRANT explicito (no se confia en ALTER DEFAULT PRIVILEGES de 0002: en
-- produccion las migraciones corren como `postgres`, cuyos objetos no
-- heredan esos defaults -- mismo hallazgo de la 0019, ver bitacora).
GRANT SELECT ON pack, component_type, parameter, parameter_rule, checklist_template TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON pack, component_type, parameter, parameter_rule, checklist_template FROM renfygrid_app;

-- ── Tablas por tenant ─────────────────────────────────────────────────

CREATE TABLE tenant_pack (
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    pack_id     text NOT NULL REFERENCES pack(id),
    adopted_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, pack_id)
);
ALTER TABLE tenant_pack ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_pack FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_pack_tenant_isolation ON tenant_pack
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE checklist_run (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    template_id   text NOT NULL REFERENCES checklist_template(id),
    performed_at  timestamptz NOT NULL DEFAULT now(),
    performed_by  text NOT NULL,   -- convencion de origen: portal:<email>
    notes         text
);
ALTER TABLE checklist_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE checklist_run FORCE ROW LEVEL SECURITY;
CREATE POLICY checklist_run_tenant_isolation ON checklist_run
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE INDEX checklist_run_tenant_template_idx ON checklist_run (tenant_id, template_id, performed_at DESC);

CREATE TABLE checklist_answer (
    run_id       uuid NOT NULL REFERENCES checklist_run(id) ON DELETE CASCADE,
    tenant_id    uuid NOT NULL REFERENCES tenant(id),
    item_key     text NOT NULL,
    answer_code  text NOT NULL,
    observation  text,
    action       text,
    responsible  text,
    due_date     date,
    PRIMARY KEY (run_id, item_key)
);
ALTER TABLE checklist_answer ENABLE ROW LEVEL SECURITY;
ALTER TABLE checklist_answer FORCE ROW LEVEL SECURITY;
CREATE POLICY checklist_answer_tenant_isolation ON checklist_answer
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Hallazgo: la pieza que conecta el mapa tecnico, las listas y (D1) las
-- lecturas fuera de rango con el plan de mejora (D7, ficha 7G.2).
CREATE TABLE finding (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenant(id),
    source_kind          text NOT NULL CHECK (source_kind IN ('critical_point', 'checklist', 'reading', 'manual')),
    source_ref           text,   -- p. ej. "<run_id>:<item_key>"
    asset_id             uuid REFERENCES network_asset(id),
    location_text        text,
    geometry             jsonb,
    description          text NOT NULL,
    priority             text NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
    support_level        text CHECK (support_level IN ('community', 'local_government', 'specialized')),
    status               text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    to_improvement_plan  boolean NOT NULL DEFAULT false,
    created_by           text NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    closed_at            timestamptz
);
ALTER TABLE finding ENABLE ROW LEVEL SECURITY;
ALTER TABLE finding FORCE ROW LEVEL SECURITY;
CREATE POLICY finding_tenant_isolation ON finding
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE INDEX finding_tenant_status_idx ON finding (tenant_id, status);

GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_pack, checklist_run, checklist_answer, finding TO renfygrid_app;

-- ── Semillas ──────────────────────────────────────────────────────────

INSERT INTO pack (id, kind, country, name, version, source_note) VALUES
('core', 'core', NULL, 'Núcleo RenfyGrid', '1', 'Tipos de componente universales de agua potable y saneamiento.'),
('EC-ARCA', 'regulatory', 'EC', 'Ecuador — referencias de calidad del agua', '2026-10',
 'Valores de referencia operativa de la Guía 3 (Municipios Azules) §3.4. La norma completa es la NTE INEN 1108; el muestreo lo define ARCA (DIR-ARCA-RG-012-2022).'),
('EC-MUNICIPIOS-AZULES', 'program', 'EC', 'Municipios Azules — Corporación Agua Para Todos', '2026-10',
 'Listas de verificación y autoevaluaciones de las Guías 3 y 4 del Proyecto Municipios Azules.');

-- Tipos urbanos que ya existian como conjunto fijo en asset_service.py
-- (stage_order NULL: accesorios de cualquier tramo, salvo el tanque).
INSERT INTO component_type (code, pack_id, service, stage_order, is_treatment_stage, label, description) VALUES
('pipe',   'core', 'water', NULL, false, 'Tubería', NULL),
('valve',  'core', 'water', NULL, false, 'Válvula', NULL),
('pump',   'core', 'water', NULL, false, 'Bomba', NULL),
('meter',  'core', 'water', NULL, false, 'Medidor', NULL),
('sensor', 'core', 'water', NULL, false, 'Sensor', NULL),
('tank',   'core', 'water', 110,  false, 'Reservorio o tanque', 'Almacena el agua tratada antes de distribuirla.'),
('water_source',         'core', 'water', 10,  false, 'Fuente', 'Río, quebrada, vertiente, pozo o manantial.'),
('intake',               'core', 'water', 20,  false, 'Captación', 'Obra donde se toma el agua de la fuente.'),
('sand_trap',            'core', 'water', 30,  true,  'Desarenador', 'Retira arena, piedras pequeñas y sedimentos pesados.'),
('conveyance',           'core', 'water', 40,  false, 'Conducción', 'Tuberías o canales desde la captación hasta la planta o el reservorio.'),
('aeration',             'core', 'water', 50,  true,  'Aireación', 'Reduce olores, gases, hierro o manganeso en algunos casos.'),
('coagulation',          'core', 'water', 60,  true,  'Coagulación', 'Junta partículas muy pequeñas que causan color o turbiedad fina.'),
('flocculation',         'core', 'water', 70,  true,  'Floculación', 'Forma grupos de partículas más grandes.'),
('sedimentation',        'core', 'water', 80,  true,  'Sedimentación', 'Permite que los sólidos bajen al fondo.'),
('filtration',           'core', 'water', 90,  true,  'Filtración', 'Retiene partículas finas antes de desinfectar.'),
('disinfection',         'core', 'water', 100, true,  'Desinfección', 'Elimina o inactiva microorganismos; última etapa del tratamiento.'),
('distribution_network', 'core', 'water', 120, false, 'Red de distribución', 'Lleva el agua desde el reservorio hasta las viviendas.'),
('sanitary_unit',        'core', 'sanitation', 10, false, 'Baño o letrina', NULL),
('grease_trap',          'core', 'sanitation', 20, false, 'Trampa de grasa', 'Retiene grasas antes de que entren a la red.'),
('inspection_box',       'core', 'sanitation', 30, false, 'Caja de revisión', 'Permite revisar, limpiar o destapar tuberías.'),
('sewer_network',        'core', 'sanitation', 40, false, 'Red sanitaria', 'Conduce las aguas residuales.'),
('septic_tank',          'core', 'sanitation', 50, false, 'Fosa séptica', 'Separa sólidos y trata parcialmente; requiere retiro de lodos.'),
('wastewater_plant',     'core', 'sanitation', 60, false, 'Planta de tratamiento de aguas residuales', NULL),
('discharge_point',      'core', 'sanitation', 70, false, 'Punto de descarga', 'Salida del efluente hacia el cuerpo receptor.'),
('warehouse',            'core', 'support', NULL, false, 'Bodega', 'Químicos, repuestos, herramientas y EPP.');

ALTER TABLE network_asset
    ADD CONSTRAINT network_asset_type_fk FOREIGN KEY (type) REFERENCES component_type(code) NOT VALID;
ALTER TABLE network_asset VALIDATE CONSTRAINT network_asset_type_fk;

INSERT INTO parameter (code, label, unit, measured_by) VALUES
('free_chlorine', 'Cloro residual', 'mg/L', 'field'),
('turbidity',     'Turbiedad', 'UTN', 'field'),
('ph',            'pH', '', 'field'),
('e_coli',        'E. coli', 'UFC/100 mL', 'lab');

INSERT INTO parameter_rule (pack_id, parameter_code, bands, citation) VALUES
('EC-ARCA', 'free_chlorine',
 '[{"upper": 0.3, "upper_inclusive": false, "code": "low", "label": "Bajo", "severity": "alert"},
   {"upper": 1.5, "upper_inclusive": true, "code": "adequate", "label": "Adecuado", "severity": "ok"},
   {"upper": null, "code": "high", "label": "Alto", "severity": "alert"}]',
 'Guía 3 Municipios Azules §3.4: 0,3 a 1,5 mg/L como rango operativo de referencia en la red. Requisito completo: NTE INEN 1108.'),
('EC-ARCA', 'turbidity',
 '[{"upper": 5, "upper_inclusive": true, "code": "adequate", "label": "Adecuado", "severity": "ok"},
   {"upper": null, "code": "high", "label": "Alto", "severity": "alert"}]',
 'Guía 3 Municipios Azules §3.4: hasta 5 UTN como referencia operativa.'),
('EC-ARCA', 'ph',
 '[{"upper": 6.5, "upper_inclusive": false, "code": "low", "label": "Bajo", "severity": "alert"},
   {"upper": 8.5, "upper_inclusive": true, "code": "adequate", "label": "Adecuado", "severity": "ok"},
   {"upper": null, "code": "high", "label": "Alto", "severity": "alert"}]',
 'Guía 3 Municipios Azules §3.4: 6,5 a 8,5 como referencia usual.'),
('EC-ARCA', 'e_coli',
 '[{"upper": 0, "upper_inclusive": true, "code": "absent", "label": "Ausente", "severity": "ok"},
   {"upper": null, "code": "present", "label": "Presente", "severity": "critical"}]',
 'Guía 3 Municipios Azules §3.4: ausencia en el agua para consumo humano (análisis de laboratorio).');

-- Escalas reutilizadas por varias listas.
INSERT INTO checklist_template (id, pack_id, kind, title, purpose, scale, items) VALUES
('MA-7A', 'EC-MUNICIPIOS-AZULES', 'inspection', '7A. Lista de inspección de agua potable',
 'Se actualiza durante el taller, al menos cada tres meses y después de una emergencia o reparación importante.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "in_progress", "label": "En proceso", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "no", "label": "No", "finding": true, "finding_priority": "high", "score": 0}]',
 '[{"key": "source_protected", "text": "La fuente y la zona de recarga están protegidas.", "component_service": "water"},
   {"key": "intake_condition", "text": "La captación tiene tapa, cerco y rejilla en buen estado.", "component_service": "water"},
   {"key": "conveyance_no_leaks", "text": "La conducción no tiene fugas visibles.", "component_service": "water"},
   {"key": "main_valves_work", "text": "Las válvulas principales abren y cierran.", "component_service": "water"},
   {"key": "treatment_works", "text": "El sistema de tratamiento funciona según su diseño.", "component_service": "water"},
   {"key": "filters_cleaned", "text": "Los filtros se limpian o retrolavan según necesidad.", "component_service": "water"},
   {"key": "doser_works", "text": "El dosificador funciona y se controla.", "component_service": "water"},
   {"key": "tank_sealed", "text": "El reservorio tiene tapa sellada y no presenta grietas.", "component_service": "water"},
   {"key": "tank_washed_6m", "text": "El reservorio fue lavado en los últimos 6 meses.", "component_service": "water"},
   {"key": "network_pressure", "text": "La red mantiene presión adecuada en puntos lejanos.", "component_service": "water"},
   {"key": "no_unauthorized_connections", "text": "No hay conexiones no autorizadas identificadas.", "component_service": "water"}]'),
('MA-7E', 'EC-MUNICIPIOS-AZULES', 'inspection', '7E. Lista de inspección de saneamiento',
 'Se actualiza durante el taller, mensualmente y después de reboses, lluvias fuertes o alertas.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "in_progress", "label": "En proceso", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "no", "label": "No", "finding": true, "finding_priority": "high", "score": 0}]',
 '[{"key": "wastewater_destination_known", "text": "La comunidad sabe dónde van sus aguas residuales.", "component_service": "sanitation"},
   {"key": "boxes_covered", "text": "Las cajas de revisión tienen tapa y no rebosan.", "component_service": "sanitation"},
   {"key": "no_discharge_near_source", "text": "No hay aguas residuales descargando cerca de la fuente.", "component_service": "sanitation"},
   {"key": "septic_maintenance_scheduled", "text": "Las fosas sépticas tienen mantenimiento programado.", "component_service": "sanitation"},
   {"key": "sludge_removed_safely", "text": "La extracción de lodos se realiza de forma segura.", "component_service": "sanitation"},
   {"key": "plant_has_manual", "text": "La planta de tratamiento, si existe, tiene manual.", "component_service": "sanitation"},
   {"key": "operator_uses_ppe", "text": "El operador usa EPP completo para saneamiento.", "component_service": "sanitation"},
   {"key": "productive_discharges_controlled", "text": "No hay descargas productivas sin control.", "component_service": "sanitation"},
   {"key": "sanitation_maintenance_logged", "text": "Hay registro de mantenimiento de saneamiento.", "component_service": "sanitation"}]'),
('MA-7G1', 'EC-MUNICIPIOS-AZULES', 'inspection', '7G.1 Lista de revisión de bodega y equipos de protección personal (EPP)',
 'Al menos una vez al mes y después de compras, daños o ingreso de nuevos equipos.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "in_progress", "label": "En proceso", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "no", "label": "No", "finding": true, "finding_priority": "high", "score": 0}]',
 '[{"key": "chemicals_labeled", "text": "Químicos cerrados, separados y con etiquetas legibles", "component_service": "support"},
   {"key": "warehouse_conditions", "text": "Bodega seca, ventilada, ordenada y con acceso restringido", "component_service": "support"},
   {"key": "no_foreign_items", "text": "No se guardan alimentos, medicinas ni objetos familiares", "component_service": "support"},
   {"key": "ppe_available", "text": "Guantes, botas, gafas, mascarilla y ropa de trabajo disponibles", "component_service": "support"},
   {"key": "ppe_good_condition", "text": "EPP limpio, seco y sin daños", "component_service": "support"},
   {"key": "tools_organized", "text": "Herramientas y repuestos ordenados e identificados", "component_service": "support"},
   {"key": "inventory_updated", "text": "Inventario y hojas de seguridad actualizados", "component_service": "support"},
   {"key": "emergency_numbers_visible", "text": "Números de emergencia y procedimientos visibles", "component_service": "support"}]'),
('MA-AP2', 'EC-MUNICIPIOS-AZULES', 'traffic_light', 'Semáforo técnico del sistema',
 'Actividad participativa 2 (Guía 3): estado de cada componente y acción inmediata acordada.',
 '[{"code": "green", "label": "Verde", "finding": false, "score": 2},
   {"code": "yellow", "label": "Amarillo", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "red", "label": "Rojo", "finding": true, "finding_priority": "high", "score": 0}]',
 '[{"key": "intake", "text": "Captación", "component_service": "water"},
   {"key": "conveyance", "text": "Conducción", "component_service": "water"},
   {"key": "treatment", "text": "Tratamiento", "component_service": "water"},
   {"key": "storage", "text": "Reservorio", "component_service": "water"},
   {"key": "network", "text": "Red", "component_service": "water"},
   {"key": "sanitation", "text": "Saneamiento", "component_service": "sanitation"},
   {"key": "warehouse_ppe", "text": "Bodega y EPP", "component_service": "support"},
   {"key": "logbooks", "text": "Bitácoras", "component_service": "support"}]'),
('MA-G3-START', 'EC-MUNICIPIOS-AZULES', 'self_assessment', 'Verificación inicial — Guía 3 (operación y mantenimiento)',
 'Sirve para saber desde dónde empieza la comunidad. No hay respuestas correctas o incorrectas.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "somewhat", "label": "Más o menos", "finding": false, "score": 1},
   {"code": "no", "label": "No", "finding": false, "score": 0}]',
 '[{"key": "operator_assigned", "text": "¿Hay una persona responsable de operar el sistema?"},
   {"key": "daily_review", "text": "¿Se revisan cada día la captación, el tratamiento, el reservorio y la red?"},
   {"key": "chlorination_measured", "text": "¿El agua se clora y se mide el cloro residual?"},
   {"key": "quality_analysis", "text": "¿La JAAPS realiza o gestiona análisis de calidad del agua?"},
   {"key": "maintenance_mingas", "text": "¿Se hacen actividades de mantenimiento y mingas durante el año?"},
   {"key": "wastewater_known", "text": "¿Sabemos dónde van las aguas residuales y si reciben tratamiento?"},
   {"key": "sanitation_maintained", "text": "¿Se mantienen las fosas, cajas, alcantarillado o planta de tratamiento?"},
   {"key": "knows_when_to_ask", "text": "¿Sabemos qué podemos resolver como comunidad y cuándo pedir apoyo técnico?"}]'),
('MA-G4-START', 'EC-MUNICIPIOS-AZULES', 'self_assessment', 'Verificación inicial — Guía 4 (administración, finanzas y tarifa)',
 'Nos ayuda a saber desde dónde empezamos. No hay respuestas incorrectas.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "somewhat", "label": "Más o menos", "finding": false, "score": 1},
   {"code": "no", "label": "No", "finding": false, "score": 0}]',
 '[{"key": "knows_monthly_cost", "text": "¿Sabemos cuánto cuesta mantener el sistema cada mes?"},
   {"key": "cash_book_updated", "text": "¿Llevamos libro de caja actualizado?"},
   {"key": "payments_with_receipts", "text": "¿Todos los pagos tienen recibos o comprobantes?"},
   {"key": "tariff_covers_costs", "text": "¿La tarifa cubre los costos reales?"},
   {"key": "accountability_yearly", "text": "¿Rendimos cuentas al menos una vez al año?"}]'),
('MA-4A', 'EC-MUNICIPIOS-AZULES', 'self_assessment', '4A. Administración y contabilidad',
 'Lista de verificación de la gestión administrativa y financiera de la junta.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "in_progress", "label": "En proceso", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "no", "label": "No", "finding": true, "finding_priority": "high", "score": 0}]',
 '[{"key": "bank_account_active", "text": "Cuenta bancaria institucional activa."},
   {"key": "cash_book_updated", "text": "Libro de caja actualizado."},
   {"key": "movements_with_receipts", "text": "Ingresos y gastos con comprobante."},
   {"key": "numbered_receipts", "text": "Recibos numerados para usuarios."},
   {"key": "payment_roll_updated", "text": "Padrón de pagos actualizado."},
   {"key": "budget_approved", "text": "Presupuesto anual aprobado."},
   {"key": "real_costs_calculated", "text": "Costos reales calculados."},
   {"key": "tariff_covers_operation", "text": "Tarifa cubre costos operativos."},
   {"key": "reserve_fund_active", "text": "Fondo de reserva en funcionamiento."}]'),
('MA-4B', 'EC-MUNICIPIOS-AZULES', 'self_assessment', '4B. Transparencia',
 'Lista de verificación de rendición de cuentas y control social.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "in_progress", "label": "En proceso", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "no", "label": "No", "finding": true, "finding_priority": "high", "score": 0}]',
 '[{"key": "accountability_12m", "text": "Rendición de cuentas realizada en últimos 12 meses."},
   {"key": "report_includes_reserve", "text": "Informe incluye ingresos, gastos y reserva."},
   {"key": "members_can_review_books", "text": "Usuarios pueden revisar libros según acuerdo."},
   {"key": "oversight_reviews_receipts", "text": "Vocal de fiscalización revisa comprobantes."},
   {"key": "assembly_approves_finance", "text": "Decisiones financieras se aprueban en asamblea."},
   {"key": "minutes_signed_archived", "text": "Actas financieras firmadas y archivadas."}]');
