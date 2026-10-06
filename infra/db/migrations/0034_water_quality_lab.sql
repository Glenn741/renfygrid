-- RenfyGrid -- 0034_water_quality_lab.sql
-- Track D, D2 (2026-10-06): calidad del agua y laboratorio. Fuente: Guia 3
-- de Municipios Azules, seccion 3.4 y calendario 7G:
--   "E. coli, coliformes y otros parametros requieren laboratorio"
--   "Nitratos, fluoruro, arsenico, hierro, manganeso u otros pueden
--    requerirse segun la fuente... Los limites corresponden a la normativa
--    vigente y al plan de muestreo."
--   "La cantidad y frecuencia de muestras se definen mediante los
--    lineamientos vigentes de ARCA, considerando la poblacion abastecida"
--   Revision del plan de muestreo: "al menos una vez al ano y cuando cambie
--    la poblacion, fuente o sistema".
--
-- Por eso:
--   - Los parametros de laboratorio entran al catalogo SIN regla: su limite
--     es de la NTE INEN 1108, que no esta en las guias; se registran sin
--     interpretacion hasta cargar la norma como regla del paquete. E. coli ya
--     tiene regla (0021/0030) y su resultado positivo es critico.
--   - El plan de muestreo lo define cada junta (frecuencia segun su categoria
--     ARCA); el sistema avisa lo vencido. Nunca una frecuencia inventada.
--   - El plazo de revision del plan es dato del paquete de programa.

INSERT INTO parameter (code, label, unit, measured_by) VALUES
('total_coliforms', 'Coliformes totales', 'UFC/100 mL', 'lab'),
('nitrate',         'Nitratos', 'mg/L', 'lab'),
('fluoride',        'Fluoruro', 'mg/L', 'lab'),
('arsenic',         'Arsénico', 'mg/L', 'lab'),
('iron',            'Hierro', 'mg/L', 'lab'),
('manganese',       'Manganeso', 'mg/L', 'lab')
ON CONFLICT (code) DO NOTHING;

-- Plazos de un programa que no son de una lista (reutilizable por otros).
CREATE TABLE program_rule (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    value_days  integer NOT NULL CHECK (value_days > 0),
    source      text NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO program_rule (pack_id, code, value_days, source) VALUES
('EC-MUNICIPIOS-AZULES', 'sampling_plan_review_days', 365,
 'Guía 3 §3.4: revisar el plan de muestreo al menos una vez al año y cuando cambie la población, la fuente o el sistema.');
GRANT SELECT ON program_rule TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON program_rule FROM renfygrid_app;

-- ── Por junta: plan de muestreo ───────────────────────────────────────
CREATE TABLE lab_plan_item (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name               text NOT NULL,
    parameters         text[] NOT NULL CHECK (cardinality(parameters) > 0),
    sampling_point_id  uuid REFERENCES sampling_point(id),
    frequency_days     integer NOT NULL CHECK (frequency_days > 0),
    source_note        text,   -- de donde sale la frecuencia (oficio ARCA, GAD, laboratorio)
    active             boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE lab_plan_review (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    reviewed_on  date NOT NULL,
    reviewed_by  text NOT NULL,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- ── Por junta: muestras y resultados de laboratorio ───────────────────
CREATE TABLE lab_sample (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    sampling_point_id  uuid REFERENCES sampling_point(id),
    plan_item_id       uuid REFERENCES lab_plan_item(id),
    sampled_at         timestamptz NOT NULL,
    laboratory         text NOT NULL,
    report_ref         text,
    reason             text NOT NULL CHECK (reason IN ('plan', 'alert', 'other')),
    notes              text,
    recorded_by        text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX lab_sample_tenant_idx ON lab_sample (tenant_id, sampled_at DESC);

CREATE TABLE lab_result (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    sample_id       uuid NOT NULL REFERENCES lab_sample(id) ON DELETE CASCADE,
    parameter_code  text NOT NULL REFERENCES parameter(code),
    value           numeric NOT NULL,
    -- '<' bajo el limite de deteccion del laboratorio, '>' sobre el rango.
    qualifier       text NOT NULL DEFAULT '=' CHECK (qualifier IN ('=', '<', '>')),
    rule_id         uuid REFERENCES parameter_rule(id),
    result_code     text,
    result_label    text,
    severity        text CHECK (severity IN ('ok', 'alert', 'critical')),
    finding_id      uuid REFERENCES finding(id),
    UNIQUE (sample_id, parameter_code)
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['lab_plan_item', 'lab_plan_review', 'lab_sample', 'lab_result'] LOOP
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

-- Permisos (0033): registrar resultados es del operador y la directiva;
-- el plan de muestreo lo define la directiva.
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('quality.record', 17, 'Calidad del agua', 'Registrar análisis de laboratorio'),
('quality.plan',   18, 'Calidad del agua', 'Definir y revisar el plan de muestreo');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'quality.record'), ('supervisor', 'quality.plan'),
('board', 'quality.record'), ('board', 'quality.plan'),
('operator', 'quality.record');
