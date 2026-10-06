-- RenfyGrid -- 0030_field_readings_operation_log.sql
-- Track D, D1.1 (2026-10-05): operacion diaria de la junta.
--   7B  Registro e interpretacion de cloro residual (Guia 3, seccion 3.4)
--   7C  Bitacora diaria de agua potable (Guia 3, secciones 3.3 y 3.10)
--   3.3 Rutina diaria en 5 momentos
--
-- Generico: los TIPOS de punto de muestreo van en `core` (toda operacion de
-- agua mide a la salida del tanque y en la red); la rutina de 5 momentos es
-- del paquete de programa; la interpretacion sale de `parameter_rule` del
-- paquete normativo (0021), que ahora tambien dice que hacer y con que
-- prioridad se abre un hallazgo. Lo de cada junta va en tablas con RLS.

-- ── Reglas: que hacer y prioridad del hallazgo, por tramo ─────────────
-- Textos de "Que hacer" de la Guia 3 (tabla de la seccion 3.4 y ficha 7B).
-- Prioridades: interpretacion propia con el mismo criterio de las listas
-- (riesgo para la salud = alta); son dato del paquete y se ajustan aqui.
UPDATE parameter_rule SET bands =
 '[{"upper": 0.3, "upper_inclusive": false, "code": "low", "label": "Bajo", "severity": "alert", "finding_priority": "high",
    "action": "Protección insuficiente. Revisar dosificador, dosis, producto, fugas y tiempo de contacto. Repetir medición. Si persiste, pedir apoyo técnico."},
   {"upper": 1.5, "upper_inclusive": true, "code": "adequate", "label": "Adecuado", "severity": "ok",
    "action": "Registrar el resultado, mantener la rutina y verificar también puntos lejanos."},
   {"upper": null, "code": "high", "label": "Alto", "severity": "alert", "finding_priority": "medium",
    "action": "Posible sobrecloración. Revisar dosis, repetir medición y ajustar con apoyo técnico."}]'
WHERE pack_id = 'EC-ARCA' AND parameter_code = 'free_chlorine';
UPDATE parameter_rule SET bands =
 '[{"upper": 5, "upper_inclusive": true, "code": "adequate", "label": "Adecuado", "severity": "ok",
    "action": "Mantener la observación diaria."},
   {"upper": null, "code": "high", "label": "Alto", "severity": "alert", "finding_priority": "high",
    "action": "Revisar la fuente, el desarenador, la sedimentación y los filtros. No compensar agua turbia aumentando el cloro."}]'
WHERE pack_id = 'EC-ARCA' AND parameter_code = 'turbidity';
UPDATE parameter_rule SET bands =
 '[{"upper": 6.5, "upper_inclusive": false, "code": "low", "label": "Bajo", "severity": "alert", "finding_priority": "medium",
    "action": "Solicitar apoyo técnico, especialmente si se usan coagulantes o reguladores de pH."},
   {"upper": 8.5, "upper_inclusive": true, "code": "adequate", "label": "Adecuado", "severity": "ok",
    "action": "Registrar el resultado."},
   {"upper": null, "code": "high", "label": "Alto", "severity": "alert", "finding_priority": "medium",
    "action": "Solicitar apoyo técnico, especialmente si se usan coagulantes o reguladores de pH."}]'
WHERE pack_id = 'EC-ARCA' AND parameter_code = 'ph';
UPDATE parameter_rule SET bands =
 '[{"upper": 0, "upper_inclusive": true, "code": "absent", "label": "Ausente", "severity": "ok",
    "action": "Archivar el informe de laboratorio."},
   {"upper": null, "code": "present", "label": "Presente", "severity": "critical", "finding_priority": "high",
    "action": "Activar una alerta, informar, corregir la fuente o el sistema, desinfectar y coordinar con GAD, MSP o ARCA."}]'
WHERE pack_id = 'EC-ARCA' AND parameter_code = 'e_coli';

-- ── Catalogo: tipos de punto de muestreo (core) ───────────────────────
-- `frequency_days`: solo donde la guia lo dice ("cada dia de operacion:
-- salida del reservorio"); los puntos de red rotan y cada junta fija su
-- frecuencia en su propio punto.
CREATE TABLE sampling_point_kind (
    code            text PRIMARY KEY,
    pack_id         text NOT NULL REFERENCES pack(id),
    sort_order      integer NOT NULL,
    label           text NOT NULL,
    purpose         text NOT NULL,
    frequency_days  integer CHECK (frequency_days IS NULL OR frequency_days > 0)
);
INSERT INTO sampling_point_kind (code, pack_id, sort_order, label, purpose, frequency_days) VALUES
('tank_outlet', 'core', 1, 'Salida del tanque', 'Confirmar que el agua inicia la distribución con protección; debe permitir que el extremo de la red conserve el mínimo.', 1),
('network_mid', 'core', 2, 'Punto medio de la red', 'Comprobar que el cloro se mantiene durante la distribución.', NULL),
('network_far', 'core', 3, 'Punto lejano', 'Confirmar que la protección llega al final de la red.', NULL),
('critical', 'core', 4, 'Punto crítico', 'Sector con más problemas: escuela, centro de salud, zona con quejas o baja presión.', NULL);

-- ── Catalogo: rutina diaria (paquete de programa) ─────────────────────
CREATE TABLE operation_moment (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    check_text  text NOT NULL,   -- que revisar
    record_text text NOT NULL,   -- que registrar
    PRIMARY KEY (pack_id, code)
);
INSERT INTO operation_moment (pack_id, code, sort_order, label, check_text, record_text) VALUES
('EC-MUNICIPIOS-AZULES', 'start', 1, 'Inicio del día',
 'Captación, nivel de reservorio, válvulas principales, estado de dosificadores y productos químicos.',
 'Hora, nivel, estado general y novedades visibles.'),
('EC-MUNICIPIOS-AZULES', 'morning', 2, 'Mañana',
 'Cloro residual en salida de tanque o punto cercano, color y turbiedad visual.',
 'Resultado de cloro, aspecto del agua y acción tomada.'),
('EC-MUNICIPIOS-AZULES', 'day', 3, 'Durante el día',
 'Fugas visibles, quejas, presión, funcionamiento de filtros o unidades de tratamiento.',
 'Lugar, tipo de problema y responsable informado.'),
('EC-MUNICIPIOS-AZULES', 'afternoon', 4, 'Tarde',
 'Cloro residual en punto medio o lejano, nivel de tanque y funcionamiento del sistema.',
 'Resultado, ajustes y observaciones.'),
('EC-MUNICIPIOS-AZULES', 'close', 5, 'Cierre',
 'Válvulas, programación de turnos, seguridad de bodega y equipos.',
 'Hora de cierre o apertura y pendientes para el día siguiente.');

GRANT SELECT ON sampling_point_kind, operation_moment TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON sampling_point_kind, operation_moment FROM renfygrid_app;

-- ── Por junta: puntos de medicion ─────────────────────────────────────
CREATE TABLE sampling_point (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    kind_code       text NOT NULL REFERENCES sampling_point_kind(code),
    name            text NOT NULL,
    asset_id        uuid REFERENCES network_asset(id),
    latitude        double precision CHECK (latitude BETWEEN -90 AND 90),
    longitude       double precision CHECK (longitude BETWEEN -180 AND 180),
    frequency_days  integer CHECK (frequency_days IS NULL OR frequency_days > 0),
    active          boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

-- ── Por junta: mediciones de campo (7B y demas parametros de campo) ───
-- La interpretacion se guarda tal como se calculo con la regla vigente
-- (`rule_id`), para que un cambio de norma no reescriba el historial.
-- `client_id`: lo genera el dispositivo; un reenvio de la app sin conexion
-- no duplica la medicion.
CREATE TABLE field_reading (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    sampling_point_id uuid REFERENCES sampling_point(id),
    parameter_code   text NOT NULL REFERENCES parameter(code),
    value            numeric NOT NULL,
    measured_at      timestamptz NOT NULL,
    measured_by      text NOT NULL,
    rule_id          uuid REFERENCES parameter_rule(id),
    result_code      text,
    result_label     text,
    severity         text CHECK (severity IN ('ok', 'alert', 'critical')),
    action_taken     text,
    finding_id       uuid REFERENCES finding(id),
    client_id        uuid,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, client_id)
);
CREATE INDEX field_reading_point_idx ON field_reading (tenant_id, sampling_point_id, parameter_code, measured_at DESC);
CREATE INDEX field_reading_time_idx ON field_reading (tenant_id, measured_at DESC);

-- ── Por junta: bitacora diaria (7C) ───────────────────────────────────
CREATE TABLE operation_log_entry (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    logged_at            timestamptz NOT NULL,
    pack_id              text,
    moment_code          text,
    tank_level_pct       numeric CHECK (tank_level_pct IS NULL OR tank_level_pct BETWEEN 0 AND 100),
    chlorine_applied     numeric CHECK (chlorine_applied IS NULL OR chlorine_applied >= 0),
    chlorine_applied_unit text CHECK (chlorine_applied_unit IN ('g', 'ml')),
    reading_id           uuid REFERENCES field_reading(id),
    appearance           text CHECK (appearance IN ('clear', 'turbid', 'colored')),
    status               text NOT NULL CHECK (status IN ('good', 'alert')),
    notes                text,
    logged_by            text NOT NULL,
    client_id            uuid,
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, client_id),
    FOREIGN KEY (pack_id, moment_code) REFERENCES operation_moment(pack_id, code),
    CHECK ((chlorine_applied IS NULL) = (chlorine_applied_unit IS NULL))
);
CREATE INDEX operation_log_entry_time_idx ON operation_log_entry (tenant_id, logged_at DESC);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['sampling_point', 'field_reading', 'operation_log_entry'] LOOP
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
