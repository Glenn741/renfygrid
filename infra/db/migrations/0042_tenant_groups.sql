-- RenfyGrid -- 0042_tenant_groups.sql
-- Track D, D12.1 (2026-10-06): agrupacion de juntas y su tablero.
--
-- Plan (docs/04 §11.2, D12): "Para una agrupacion de juntas (asociacion, ACC)
-- que comparte tecnico, compras o laboratorio: indice de madurez inicial vs.
-- actual, alertas de calidad abiertas, cumplimiento del calendario, tarifa
-- frente a costos, morosidad agregada."
--
-- Modelo:
-- - La agrupacion es una organizacion (tenant) de tipo 'group' con sus
--   propios usuarios; no ve datos operativos de nadie.
-- - Una junta entra solo si acepta la invitacion, y elige QUE indicadores
--   comparte; puede cambiarlos o salir cuando quiera. El tablero lee cada
--   junta por separado, con su RLS, y solo los indicadores compartidos.
-- - Los indicadores son catalogo; `params` dice de donde se calculan (p. ej.
--   que listas forman el indice de madurez). Los que dependen de renfy_pool
--   (tarifa, morosidad) quedan declarados como no disponibles hasta D8-D11.

ALTER TABLE tenant ADD COLUMN kind text NOT NULL DEFAULT 'provider' CHECK (kind IN ('provider', 'group'));

-- ── Catalogo: indicadores que una junta puede compartir ──────────────
CREATE TABLE group_indicator (
    code         text PRIMARY KEY,
    sort_order   integer NOT NULL,
    label        text NOT NULL,
    description  text NOT NULL,
    params       jsonb NOT NULL DEFAULT '{}'::jsonb,
    available    boolean NOT NULL DEFAULT true,
    unavailable_note text
);
INSERT INTO group_indicator (code, sort_order, label, description, params, available, unavailable_note) VALUES
('maturity', 1, 'Índice de madurez inicial y actual',
 'Puntaje de las verificaciones de cada guía: la primera aplicación frente a la última.',
 '{"template_ids": ["MA-G2-START", "MA-G3-START", "MA-G4-START", "MA-G5-START", "MA-G6-START", "MA-4A", "MA-4B"]}', true, NULL),
('quality_alerts', 2, 'Alertas de calidad abiertas',
 'Mediciones de campo y análisis de laboratorio fuera de rango sin cerrar; cuántas son críticas.', '{}', true, NULL),
('calendar', 3, 'Cumplimiento del calendario anual',
 'Porcentaje de actividades del calendario 7G (mantenimiento, revisiones y análisis) hechas en el año.', '{}', true, NULL),
('products', 4, 'Productos finales de las guías',
 'Productos verificados como completos en las listas 7H de cada guía.', '{}', true, NULL),
('improvement', 5, 'Insumos para el Plan de Mejora',
 'Problemas en la ficha 7G.2, costo estimado y cuántos falta cotizar.', '{}', true, NULL),
('sanitation', 6, 'Saneamiento',
 'Fosas y plantas con retiro de lodos vencido y descargas productivas sin controlar.', '{}', true, NULL),
('emergencies', 7, 'Emergencias activas', 'Emergencias activadas y aún no cerradas.', '{}', true, NULL),
('tariff_cost', 8, 'Tarifa frente a costos', 'Cobertura de los costos reales con la tarifa vigente.', '{}', false,
 'Se calcula con la planilla de costos y la tarifa (D9, renfy_pool), todavía no integradas.'),
('delinquency', 9, 'Morosidad', 'Usuarios con pagos atrasados y monto por cobrar.', '{}', false,
 'Se calcula con la recaudación (D10, renfy_pool), todavía no integrada.');
GRANT SELECT ON group_indicator TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON group_indicator FROM renfygrid_app;

-- ── Membresia: la ven las dos partes ──────────────────────────────────
CREATE TABLE group_membership (
    group_tenant_id   uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    member_tenant_id  uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    status            text NOT NULL DEFAULT 'invited' CHECK (status IN ('invited', 'accepted', 'declined', 'left', 'removed')),
    shared            text[] NOT NULL DEFAULT '{}',   -- codigos de group_indicator que la junta comparte
    invited_by        text NOT NULL,
    invited_at        timestamptz NOT NULL DEFAULT now(),
    decided_by        text,
    decided_at        timestamptz,
    PRIMARY KEY (group_tenant_id, member_tenant_id),
    CHECK (group_tenant_id <> member_tenant_id),
    CHECK (status = 'accepted' OR shared = '{}')
);
ALTER TABLE group_membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_membership FORCE ROW LEVEL SECURITY;
CREATE POLICY group_membership_parties ON group_membership FOR ALL
    USING (group_tenant_id = current_setting('app.tenant_id', true)::uuid
           OR member_tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (group_tenant_id = current_setting('app.tenant_id', true)::uuid
                OR member_tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON group_membership TO renfygrid_app;

-- ── Permisos ──────────────────────────────────────────────────────────
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('group.view', 27, 'Agrupación', 'Ver el tablero de la agrupación'),
('group.manage', 28, 'Agrupación', 'Invitar o retirar juntas de la agrupación'),
('group.consent', 29, 'Agrupación', 'Aceptar una agrupación y decidir qué indicadores comparte la junta');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'group.view'), ('supervisor', 'group.manage'), ('supervisor', 'group.consent'),
('board', 'group.view'), ('board', 'group.consent');
