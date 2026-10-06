-- RenfyGrid -- 0035_community_maintenance.sql
-- Track D, D3.1 (2026-10-06): mantenimiento comunitario sobre el CMMS (0019).
-- Fuente: Guia 3 de Municipios Azules, seccion 3.6 y fichas 7D y 7G:
--   - Tipos: preventivo, correctivo y EMERGENTE ("cuando hay riesgo inmediato
--     para la salud, la continuidad o la infraestructura").
--   - Cinco pasos: revisar, limpiar, corregir, comprobar, registrar.
--   - 7D: fecha, componente, tipo, materiales, responsable, pendiente.
--   - Frecuencias por tiempo Y por evento: "semanal y despues de lluvias",
--     "mensual y despues de movimientos de tierra", "mensual y ante quejas".
--   - Mingas: la comunidad aporta trabajo (participantes, horas donadas).
--
-- Los pasos y los tipos de evento son CATALOGO del paquete de programa; el
-- tipo 'emergency' y la fuente 'event' son estados del flujo del CMMS.

-- ── Orden: lo que pide la ficha 7D y la minga ─────────────────────────
ALTER TABLE maintenance_order ADD COLUMN pm_plan_id uuid REFERENCES maintenance_pm_plan(id);
ALTER TABLE maintenance_order ADD COLUMN event_id uuid;
ALTER TABLE maintenance_order ADD COLUMN steps_done integer[] NOT NULL DEFAULT '{}';
ALTER TABLE maintenance_order ADD COLUMN responsible text;
ALTER TABLE maintenance_order ADD COLUMN pending_notes text;
ALTER TABLE maintenance_order ADD COLUMN community_participants integer CHECK (community_participants IS NULL OR community_participants >= 0);
ALTER TABLE maintenance_order ADD COLUMN volunteer_hours numeric CHECK (volunteer_hours IS NULL OR volunteer_hours >= 0);
CREATE INDEX maintenance_order_pm_plan_idx ON maintenance_order (tenant_id, pm_plan_id);

-- ── Plan: actividad, responsable y eventos que lo disparan ────────────
ALTER TABLE maintenance_pm_plan ADD COLUMN title text;
ALTER TABLE maintenance_pm_plan ADD COLUMN responsible text;
ALTER TABLE maintenance_pm_plan ADD COLUMN trigger_events text[] NOT NULL DEFAULT '{}';

-- ── Catalogo: los cinco pasos ─────────────────────────────────────────
CREATE TABLE maintenance_step (
    pack_id   text NOT NULL REFERENCES pack(id),
    step_no   integer NOT NULL CHECK (step_no > 0),
    label     text NOT NULL,
    PRIMARY KEY (pack_id, step_no)
);
INSERT INTO maintenance_step (pack_id, step_no, label) VALUES
('EC-MUNICIPIOS-AZULES', 1, 'Revisar el estado.'),
('EC-MUNICIPIOS-AZULES', 2, 'Limpiar o retirar obstáculos.'),
('EC-MUNICIPIOS-AZULES', 3, 'Corregir daños que la comunidad puede resolver.'),
('EC-MUNICIPIOS-AZULES', 4, 'Comprobar que el componente vuelve a funcionar.'),
('EC-MUNICIPIOS-AZULES', 5, 'Registrar la actividad, materiales, responsables y pendientes.');

-- ── Catalogo: eventos que disparan mantenimiento ──────────────────────
CREATE TABLE maintenance_event_type (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO maintenance_event_type (pack_id, code, sort_order, label) VALUES
('EC-MUNICIPIOS-AZULES', 'heavy_rain', 1, 'Lluvias fuertes'),
('EC-MUNICIPIOS-AZULES', 'ground_movement', 2, 'Deslizamiento o movimiento de tierra'),
('EC-MUNICIPIOS-AZULES', 'user_complaints', 3, 'Quejas de usuarios');

GRANT SELECT ON maintenance_step, maintenance_event_type TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON maintenance_step, maintenance_event_type FROM renfygrid_app;

-- ── Por junta: eventos ocurridos ──────────────────────────────────────
CREATE TABLE maintenance_event (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id           text NOT NULL,
    event_type_code   text NOT NULL,
    occurred_at       timestamptz NOT NULL,
    notes             text,
    reported_by       text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pack_id, event_type_code) REFERENCES maintenance_event_type(pack_id, code)
);
ALTER TABLE maintenance_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_event FORCE ROW LEVEL SECURITY;
CREATE POLICY maintenance_event_tenant_isolation ON maintenance_event FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON maintenance_event TO renfygrid_app;
ALTER TABLE maintenance_order ADD CONSTRAINT maintenance_order_event_fkey FOREIGN KEY (event_id) REFERENCES maintenance_event(id);
