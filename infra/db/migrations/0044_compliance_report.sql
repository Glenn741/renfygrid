-- RenfyGrid -- 0044_compliance_report.sql
-- Track D, D12.3 (2026-10-06): informe de cumplimiento al ente rector.
--
-- Plan (docs/04 §11.2, D12): "Para ARCA, reportes de cumplimiento
-- exportables que la junta decide enviar (no acceso directo a los datos
-- operativos)".
--
-- - La junta elige el periodo y genera el informe: queda una FOTO inmutable
--   (`content`) de lo que el sistema tenia en ese momento; si algo cambia
--   despues, se genera otro informe, el anterior no se reescribe.
-- - La junta decide enviarlo y registra a quien y cuando; el ente rector no
--   entra al sistema.
-- - Las secciones del informe son CATALOGO del paquete regulatorio: cada una
--   apunta a un detector del motor. El formato oficial de ARCA
--   (DIR-ARCA-RG-012-2022, plan de muestreo por categoria poblacional) aun no
--   esta cargado: este es un formato provisional, declarado como tal en el
--   propio informe; al llegar el documento se ajustan estas filas.

CREATE TABLE report_template (
    pack_id      text NOT NULL REFERENCES pack(id),
    code         text NOT NULL,
    title        text NOT NULL,
    purpose      text NOT NULL,
    recipient    text,             -- a quien suele dirigirse
    format_note  text,             -- estado del formato (provisional, oficial)
    PRIMARY KEY (pack_id, code)
);
CREATE TABLE report_section (
    pack_id      text NOT NULL,
    report_code  text NOT NULL,
    code         text NOT NULL,
    sort_order   integer NOT NULL,
    title        text NOT NULL,
    description  text NOT NULL,
    detector     text NOT NULL CHECK (detector IN (
        'lab_quality', 'field_readings', 'sampling_plan', 'alerts_emergencies', 'maintenance_calendar', 'sanitation')),
    params       jsonb NOT NULL DEFAULT '{}'::jsonb,   -- p. ej. que parametro de campo resume
    PRIMARY KEY (pack_id, report_code, code),
    FOREIGN KEY (pack_id, report_code) REFERENCES report_template(pack_id, code)
);

INSERT INTO report_template (pack_id, code, title, purpose, recipient, format_note) VALUES
('EC-ARCA', 'compliance', 'Informe de cumplimiento de la junta',
 'Resumen verificable del control de calidad del agua, la operación y el mantenimiento en el periodo, para el ente rector o el GAD. Lo genera la junta y decide enviarlo.',
 'ARCA / GAD municipal',
 'Formato provisional de RenfyGrid: el formato oficial de ARCA (DIR-ARCA-RG-012-2022 y plan de muestreo por categoría poblacional) se aplicará cuando se cargue el documento. Los valores de referencia usados son los del paquete vigente, con su fuente.');
INSERT INTO report_section (pack_id, report_code, code, sort_order, title, description, detector, params) VALUES
('EC-ARCA', 'compliance', 'lab', 1, 'Análisis de laboratorio',
 'Muestras del periodo, cada resultado con su interpretación y la regla (fuente) vigente al momento del análisis.', 'lab_quality', '{}'),
('EC-ARCA', 'compliance', 'chlorine', 2, 'Control de cloro residual',
 'Mediciones de campo del periodo por tipo de punto: cuántas, cuántas dentro del rango, mínimo y máximo.', 'field_readings', '{"parameter_code": "free_chlorine"}'),
('EC-ARCA', 'compliance', 'sampling_plan', 3, 'Cumplimiento del plan de muestreo',
 'Muestras esperadas según la frecuencia de cada ítem del plan de la junta frente a las tomadas en el periodo.', 'sampling_plan', '{}'),
('EC-ARCA', 'compliance', 'alerts', 4, 'Alertas y emergencias',
 'Resultados fuera de rango del periodo, cuántos se cerraron, y emergencias activadas.', 'alerts_emergencies', '{}'),
('EC-ARCA', 'compliance', 'maintenance', 5, 'Mantenimiento y calendario anual',
 'Cumplimiento del calendario 7G al cierre del periodo.', 'maintenance_calendar', '{}'),
('EC-ARCA', 'compliance', 'sanitation', 6, 'Saneamiento',
 'Retiro de lodos, destino seguro verificado y descargas productivas.', 'sanitation', '{}');
GRANT SELECT ON report_template, report_section TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON report_template, report_section FROM renfygrid_app;

CREATE TABLE compliance_report (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id       text NOT NULL,
    report_code   text NOT NULL,
    period_from   date NOT NULL,
    period_to     date NOT NULL,
    content       jsonb NOT NULL,
    generated_by  text NOT NULL,
    generated_at  timestamptz NOT NULL DEFAULT now(),
    sent_to       text,
    sent_on       date,
    sent_by       text,
    sent_note     text,
    CHECK (period_from <= period_to),
    CHECK ((sent_to IS NULL) = (sent_on IS NULL)),
    FOREIGN KEY (pack_id, report_code) REFERENCES report_template(pack_id, code)
);
CREATE INDEX compliance_report_tenant_idx ON compliance_report (tenant_id, generated_at DESC);
ALTER TABLE compliance_report ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_report FORCE ROW LEVEL SECURITY;
CREATE POLICY compliance_report_tenant_isolation ON compliance_report FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE ON compliance_report TO renfygrid_app;

-- El contenido de un informe generado no se modifica: solo se registra el
-- envio, una vez.
CREATE FUNCTION compliance_report_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.content IS DISTINCT FROM OLD.content OR NEW.period_from <> OLD.period_from OR NEW.period_to <> OLD.period_to
       OR NEW.generated_at <> OLD.generated_at OR NEW.generated_by <> OLD.generated_by THEN
        RAISE EXCEPTION 'Un informe generado no se modifica; genere uno nuevo';
    END IF;
    IF OLD.sent_on IS NOT NULL THEN
        RAISE EXCEPTION 'El informe ya fue registrado como enviado';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER compliance_report_immutable BEFORE UPDATE ON compliance_report
    FOR EACH ROW EXECUTE FUNCTION compliance_report_immutable();

INSERT INTO app_permission (code, sort_order, area, label) VALUES
('report.generate', 31, 'Informes', 'Generar el informe de cumplimiento y registrar su envío');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'report.generate'), ('board', 'report.generate');
