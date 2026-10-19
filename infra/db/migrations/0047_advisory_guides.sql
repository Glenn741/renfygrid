-- RenfyGrid -- 0047_advisory_guides.sql
-- Track E, E1 (2026-10-19): modulo Guias y asesoria de la ONG
-- (docs/04-plan-sprints.md §12).
--
-- Decisiones del usuario (19-oct):
-- - La ONG (p. ej. APT) es una organizacion de tipo 'advisor'. Sus asesores
--   solo ven las guias.
-- - Los formularios que el asesor levanta con cada operador son REGISTROS DE
--   LA ONG (`advised_operator` + `checklist_run`/`form_entry` marcados con el
--   operador). Si el operador lo solicita, se crea su organizacion con esos
--   datos (`transferred_tenant_id`).
-- - Se pueden cargar despues del taller desde Excel o archivo plano.
-- - Un operador que no paso por un taller usa las mismas guias desde su
--   organizacion (o va directo a operar): las plantillas son las mismas.
-- - Se crean organizaciones y usuarios nuevos desde la plataforma
--   (organizacion de tipo 'platform').
--
-- Dos tipos de formulario nuevos en el motor, genericos (ningun formato se
-- programa como pantalla propia, §11.3):
-- - 'record' (ficha): campos tipados, cada uno con "dato estimado, por
--   verificar" y nota de donde verificarlo (lo pide la Guia 1).
-- - 'table' (tabla o matriz): filas con columnas.
-- Su definicion va en `checklist_template.form_spec`; su contenido es un
-- documento vivo por organizacion (u operador asesorado) con versiones.

ALTER TABLE tenant DROP CONSTRAINT tenant_kind_check;
ALTER TABLE tenant ADD CONSTRAINT tenant_kind_check CHECK (kind IN ('provider', 'group', 'advisor', 'platform'));

-- ── Plantillas: tipos ficha y tabla ──────────────────────────────────
ALTER TABLE checklist_template DROP CONSTRAINT checklist_template_kind_check;
ALTER TABLE checklist_template ADD CONSTRAINT checklist_template_kind_check
    CHECK (kind IN ('inspection', 'traffic_light', 'self_assessment', 'products', 'questionnaire', 'record', 'table'));
ALTER TABLE checklist_template ADD COLUMN form_spec jsonb;
ALTER TABLE checklist_template ADD COLUMN sort_order integer;

-- ── Operadores asesorados (registros de la ONG) ──────────────────────
CREATE TABLE advised_operator (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name                   text NOT NULL CHECK (btrim(name) <> ''),
    community              text,
    contact_name           text,
    contact_phone          text,
    contact_email          text,
    origin                 text NOT NULL DEFAULT 'workshop' CHECK (origin IN ('workshop', 'direct', 'import')),
    status                 text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'transferred', 'inactive')),
    notes                  text,
    transferred_tenant_id  uuid REFERENCES tenant(id) ON DELETE SET NULL,
    transferred_at         timestamptz,
    transferred_by         text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    created_by             text NOT NULL,
    CHECK ((status = 'transferred') = (transferred_tenant_id IS NOT NULL OR transferred_at IS NOT NULL))
);
CREATE UNIQUE INDEX advised_operator_name_uq ON advised_operator (tenant_id, lower(btrim(name)));
ALTER TABLE advised_operator ENABLE ROW LEVEL SECURITY;
ALTER TABLE advised_operator FORCE ROW LEVEL SECURITY;
CREATE POLICY advised_operator_tenant_isolation ON advised_operator FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON advised_operator TO renfygrid_app;

-- ── Talleres (G7: ruta de jornadas, T-02 asistencia, T-03 caracterizacion) ──
CREATE TABLE workshop (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    title         text NOT NULL CHECK (btrim(title) <> ''),
    held_on       date NOT NULL,
    place         text,
    stage_codes   text[] NOT NULL DEFAULT '{}',
    facilitators  text,
    notes         text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    created_by    text NOT NULL
);
ALTER TABLE workshop ENABLE ROW LEVEL SECURITY;
ALTER TABLE workshop FORCE ROW LEVEL SECURITY;
CREATE POLICY workshop_tenant_isolation ON workshop FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON workshop TO renfygrid_app;

CREATE TABLE workshop_operator (
    workshop_id  uuid NOT NULL REFERENCES workshop(id) ON DELETE CASCADE,
    operator_id  uuid NOT NULL REFERENCES advised_operator(id) ON DELETE CASCADE,
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    PRIMARY KEY (workshop_id, operator_id)
);
ALTER TABLE workshop_operator ENABLE ROW LEVEL SECURITY;
ALTER TABLE workshop_operator FORCE ROW LEVEL SECURITY;
CREATE POLICY workshop_operator_tenant_isolation ON workshop_operator FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON workshop_operator TO renfygrid_app;

-- T-02/T-03: solo lo necesario para participar (la G7 pide no registrar
-- diagnosticos personales).
CREATE TABLE workshop_attendee (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    workshop_id    uuid NOT NULL REFERENCES workshop(id) ON DELETE CASCADE,
    operator_id    uuid REFERENCES advised_operator(id) ON DELETE CASCADE,
    full_name      text NOT NULL CHECK (btrim(full_name) <> ''),
    role_label     text,
    sector         text,
    support_needs  text,
    created_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE workshop_attendee ENABLE ROW LEVEL SECURITY;
ALTER TABLE workshop_attendee FORCE ROW LEVEL SECURITY;
CREATE POLICY workshop_attendee_tenant_isolation ON workshop_attendee FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON workshop_attendee TO renfygrid_app;

-- ── Listas aplicadas para un operador asesorado ───────────────────────
-- NULL = la lista es de la propia organizacion (como hasta ahora).
ALTER TABLE checklist_run ADD COLUMN advised_operator_id uuid REFERENCES advised_operator(id) ON DELETE CASCADE;
ALTER TABLE checklist_run ADD COLUMN workshop_id uuid REFERENCES workshop(id) ON DELETE SET NULL;
CREATE INDEX checklist_run_operator_idx ON checklist_run (tenant_id, advised_operator_id, template_id, performed_at DESC);

-- ── Fichas y tablas: documento vivo con versiones ─────────────────────
CREATE TABLE form_entry (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    template_id          text NOT NULL REFERENCES checklist_template(id),
    advised_operator_id  uuid REFERENCES advised_operator(id) ON DELETE CASCADE,
    data                 jsonb NOT NULL,
    complete             boolean NOT NULL,
    workshop_id          uuid REFERENCES workshop(id) ON DELETE SET NULL,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    updated_by           text NOT NULL
);
CREATE UNIQUE INDEX form_entry_uq ON form_entry
    (tenant_id, template_id, coalesce(advised_operator_id, '00000000-0000-0000-0000-000000000000'::uuid));
ALTER TABLE form_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_entry FORCE ROW LEVEL SECURITY;
CREATE POLICY form_entry_tenant_isolation ON form_entry FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON form_entry TO renfygrid_app;

CREATE TABLE form_entry_version (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id     uuid NOT NULL REFERENCES form_entry(id) ON DELETE CASCADE,
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    data         jsonb NOT NULL,
    complete     boolean NOT NULL,
    workshop_id  uuid REFERENCES workshop(id) ON DELETE SET NULL,
    source       text NOT NULL DEFAULT 'portal' CHECK (source IN ('portal', 'import', 'transfer')),
    saved_at     timestamptz NOT NULL DEFAULT now(),
    saved_by     text NOT NULL
);
CREATE INDEX form_entry_version_entry_idx ON form_entry_version (entry_id, saved_at DESC);
ALTER TABLE form_entry_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE form_entry_version FORCE ROW LEVEL SECURITY;
CREATE POLICY form_entry_version_tenant_isolation ON form_entry_version FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON form_entry_version TO renfygrid_app;

-- ── Mapa tematico de la ONG: que campo de que ficha da cada capa ─────
-- Catalogo del paquete de programa (otro programa declara su propia ficha).
CREATE TABLE advisory_map_layer (
    pack_id      text NOT NULL REFERENCES pack(id),
    role         text NOT NULL CHECK (role IN ('location', 'size', 'color', 'shape')),
    template_id  text NOT NULL REFERENCES checklist_template(id),
    field_key    text NOT NULL,
    label        text NOT NULL,
    PRIMARY KEY (pack_id, role)
);
GRANT SELECT ON advisory_map_layer TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON advisory_map_layer FROM renfygrid_app;

-- ── Permisos y rol de asesor ──────────────────────────────────────────
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('advisory.manage',      40, 'Asesoría', 'Registrar operadores asesorados y talleres'),
('advisory.record',      41, 'Asesoría', 'Llenar los formularios de las guías de un operador asesorado'),
('advisory.transfer',    42, 'Asesoría', 'Crear la organización de un operador con los datos levantados'),
('organizations.manage', 43, 'Plataforma', 'Crear organizaciones y su primer usuario (solo en la organización de la plataforma)');

INSERT INTO app_role (code, sort_order, label, description, assignable) VALUES
('advisor',  5, 'Asesoría', 'Persona asesora de la ONG: registra operadores y talleres y llena con ellos los formularios de las guías.', true),
('platform', 6, 'Plataforma', 'Administra la plataforma: crea organizaciones y su primer usuario.', true);

INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'advisory.manage'), ('supervisor', 'advisory.record'), ('supervisor', 'advisory.transfer'),
('advisor', 'advisory.manage'), ('advisor', 'advisory.record'), ('advisor', 'advisory.transfer'), ('advisor', 'program.observe'),
('platform', 'organizations.manage'), ('platform', 'users.manage'), ('platform', 'settings.manage');

-- Etapas de la ruta que son de la persona facilitadora (G7: CAP, T-06,
-- T-08), no del operador: no se muestran en las guias de un operador
-- asesorado ni en su avance.
ALTER TABLE process_stage ADD COLUMN audience text NOT NULL DEFAULT 'operator' CHECK (audience IN ('operator', 'facilitator'));
UPDATE process_stage SET audience = 'facilitator' WHERE pack_id = 'EC-MUNICIPIOS-AZULES' AND code = 'INT';

-- Orden de los formularios dentro de su guia (los existentes, por id).
UPDATE checklist_template SET sort_order = 50 WHERE sort_order IS NULL;
UPDATE checklist_template SET sort_order = 10 WHERE id LIKE '%-START';
UPDATE checklist_template SET sort_order = 90 WHERE kind = 'products';

-- ── Guia 1 (Diagnostico participativo): todos sus formatos ────────────
-- Textos literales de la Guia 1 (Municipios Azules). Agregados de la
-- plataforma, declarados: en la ficha, "que agua entrega el sistema",
-- "saneamiento" y "ubicacion" (los usa el mapa de la ONG; la G1 los pide en
-- el mapa parlante y en la tarjeta de diagnostico), y el numero de
-- viviendas con bano o letrina (en la G1 esta dentro de la tarjeta).
INSERT INTO checklist_template (id, pack_id, kind, title, purpose, scale, items, stage_code, sort_order, form_spec) VALUES
('MA-G1-PERCEPTION', 'EC-MUNICIPIOS-AZULES', 'self_assessment', '¿Cómo vemos nuestros servicios hoy?',
 'Primera conversación de la Guía 1: cómo ve la comunidad sus servicios de agua y saneamiento antes del diagnóstico.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 2},
   {"code": "partly", "label": "Más o menos", "finding": false, "score": 1},
   {"code": "no", "label": "No", "finding": false, "score": 0}]',
 '[{"key": "know_users", "text": "¿Sabemos cuántos usuarios/consumidores usan nuestro sistema de agua?"},
   {"key": "know_route", "text": "¿Tenemos claro de dónde viene el agua y por dónde llega a las casas?"},
   {"key": "know_problems", "text": "¿Conocemos los principales problemas del sistema de agua y saneamiento?"},
   {"key": "know_service", "text": "¿Sabemos si el agua llega limpia, suficiente y todos los días?"},
   {"key": "know_wastewater", "text": "¿Conocemos cómo se manejan las aguas residuales y las excretas en la comunidad?"},
   {"key": "participation", "text": "¿La comunidad participa cuando hay que tomar decisiones?"}]',
 'G1', 5, NULL),

('MA-G1-PROFILE', 'EC-MUNICIPIOS-AZULES', 'record', 'Ficha básica de la comunidad y el territorio',
 'Cuántas personas dependen del servicio, qué grupos necesitan mayor cuidado y qué problemas de salud o ambiente pueden relacionarse con el agua y el saneamiento. Completen con lo que ya conoce la junta; si falta un dato, anoten quién puede ayudar a conseguirlo. No inventen datos: si no hay información exacta, usen una estimación y márquenla para verificar.',
 '[]', '[]', 'G1', 10,
 '{"fields": [
   {"key": "canton", "label": "Cantón", "type": "text", "group": "Territorio", "verify": "GAD / INEC", "required": true},
   {"key": "parish", "label": "Parroquia", "type": "text", "group": "Territorio", "verify": "GAD / INEC", "required": true},
   {"key": "sectors", "label": "Comunidades o sectores atendidos", "type": "textarea", "group": "Territorio", "verify": "Junta / Asamblea"},
   {"key": "location", "label": "Ubicación del sistema (punto en el mapa)", "type": "geo", "group": "Territorio", "verify": "GPS del teléfono o mapa", "required": true, "platform_note": "Agregado de la plataforma para el mapa de la organización que asesora."},
   {"key": "users", "label": "Número de usuarias / consumidores", "type": "integer", "group": "Población", "verify": "Padrón de usuarios", "required": true},
   {"key": "inhabitants", "label": "Número aproximado de habitantes", "type": "integer", "group": "Población", "verify": "INEC / GAD / Asamblea"},
   {"key": "children_under5", "label": "Niños y niñas menores de 5 años", "type": "integer", "group": "Población", "verify": "Centro de salud / INEC"},
   {"key": "older_adults", "label": "Personas adultas mayores", "type": "integer", "group": "Población", "verify": "Asamblea / GAD"},
   {"key": "women_heads", "label": "Mujeres usuarias o jefas de hogar", "type": "integer", "group": "Población", "verify": "Padrón / Asamblea"},
   {"key": "youth", "label": "Jóvenes que participan en la comunidad", "type": "integer", "group": "Población", "verify": "Escuela / Asamblea"},
   {"key": "education", "label": "Nivel de instrucción más común", "type": "choice", "group": "Población", "verify": "INEC / Asamblea",
    "options": [{"code": "primary", "label": "Primaria"}, {"code": "basic", "label": "Básica"}, {"code": "high_school", "label": "Bachillerato"}, {"code": "other", "label": "Otro"}]},
   {"key": "economy", "label": "Principales actividades económicas", "type": "multi", "group": "Población", "verify": "Asamblea / GAD",
    "options": [{"code": "agriculture", "label": "Agricultura"}, {"code": "livestock", "label": "Ganadería"}, {"code": "trade", "label": "Comercio"}, {"code": "other", "label": "Otra"}]},
   {"key": "diseases", "label": "Enfermedades relacionadas con agua o saneamiento", "type": "multi", "group": "Salud", "verify": "Centro de salud / MSP",
    "options": [{"code": "diarrhea", "label": "Diarrea"}, {"code": "parasites", "label": "Parasitosis"}, {"code": "amoebiasis", "label": "Amebiasis"}, {"code": "other", "label": "Otra"}]},
   {"key": "dci", "label": "Dato local de DCI, si existe (% o número de casos)", "type": "text", "group": "Salud", "verify": "Centro de salud / ENDI / GAD"},
   {"key": "supply_type", "label": "¿Qué agua entrega el sistema?", "type": "choice", "group": "Servicios", "required": true, "verify": "Tarjeta de diagnóstico (cloración, análisis)",
    "platform_note": "Agregado de la plataforma para el mapa de la organización que asesora.",
    "options": [{"code": "potable", "label": "Agua potable (tratada y desinfectada)"}, {"code": "raw", "label": "Agua cruda o entubada sin tratamiento"}, {"code": "none", "label": "Sin servicio de agua"}]},
   {"key": "sanitation", "label": "Saneamiento de la comunidad", "type": "choice", "group": "Servicios", "required": true, "verify": "Mapa parlante / tarjeta de diagnóstico",
    "platform_note": "Agregado de la plataforma para el mapa de la organización que asesora.",
    "options": [{"code": "sewer", "label": "Alcantarillado o sistema comunitario"}, {"code": "onsite", "label": "Saneamiento en sitio (pozo séptico, letrina, biodigestor)"}, {"code": "none", "label": "Sin sistema de saneamiento"}]},
   {"key": "homes_with_toilet", "label": "Número de viviendas con baño o letrina", "type": "integer", "group": "Servicios", "verify": "Tarjeta de diagnóstico / Asamblea"}
 ]}'),

('MA-G1-MAP', 'EC-MUNICIPIOS-AZULES', 'self_assessment', 'Mapa parlante: cómo funciona cada parte del sistema',
 'Después de dibujar el sistema entre todas y todos, marquen cada parte con el color que corresponde. Verde: funciona bien (mantener y cuidar). Amarillo: necesita mejorar (planificar una acción). Rojo: problema urgente (atender primero). Anoten dónde hay fugas, contaminación, basura, animales, descargas, reboses o malos olores.',
 '[{"code": "green", "label": "Verde · funciona bien", "finding": false, "score": 2},
   {"code": "yellow", "label": "Amarillo · necesita mejorar", "finding": true, "finding_priority": "medium", "score": 1},
   {"code": "red", "label": "Rojo · problema urgente", "finding": true, "finding_priority": "high", "score": 0},
   {"code": "absent", "label": "No existe", "finding": false, "ask_note": true, "score": 0}]',
 '[{"key": "source", "text": "Fuente de agua"},
   {"key": "intake", "text": "Captación"},
   {"key": "tank", "text": "Tanque de almacenamiento"},
   {"key": "network", "text": "Red de distribución"},
   {"key": "homes", "text": "Viviendas atendidas"},
   {"key": "protection", "text": "Zonas de protección"},
   {"key": "sanitation", "text": "Sistemas de saneamiento: alcantarillado, letrinas, pozos sépticos, biodigestores u otros"},
   {"key": "water_bodies", "text": "Ríos, quebradas o cuerpos de agua cercanos"}]',
 'G1', 20, NULL),

('MA-G1-DIAG', 'EC-MUNICIPIOS-AZULES', 'inspection', 'Herramienta 2. Tarjeta de Diagnóstico Comunitario Integral',
 'Revisen cada aspecto, conversen y lleguen a un acuerdo. Marquen Sí existe / Sí se realiza o No existe / No se realiza, y anoten observaciones o actividades por realizar. Lo marcado como problema pasa a la priorización.',
 '[{"code": "yes", "label": "Sí", "finding": false, "score": 1},
   {"code": "no", "label": "No", "finding": true, "finding_priority": "medium", "score": 0}]',
 '[{"key": "org_legal", "group": "Organización y permisos", "text": "Tiene personería jurídica"},
   {"key": "org_board", "group": "Organización y permisos", "text": "La junta tiene directiva legalizada"},
   {"key": "org_statute", "group": "Organización y permisos", "text": "Existen estatutos"},
   {"key": "org_rules", "group": "Organización y permisos", "text": "Existe reglamento interno"},
   {"key": "org_meetings", "group": "Organización y permisos", "text": "Se realizan reuniones periódicas"},
   {"key": "org_minutes", "group": "Organización y permisos", "text": "Se elaboran actas de reuniones"},
   {"key": "org_inform", "group": "Organización y permisos", "text": "Se informa a la comunidad sobre las decisiones tomadas"},
   {"key": "org_agreements", "group": "Organización y permisos", "text": "Se lleva un registro de actas de los acuerdos comunitarios"},
   {"key": "org_water_permit", "group": "Organización y permisos", "text": "Dispone de autorización de uso y aprovechamiento de agua"},
   {"key": "org_archive", "group": "Organización y permisos", "text": "Existe archivo físico o digital de documentos"},
   {"key": "org_recognition", "group": "Organización y permisos", "text": "La organización cuenta con reconocimiento legal vigente"},
   {"key": "inf_source_protected", "group": "Infraestructura", "text": "La fuente de agua está protegida"},
   {"key": "inf_intake", "group": "Infraestructura", "text": "La captación está en buen estado"},
   {"key": "inf_tank", "group": "Infraestructura", "text": "El tanque funciona adecuadamente"},
   {"key": "inf_main_leaks", "group": "Infraestructura", "text": "La red o conducción principal presenta fugas",
    "options": [{"code": "yes", "label": "Sí", "finding": true, "finding_priority": "medium", "score": 0}, {"code": "no", "label": "No", "finding": false, "score": 1}]},
   {"key": "inf_secondary_leaks", "group": "Infraestructura", "text": "La red secundaria presenta fugas",
    "options": [{"code": "yes", "label": "Sí", "finding": true, "finding_priority": "medium", "score": 0}, {"code": "no", "label": "No", "finding": false, "score": 1}]},
   {"key": "inf_valves", "group": "Infraestructura", "text": "Existen válvulas y accesorios en buen estado"},
   {"key": "inf_meters", "group": "Infraestructura", "text": "Existen micromedidores funcionando"},
   {"key": "inf_enough_water", "group": "Infraestructura", "text": "Hay suficiente agua durante todo el año"},
   {"key": "q_chlorination", "group": "Calidad del agua", "text": "Se realiza cloración"},
   {"key": "q_residual", "group": "Calidad del agua", "text": "Se controla el cloro residual"},
   {"key": "q_lab", "group": "Calidad del agua", "text": "Se realizan análisis de calidad del agua"},
   {"key": "q_aspect", "group": "Calidad del agua", "text": "El agua tiene buen aspecto, olor y sabor"},
   {"key": "q_perceived_safe", "group": "Calidad del agua", "text": "La comunidad considera que el agua es potable y buena para el consumo humano"},
   {"key": "san_sewer", "group": "Saneamiento", "text": "Existe alcantarillado o sistema comunitario de saneamiento"},
   {"key": "san_septic", "group": "Saneamiento", "text": "Existen pozos sépticos en buen estado"},
   {"key": "san_latrines", "group": "Saneamiento", "text": "Existen letrinas en buen estado"},
   {"key": "san_treatment", "group": "Saneamiento", "text": "Existen sistemas de tratamiento de aguas residuales"},
   {"key": "san_direct_discharge", "group": "Saneamiento", "text": "Las aguas residuales se descargan directamente a ríos o quebradas",
    "options": [{"code": "yes", "label": "Sí", "finding": true, "finding_priority": "high", "score": 0}, {"code": "no", "label": "No", "finding": false, "score": 1}]},
   {"key": "san_maintenance", "group": "Saneamiento", "text": "Los sistemas de saneamiento reciben mantenimiento periódico"},
   {"key": "san_odors", "group": "Saneamiento", "text": "Existen problemas de malos olores o reboses",
    "options": [{"code": "yes", "label": "Sí", "finding": true, "finding_priority": "medium", "score": 0}, {"code": "no", "label": "No", "finding": false, "score": 1}]},
   {"key": "san_practices", "group": "Saneamiento", "text": "La comunidad conoce prácticas adecuadas de saneamiento e higiene"},
   {"key": "fin_bank", "group": "Administración y finanzas", "text": "Existe cuenta bancaria de la organización"},
   {"key": "fin_fees", "group": "Administración y finanzas", "text": "Se cobran tarifas regularmente"},
   {"key": "fin_on_time", "group": "Administración y finanzas", "text": "La mayoría de usuarios paga a tiempo"},
   {"key": "fin_budget", "group": "Administración y finanzas", "text": "Existe presupuesto anual"},
   {"key": "fin_books", "group": "Administración y finanzas", "text": "Se llevan registros contables"},
   {"key": "fin_reports", "group": "Administración y finanzas", "text": "Se presentan informes económicos a la comunidad"},
   {"key": "par_meetings", "group": "Participación", "text": "La comunidad participa en reuniones"},
   {"key": "par_mingas", "group": "Participación", "text": "Se realizan mingas comunitarias"},
   {"key": "par_women", "group": "Participación", "text": "Participan mujeres en espacios de decisión"},
   {"key": "par_youth", "group": "Participación", "text": "Participan jóvenes en actividades de la junta"},
   {"key": "par_accountability", "group": "Participación", "text": "Se realizan rendiciones de cuentas"},
   {"key": "hh_handwashing", "group": "Salud e higiene", "text": "Se promueve el lavado de manos y la higiene familiar"},
   {"key": "hh_safe_use", "group": "Salud e higiene", "text": "La comunidad conoce prácticas de uso seguro del agua"},
   {"key": "hh_diarrhea", "group": "Salud e higiene", "text": "Existen casos de diarreas o parasitosis asociados al agua",
    "options": [{"code": "yes", "label": "Sí", "finding": true, "finding_priority": "high", "score": 0}, {"code": "no", "label": "No", "finding": false, "score": 1}]},
   {"key": "env_education", "group": "Ambiente", "text": "Se realizan actividades de educación sanitaria"},
   {"key": "env_protection_zone", "group": "Ambiente", "text": "Existen zonas de protección alrededor de la fuente"},
   {"key": "env_reforestation", "group": "Ambiente", "text": "Se realizan actividades de conservación o reforestación y/o alguna otra acción"},
   {"key": "env_polluting", "group": "Ambiente", "text": "Existen actividades contaminantes cerca de la fuente",
    "options": [{"code": "yes", "label": "Sí", "finding": true, "finding_priority": "high", "score": 0}, {"code": "no", "label": "No", "finding": false, "score": 1}]},
   {"key": "env_community_care", "group": "Ambiente", "text": "La comunidad participa en el cuidado de las fuentes de agua"}]',
 'G1', 30, NULL),

('MA-G1-PRIORITIES', 'EC-MUNICIPIOS-AZULES', 'table', '¿Qué problemas nos preocupan más y por qué ocurren?',
 'Revisen los aspectos marcados como "No existe / No se realiza", conversen cuáles afectan más a la comunidad y anoten los más urgentes. No todos los problemas pueden resolverse al mismo tiempo.',
 '[]', '[]', 'G1', 40,
 '{"min_rows": 1, "columns": [
   {"key": "problem", "label": "Problema identificado", "type": "text", "required": true},
   {"key": "health", "label": "¿Afecta la salud?", "type": "text"},
   {"key": "cause", "label": "¿Por qué ocurre?", "type": "text"},
   {"key": "families", "label": "¿A cuántas familias?", "type": "integer"},
   {"key": "priority", "label": "Prioridad", "type": "choice", "required": true,
    "options": [{"code": "high", "label": "Alta"}, {"code": "medium", "label": "Media"}, {"code": "low", "label": "Baja"}]},
   {"key": "why", "label": "¿Por qué?", "type": "text"}]}'),

('MA-G1-TREE', 'EC-MUNICIPIOS-AZULES', 'record', 'Profundicemos en el problema principal',
 'Seleccionen uno de los problemas con prioridad alta y conversen sobre sus causas (¿por qué pasa esto?) y sus consecuencias (¿qué provoca en la comunidad?).',
 '[]', '[]', 'G1', 50,
 '{"fields": [
   {"key": "problem", "label": "Problema principal: ¿qué está pasando?", "type": "textarea", "required": true},
   {"key": "causes", "label": "Causas: ¿por qué ocurre?", "type": "list", "required": true},
   {"key": "consequences", "label": "Consecuencias: ¿qué provoca?", "type": "list", "required": true}]}'),

('MA-G1-ACTIONS', 'EC-MUNICIPIOS-AZULES', 'table', '¿Qué podemos hacer para mejorar? Primeras acciones',
 'Seleccionen los tres problemas más importantes, conversen sobre acciones sencillas y posibles y definan quién puede apoyar. Estas acciones no reemplazan el Plan de Mejora de la Guía 6; son el primer paso.',
 '[]', '[]', 'G1', 60,
 '{"min_rows": 1, "suggested_rows": 3, "columns": [
   {"key": "problem", "label": "Problema identificado", "type": "text", "required": true},
   {"key": "who_supports", "label": "¿Quién puede apoyar?", "type": "text"},
   {"key": "first_action", "label": "¿Qué podemos hacer primero?", "type": "text", "required": true},
   {"key": "when", "label": "¿Cuándo?", "type": "text"},
   {"key": "needs", "label": "¿Qué necesitamos?", "type": "text"}]}'),

('MA-G1-COMMITMENT', 'EC-MUNICIPIOS-AZULES', 'record', 'Nuestro compromiso comunitario',
 'Cierre de la Guía 1: lo que la comunidad se compromete a mejorar primero.',
 '[]', '[]', 'G1', 70,
 '{"fields": [
   {"key": "improve_first", "label": "¿Qué queremos mejorar primero?", "type": "textarea", "required": true},
   {"key": "action", "label": "¿Qué acción podemos realizar en los próximos meses?", "type": "textarea", "required": true},
   {"key": "who", "label": "¿Quiénes participarán?", "type": "textarea"},
   {"key": "support", "label": "¿Qué apoyo necesitamos?", "type": "textarea"}]}'),

('MA-G1-PRODUCTS', 'EC-MUNICIPIOS-AZULES', 'products', 'Al finalizar la Guía 1',
 'Revisen si quedó cada producto del diagnóstico participativo.',
 '[{"code": "ready", "label": "Sí", "finding": false, "score": 2},
   {"code": "pending", "label": "No", "finding": false, "ask_note": true, "score": 0}]',
 '[{"key": "basic_info", "text": "¿Levantamos información básica de la comunidad y el territorio?"},
   {"key": "problems", "text": "¿Identificamos los principales problemas del sistema?"},
   {"key": "talking_map", "text": "¿Elaboramos el mapa parlante?"},
   {"key": "traffic_light", "text": "¿Completamos el semáforo comunitario?"},
   {"key": "priorities", "text": "¿Priorizamos los problemas más urgentes?"},
   {"key": "causes", "text": "¿Identificamos sus causas y consecuencias?"},
   {"key": "first_actions", "text": "¿Definimos primeras acciones de mejora?"}]',
 'G1', 90, NULL);

-- ── Guia 2: los formatos que son tablas (7A, 7D, 7E, 7F, 7I) ──────────
-- 7G es un cuadro de consulta (no se llena); 7B, 7C y 7H ya son listas (0024).
INSERT INTO checklist_template (id, pack_id, kind, title, purpose, scale, items, stage_code, sort_order, form_spec) VALUES
('MA-G2-7A', 'EC-MUNICIPIOS-AZULES', 'table', '7A. Ficha de roles y responsabilidades',
 'Se usa en la Actividad participativa 1. Escriban una tarea concreta por fila y acuerden quién la realiza y a quién informa.',
 '[]', '[]', 'G2', 20,
 '{"min_rows": 1, "columns": [
   {"key": "position", "label": "Cargo o espacio", "type": "text", "required": true},
   {"key": "task", "label": "Tarea acordada", "type": "text", "required": true},
   {"key": "reports_to", "label": "A quién informa", "type": "text"},
   {"key": "improve", "label": "Qué debe mejorar", "type": "text"}]}'),

('MA-G2-7D', 'EC-MUNICIPIOS-AZULES', 'table', '7D. Ruta para actualizar instrumentos y trámites',
 'Se usa al final de la Actividad participativa 3. Elijan como máximo tres asuntos urgentes y anoten un primer paso posible.',
 '[]', '[]', 'G2', 40,
 '{"min_rows": 1, "max_rows": 3, "columns": [
   {"key": "missing", "label": "Qué falta", "type": "text", "required": true},
   {"key": "status", "label": "Cómo está", "type": "text"},
   {"key": "first_step", "label": "Primer paso", "type": "text", "required": true},
   {"key": "responsible", "label": "Responsable", "type": "text"},
   {"key": "date", "label": "Fecha", "type": "date"}]}'),

('MA-G2-7E', 'EC-MUNICIPIOS-AZULES', 'table', '7E. Propuesta sencilla de alianza',
 'Se usa en la Actividad participativa 4. Completen una sola necesidad por fila y definan con quién hablarán primero (el cuadro 7G de la guía ayuda a elegir la institución).',
 '[]', '[]', 'G2', 50,
 '{"min_rows": 1, "columns": [
   {"key": "need", "label": "Necesidad", "type": "text", "required": true},
   {"key": "with_whom", "label": "Con quién (quién ayuda)", "type": "text", "required": true},
   {"key": "we_ask", "label": "Qué pedimos", "type": "text"},
   {"key": "we_give", "label": "Qué damos", "type": "text"},
   {"key": "first_step", "label": "Primer paso", "type": "text"},
   {"key": "date", "label": "Fecha", "type": "date"}]}'),

('MA-G2-7F', 'EC-MUNICIPIOS-AZULES', 'table', '7F. Plan de transparencia y rendición de cuentas',
 'Se usa en la Actividad participativa 5. Escojan información que la comunidad pueda comprender y una prueba sencilla para respaldarla: una persona responsable, una frecuencia y una evidencia para cada tema.',
 '[]', '[]', 'G2', 60,
 '{"min_rows": 1, "columns": [
   {"key": "topic", "label": "Qué informamos", "type": "text", "required": true},
   {"key": "how", "label": "Cómo lo contamos", "type": "text", "required": true},
   {"key": "who", "label": "Quién", "type": "text", "required": true},
   {"key": "frequency", "label": "Cada cuánto", "type": "text", "required": true},
   {"key": "evidence", "label": "Prueba", "type": "text", "required": true}],
  "preset_rows": [{"topic": "Ingresos, gastos y saldo"}, {"topic": "Actividades y mantenimientos"}, {"topic": "Trámites y documentos"},
                  {"topic": "Reclamos y respuestas"}, {"topic": "Metas del siguiente período"}]}'),

('MA-G2-7I', 'EC-MUNICIPIOS-AZULES', 'table', '7I. Padrón simple de personas usuarias',
 'Secretaría escribe una fila por cada conexión; en Estado anota Activo o Suspendido, y la directiva revisa la lista. Guarde el padrón en la sede o archivo oficial: no lo coloque completo en carteleras ni lo comparta en grupos abiertos.',
 '[]', '[]', 'G2', 70,
 '{"min_rows": 1, "personal_data": true, "columns": [
   {"key": "name", "label": "Nombre", "type": "text", "required": true},
   {"key": "sector", "label": "Comunidad o sector", "type": "text"},
   {"key": "connection", "label": "Conexión o medidor", "type": "text"},
   {"key": "status", "label": "Estado", "type": "choice", "required": true,
    "options": [{"code": "active", "label": "Activo"}, {"code": "suspended", "label": "Suspendido"}]},
   {"key": "note", "label": "Fecha / nota", "type": "text"}]}');

UPDATE checklist_template SET sort_order = 30 WHERE id = 'MA-G2-7B';
UPDATE checklist_template SET sort_order = 35 WHERE id = 'MA-G2-7C';

-- ── Capas del mapa de la ONG (paquete Municipios Azules) ─────────────
INSERT INTO advisory_map_layer (pack_id, role, template_id, field_key, label) VALUES
('EC-MUNICIPIOS-AZULES', 'location', 'MA-G1-PROFILE', 'location', 'Ubicación'),
('EC-MUNICIPIOS-AZULES', 'size', 'MA-G1-PROFILE', 'users', 'Número de usuarias / consumidores'),
('EC-MUNICIPIOS-AZULES', 'color', 'MA-G1-PROFILE', 'supply_type', 'Agua que entrega el sistema'),
('EC-MUNICIPIOS-AZULES', 'shape', 'MA-G1-PROFILE', 'sanitation', 'Saneamiento');
