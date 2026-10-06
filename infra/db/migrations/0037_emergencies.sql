-- RenfyGrid -- 0037_emergencies.sql
-- Track D, D5 (2026-10-06): plan de emergencia de la junta. Fuente: Guia 3 de
-- Municipios Azules, seccion 3.11 ("Las emergencias no se improvisan. La JAAPS
-- debe saber quien activa la respuesta, quien comunica, que se hace primero y
-- a que institucion se informa") y Actividad participativa 6 (plan basico).
--
-- Catalogo del paquete: los 6 tipos de la tabla de la seccion 3.11 con sus
-- textos literales (senales, que hacer primero, a quien avisar) y, donde el
-- ejemplo de la Actividad 6 lo trae, responsable/primera accion y mensaje a
-- la comunidad (en la rotura principal se quito el nombre de los sectores del
-- caso ficticio: "sectores afectados"). Cada junta parte de ahi y lo edita. Los telefonos
-- de las instituciones no estan en la guia: los carga cada junta.
-- Activacion automatica: por regla del paquete (E. coli presente ->
-- contaminacion). "Turbiedad extrema" no tiene umbral en la guia: no se
-- inventa; queda activacion manual.

CREATE TABLE emergency_type (
    pack_id            text NOT NULL REFERENCES pack(id),
    code               text NOT NULL,
    sort_order         integer NOT NULL,
    label              text NOT NULL,
    signals            text NOT NULL,
    first_action       text NOT NULL,
    notify             text NOT NULL,
    example_responsible text,
    example_message    text,
    example_support    text,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO emergency_type (pack_id, code, sort_order, label, signals, first_action, notify, example_responsible, example_message, example_support) VALUES
('EC-MUNICIPIOS-AZULES', 'heavy_rain', 1, 'Lluvias fuertes',
 'Agua café, captación tapada, deslizamientos.',
 'Cerrar captación si hay riesgo, avisar que hiervan el agua, revisar turbiedad y cloro.',
 'Directiva, GAD, ARCA si hay afectación.', NULL, NULL, NULL),
('EC-MUNICIPIOS-AZULES', 'drought', 2, 'Sequía',
 'Caudal bajo, tanque no llena, sectores sin agua.',
 'Racionar con horarios, cuidar usos y buscar fuente alterna.',
 'GAD, COE cantonal.',
 'La directiva activa horarios de distribución y el operador registra el nivel del reservorio.',
 'Usar el agua solo para consumo, higiene y preparación de alimentos. Respetar los horarios.',
 'GAD y COE cantonal.'),
('EC-MUNICIPIOS-AZULES', 'main_break', 3, 'Rotura principal',
 'Fuga grande, sector sin agua.',
 'Cerrar válvula, comunicar, reparar o pedir apoyo.',
 'Directiva, GAD, técnico.',
 'El operador cierra la válvula del tramo, identifica el daño y comunica a la directiva.',
 'El servicio estará suspendido en los sectores afectados. Almacenar solo el agua necesaria.',
 'GAD o técnico para reparación si supera la capacidad local.'),
('EC-MUNICIPIOS-AZULES', 'contamination', 4, 'Contaminación de agua',
 'E. coli, olor extraño, brote de diarrea, color anormal.',
 'Suspender si hay riesgo, informar, tomar muestras y corregir la causa.',
 'MSP, ARCA, GAD.',
 'El operador cierra la captación si existe riesgo, toma una muestra y avisa a la presidencia. La directiva activa el plan.',
 'No consumir el agua hasta nuevo aviso. Hervir el agua disponible y usar fuentes seguras.',
 'GAD, MSP y ARCA, según la afectación.'),
('EC-MUNICIPIOS-AZULES', 'sewage_overflow', 5, 'Rebose de aguas residuales',
 'Aguas negras en calle, vivienda, escuela o cerca de fuente.',
 'Aislar zona, evitar contacto, usar EPP, reducir uso si es posible y pedir apoyo inmediato.',
 'GAD, MSP, ECU 911 si hay riesgo.',
 'El operador señaliza, evita el contacto, usa EPP y avisa a la directiva.',
 'Evitar el área y mantener alejados a niñas, niños y animales hasta resolver el problema.',
 'GAD y MSP.'),
('EC-MUNICIPIOS-AZULES', 'treatment_collapse', 6, 'Colapso de fosa o planta',
 'Olor fuerte, lodos expuestos, efluente sin tratar.',
 'Señalizar, evitar contacto, reducir uso si es posible y solicitar succión o apoyo técnico.',
 'GAD, ministerio rector, MSP según el caso.', NULL, NULL, NULL);

-- Activacion automatica: resultado con esta severidad en este parametro.
CREATE TABLE emergency_auto_trigger (
    pack_id               text NOT NULL,
    parameter_code        text NOT NULL REFERENCES parameter(code),
    severity              text NOT NULL CHECK (severity IN ('alert', 'critical')),
    emergency_type_code   text NOT NULL,
    PRIMARY KEY (pack_id, parameter_code, severity),
    FOREIGN KEY (pack_id, emergency_type_code) REFERENCES emergency_type(pack_id, code)
);
INSERT INTO emergency_auto_trigger (pack_id, parameter_code, severity, emergency_type_code) VALUES
('EC-MUNICIPIOS-AZULES', 'e_coli', 'critical', 'contamination');

INSERT INTO program_rule (pack_id, code, value_days, source) VALUES
('EC-MUNICIPIOS-AZULES', 'emergency_plan_review_days', 365,
 'Guía 3, calendario 7G: revisión del plan de emergencia antes de la época de lluvias y una vez al año.');

GRANT SELECT ON emergency_type, emergency_auto_trigger TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON emergency_type, emergency_auto_trigger FROM renfygrid_app;

-- ── Por junta ─────────────────────────────────────────────────────────
-- Plan: una fila por tipo del catalogo que la junta ajusto, o por una
-- emergencia propia (custom_label). Lo no ajustado se muestra con el texto del
-- catalogo.
CREATE TABLE emergency_plan_entry (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id             text,
    type_code           text,
    custom_label        text,
    responsible         text,
    first_action        text,
    community_message   text,
    external_support    text,
    resources           text,
    active              boolean NOT NULL DEFAULT true,
    updated_at          timestamptz NOT NULL DEFAULT now(),
    updated_by          text NOT NULL,
    FOREIGN KEY (pack_id, type_code) REFERENCES emergency_type(pack_id, code),
    CHECK ((type_code IS NOT NULL) <> (custom_label IS NOT NULL)),
    UNIQUE (tenant_id, pack_id, type_code)
);

CREATE TABLE emergency_contact (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    institution  text NOT NULL,
    person       text,
    phone        text NOT NULL,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE emergency_activation (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id          text,
    type_code        text,
    plan_entry_id    uuid REFERENCES emergency_plan_entry(id),
    label            text NOT NULL,
    trigger          text NOT NULL CHECK (trigger IN ('manual', 'auto')),
    trigger_ref      text,
    activated_at     timestamptz NOT NULL DEFAULT now(),
    activated_by     text NOT NULL,
    notes            text,
    status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed')),
    closed_at        timestamptz,
    closed_by        text,
    closing_notes    text
);
CREATE INDEX emergency_activation_tenant_idx ON emergency_activation (tenant_id, status, activated_at DESC);

CREATE TABLE emergency_plan_review (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    reviewed_on  date NOT NULL,
    reviewed_by  text NOT NULL,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['emergency_plan_entry', 'emergency_contact', 'emergency_activation', 'emergency_plan_review'] LOOP
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

-- Permisos: activar y cerrar una emergencia (operador y directiva); el plan,
-- los contactos y su revision los define la directiva.
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('emergency.activate', 19, 'Emergencias', 'Activar y cerrar emergencias'),
('emergency.plan',     20, 'Emergencias', 'Editar el plan de emergencia, contactos y su revisión');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'emergency.activate'), ('supervisor', 'emergency.plan'),
('board', 'emergency.activate'), ('board', 'emergency.plan'),
('operator', 'emergency.activate');
