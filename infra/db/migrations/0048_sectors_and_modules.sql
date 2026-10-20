-- RenfyGrid -- 0048_sectors_and_modules.sql
-- Track F, sprint Q1 (2026-10-20). docs/09-multi-industria.md y
-- docs/10-caso-energia-fronteras.md.
--
-- RenfyGrid es un producto estandar para energia, gas y agua. Lo propio de
-- cada sector va en un modulo con su nombre; lo comun (MDM, mantenimiento,
-- configuracion) es transversal. Hasta aqui el menu era un literal del
-- frontend (`NAV_GROUPS`) filtrado solo por tipo de organizacion: ahora es
-- dato.
--
--   sector          -- catalogo global: agua, energia, gas (agregar uno es una fila)
--   tenant_sector   -- los sectores que opera cada organizacion (una
--                      empresa multiservicio tiene varios)
--   pack.sector_code -- el paquete de agua no se ofrece a una empresa de gas
--   nav_group       -- grupos del menu
--   product_module  -- cada modulo: ruta, nombre, grupo, orden, tipos de
--                      organizacion y sectores que lo ven
--   tenant_module   -- excepciones por organizacion ("a la carte",
--                      docs/01-planteamiento.md §3)
--
-- Regla de visibilidad (portal-api/product_modules.py): el tipo de la
-- organizacion esta en `kinds`, y `sectors` es NULL (transversal) o comparte
-- un sector con la organizacion, salvo que `tenant_module` lo apague; un
-- `tenant_module` encendido lo agrega aunque no le toque por sector.
--
-- Paridad: toda organizacion existente queda con el sector agua y ve
-- exactamente el mismo menu que antes. Lo que hoy tiene contenido solo de
-- agua (calidad, saneamiento, dosificacion, balance IWA, EPANET, guias...)
-- se marca de agua; F2 lo separa mejor.

-- ── Sectores ──────────────────────────────────────────────────────────

-- `obis_medium`: valores del grupo A del codigo OBIS (IEC 62056-61) que
-- corresponden al sector; con ellos F3 deduce el sector de cada medidor.
CREATE TABLE sector (
    code          text PRIMARY KEY,
    sort_order    integer NOT NULL,
    label         text NOT NULL,
    icon          text NOT NULL,
    billing_unit  text NOT NULL,
    obis_medium   integer[] NOT NULL DEFAULT '{}',
    description   text NOT NULL
);
INSERT INTO sector (code, sort_order, label, icon, billing_unit, obis_medium, description) VALUES
('electricity', 1, 'Energía', 'energy', 'kWh', '{1}', 'Distribución y comercialización de energía eléctrica'),
('gas',         2, 'Gas', 'gas', 'm³', '{7}', 'Distribución de gas por red'),
('water',       3, 'Agua', 'water', 'm³', '{8,9}', 'Acueducto y saneamiento');
GRANT SELECT ON sector TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON sector FROM renfygrid_app;

CREATE TABLE tenant_sector (
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    sector_code  text NOT NULL REFERENCES sector(code),
    added_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, sector_code)
);
ALTER TABLE tenant_sector ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_sector FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_sector_tenant_isolation ON tenant_sector FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, DELETE ON tenant_sector TO renfygrid_app;

-- Paridad: las organizaciones que operan (o asesoran) hoy son de agua. La
-- de la plataforma no opera ningun sector.
INSERT INTO tenant_sector (tenant_id, sector_code)
SELECT id, 'water' FROM tenant WHERE kind IN ('provider', 'group', 'advisor');

ALTER TABLE pack ADD COLUMN sector_code text REFERENCES sector(code);
UPDATE pack SET sector_code = 'water' WHERE id IN ('EC-ARCA', 'EC-MUNICIPIOS-AZULES');

-- ── Menu ──────────────────────────────────────────────────────────────

CREATE TABLE nav_group (
    code        text PRIMARY KEY,
    sort_order  integer NOT NULL,
    label       text           -- NULL = sin titulo (la Vista general)
);
INSERT INTO nav_group (code, sort_order, label) VALUES
('home', 0, NULL),
('start', 10, 'Punto de partida'),
('advisory', 20, 'Asesoría'),
('platform', 30, 'Plataforma'),
('energy', 35, 'Energía'),
('operation', 40, 'Operación del sistema'),
('metering', 50, 'Medición (MDM)'),
('network', 60, 'Red y pérdidas'),
('organization', 70, 'Organización');

-- `path` es la ruta de la pantalla; las secciones internas de cada pantalla
-- (anclas) son estructura del frontend y siguen alla.
CREATE TABLE product_module (
    code         text PRIMARY KEY,
    path         text NOT NULL UNIQUE,
    group_code   text NOT NULL REFERENCES nav_group(code),
    sort_order   integer NOT NULL,
    label        text NOT NULL,
    icon         text NOT NULL,
    description  text,
    kinds        text[] NOT NULL DEFAULT '{provider,group}',
    sectors      text[]          -- NULL = transversal
);
INSERT INTO product_module (code, path, group_code, sort_order, label, icon, description, kinds, sectors) VALUES
('overview', '/', 'home', 1, 'Vista general', 'overview', 'Estado de la operación, la medición y la red, y acceso a todos los módulos', '{provider,group}', '{water}'),
('guides', '/inspections', 'start', 1, 'Guías', 'guides', 'Las guías del programa: fichas, tablas y listas que dan el marco para operar', '{provider,group}', '{water}'),
('advisory', '/advisory', 'advisory', 1, 'Tablero de asesoría', 'overview', 'Operadores capacitados, guías cubiertas con cada uno y mapa temático', '{advisor}', NULL),
('advisory-guides', '/advisory/guides', 'advisory', 2, 'Guías', 'guides', 'Las guías y sus formularios; elija el operador con el que los va a llenar', '{advisor}', NULL),
('advisory-operators', '/advisory/operators', 'advisory', 3, 'Operadores', 'organization', 'Operadores asesorados, sus guías y la carga por archivo', '{advisor}', NULL),
('advisory-workshops', '/advisory/workshops', 'advisory', 4, 'Talleres', 'workshop', 'Talleres, guías que cubren, operadores y asistencia', '{advisor}', NULL),
('organizations', '/organizations', 'platform', 1, 'Organizaciones', 'organization', 'Crear organizaciones (empresas, juntas, agrupaciones, ONG) y su primer usuario', '{platform}', NULL),
('operations', '/operations', 'operation', 1, 'Operación diaria', 'operations', 'Rutina del operador: mediciones de campo, bitácora, dosificación y lectura de medidores', '{provider,group}', '{water}'),
('system', '/system', 'operation', 2, 'Mi sistema', 'system', 'Componentes por etapa, semáforo técnico, tren de tratamiento y hallazgos', '{provider,group}', '{water}'),
('quality', '/quality', 'operation', 3, 'Calidad del agua', 'quality', 'Alertas de calidad, análisis de laboratorio y plan de muestreo', '{provider,group}', '{water}'),
('emergencies', '/emergencies', 'operation', 4, 'Emergencias', 'emergencies', 'Plan por tipo de emergencia, contactos y activaciones', '{provider,group}', '{water}'),
('warehouse', '/warehouse', 'operation', 5, 'Bodega y EPP', 'warehouse', 'Insumos y EPP: existencias, vencimientos y cruce del cloro aplicado', '{provider,group}', '{water}'),
('sanitation', '/sanitation', 'operation', 6, 'Saneamiento', 'sanitation', 'Componentes y lodos, registro de intervenciones y descargas productivas', '{provider,group}', '{water}'),
('improvement', '/improvement', 'operation', 7, 'Plan mínimo y mejora', 'improvement', 'Plan mínimo de operación y mantenimiento, insumos para el Plan de Mejora y productos', '{provider,group}', '{water}'),
('compliance-reports', '/compliance-reports', 'operation', 8, 'Informe de cumplimiento', 'report', 'Informe del período para la autoridad, que la organización decide enviar', '{provider,group}', '{water}'),
('maintenance', '/maintenance', 'operation', 9, 'Mantenimiento', 'maintenance', 'Órdenes, preventivo programado, eventos y calendario anual', '{provider,group}', NULL),
('meters', '/meters', 'metering', 1, 'HES / Ingesta', 'metering', 'Medidores, concentradores, flota y eventos/alarmas', '{provider,group}', NULL),
('vee', '/vee', 'metering', 2, 'VEE', 'validation', 'Validación, estimación y edición manual de lecturas', '{provider,group}', NULL),
('consumption', '/consumption', 'metering', 3, 'Consumo', 'consumption', 'Consumo facturable y anomalías bajo revisión', '{provider,group}', NULL),
('control', '/control', 'metering', 4, 'Control (SCR)', 'control', 'Suspensión, corte y reconexión remota', '{provider,group}', NULL),
('network-balance', '/network-balance', 'network', 1, 'Balance de Red', 'balance', 'Agua no contabilizada, ILI y balance hídrico IWA por zona', '{provider,group}', '{water}'),
('digital-twin', '/digital-twin', 'network', 2, 'Gemelo Digital', 'twin', 'Inventario georreferenciado de activos de red', '{provider,group}', '{water}'),
('network-model', '/network-model', 'network', 3, 'Modelado Hidráulico', 'model', 'Simulación hidráulica (EPANET/WNTR) de presión y caudal', '{provider,group}', '{water}'),
('team', '/team', 'organization', 1, 'Usuarios', 'group', 'Usuarios de la organización y sus roles', '{advisor,platform}', NULL),
('group', '/group', 'organization', 2, 'Agrupación', 'group', 'Indicadores que cada organización miembro decide compartir', '{provider,group}', '{water}'),
('program-observations', '/program-observations', 'organization', 3, 'Observaciones del programa', 'observations', 'Observaciones para mejorar los materiales del programa', '{provider,group}', '{water}'),
('integrations', '/integrations', 'organization', 4, 'Integraciones (CIS)', 'integrations', 'Feed unificado de órdenes y lecturas bajo demanda', '{provider,group}', NULL),
('observability', '/observability', 'organization', 5, 'Observabilidad', 'observability', 'Alertas activas de ingesta en tiempo real', '{provider,group}', NULL),
('configuration', '/configuration', 'organization', 6, 'Configuración', 'settings', 'Usuarios, región, terminología, paquetes, reglas y parámetros', '{provider,group}', NULL);

CREATE TABLE tenant_module (
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    module_code  text NOT NULL REFERENCES product_module(code),
    enabled      boolean NOT NULL,
    updated_by   text NOT NULL,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, module_code)
);
ALTER TABLE tenant_module ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_module FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_module_tenant_isolation ON tenant_module FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_module TO renfygrid_app;

GRANT SELECT ON nav_group, product_module TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON nav_group, product_module FROM renfygrid_app;
