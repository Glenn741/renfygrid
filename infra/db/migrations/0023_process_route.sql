-- RenfyGrid -- 0023_process_route.sql
-- Ruta del programa (2026-10-05, a pedido del usuario: "la vision de proceso
-- no es claramente visible"). Un paquete de programa define las ETAPAS de su
-- ruta y a que etapa pertenece cada lista y cada cuanto se aplica. Todo en
-- catalogo, nada en codigo: otro programa trae su propia ruta.
--
-- Fuente de la ruta de Municipios Azules: Guia de Formacion de Personas
-- Facilitadoras (Guia 7), seccion 9 "Ruta formativa presencial de ocho
-- jornadas" y T-07 "Pasaporte de productos". Frecuencias: solo las que las
-- guias dicen explicitamente (Guia 3: 7A "al menos cada tres meses", 7E
-- "mensualmente", 7G.1 "al menos una vez al mes"); el resto queda NULL
-- (se aplica cuando corresponde), nunca una frecuencia inventada.

CREATE TABLE process_stage (
    pack_id      text NOT NULL REFERENCES pack(id),
    code         text NOT NULL,
    sort_order   integer NOT NULL,
    title        text NOT NULL,
    source_ref   text NOT NULL,   -- de donde sale la etapa (guia del programa)
    purpose      text NOT NULL,
    products     jsonb NOT NULL,  -- productos esperados de la etapa (pasaporte)
    PRIMARY KEY (pack_id, code)
);
GRANT SELECT ON process_stage TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON process_stage FROM renfygrid_app;

ALTER TABLE checklist_template ADD COLUMN stage_code text;
ALTER TABLE checklist_template ADD COLUMN frequency_days integer CHECK (frequency_days IS NULL OR frequency_days > 0);

INSERT INTO process_stage (pack_id, code, sort_order, title, source_ref, purpose, products) VALUES
('EC-MUNICIPIOS-AZULES', 'G1', 1, 'Diagnóstico y línea base', 'Guía 1 · Jornada 1',
 'Conocer el punto de partida de la junta con evidencia: territorio, sistema, problemas y prioridades.',
 '["Ficha territorial", "Mapa del sistema", "Diagnóstico participativo", "Priorización de problemas", "Causas y primeras acciones"]'),
('EC-MUNICIPIOS-AZULES', 'G2', 2, 'Gobernanza y marco legal', 'Guía 2 · Jornada 2',
 'Ordenar quién decide, quién ejecuta y quién controla, con documentos al día.',
 '["Roles y responsabilidades", "Acta de asamblea", "Estatuto y reglamento actualizados", "Padrón simple", "Alianzas y transparencia", "Plan de gobernanza"]'),
('EC-MUNICIPIOS-AZULES', 'G3', 3, 'Operación, calidad y mantenimiento', 'Guía 3 · Jornadas 3 y 4',
 'Operar el sistema cada día, controlar la calidad del agua, mantener la infraestructura y responder a emergencias.',
 '["Mapa técnico", "Semáforo del sistema", "Tren de tratamiento", "Registro de cloro y bitácora", "Calendario de mantenimiento", "Saneamiento y lodos", "Bodega y EPP", "Plan de emergencia", "Plan mínimo de O&M"]'),
('EC-MUNICIPIOS-AZULES', 'G4', 4, 'Administración, finanzas y tarifa', 'Guía 4 · Jornada 5',
 'Cobrar lo justo, registrar cada movimiento y rendir cuentas a la asamblea.',
 '["Padrón verificado", "Pagos y cartera", "Libro de caja", "Costos reales", "Tarifa", "Morosidad", "POA y presupuesto", "Rendición de cuentas"]'),
('EC-MUNICIPIOS-AZULES', 'G5', 5, 'Ambiente, agua segura y WASH', 'Guía 5 · Jornada 6',
 'Cuidar el agua desde la fuente hasta el vaso: microcuenca, saneamiento, higiene y hogar.',
 '["Diagnóstico WASH", "Mapa ambiental de la fuente", "Prácticas de agua y saneamiento", "Campaña de higiene", "Compromisos comunitarios"]'),
('EC-MUNICIPIOS-AZULES', 'G6', 6, 'Plan de Mejora y proyectos', 'Guía 6 · Jornada 7',
 'Pasar del diagnóstico a la acción: priorizar, planificar, presupuestar y dar seguimiento.',
 '["Consolidado de hallazgos", "Prioridades por criticidad y factibilidad", "Plan de Mejora", "Presupuesto", "Perfil de proyecto", "Tablero de seguimiento"]');

UPDATE checklist_template SET stage_code = 'G3' WHERE id IN ('MA-G3-START', 'MA-AP2', 'MA-7A', 'MA-7E', 'MA-7G1');
UPDATE checklist_template SET stage_code = 'G4' WHERE id IN ('MA-G4-START', 'MA-4A', 'MA-4B');
UPDATE checklist_template SET frequency_days = 90 WHERE id = 'MA-7A';
UPDATE checklist_template SET frequency_days = 30 WHERE id IN ('MA-7E', 'MA-7G1');
