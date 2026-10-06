-- RenfyGrid -- 0031_dosing.sql
-- Track D, D1.2 (2026-10-06): calculadora de dosificacion de cloro con
-- guardas. Fuente: Guia 3 de Municipios Azules, seccion 3.5 "Dosificacion
-- segura de cloro y productos quimicos":
--   Gramos de producto por dia = (Caudal L/s x 86.400 x dosis mg/L) / (% de
--   cloro activo x 10)  -- comprobado con la tabla de la guia (0,1 L/s, 1,5
--   mg/L, 65 % -> 19,9 g/dia).
-- Para un producto liquido con % peso/volumen (g por 100 mL) el mismo numero
-- son mililitros por dia.
--
-- Las GUARDAS las decide el motor con los datos del dia (ultimo cloro
-- residual en la salida del tanque, turbiedad, aspecto del agua en la
-- bitacora, tipo de producto); los TEXTOS son de la guia y van como catalogo
-- del paquete de programa. Otro programa trae los suyos.

-- ── Por junta: productos quimicos (D4 les sumara existencias) ──────────
CREATE TABLE chemical_product (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name        text NOT NULL,
    purpose     text NOT NULL CHECK (purpose IN ('disinfection', 'coagulation', 'ph_adjustment')),
    form        text NOT NULL CHECK (form IN ('solid', 'liquid')),
    active_pct  numeric NOT NULL CHECK (active_pct > 0 AND active_pct <= 100),
    notes       text,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);
ALTER TABLE chemical_product ENABLE ROW LEVEL SECURITY;
ALTER TABLE chemical_product FORCE ROW LEVEL SECURITY;
CREATE POLICY chemical_product_tenant_isolation ON chemical_product FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON chemical_product TO renfygrid_app;

-- ── Catalogo: textos de las guardas ───────────────────────────────────
-- level: stop (no aplicar sin apoyo tecnico), warn (revisar antes), info.
CREATE TABLE dosing_guidance (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    level       text NOT NULL CHECK (level IN ('stop', 'warn', 'info')),
    sort_order  integer NOT NULL,
    message     text NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO dosing_guidance (pack_id, code, level, sort_order, message) VALUES
('EC-MUNICIPIOS-AZULES', 'not_disinfectant', 'stop', 1,
 'Si el sistema usa coagulantes, reguladores de pH u otros productos químicos, la dosis debe definirse mediante prueba de jarras, análisis de agua y acompañamiento técnico. La JAAPS no debe aumentar productos químicos solo por observación visual, sin orientación especializada.'),
('EC-MUNICIPIOS-AZULES', 'turbid_water', 'stop', 2,
 'El agua está turbia o con color. Nunca aumente la dosis por intuición ni para compensar agua turbia o con residuos: revise la fuente, el desarenador, la sedimentación y los filtros.'),
('EC-MUNICIPIOS-AZULES', 'high_residual', 'stop', 3,
 'El último cloro residual en la salida del tanque está alto: puede haber sobrecloración. Revisar el cálculo de dosis, repetir la medición y ajustar con apoyo del operador capacitado o técnico.'),
('EC-MUNICIPIOS-AZULES', 'low_residual', 'warn', 4,
 'El último cloro residual está bajo. Antes de subir la dosis, revisar dosificador, dosis, producto, fugas y tiempo de contacto, y repetir la medición. Si persiste, pedir apoyo técnico.'),
('EC-MUNICIPIOS-AZULES', 'no_reading_today', 'warn', 5,
 'Hoy no hay medición de cloro residual en la salida del tanque. Mida antes de cambiar la dosis: la JAAPS debe evitar cambiar dosis por intuición.'),
('EC-MUNICIPIOS-AZULES', 'orientative', 'info', 6,
 'Valores únicamente orientativos: dependen de la calidad inicial del agua, el caudal real, la concentración y el estado del producto, el tiempo de contacto y el cloro residual medido. Deben usarse por operadores capacitados o con apoyo técnico.'),
('EC-MUNICIPIOS-AZULES', 'verify_after', 'info', 7,
 'Después de aplicar, medir cloro residual. Si el resultado no está en rango, no seguir aumentando sin revisar la causa. Toda modificación debe verificarse con mediciones y bitácora.'),
('EC-MUNICIPIOS-AZULES', 'safety', 'info', 8,
 'Use guantes, mascarilla, gafas y ropa de trabajo. Guarde el cloro cerrado, seco y ventilado, lejos del sol, los niños, los alimentos y los combustibles. Nunca mezcle el cloro con detergentes, ácidos, desinfectantes o productos desconocidos.');
GRANT SELECT ON dosing_guidance TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON dosing_guidance FROM renfygrid_app;
