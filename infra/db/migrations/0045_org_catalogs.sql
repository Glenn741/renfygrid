-- RenfyGrid -- 0045_org_catalogs.sql
-- Base generica (2026-10-06). RenfyGrid opera acueductos en distintos paises:
-- nada propio de un pais, una entidad o un programa vive en el codigo
-- (docs/08-estandares-mundiales.md §3). Este cambio mueve a tablas lo que
-- estaba escrito en la interfaz:
--   - moneda y region (formato de numeros) de cada organizacion;
--   - etiquetas de los codigos de estado, tipo y prioridad (antes ~50 mapas
--     en el frontend); el nucleo trae las suyas y un paquete puede cambiarlas;
--   - terminologia: como se llama el prestador, su directiva, la autoridad,
--     el gobierno local... (antes "junta", "ARCA", "GAD", "MSP" en la interfaz);
--     la trae el paquete y cada organizacion puede cambiarla;
--   - formatos de un paquete (p. ej. "7G.2"): solo se muestran si el paquete
--     adoptado los declara.

-- ── Monedas y regiones ────────────────────────────────────────────────
CREATE TABLE currency (
    code      text PRIMARY KEY CHECK (code ~ '^[A-Z]{3}$'),   -- ISO 4217
    label     text NOT NULL,
    decimals  integer NOT NULL CHECK (decimals BETWEEN 0 AND 4)
);
INSERT INTO currency (code, label, decimals) VALUES
('USD', 'Dólar estadounidense', 2), ('COP', 'Peso colombiano', 0), ('PEN', 'Sol peruano', 2), ('MXN', 'Peso mexicano', 2),
('CLP', 'Peso chileno', 0), ('BOB', 'Boliviano', 2), ('GTQ', 'Quetzal', 2), ('HNL', 'Lempira', 2), ('NIO', 'Córdoba', 2),
('CRC', 'Colón costarricense', 2), ('PAB', 'Balboa', 2), ('DOP', 'Peso dominicano', 2), ('ARS', 'Peso argentino', 2),
('UYU', 'Peso uruguayo', 2), ('PYG', 'Guaraní', 0), ('BRL', 'Real brasileño', 2), ('EUR', 'Euro', 2);

-- Separadores tomados de Intl (CLDR), el mismo estandar que usa el navegador.
CREATE TABLE locale_option (
    code         text PRIMARY KEY,   -- BCP 47
    label        text NOT NULL,
    decimal_sep  text NOT NULL,
    group_sep    text NOT NULL
);
INSERT INTO locale_option (code, label, decimal_sep, group_sep) VALUES
('es-EC', 'Español (Ecuador)', ',', '.'), ('es-CO', 'Español (Colombia)', ',', '.'), ('es-PE', 'Español (Perú)', '.', ','),
('es-MX', 'Español (México)', '.', ','), ('es-CL', 'Español (Chile)', ',', '.'), ('es-BO', 'Español (Bolivia)', ',', '.'),
('es-GT', 'Español (Guatemala)', '.', ','), ('es-HN', 'Español (Honduras)', '.', ','), ('es-NI', 'Español (Nicaragua)', '.', ','),
('es-SV', 'Español (El Salvador)', '.', ','), ('es-CR', 'Español (Costa Rica)', ',', ' '), ('es-PA', 'Español (Panamá)', '.', ','),
('es-DO', 'Español (República Dominicana)', '.', ','), ('es-AR', 'Español (Argentina)', ',', '.'), ('es-UY', 'Español (Uruguay)', ',', '.'),
('es-PY', 'Español (Paraguay)', ',', '.'), ('es-ES', 'Español (España)', ',', '.'), ('pt-BR', 'Português (Brasil)', ',', '.'),
('en-US', 'English (United States)', '.', ',');

-- ── Etiquetas de codigos ──────────────────────────────────────────────
-- `tone`: como se pinta (exito, alerta, peligro...); el estilo de cada tono
-- es de la interfaz, el tono de cada estado es dato.
CREATE TABLE code_label (
    pack_id     text NOT NULL REFERENCES pack(id),
    domain      text NOT NULL,
    code        text NOT NULL,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    tone        text CHECK (tone IN ('success', 'warning', 'danger', 'info', 'neutral')),
    PRIMARY KEY (pack_id, domain, code)
);
INSERT INTO code_label (pack_id, domain, code, sort_order, label, tone) VALUES
('core', 'priority', 'high', 1, 'Alta', 'danger'), ('core', 'priority', 'medium', 2, 'Media', 'warning'),
('core', 'priority', 'low', 3, 'Baja', 'neutral'),
('core', 'maintenance.priority', 'low', 1, 'Baja', 'neutral'), ('core', 'maintenance.priority', 'medium', 2, 'Media', 'warning'),
('core', 'maintenance.priority', 'high', 3, 'Alta', 'danger'), ('core', 'maintenance.priority', 'emergency', 4, 'Emergencia', 'danger'),
('core', 'pack.kind', 'core', 1, 'Núcleo', NULL), ('core', 'pack.kind', 'regulatory', 2, 'Normativo', NULL),
('core', 'pack.kind', 'program', 3, 'Programa', NULL),
('core', 'instrumentation.module', 'metering', 1, 'Medición', NULL), ('core', 'instrumentation.module', 'water_balance', 2, 'Balance de agua', NULL),
('core', 'instrumentation.module', 'quality', 3, 'Calidad del agua', NULL), ('core', 'instrumentation.module', 'maintenance', 4, 'Mantenimiento', NULL),
('core', 'instrumentation.module', 'network', 5, 'Red', NULL), ('core', 'instrumentation.module', 'billing', 6, 'Cobro', NULL),
('core', 'instrumentation.level', 'basic', 1, 'Básico — sin medidores', NULL),
('core', 'instrumentation.level', 'intermediate', 2, 'Intermedio — macromedidor y lectura manual', NULL),
('core', 'instrumentation.level', 'advanced', 3, 'Avanzado — telemedida, SIG, modelo', NULL),
('core', 'consumption.action', 'reread_order', 1, 'Orden de relectura', NULL),
('core', 'consumption.action', 'inspection_order', 2, 'Orden de inspección', NULL),
('core', 'control.type', 'suspension', 1, 'Suspensión', NULL), ('core', 'control.type', 'reconnection', 2, 'Reconexión', NULL),
('core', 'control.type', 'disconnection', 3, 'Desconexión', NULL),
('core', 'control.status', 'requested', 1, 'Solicitada', 'neutral'), ('core', 'control.status', 'pending_approval', 2, 'Pendiente de aprobación', 'warning'),
('core', 'control.status', 'approved', 3, 'Aprobada', 'info'), ('core', 'control.status', 'sent', 4, 'Enviada', 'info'),
('core', 'control.status', 'confirmed', 5, 'Confirmada', 'success'), ('core', 'control.status', 'failed', 6, 'Fallida', 'danger'),
('core', 'asset.status', 'operational', 1, 'Operativo', 'success'), ('core', 'asset.status', 'maintenance', 2, 'En mantenimiento', 'warning'),
('core', 'asset.status', 'out_of_service', 3, 'Fuera de servicio', 'danger'),
('core', 'maintenance.type', 'preventive', 1, 'Preventivo', NULL), ('core', 'maintenance.type', 'corrective', 2, 'Correctivo', NULL),
('core', 'maintenance.type', 'inspection', 3, 'Inspección', NULL), ('core', 'maintenance.type', 'emergency', 4, 'Emergente', NULL),
('core', 'maintenance.source', 'asset_condition', 1, 'Condición del activo', NULL),
('core', 'maintenance.source', 'simulation_result', 2, 'Resultado de simulación', NULL),
('core', 'maintenance.source', 'balance_anomaly', 3, 'Anomalía de balance', NULL),
('core', 'maintenance.source', 'pm_schedule', 4, 'Preventivo programado', NULL),
('core', 'maintenance.source', 'manual', 5, 'Manual', NULL), ('core', 'maintenance.source', 'event', 6, 'Por evento', NULL),
('core', 'maintenance.status', 'generated', 1, 'Generada', 'neutral'), ('core', 'maintenance.status', 'scheduled', 2, 'Programada', 'info'),
('core', 'maintenance.status', 'assigned', 3, 'Asignada', 'info'), ('core', 'maintenance.status', 'sent_to_bayforce', 4, 'Enviada a BayForce', 'info'),
('core', 'maintenance.status', 'in_progress', 5, 'En progreso', 'warning'), ('core', 'maintenance.status', 'completed', 6, 'Completada', 'success'),
('core', 'maintenance.status', 'cancelled', 7, 'Cancelada', 'neutral'),
('core', 'meter.type', 'micro', 1, 'Micro (cliente)', NULL), ('core', 'meter.type', 'macro', 2, 'Macro (sector)', NULL),
('core', 'meter.event_type', 'meter_alarm', 1, 'Alarma del medidor', 'warning'),
('core', 'meter.event_type', 'communication_success', 2, 'Comunicación exitosa', 'success'),
('core', 'meter.event_type', 'communication_failure', 3, 'Falla de comunicación', 'danger'),
('core', 'zone.type', 'dma', 1, 'DMA (Distrito Hidrométrico)', NULL), ('core', 'zone.type', 'circuit', 2, 'Circuito', NULL),
('core', 'zone.type', 'district', 3, 'Distrito', NULL), ('core', 'zone.type', 'pressure_zone', 4, 'Zona de presión', NULL),
('core', 'balance.method', 'top_down', 1, 'Top-Down (auditoría)', NULL), ('core', 'balance.method', 'bottom_up', 2, 'Bottom-Up (componentes)', NULL),
('core', 'vee.rule_type', 'range', 1, 'Rango', NULL), ('core', 'vee.rule_type', 'channel_consistency', 2, 'Coherencia entre canales', NULL),
('core', 'vee.rule_type', 'missing_interval', 3, 'Intervalo faltante', NULL), ('core', 'vee.rule_type', 'sin_regla_o_formato', 4, 'Sin regla / formato', NULL),
('core', 'vee.method', 'linear_interpolation', 1, 'Interpolación lineal', NULL),
('core', 'vee.method', 'customer_historical_average', 2, 'Promedio histórico del medidor', NULL),
('core', 'vee.method', 'similar_customers_average', 3, 'Promedio de medidores similares', NULL),
('core', 'vee.method', 'desconocido', 4, 'Método desconocido', NULL),
('core', 'discharge.status', 'identified', 1, 'Identificada', 'warning'), ('core', 'discharge.status', 'agreement', 2, 'Con acuerdo', 'info'),
('core', 'discharge.status', 'controlled', 3, 'Controlada', 'success'), ('core', 'discharge.status', 'closed', 4, 'Cerrada', 'neutral'),
('core', 'membership.status', 'invited', 1, 'Invitada', 'warning'), ('core', 'membership.status', 'accepted', 2, 'Miembro', 'success'),
('core', 'membership.status', 'declined', 3, 'Rechazó', 'neutral'), ('core', 'membership.status', 'left', 4, 'Salió', 'neutral'),
('core', 'membership.status', 'removed', 5, 'Retirada', 'neutral'),
('core', 'support_level', 'community', 1, 'La comunidad puede resolverlo', NULL),
('core', 'support_level', 'local_government', 2, 'Apoyo del gobierno local', NULL),
('core', 'support_level', 'specialized', 3, 'Asistencia especializada', NULL),
('core', 'finding.status', 'open', 1, 'Abierto', 'warning'), ('core', 'finding.status', 'in_progress', 2, 'En curso', 'info'),
('core', 'finding.status', 'closed', 3, 'Cerrado', 'neutral'),
('core', 'finding.source', 'critical_point', 1, 'Punto crítico', NULL), ('core', 'finding.source', 'checklist', 2, 'Lista de verificación', NULL),
('core', 'finding.source', 'reading', 3, 'Lectura', NULL), ('core', 'finding.source', 'manual', 4, 'Manual', NULL),
('core', 'observation.status', 'open', 1, 'Abierta', 'warning'), ('core', 'observation.status', 'in_review', 2, 'En revisión', 'info'),
('core', 'observation.status', 'incorporated', 3, 'Incorporada', 'success'), ('core', 'observation.status', 'discarded', 4, 'Descartada', 'neutral'),
('core', 'sample.reason', 'plan', 1, 'Plan de muestreo', NULL), ('core', 'sample.reason', 'alert', 2, 'Por alerta', NULL),
('core', 'sample.reason', 'other', 3, 'Otro', NULL),
('core', 'quality.plan_status', 'never', 1, 'Sin muestra', 'neutral'), ('core', 'quality.plan_status', 'ok', 2, 'Al día', 'success'),
('core', 'quality.plan_status', 'done', 3, 'Al día', 'success'), ('core', 'quality.plan_status', 'overdue', 4, 'Vencido', 'danger'),
('core', 'service', 'water', 1, 'Agua potable', NULL), ('core', 'service', 'sanitation', 2, 'Saneamiento', NULL),
('core', 'service', 'support', 3, 'Soporte', NULL),
('core', 'warehouse.unit', 'g', 1, 'g', NULL), ('core', 'warehouse.unit', 'kg', 2, 'kg', NULL), ('core', 'warehouse.unit', 'ml', 3, 'ml', NULL),
('core', 'warehouse.unit', 'l', 4, 'L', NULL), ('core', 'warehouse.unit', 'unit', 5, 'unidad', NULL), ('core', 'warehouse.unit', 'pair', 6, 'par', NULL),
('core', 'warehouse.unit', 'm', 7, 'm', NULL),
('core', 'warehouse.movement_kind', 'in', 1, 'Entrada', NULL), ('core', 'warehouse.movement_kind', 'out', 2, 'Salida', NULL),
('core', 'warehouse.movement_kind', 'adjust', 3, 'Ajuste por conteo', NULL),
('core', 'emergency.trigger', 'manual', 1, 'Manual', NULL), ('core', 'emergency.trigger', 'auto', 2, 'Automática', NULL);

-- ── Terminologia ──────────────────────────────────────────────────────
-- El nucleo trae terminos neutros; un paquete los cambia (el de programa,
-- p. ej., llama "junta" al prestador; el regulatorio nombra la autoridad y
-- las instituciones del pais) y cada organizacion puede cambiarlos.
CREATE TABLE term (
    pack_id  text NOT NULL REFERENCES pack(id),
    key      text NOT NULL,
    label    text NOT NULL,
    plural   text NOT NULL,
    PRIMARY KEY (pack_id, key)
);
INSERT INTO term (pack_id, key, label, plural) VALUES
('core', 'provider', 'organización', 'organizaciones'),
('core', 'board', 'directiva', 'directivas'),
('core', 'operator', 'operador', 'operadores'),
('core', 'local_government', 'gobierno local', 'gobiernos locales'),
('core', 'health_authority', 'autoridad de salud', 'autoridades de salud'),
('core', 'regulator', 'ente rector', 'entes rectores'),
('core', 'emergency_line', 'línea de emergencias', 'líneas de emergencias'),
('core', 'civil_protection', 'protección civil', 'protección civil'),
('core', 'community_work', 'jornada comunitaria', 'jornadas comunitarias'),
('EC-MUNICIPIOS-AZULES', 'provider', 'junta', 'juntas'),
('EC-MUNICIPIOS-AZULES', 'community_work', 'minga', 'mingas'),
('EC-ARCA', 'local_government', 'GAD municipal', 'GAD municipales'),
('EC-ARCA', 'health_authority', 'MSP', 'MSP'),
('EC-ARCA', 'regulator', 'ARCA', 'ARCA'),
('EC-ARCA', 'emergency_line', 'ECU 911', 'ECU 911'),
('EC-ARCA', 'civil_protection', 'COE cantonal', 'COE cantonales');

CREATE TABLE tenant_term (
    tenant_id   uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    key         text NOT NULL,
    label       text NOT NULL,
    plural      text NOT NULL,
    updated_by  text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, key)
);
ALTER TABLE tenant_term ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_term FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_term_tenant_isolation ON tenant_term FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_term TO renfygrid_app;

-- ── Formatos de un paquete ────────────────────────────────────────────
-- El nombre con que un programa conoce cada registro ("7G.2", "7F"); la
-- pantalla lo muestra junto al nombre generico solo si el paquete lo declara.
-- `template_id`/`stage_code`: la lista con que se aplica y la etapa de la
-- ruta donde vive (antes la pantalla enlazaba a una etapa fija).
CREATE TABLE pack_form (
    pack_id      text NOT NULL REFERENCES pack(id),
    domain       text NOT NULL,
    code         text NOT NULL,
    title        text NOT NULL,
    stage_code   text,
    template_id  text REFERENCES checklist_template(id),
    PRIMARY KEY (pack_id, domain),
    FOREIGN KEY (pack_id, stage_code) REFERENCES process_stage(pack_id, code)
);
INSERT INTO pack_form (pack_id, domain, code, title, stage_code, template_id) VALUES
('EC-MUNICIPIOS-AZULES', 'field_readings', '7B', 'Registro de cloro residual', 'G3', NULL),
('EC-MUNICIPIOS-AZULES', 'operation_log', '7C', 'Bitácora diaria de operación', 'G3', NULL),
('EC-MUNICIPIOS-AZULES', 'maintenance_record', '7D', 'Registro de mantenimiento', 'G3', NULL),
('EC-MUNICIPIOS-AZULES', 'sanitation_inspection', '7E', 'Lista de inspección de saneamiento', 'G3', 'MA-7E'),
('EC-MUNICIPIOS-AZULES', 'sanitation_register', '7F', 'Registro de limpieza, lodos y saneamiento', 'G3', NULL),
('EC-MUNICIPIOS-AZULES', 'annual_calendar', '7G', 'Calendario anual', 'G3', NULL),
('EC-MUNICIPIOS-AZULES', 'warehouse_review', '7G.1', 'Revisión de bodega y EPP', 'G3', 'MA-7G1'),
('EC-MUNICIPIOS-AZULES', 'improvement_inputs', '7G.2', 'Ficha de insumos para el Plan de Mejora', 'G3', NULL),
('EC-MUNICIPIOS-AZULES', 'products_board', '7H', 'Productos finales', 'G3', 'MA-G3-7H'),
('EC-MUNICIPIOS-AZULES', 'improvement_plan', 'Guía 6', 'Plan de Mejora', 'G6', NULL),
('EC-MUNICIPIOS-AZULES', 'daily_evaluation', 'T-06', 'Evaluación diaria', 'INT', 'MA-T06'),
('EC-MUNICIPIOS-AZULES', 'microfacilitation_rubric', 'T-08', 'Rúbrica de microfacilitación', 'INT', 'MA-T08'),
('EC-MUNICIPIOS-AZULES', 'program_observations', 'T-10', 'Consolidado de observaciones para mejora', 'INT', NULL);

-- El plan minimo pertenece a una etapa de la ruta: su tablero de productos
-- son las listas de tipo `products` de esa etapa (antes el id estaba fijo en
-- la pantalla).
ALTER TABLE minimum_plan_row ADD COLUMN stage_code text;
UPDATE minimum_plan_row SET stage_code = 'G3' WHERE pack_id = 'EC-MUNICIPIOS-AZULES';
ALTER TABLE minimum_plan_row ADD CONSTRAINT minimum_plan_row_stage_fkey FOREIGN KEY (pack_id, stage_code) REFERENCES process_stage(pack_id, code);

GRANT SELECT ON currency, locale_option, code_label, term, pack_form TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON currency, locale_option, code_label, term, pack_form FROM renfygrid_app;
