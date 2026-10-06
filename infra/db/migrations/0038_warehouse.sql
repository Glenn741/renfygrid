-- RenfyGrid -- 0038_warehouse.sql
-- Track D, D4 (2026-10-06): bodega y EPP. Fuente: Guia 3 de Municipios
-- Azules, seccion 3.9 ("La bodega debe ser segura, ventilada y ordenada. Debe
-- proteger quimicos, EPP, herramientas, repuestos y bitacoras") y registro de
-- bodega de la seccion 3.10 ("Controlar quimicos, repuestos, EPP y
-- herramientas"). La lista 7G.1 ya existe (0021).
--
-- Catalogo del paquete: categorias de la "bodega basica" con lo que debe
-- incluir cada una, y el EPP minimo por tarea (texto literal). Por junta:
-- articulos (stock minimo lo fija la junta), entradas con vencimiento,
-- salidas y ajustes. El cruce cloro aplicado (bitacora 7C) vs. salidas de
-- bodega se calcula, no se guarda.

CREATE TABLE warehouse_category (
    pack_id     text NOT NULL REFERENCES pack(id),
    code        text NOT NULL,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    should_include text NOT NULL,
    PRIMARY KEY (pack_id, code)
);
INSERT INTO warehouse_category (pack_id, code, sort_order, label, should_include) VALUES
('EC-MUNICIPIOS-AZULES', 'chemicals', 1, 'Químicos', 'Hipoclorito y otros productos usados por el sistema, separados y rotulados.'),
('EC-MUNICIPIOS-AZULES', 'spare_parts', 2, 'Repuestos', 'Tuberías, uniones, codos, tees, válvulas, pegamento, lija y accesorios de los diámetros usados.'),
('EC-MUNICIPIOS-AZULES', 'tools', 3, 'Herramientas', 'Llave stilson, pala, pico, linterna, cinta, baldes y recipientes medidores.'),
('EC-MUNICIPIOS-AZULES', 'control', 4, 'Control', 'Kit de cloro residual, registros, bitácoras y formatos.'),
('EC-MUNICIPIOS-AZULES', 'ppe', 5, 'EPP', 'Guantes, botas, gafas, mascarillas y ropa de trabajo.');

CREATE TABLE ppe_task (
    pack_id     text NOT NULL REFERENCES pack(id),
    sort_order  integer NOT NULL,
    task        text NOT NULL,
    ppe         text NOT NULL,
    care        text NOT NULL,
    PRIMARY KEY (pack_id, sort_order)
);
INSERT INTO ppe_task (pack_id, sort_order, task, ppe, care) VALUES
('EC-MUNICIPIOS-AZULES', 1, 'Preparar cloro o químicos', 'Guantes, mascarilla, gafas, ropa de trabajo.', 'No mezclar productos. Preparar en sitio ventilado.'),
('EC-MUNICIPIOS-AZULES', 2, 'Revisar captación o reservorio', 'Botas, guantes, casco si hay riesgo de caída.', 'No ingresar solo a espacios cerrados o resbalosos.'),
('EC-MUNICIPIOS-AZULES', 3, 'Destapar caja o red sanitaria', 'Botas, guantes resistentes, gafas, mascarilla u overol.', 'Evitar contacto directo con aguas residuales.'),
('EC-MUNICIPIOS-AZULES', 4, 'Extraer lodos', 'EPP completo y apoyo especializado.', 'No manipular lodos sin procedimiento seguro.');

GRANT SELECT ON warehouse_category, ppe_task TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON warehouse_category, ppe_task FROM renfygrid_app;

CREATE TABLE warehouse_item (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id              text NOT NULL,
    category_code        text NOT NULL,
    name                 text NOT NULL,
    unit                 text NOT NULL CHECK (unit IN ('g', 'kg', 'ml', 'l', 'unit', 'pair', 'm')),
    min_stock            numeric CHECK (min_stock IS NULL OR min_stock >= 0),
    chemical_product_id  uuid REFERENCES chemical_product(id),
    active               boolean NOT NULL DEFAULT true,
    created_at           timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pack_id, category_code) REFERENCES warehouse_category(pack_id, code),
    UNIQUE (tenant_id, name)
);

CREATE TABLE warehouse_movement (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    item_id       uuid NOT NULL REFERENCES warehouse_item(id),
    kind          text NOT NULL CHECK (kind IN ('in', 'out', 'adjust')),
    -- in/out: cantidad positiva. adjust: diferencia con signo (conteo fisico).
    quantity      numeric NOT NULL CHECK (quantity <> 0),
    moved_at      timestamptz NOT NULL,
    expires_on    date,
    reason        text,
    maintenance_order_id uuid REFERENCES maintenance_order(id),
    recorded_by   text NOT NULL,
    client_id     uuid,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, client_id),
    CHECK (kind = 'adjust' OR quantity > 0)
);
CREATE INDEX warehouse_movement_item_idx ON warehouse_movement (tenant_id, item_id, moved_at DESC);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['warehouse_item', 'warehouse_movement'] LOOP
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

INSERT INTO app_permission (code, sort_order, area, label) VALUES
('warehouse.record', 21, 'Bodega', 'Registrar entradas, salidas y conteos de bodega'),
('warehouse.manage', 22, 'Bodega', 'Administrar artículos de bodega y stock mínimo');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'warehouse.record'), ('supervisor', 'warehouse.manage'),
('board', 'warehouse.record'), ('board', 'warehouse.manage'),
('operator', 'warehouse.record');
