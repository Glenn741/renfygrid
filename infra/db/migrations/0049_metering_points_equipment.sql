-- RenfyGrid -- 0049_metering_points_equipment.sql
-- Track F, sprint Q2 (2026-10-20). docs/10-caso-energia-fronteras.md.
--
-- Hoja de vida, calibracion y mantenimiento de los sistemas de medicion de
-- un comercializador de energia. El modelo separa el LUGAR del EQUIPO (el
-- patron de SAP IS-U Device Management):
--
--   metering_point          -- la frontera comercial (el lugar)
--   equipment               -- el equipo fisico por numero de serie
--   equipment_installation  -- que equipo estuvo en que frontera, en que
--                              posicion y desde/hasta cuando
--   metering_event          -- la bitacora: calibraciones, pruebas de
--                              rutina, sellos, accesos de nivel 2, visitas,
--                              novedades; solo se agrega, nunca se edita
--   metering_point_section  -- las secciones de la hoja de vida que no son
--                              equipos (conductores, paneles, bornera...),
--                              como fichas del motor de formularios (0047)
--
-- Todo lo que depende del pais va en el paquete regulatorio `CO-CREG-038`
-- (Codigo de Medida, Resolucion CREG 038 de 2014): tipos de punto,
-- frecuencias de calibracion y de pruebas de rutina, tipos de novedad y los
-- campos de la hoja de vida (Circular CREG 119 de 2014; los genera
-- infra/db/tools/build_creg_hoja_vida.py en 0050). Nada de eso esta en el
-- codigo.

INSERT INTO pack (id, kind, country, name, version, source_note, sector_code) VALUES
('CO-CREG-038', 'regulatory', 'CO', 'Colombia — Código de Medida (CREG 038 de 2014)', '2026-10',
 'Resolución CREG 038 de 2014 (Código de Medida): art. 6 (tipos de punto), art. 11 (calibración), art. 28 tabla 4 (frecuencia de mantenimiento). Acuerdo CNO 981 de 2017 (pruebas de rutina de CT y PT, máximo 12 años). Circular CREG 119 de 2014 (hoja de vida).',
 'electricity');

-- ── Catalogos (globales, solo lectura para la aplicacion) ─────────────

CREATE TABLE equipment_class (
    code                  text PRIMARY KEY,
    sector_code           text NOT NULL REFERENCES sector(code),
    sort_order            integer NOT NULL,
    label                 text NOT NULL,
    plural                text NOT NULL,
    -- actividad periodica que exige este tipo de equipo (la frecuencia sale
    -- del paquete, `maintenance_frequency`)
    periodic_activity     text CHECK (periodic_activity IN ('calibration', 'routine_test'))
);
INSERT INTO equipment_class (code, sector_code, sort_order, label, plural, periodic_activity) VALUES
('meter', 'electricity', 1, 'Medidor', 'Medidores', 'calibration'),
('ct',    'electricity', 2, 'Transformador de corriente (CT)', 'Transformadores de corriente', 'routine_test'),
('pt',    'electricity', 3, 'Transformador de tensión (PT)', 'Transformadores de tensión', 'routine_test'),
('modem', 'electricity', 4, 'Módem de comunicaciones', 'Módems', NULL);

-- `novelty_type`: la novedad de la hoja de vida que genera instalar un
-- equipo en esta posicion de una frontera que ya estaba en servicio.
CREATE TABLE installation_position (
    code             text PRIMARY KEY,
    sector_code      text NOT NULL REFERENCES sector(code),
    equipment_class  text NOT NULL REFERENCES equipment_class(code),
    sort_order       integer NOT NULL,
    label            text NOT NULL,
    novelty_type     text            -- FK al final (metering_event_type)
);
INSERT INTO installation_position (code, sector_code, equipment_class, sort_order, label, novelty_type) VALUES
('main_active',   'electricity', 'meter', 1, 'Medidor principal (energía activa)', 'meter_change_main'),
('main_reactive', 'electricity', 'meter', 2, 'Medidor principal (energía reactiva)', 'meter_change_main'),
('backup',        'electricity', 'meter', 3, 'Medidor de respaldo', 'meter_change_backup'),
('ct_1',          'electricity', 'ct', 4, 'CT fase 1', 'ct_change'),
('ct_2',          'electricity', 'ct', 5, 'CT fase 2', 'ct_change'),
('ct_3',          'electricity', 'ct', 6, 'CT fase 3', 'ct_change'),
('pt_1',          'electricity', 'pt', 7, 'PT fase 1', 'pt_change'),
('pt_2',          'electricity', 'pt', 8, 'PT fase 2', 'pt_change'),
('pt_3',          'electricity', 'pt', 9, 'PT fase 3', 'pt_change'),
('modem_main',    'electricity', 'modem', 10, 'Módem del medidor principal', 'modem_change'),
('modem_backup',  'electricity', 'modem', 11, 'Módem del medidor de respaldo', 'modem_change');

-- Tipo de punto de medicion (art. 6): consumo o transferencia mensual (MWh)
-- o capacidad instalada (MVA), lo que de el tipo mas exigente.
CREATE TABLE metering_point_class (
    pack_id         text NOT NULL REFERENCES pack(id),
    code            text NOT NULL,
    sort_order      integer NOT NULL,
    label           text NOT NULL,
    min_mwh_month   numeric NOT NULL,
    min_mva         numeric NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO metering_point_class (pack_id, code, sort_order, label, min_mwh_month, min_mva) VALUES
('CO-CREG-038', '1', 1, 'Tipo 1', 15000, 30),
('CO-CREG-038', '2', 2, 'Tipo 2', 500, 1),
('CO-CREG-038', '3', 3, 'Tipo 3', 50, 0.1),
('CO-CREG-038', '4', 4, 'Tipo 4', 5, 0.01),
('CO-CREG-038', '5', 5, 'Tipo 5', 0, 0);

CREATE TABLE maintenance_frequency (
    pack_id          text NOT NULL,
    point_class      text NOT NULL,
    equipment_class  text NOT NULL REFERENCES equipment_class(code),
    activity         text NOT NULL CHECK (activity IN ('calibration', 'routine_test')),
    every_months     integer NOT NULL CHECK (every_months > 0),
    citation         text NOT NULL,
    PRIMARY KEY (pack_id, point_class, equipment_class, activity),
    FOREIGN KEY (pack_id, point_class) REFERENCES metering_point_class(pack_id, code)
);
INSERT INTO maintenance_frequency (pack_id, point_class, equipment_class, activity, every_months, citation)
SELECT 'CO-CREG-038', c, 'meter', 'calibration', m, 'Resolución CREG 038 de 2014, art. 28, tabla 4'
FROM (VALUES ('1', 24), ('2', 48), ('3', 48), ('4', 120), ('5', 120)) AS f(c, m);
INSERT INTO maintenance_frequency (pack_id, point_class, equipment_class, activity, every_months, citation)
SELECT 'CO-CREG-038', c, e, 'routine_test', 144, 'Acuerdo CNO 981 de 2017, numeral 8 (art. 28 de la CREG 038 de 2014)'
FROM (VALUES ('1'), ('2'), ('3'), ('4'), ('5')) AS f(c) CROSS JOIN (VALUES ('ct'), ('pt')) AS q(e);

-- Tipos de registro de la bitacora. `scope`: sobre la frontera o sobre un
-- equipo. `activity`: si cumple la actividad periodica (calibracion o
-- prueba de rutina). `requires_xm_update`: la novedad obliga a actualizar
-- el registro de la frontera ante el ASIC (cambio de un equipo registrado:
-- medidor, CT o PT); las demas novedades actualizan solo la hoja de vida. `invalidates_calibration`: el
-- equipo debe volver a calibrarse ('always' o la clave de un campo booleano
-- de `data_spec` que lo indica, p. ej. retirar el sello de la tapa
-- principal, art. 11). `data_spec`: los datos del registro, como ficha.
CREATE TABLE metering_event_type (
    code                     text PRIMARY KEY,
    pack_id                  text NOT NULL REFERENCES pack(id),
    sector_code              text REFERENCES sector(code),
    sort_order               integer NOT NULL,
    label                    text NOT NULL,
    scope                    text NOT NULL CHECK (scope IN ('point', 'equipment', 'any')),
    activity                 text CHECK (activity IN ('calibration', 'routine_test')),
    requires_xm_update       boolean NOT NULL DEFAULT false,
    invalidates_calibration  text,
    manual                   boolean NOT NULL DEFAULT true,   -- false: solo lo genera el sistema
    data_spec                jsonb NOT NULL DEFAULT '{"fields": []}',
    source_ref               text
);
INSERT INTO metering_event_type (code, pack_id, sector_code, sort_order, label, scope, activity, requires_xm_update, invalidates_calibration, manual, data_spec, source_ref) VALUES
('installed', 'core', NULL, 1, 'Instalación', 'equipment', NULL, false, NULL, false, '{"fields": []}', NULL),
('removed', 'core', NULL, 2, 'Retiro', 'equipment', NULL, false, NULL, false, '{"fields": []}', NULL),
('note', 'core', NULL, 3, 'Observación', 'any', NULL, false, NULL, true, '{"fields": []}', NULL),
('initial_verification', 'CO-CREG-038', 'electricity', 10, 'Hoja de vida inicial — verificación inicial', 'point', NULL, false, NULL, true,
 '{"fields": [{"key": "verifier", "label": "Firma o persona que verifica", "type": "text", "required": true}, {"key": "report_number", "label": "Número del informe", "type": "text"}]}', 'CREG 038/2014 art. 23; Circular 119/2014 §1.2'),
('verification_visit', 'CO-CREG-038', 'electricity', 11, 'Visita de verificación', 'point', NULL, false, NULL, true,
 '{"fields": [{"key": "result", "label": "Resultado", "type": "choice", "required": true, "options": [{"code": "ok", "label": "Dentro de la precisión del equipo"}, {"code": "corrected", "label": "Con correcciones en sitio"}, {"code": "new_visit", "label": "Requiere nueva visita"}]}, {"key": "report_number", "label": "Número del acta", "type": "text"}]}', 'Circular 119/2014 §1.2'),
('scheduled_maintenance', 'CO-CREG-038', 'electricity', 12, 'Mantenimiento programado', 'point', NULL, false, NULL, true,
 '{"fields": [{"key": "report_number", "label": "Número del acta", "type": "text"}]}', 'CREG 038/2014 art. 28; Circular 119/2014 §1.2'),
('onsite_reading', 'CO-CREG-038', 'electricity', 13, 'Lectura en sitio', 'point', NULL, false, NULL, true,
 '{"fields": [{"key": "reading_kwh", "label": "Lectura de energía activa (kWh)", "type": "number"}]}', 'Circular 119/2014 §1.2'),
('cell_adequacy', 'CO-CREG-038', 'electricity', 14, 'Adecuaciones en celda de medida', 'point', NULL, false, NULL, true, '{"fields": []}', 'Circular 119/2014 §1.2'),
('meter_parametrization', 'CO-CREG-038', 'electricity', 15, 'Parametrización de medidor', 'equipment', NULL, false, 'affects_calibration', true,
 '{"fields": [{"key": "affects_calibration", "label": "El cambio de programación afecta la calibración", "type": "boolean"}]}', 'CREG 038/2014 art. 32; Circular 119/2014 §1.2'),
('time_update', 'CO-CREG-038', 'electricity', 16, 'Actualización de hora', 'equipment', NULL, false, NULL, true, '{"fields": []}', 'Circular 119/2014 §1.2'),
('meter_change_main', 'CO-CREG-038', 'electricity', 20, 'Cambio de medidor principal', 'point', NULL, true, NULL, false, '{"fields": []}', 'Circular 119/2014 §1.2'),
('meter_change_backup', 'CO-CREG-038', 'electricity', 21, 'Cambio de medidor de respaldo', 'point', NULL, true, NULL, false, '{"fields": []}', 'Circular 119/2014 §1.2'),
('ct_change', 'CO-CREG-038', 'electricity', 22, 'Cambio de transformador de corriente', 'point', NULL, true, NULL, false, '{"fields": []}', 'Circular 119/2014 §1.2'),
('pt_change', 'CO-CREG-038', 'electricity', 23, 'Cambio de transformador de tensión', 'point', NULL, true, NULL, false, '{"fields": []}', 'Circular 119/2014 §1.2'),
('modem_change', 'CO-CREG-038', 'electricity', 24, 'Cambio de módem', 'point', NULL, false, NULL, false, '{"fields": []}', 'Circular 119/2014 §1.2'),
('calibration', 'CO-CREG-038', 'electricity', 30, 'Calibración', 'equipment', 'calibration', false, NULL, true,
 '{"fields": [{"key": "certificate_number", "label": "Número del certificado", "type": "text", "required": true}, {"key": "laboratory", "label": "Laboratorio", "type": "text", "required": true}, {"key": "accredited", "label": "Laboratorio acreditado", "type": "boolean"}, {"key": "issued_on", "label": "Fecha de emisión del certificado", "type": "date", "required": true}, {"key": "error_pct", "label": "Error encontrado (%)", "type": "number", "signed": true}, {"key": "result", "label": "Resultado", "type": "choice", "required": true, "options": [{"code": "pass", "label": "Conforme"}, {"code": "fail", "label": "No conforme"}]}]}', 'CREG 038/2014 art. 11 y 28; Circular 119/2014 §3.40'),
('routine_test', 'CO-CREG-038', 'electricity', 31, 'Prueba de rutina', 'equipment', 'routine_test', false, NULL, true,
 '{"fields": [{"key": "certificate_number", "label": "Número del certificado", "type": "text", "required": true}, {"key": "issued_on", "label": "Fecha de emisión", "type": "date", "required": true}, {"key": "laboratory", "label": "Laboratorio o firma", "type": "text"}, {"key": "result", "label": "Resultado", "type": "choice", "required": true, "options": [{"code": "pass", "label": "Conforme"}, {"code": "fail", "label": "No conforme"}]}]}', 'Acuerdo CNO 981/2017; Circular 119/2014 §6.21'),
('seal_installed', 'CO-CREG-038', 'electricity', 40, 'Instalación de sello', 'any', NULL, false, NULL, true,
 '{"fields": [{"key": "serial", "label": "Serie del sello", "type": "text", "required": true}, {"key": "location", "label": "Ubicación", "type": "text", "required": true}, {"key": "seal_type", "label": "Tipo", "type": "text"}, {"key": "color", "label": "Color", "type": "text"}, {"key": "ownership", "label": "Propiedad", "type": "choice", "options": [{"code": "user", "label": "Usuario"}, {"code": "rf", "label": "RF"}, {"code": "or", "label": "OR"}]}]}', 'Circular 119/2014 §3.27'),
('seal_removed', 'CO-CREG-038', 'electricity', 41, 'Retiro de sello', 'any', NULL, false, 'main_cover', true,
 '{"fields": [{"key": "serial", "label": "Serie del sello", "type": "text", "required": true}, {"key": "location", "label": "Ubicación", "type": "text"}, {"key": "main_cover", "label": "Sello de la tapa principal del medidor", "type": "boolean"}]}', 'CREG 038/2014 art. 11; Circular 119/2014 §3.27'),
('level2_access', 'CO-CREG-038', 'electricity', 42, 'Acceso a nivel 2 del medidor', 'equipment', NULL, false, NULL, true,
 '{"fields": [{"key": "responsible", "label": "Responsable", "type": "text", "required": true}, {"key": "reason", "label": "Motivo o novedad", "type": "text", "required": true}]}', 'Circular 119/2014 §13 y §14'),
('battery_change', 'CO-CREG-038', 'electricity', 43, 'Cambio de batería', 'equipment', NULL, false, NULL, true, '{"fields": []}', 'Circular 119/2014 §3.33');

ALTER TABLE installation_position ADD CONSTRAINT installation_position_novelty_fkey
    FOREIGN KEY (novelty_type) REFERENCES metering_event_type(code);

-- Formularios de la hoja de vida (los llena 0050 desde la Circular 119).
-- `scope = 'point'`: seccion de la frontera; `scope = 'equipment'`: datos
-- tecnicos de un tipo de equipo.
CREATE TABLE asset_form (
    id               text PRIMARY KEY,
    pack_id          text NOT NULL REFERENCES pack(id),
    scope            text NOT NULL CHECK (scope IN ('point', 'equipment')),
    equipment_class  text REFERENCES equipment_class(code),
    sort_order       integer NOT NULL,
    title            text NOT NULL,
    form_spec        jsonb NOT NULL,
    source_ref       text NOT NULL,
    CHECK ((scope = 'equipment') = (equipment_class IS NOT NULL))
);

INSERT INTO code_label (pack_id, domain, code, sort_order, label, tone) VALUES
('core', 'metering_point.status', 'active', 1, 'Activa', 'success'),
('core', 'metering_point.status', 'suspended', 2, 'Suspendida', 'warning'),
('core', 'metering_point.status', 'failure', 3, 'En falla', 'danger'),
('core', 'metering_point.status', 'cancelled', 4, 'Cancelada', 'neutral'),
('core', 'equipment.status', 'installed', 1, 'Instalado', 'success'),
('core', 'equipment.status', 'stock', 2, 'En bodega', 'info'),
('core', 'equipment.status', 'lab', 3, 'En laboratorio', 'warning'),
('core', 'equipment.status', 'retired', 4, 'Dado de baja', 'neutral'),
('core', 'equipment.ownership', 'user', 1, 'Usuario', NULL),
('core', 'equipment.ownership', 'rf', 2, 'Representante de la frontera', NULL),
('core', 'equipment.ownership', 'or', 3, 'Operador de red', NULL),
('core', 'periodic.status', 'ok', 1, 'Al día', 'success'),
('core', 'periodic.status', 'due_soon', 2, 'Por vencer', 'warning'),
('core', 'periodic.status', 'overdue', 3, 'Vencida', 'danger'),
('core', 'periodic.status', 'missing', 4, 'Sin registro', 'danger'),
('core', 'periodic.status', 'not_required', 5, 'No aplica', 'neutral'),
('core', 'xm.status', 'pending', 1, 'Pendiente de reportar', 'warning'),
('core', 'xm.status', 'reported', 2, 'Reportada a XM', 'success'),
('core', 'event.source', 'manual', 1, 'Registro manual', NULL),
('core', 'event.source', 'import', 2, 'Carga por archivo', NULL),
('core', 'event.source', 'field', 3, 'Trabajo de campo', NULL),
('core', 'event.source', 'system', 4, 'Sistema', NULL);

GRANT SELECT ON equipment_class, installation_position, metering_point_class, maintenance_frequency,
                metering_event_type, asset_form TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON equipment_class, installation_position, metering_point_class, maintenance_frequency,
                metering_event_type, asset_form FROM renfygrid_app;

-- ── Tablas por organizacion (RLS) ─────────────────────────────────────

CREATE TABLE metering_point (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              uuid NOT NULL REFERENCES tenant(id),
    code                   text NOT NULL,            -- código SIC de importación (o el que use la empresa)
    export_code            text,                     -- código SIC de exportación
    niu                    text,                     -- código NIU asignado por el OR
    name                   text NOT NULL,
    customer_name          text NOT NULL,
    address                text,
    city                   text,
    region                 text,                     -- departamento
    lat                    numeric,
    lon                    numeric,
    point_class            text,                     -- tipo de punto del paquete (1-5)
    pack_id                text REFERENCES pack(id),
    voltage_kv             numeric,
    capacity_kva           numeric,
    consumption_mwh_month  numeric,
    status                 text NOT NULL DEFAULT 'active',
    registered_on          date,                     -- matrícula ante el ASIC
    verified_on            date,                     -- verificación inicial
    created_by             text NOT NULL,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pack_id, point_class) REFERENCES metering_point_class(pack_id, code)
);
CREATE UNIQUE INDEX metering_point_code_uq ON metering_point (tenant_id, lower(btrim(code)));

CREATE TABLE equipment (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    class_code    text NOT NULL REFERENCES equipment_class(code),
    serial        text NOT NULL,
    brand         text,
    model         text,
    manufacturer  text,
    year          integer,
    ownership     text,
    status        text NOT NULL DEFAULT 'stock',
    attributes    jsonb NOT NULL DEFAULT '{"fields": {}}',   -- ficha técnica (asset_form del tipo)
    created_by    text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX equipment_serial_uq ON equipment (tenant_id, class_code, lower(coalesce(brand, '')), lower(btrim(serial)));

CREATE TABLE equipment_installation (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    equipment_id    uuid NOT NULL REFERENCES equipment(id),
    point_id        uuid NOT NULL REFERENCES metering_point(id),
    position_code   text NOT NULL REFERENCES installation_position(code),
    installed_on    date NOT NULL,
    removed_on      date,
    installed_by    text NOT NULL,
    removed_by      text,
    removal_reason  text,
    CHECK (removed_on IS NULL OR removed_on >= installed_on)
);
-- Un equipo esta en un solo lugar y una posicion tiene un solo equipo.
CREATE UNIQUE INDEX equipment_installation_equipment_uq ON equipment_installation (equipment_id) WHERE removed_on IS NULL;
CREATE UNIQUE INDEX equipment_installation_position_uq ON equipment_installation (point_id, position_code) WHERE removed_on IS NULL;
CREATE INDEX equipment_installation_point_idx ON equipment_installation (point_id);

CREATE TABLE metering_event (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             uuid NOT NULL REFERENCES tenant(id),
    point_id              uuid REFERENCES metering_point(id),
    equipment_id          uuid REFERENCES equipment(id),
    type_code             text NOT NULL REFERENCES metering_event_type(code),
    occurred_on           date NOT NULL,
    data                  jsonb NOT NULL DEFAULT '{"fields": {}}',
    notes                 text,
    source                text NOT NULL DEFAULT 'manual',
    external_ref          text,                -- orden de campo (BayForce) u otro sistema
    maintenance_order_id  uuid,
    recorded_by           text NOT NULL,
    recorded_at           timestamptz NOT NULL DEFAULT now(),
    xm_status             text,                -- NULL si la novedad no se reporta
    xm_reported_on        date,
    xm_reported_by        text,
    CHECK (point_id IS NOT NULL OR equipment_id IS NOT NULL)
);
CREATE INDEX metering_event_point_idx ON metering_event (point_id, occurred_on DESC);
CREATE INDEX metering_event_equipment_idx ON metering_event (equipment_id, occurred_on DESC);
CREATE INDEX metering_event_xm_idx ON metering_event (tenant_id) WHERE xm_status = 'pending';

CREATE TABLE metering_point_section (
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    point_id    uuid NOT NULL REFERENCES metering_point(id),
    form_id     text NOT NULL REFERENCES asset_form(id),
    data        jsonb NOT NULL,
    version     integer NOT NULL DEFAULT 1,
    updated_by  text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (point_id, form_id)
);

CREATE TABLE metering_point_section_version (
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    point_id    uuid NOT NULL REFERENCES metering_point(id),
    form_id     text NOT NULL REFERENCES asset_form(id),
    version     integer NOT NULL,
    data        jsonb NOT NULL,
    saved_by    text NOT NULL,
    saved_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (point_id, form_id, version)
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['metering_point', 'equipment', 'equipment_installation', 'metering_event',
                             'metering_point_section', 'metering_point_section_version'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (tenant_id = current_setting(''app.tenant_id'', true)::uuid) '
                       'WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true)::uuid)', t || '_tenant_isolation', t);
    END LOOP;
END $$;

-- REVOKE explicito primero: donde las migraciones corren con el rol que
-- creo los default privileges de 0002 (BD local), las tablas nuevas nacen
-- con ALL para la aplicacion y el GRANT de abajo no restringiria nada
-- (encontrado por verify_energy_assets_end_to_end, 2026-10-20).
REVOKE ALL ON metering_point, equipment, equipment_installation, metering_event, metering_point_section,
              metering_point_section_version FROM renfygrid_app;
GRANT SELECT, INSERT, UPDATE ON metering_point, equipment, equipment_installation, metering_point_section TO renfygrid_app;
GRANT SELECT, INSERT ON metering_point_section_version TO renfygrid_app;
-- La bitacora solo crece: no se edita ni se borra. Lo unico que cambia de
-- un registro es su estado de reporte ante XM.
GRANT SELECT, INSERT ON metering_event TO renfygrid_app;
GRANT UPDATE (xm_status, xm_reported_on, xm_reported_by) ON metering_event TO renfygrid_app;

-- La aplicacion no puede borrar fronteras, equipos ni la bitacora. Las
-- pruebas end-to-end (que corren con el rol de aplicacion, tambien contra
-- produccion) limpian lo que crearon con esta funcion, que SOLO acepta
-- organizaciones de prueba (codigo "e2e-...").
CREATE FUNCTION e2e_purge_metering_assets(p_tenant uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tenant WHERE id = p_tenant AND name LIKE 'e2e-%') THEN
        RAISE EXCEPTION 'Solo se purgan organizaciones de prueba (e2e-...)';
    END IF;
    DELETE FROM metering_point_section_version WHERE tenant_id = p_tenant;
    DELETE FROM metering_point_section WHERE tenant_id = p_tenant;
    DELETE FROM metering_event WHERE tenant_id = p_tenant;
    DELETE FROM equipment_installation WHERE tenant_id = p_tenant;
    DELETE FROM equipment WHERE tenant_id = p_tenant;
    DELETE FROM metering_point WHERE tenant_id = p_tenant;
END $$;
REVOKE ALL ON FUNCTION e2e_purge_metering_assets(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION e2e_purge_metering_assets(uuid) TO renfygrid_app;

-- ── Permisos ──────────────────────────────────────────────────────────
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('assets.manage', 44, 'Activos', 'Registrar fronteras y equipos, instalarlos y retirarlos, y cargarlos por archivo'),
('assets.record', 45, 'Activos', 'Registrar calibraciones, pruebas, sellos, accesos y visitas en la hoja de vida'),
('assets.report', 46, 'Activos', 'Marcar novedades como reportadas a XM');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'assets.manage'), ('supervisor', 'assets.record'), ('supervisor', 'assets.report'),
('board', 'assets.report'),
('operator', 'assets.record');

-- ── Modulos del sector energia ────────────────────────────────────────
INSERT INTO product_module (code, path, group_code, sort_order, label, icon, description, kinds, sectors) VALUES
('energy', '/energy', 'energy', 1, 'Tablero de fronteras', 'overview', 'Fronteras por tipo de punto, calibraciones vencidas y por vencer, y novedades pendientes de reportar', '{provider,group}', '{electricity}'),
('energy-points', '/energy/points', 'energy', 2, 'Fronteras comerciales', 'meter-point', 'Cada frontera con su hoja de vida: equipos instalados, calibraciones, sellos y novedades', '{provider,group}', '{electricity}'),
('energy-equipment', '/energy/equipment', 'energy', 3, 'Equipos', 'equipment', 'Medidores, CT, PT y módems por número de serie, con su historial', '{provider,group}', '{electricity}');
