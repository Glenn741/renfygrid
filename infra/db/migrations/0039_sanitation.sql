-- RenfyGrid -- 0039_sanitation.sql
-- Track D, D6 (2026-10-06): saneamiento. Fuente: Guia 3 de Municipios
-- Azules, secciones 3.7-3.8, Actividad participativa 5 y ficha 7F
-- ("Registre tambien quien retiro los residuos y a que sitio seguro fueron
-- llevados"; "la directiva verifica el destino seguro").
--
--   - 7F sobre el CMMS: la orden de mantenimiento de un componente de
--     saneamiento registra quien retiro los residuos, el destino seguro y el
--     volumen de lodos; la directiva verifica el destino.
--   - Lodos: "retiro de lodos al menos una vez al ano o segun diseno, uso y
--     nivel de lodos" -> plazo del paquete; tipos que acumulan lodos, en el
--     catalogo de componentes.
--   - Descargas productivas (queseras, chancheras, camales, lavanderias,
--     textileras...) con seguimiento.
--   - DBO y DQO como parametros de laboratorio (sin regla: los interpreta
--     personal tecnico, dice la guia); una muestra puede ser de una descarga.

ALTER TABLE maintenance_order ADD COLUMN waste_handler text;
ALTER TABLE maintenance_order ADD COLUMN waste_destination text;
ALTER TABLE maintenance_order ADD COLUMN sludge_volume_m3 numeric CHECK (sludge_volume_m3 IS NULL OR sludge_volume_m3 >= 0);
ALTER TABLE maintenance_order ADD COLUMN destination_verified_by text;
ALTER TABLE maintenance_order ADD COLUMN destination_verified_at timestamptz;

ALTER TABLE component_type ADD COLUMN accumulates_sludge boolean NOT NULL DEFAULT false;
UPDATE component_type SET accumulates_sludge = true WHERE code IN ('septic_tank', 'wastewater_plant');

INSERT INTO program_rule (pack_id, code, value_days, source) VALUES
('EC-MUNICIPIOS-AZULES', 'sludge_extraction_max_days', 365,
 'Guía 3 §3.8: retiro de lodos al menos una vez al año o según diseño, uso y nivel de lodos.');

INSERT INTO parameter (code, label, unit, measured_by) VALUES
('bod5', 'DBO (Demanda Bioquímica de Oxígeno)', 'mg/L', 'lab'),
('cod', 'DQO (Demanda Química de Oxígeno)', 'mg/L', 'lab')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE discharge_activity (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO discharge_activity (pack_id, code, sort_order, label) VALUES
('EC-MUNICIPIOS-AZULES', 'cheese_factory', 1, 'Quesera'),
('EC-MUNICIPIOS-AZULES', 'pig_farm', 2, 'Chanchera'),
('EC-MUNICIPIOS-AZULES', 'slaughterhouse', 3, 'Camal'),
('EC-MUNICIPIOS-AZULES', 'laundry', 4, 'Lavandería'),
('EC-MUNICIPIOS-AZULES', 'textile', 5, 'Textilera'),
('EC-MUNICIPIOS-AZULES', 'other', 6, 'Otra actividad productiva');
GRANT SELECT ON discharge_activity TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON discharge_activity FROM renfygrid_app;

CREATE TABLE productive_discharge (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id          text NOT NULL,
    activity_code    text NOT NULL,
    name             text NOT NULL,
    owner            text,
    location_text    text,
    asset_id         uuid REFERENCES network_asset(id),
    problem          text,
    status           text NOT NULL DEFAULT 'identified'
                     CHECK (status IN ('identified', 'agreement', 'controlled', 'closed')),
    agreement        text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    created_by       text NOT NULL,
    FOREIGN KEY (pack_id, activity_code) REFERENCES discharge_activity(pack_id, code)
);

CREATE TABLE productive_discharge_followup (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    discharge_id   uuid NOT NULL REFERENCES productive_discharge(id) ON DELETE CASCADE,
    noted_at       timestamptz NOT NULL DEFAULT now(),
    note           text NOT NULL,
    new_status     text CHECK (new_status IN ('identified', 'agreement', 'controlled', 'closed')),
    noted_by       text NOT NULL
);

ALTER TABLE lab_sample ADD COLUMN discharge_id uuid REFERENCES productive_discharge(id);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['productive_discharge', 'productive_discharge_followup'] LOOP
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

INSERT INTO app_permission (code, sort_order, area, label) VALUES
('sanitation.record', 23, 'Saneamiento', 'Registrar descargas productivas y su seguimiento'),
('sanitation.verify', 24, 'Saneamiento', 'Verificar el destino seguro de residuos y lodos (7F)');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'sanitation.record'), ('supervisor', 'sanitation.verify'),
('board', 'sanitation.record'), ('board', 'sanitation.verify'),
('operator', 'sanitation.record');
