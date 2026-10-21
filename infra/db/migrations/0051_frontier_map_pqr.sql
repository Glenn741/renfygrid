-- RenfyGrid -- 0051_frontier_map_pqr.sql
-- Track F, sprint Q2.5 (2026-10-21): mapa tematico de fronteras.
-- docs/11-mapa-fronteras.md.
--
-- Pedido del usuario: filtrar y pintar las fronteras por estado tecnico,
-- estado comercial, tipo de cliente, PQRS (si tiene y de que tipo), rango de
-- consumo, tipo y marca de medidor y de modem. Lo que el mercado hace
-- (investigado en docs/11): pintar por UNA variable a la vez, tamano por
-- magnitud en rangos, filtros por facetas con conteo, capas de excepcion,
-- agrupamiento y vistas guardadas.
--
--   metering_point.customer_class / market / commercial_status
--   pack CO-SSPD + pqr_cause      -- taxonomia de PQR de la Superservicios
--   customer_request              -- PQR por frontera (por NIU o cuenta)
--   map_dimension                 -- variables por las que se pinta o filtra (dato)
--   map_view                      -- vistas guardadas de la organizacion
--
-- Ninguna variable del mapa esta en el codigo: cada una es una fila de
-- map_dimension con su origen; agregar otra es agregar una fila.

-- ── Datos nuevos de la frontera ───────────────────────────────────────
ALTER TABLE metering_point ADD COLUMN customer_class text;     -- Circular 119 §2.17 (clase de servicio)
ALTER TABLE metering_point ADD COLUMN market text;             -- regulado / no regulado
ALTER TABLE metering_point ADD COLUMN commercial_status text;  -- del CIS o de facturacion

INSERT INTO code_label (pack_id, domain, code, sort_order, label, tone) VALUES
('CO-CREG-038', 'customer.class', 'residential', 1, 'Residencial', NULL),
('CO-CREG-038', 'customer.class', 'commercial', 2, 'Comercial', NULL),
('CO-CREG-038', 'customer.class', 'industrial', 3, 'Industrial', NULL),
('CO-CREG-038', 'customer.class', 'official', 4, 'Oficial', NULL),
('CO-CREG-038', 'customer.class', 'public_lighting', 5, 'Alumbrado público', NULL),
('CO-CREG-038', 'customer.class', 'provisional', 6, 'Provisional', NULL),
('CO-CREG-038', 'customer.class', 'other', 7, 'Otro', NULL),
('CO-CREG-038', 'market', 'regulated', 1, 'Mercado regulado', NULL),
('CO-CREG-038', 'market', 'non_regulated', 2, 'Mercado no regulado', NULL),
('core', 'commercial.status', 'current', 1, 'Al día', 'success'),
('core', 'commercial.status', 'payment_agreement', 2, 'Con acuerdo de pago', 'info'),
('core', 'commercial.status', 'arrears', 3, 'En mora', 'warning'),
('core', 'commercial.status', 'disconnection', 4, 'En proceso de corte', 'danger'),
('core', 'commercial.status', 'suspended_debt', 5, 'Suspendida por cartera', 'danger'),
('core', 'commercial.status', 'retired', 6, 'Retirada', 'neutral'),
-- Estados calculados del mapa (el tono es dato; el calculo, del servicio).
('core', 'comms.status', 'reporting', 1, 'Reportando', 'success'),
('core', 'comms.status', 'silent', 2, 'Sin reportar', 'danger'),
('core', 'comms.status', 'no_link', 3, 'Sin telemedida vinculada', 'neutral'),
('core', 'comms.status', 'no_window', 4, 'Ventana de reporte sin definir', 'neutral'),
('core', 'alarm.recent', 'yes', 1, 'Con alarma reciente', 'danger'),
('core', 'alarm.recent', 'no', 2, 'Sin alarmas', 'success'),
('core', 'xm.pending_flag', 'yes', 1, 'Con novedad pendiente de XM', 'warning'),
('core', 'xm.pending_flag', 'no', 2, 'Sin novedades pendientes', 'success'),
('core', 'pqr.open', 'yes', 1, 'Con PQR abierta', 'danger'),
('core', 'pqr.open', 'no', 2, 'Sin PQR abierta', 'success'),
('core', 'pqr.status', 'open', 1, 'Abierta', 'warning'),
('core', 'pqr.status', 'answered', 2, 'Respondida', 'info'),
('core', 'pqr.status', 'appealed', 3, 'En recurso', 'warning'),
('core', 'pqr.status', 'closed', 4, 'Cerrada', 'neutral'),
('core', 'map.none', 'none', 99, 'Sin dato', 'neutral');

-- ── PQR: taxonomia de la Superservicios ───────────────────────────────
INSERT INTO pack (id, kind, country, name, version, source_note, sector_code) VALUES
('CO-SSPD', 'regulatory', 'CO', 'Colombia — Superservicios (PQR y reporte al SUI)', '2026-10',
 'Resolución SSPD 20261000681915 de 5 de agosto de 2026 (reporte de PQR al SUI; vigente según sui.superservicios.gov.co). Códigos tomados del proyecto de resolución publicado en abril de 2026: verificar contra el texto final y corregir aquí.',
 NULL);

INSERT INTO code_label (pack_id, domain, code, sort_order, label, tone) VALUES
('CO-SSPD', 'pqr.request_type', '1', 1, 'Reclamación', NULL),
('CO-SSPD', 'pqr.request_type', '2', 2, 'Queja', NULL),
('CO-SSPD', 'pqr.request_type', '4', 3, 'Recurso de reposición', NULL),
('CO-SSPD', 'pqr.request_type', '5', 4, 'Recurso de reposición y en subsidio de apelación', NULL),
('CO-SSPD', 'pqr.cause_group', 'F', 1, 'Facturación', NULL),
('CO-SSPD', 'pqr.cause_group', 'P', 2, 'Prestación', NULL),
('CO-SSPD', 'pqr.response', '1', 1, 'Accede', 'success'),
('CO-SSPD', 'pqr.response', '2', 2, 'Accede parcialmente', 'info'),
('CO-SSPD', 'pqr.response', '3', 3, 'No accede', 'neutral'),
('CO-SSPD', 'pqr.response', '4', 4, 'Confirma', 'neutral'),
('CO-SSPD', 'pqr.response', '5', 5, 'Modifica', 'info'),
('CO-SSPD', 'pqr.response', '6', 6, 'Revoca', 'success'),
('CO-SSPD', 'pqr.response', '9', 7, 'Pendiente de respuesta', 'warning'),
('CO-SSPD', 'pqr.response', '10', 8, 'Sin respuesta', 'danger');

-- `request_kind`: reclamacion (art. 154 Ley 142) o queja. `sectors`: NULL =
-- aplica a todos; un arreglo vacio = solo aseo (no es un sector de RenfyGrid).
CREATE TABLE pqr_cause (
    pack_id       text NOT NULL REFERENCES pack(id),
    code          text NOT NULL,
    group_code    text NOT NULL CHECK (group_code IN ('F', 'P')),
    request_kind  text NOT NULL CHECK (request_kind IN ('claim', 'complaint')),
    label         text NOT NULL,
    description   text NOT NULL,
    sectors       text[],
    PRIMARY KEY (pack_id, code)
);
GRANT SELECT ON pqr_cause TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON pqr_cause FROM renfygrid_app;

CREATE TABLE customer_request (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenant(id),
    point_id       uuid REFERENCES metering_point(id),
    account        text,                 -- NIU o cuenta con que llego (se usa para ubicar la frontera)
    filing_number  text NOT NULL,        -- radicado
    filed_on       date NOT NULL,
    request_type   text NOT NULL,        -- pqr.request_type
    pack_id        text NOT NULL,
    cause_code     text NOT NULL,
    status         text NOT NULL DEFAULT 'open',
    response_code  text,                 -- pqr.response
    responded_on   date,
    invoice_number text,
    notes          text,
    source         text NOT NULL DEFAULT 'manual',
    created_by     text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pack_id, cause_code) REFERENCES pqr_cause(pack_id, code),
    CHECK (status IN ('open', 'answered', 'appealed', 'closed'))
);
-- Unidad de registro del SUI: radicado + cuenta + causal.
CREATE UNIQUE INDEX customer_request_uq ON customer_request (tenant_id, filing_number, coalesce(account, ''), cause_code);
CREATE INDEX customer_request_point_idx ON customer_request (point_id, status);

-- ── Mapa ──────────────────────────────────────────────────────────────
-- `source`: de donde sale el valor de cada frontera. Formas que entiende el
-- servicio (metering_asset_map.py):
--   point:<columna>                      columna de metering_point
--   equipment:<posicion>:<campo>         campo del equipo instalado en esa posicion
--   equipment_attr:<posicion>:<clave>    campo de su ficha tecnica (Circular 119)
--   equipment_age:<posicion>             antiguedad (anos desde su ano de fabricacion), con `bins`
--   computed:<nombre>                    calibracion, comunicacion, alarma, XM, PQR, rango de consumo
-- `role`: 'category' (pintar y/o filtrar) o 'size' (tamano del simbolo).
-- `labels_domain`: dominio de code_label con nombres y tonos; si es NULL, los
-- valores se muestran tal cual (p. ej. marcas, ciudades).
-- `alert_codes`: si no es NULL, la dimension tambien es una capa de
-- excepcion que resalta las fronteras con esos valores.
CREATE TABLE map_dimension (
    key            text PRIMARY KEY,
    pack_id        text NOT NULL REFERENCES pack(id),
    sector_code    text REFERENCES sector(code),
    group_label    text NOT NULL,
    sort_order     integer NOT NULL,
    label          text NOT NULL,
    role           text NOT NULL DEFAULT 'category' CHECK (role IN ('category', 'size')),
    source         text NOT NULL,
    labels_domain  text,
    bins           jsonb,
    can_paint      boolean NOT NULL DEFAULT true,
    can_filter     boolean NOT NULL DEFAULT true,
    alert_codes    text[],
    alert_label    text,
    description    text
);
INSERT INTO map_dimension (key, pack_id, sector_code, group_label, sort_order, label, role, source, labels_domain, bins, can_paint, can_filter, alert_codes, alert_label, description) VALUES
('calibration', 'CO-CREG-038', 'electricity', 'Estado técnico', 1, 'Calibración y pruebas', 'category', 'computed:periodic', 'periodic.status', NULL, true, true, '{overdue,missing}', 'Calibración vencida o sin registro', 'El peor estado de calibración o prueba de rutina de los equipos instalados'),
('comms', 'CO-CREG-038', 'electricity', 'Estado técnico', 2, 'Comunicación (telemedida)', 'category', 'computed:comms', 'comms.status', NULL, true, true, '{silent}', 'Sin reportar', 'Si el medidor principal reportó lecturas dentro de la ventana de la organización (Configuración → HES)'),
('alarm', 'CO-CREG-038', 'electricity', 'Estado técnico', 3, 'Alarmas del medidor', 'category', 'computed:alarm', 'alarm.recent', NULL, true, true, '{yes}', 'Con alarma reciente', 'Eventos del medidor que no son informativos, dentro de la ventana de reporte'),
('point_status', 'CO-CREG-038', 'electricity', 'Estado técnico', 4, 'Estado de la frontera (ASIC)', 'category', 'point:status', 'metering_point.status', NULL, true, true, NULL, NULL, NULL),
('xm_pending', 'CO-CREG-038', 'electricity', 'Estado técnico', 5, 'Novedades para XM', 'category', 'computed:xm_pending', 'xm.pending_flag', NULL, true, true, '{yes}', 'Novedad pendiente de XM', NULL),
('commercial_status', 'CO-CREG-038', 'electricity', 'Estado comercial', 10, 'Estado comercial', 'category', 'point:commercial_status', 'commercial.status', NULL, true, true, '{disconnection,suspended_debt}', 'En corte o suspendida por cartera', 'Lo informa el sistema comercial (CIS) o la carga por archivo'),
('market', 'CO-CREG-038', 'electricity', 'Estado comercial', 11, 'Mercado', 'category', 'point:market', 'market', NULL, true, true, NULL, NULL, NULL),
('consumption_range', 'CO-CREG-038', 'electricity', 'Estado comercial', 12, 'Rango de consumo', 'category', 'computed:consumption_range', NULL, NULL, true, true, NULL, NULL, 'Los rangos son los umbrales de consumo de los tipos de punto del paquete'),
('point_class', 'CO-CREG-038', 'electricity', 'Estado comercial', 13, 'Tipo de punto', 'category', 'point:point_class', NULL, NULL, true, true, NULL, NULL, NULL),
('customer_class', 'CO-CREG-038', 'electricity', 'Cliente', 20, 'Tipo de cliente', 'category', 'point:customer_class', 'customer.class', NULL, true, true, NULL, NULL, 'Clase de servicio (Circular CREG 119, §2.17)'),
('region', 'CO-CREG-038', 'electricity', 'Cliente', 21, 'Departamento', 'category', 'point:region', NULL, NULL, true, true, NULL, NULL, NULL),
('city', 'CO-CREG-038', 'electricity', 'Cliente', 22, 'Ciudad o municipio', 'category', 'point:city', NULL, NULL, false, true, NULL, NULL, NULL),
('pqr_open', 'CO-SSPD', NULL, 'PQRS', 30, 'Con PQR abierta', 'category', 'computed:pqr_open', 'pqr.open', NULL, true, true, '{yes}', 'PQR abierta', 'Peticiones, quejas y reclamos que no se han cerrado'),
('pqr_group', 'CO-SSPD', NULL, 'PQRS', 31, 'Grupo de causal (PQR abiertas)', 'category', 'computed:pqr_group', 'pqr.cause_group', NULL, true, true, NULL, NULL, 'Facturación o prestación, según la Superservicios'),
('pqr_type', 'CO-SSPD', NULL, 'PQRS', 32, 'Tipo de trámite (PQR abiertas)', 'category', 'computed:pqr_type', 'pqr.request_type', NULL, true, true, NULL, NULL, NULL),
('pqr_cause', 'CO-SSPD', NULL, 'PQRS', 33, 'Causal (PQR abiertas)', 'category', 'computed:pqr_cause', NULL, NULL, false, true, NULL, NULL, 'Detalle de la causal de 3 dígitos de la Superservicios'),
('meter_brand', 'CO-CREG-038', 'electricity', 'Equipos', 40, 'Marca del medidor', 'category', 'equipment:main_active:brand', NULL, NULL, true, true, NULL, NULL, 'Medidor principal'),
('meter_model', 'CO-CREG-038', 'electricity', 'Equipos', 41, 'Modelo del medidor', 'category', 'equipment:main_active:model', NULL, NULL, false, true, NULL, NULL, NULL),
('meter_technology', 'CO-CREG-038', 'electricity', 'Equipos', 42, 'Tecnología del medidor', 'category', 'equipment_attr:main_active:c3_9', NULL, NULL, true, true, NULL, NULL, 'Circular CREG 119, §3.9'),
('meter_connection', 'CO-CREG-038', 'electricity', 'Equipos', 43, 'Conexión del medidor', 'category', 'equipment_attr:main_active:c3_10', NULL, NULL, true, true, NULL, NULL, 'Directa, semidirecta o indirecta (§3.10)'),
('meter_age', 'CO-CREG-038', 'electricity', 'Equipos', 44, 'Antigüedad del medidor', 'category', 'equipment_age:main_active', NULL,
 '[{"code": "0-4", "max": 5, "label": "Menos de 5 años"}, {"code": "5-9", "max": 10, "label": "5 a 9 años"}, {"code": "10-14", "max": 15, "label": "10 a 14 años"}, {"code": "15+", "max": null, "label": "15 años o más"}]',
 true, true, NULL, NULL, 'Desde su año de fabricación'),
('meter_owner', 'CO-CREG-038', 'electricity', 'Equipos', 45, 'Propiedad del medidor', 'category', 'equipment:main_active:ownership', 'equipment.ownership', NULL, true, true, NULL, NULL, NULL),
('modem_brand', 'CO-CREG-038', 'electricity', 'Equipos', 46, 'Marca del módem', 'category', 'equipment:modem_main:brand', NULL, NULL, true, true, NULL, NULL, NULL),
('modem_medium', 'CO-CREG-038', 'electricity', 'Equipos', 47, 'Medio de comunicación', 'category', 'equipment_attr:modem_main:c11_9', NULL, NULL, true, true, NULL, NULL, 'GPRS, 3G, 4G, fibra… (§11.9)'),
('size_consumption', 'CO-CREG-038', 'electricity', 'Tamaño', 60, 'Consumo mensual (MWh)', 'size', 'point:consumption_mwh_month', NULL, NULL, false, false, NULL, NULL, NULL),
('size_capacity', 'CO-CREG-038', 'electricity', 'Tamaño', 61, 'Capacidad instalada (kVA)', 'size', 'point:capacity_kva', NULL, NULL, false, false, NULL, NULL, NULL);
GRANT SELECT ON map_dimension TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON map_dimension FROM renfygrid_app;

CREATE TABLE map_view (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    name        text NOT NULL,
    config      jsonb NOT NULL,      -- {paint, size, filters: {dim: [codigos]}, layers: [dim]}
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX map_view_name_uq ON map_view (tenant_id, lower(btrim(name)));

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['customer_request', 'map_view'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (tenant_id = current_setting(''app.tenant_id'', true)::uuid) '
                       'WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true)::uuid)', t || '_tenant_isolation', t);
    END LOOP;
END $$;
REVOKE ALL ON customer_request, map_view FROM renfygrid_app;
GRANT SELECT, INSERT, UPDATE ON customer_request TO renfygrid_app;
GRANT SELECT, INSERT, DELETE ON map_view TO renfygrid_app;

-- La purga de pruebas end-to-end (0049) tambien limpia PQR y vistas.
CREATE OR REPLACE FUNCTION e2e_purge_metering_assets(p_tenant uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM tenant WHERE id = p_tenant AND name LIKE 'e2e-%') THEN
        RAISE EXCEPTION 'Solo se purgan organizaciones de prueba (e2e-...)';
    END IF;
    DELETE FROM map_view WHERE tenant_id = p_tenant;
    DELETE FROM customer_request WHERE tenant_id = p_tenant;
    DELETE FROM metering_point_section_version WHERE tenant_id = p_tenant;
    DELETE FROM metering_point_section WHERE tenant_id = p_tenant;
    DELETE FROM metering_event WHERE tenant_id = p_tenant;
    DELETE FROM equipment_installation WHERE tenant_id = p_tenant;
    DELETE FROM equipment WHERE tenant_id = p_tenant;
    DELETE FROM metering_point WHERE tenant_id = p_tenant;
END $$;

-- ── Permisos y modulo ─────────────────────────────────────────────────
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('requests.manage', 47, 'Activos', 'Registrar y responder PQR de los usuarios');
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('supervisor', 'requests.manage'), ('board', 'requests.manage');

UPDATE product_module SET sort_order = sort_order + 1 WHERE code IN ('energy-points', 'energy-equipment');
INSERT INTO product_module (code, path, group_code, sort_order, label, icon, description, kinds, sectors) VALUES
('energy-map', '/energy/map', 'energy', 2, 'Mapa de fronteras', 'map', 'Mapa temático: pinte y filtre las fronteras por estado técnico, comercial, cliente, PQRS y equipos', '{provider,group}', '{electricity}');

-- Las causales de PQR van en 0052 (las genera infra/db/tools/build_sspd_pqr_causes.py).
