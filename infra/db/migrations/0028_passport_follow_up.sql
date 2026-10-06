-- RenfyGrid -- 0028_passport_follow_up.sql
-- Track D, D0.6 (2026-10-05): pasaporte de productos (T-07) y seguimiento a
-- 7, 30 y 90 dias (T-09) de la Guia 7 de Municipios Azules.
--
-- T-07: "verificar que producto se construyo, que evidencia existe y que debe
-- validarse o trasladarse a la Guia 6". Columnas de la guia: Dia, Producto,
-- Guia/actividad, Evidencia, Completo, Validar, Pendiente, Pasa a G6. Se
-- actualiza al cierre de los dias 1-7 y se revisa el dia 8.
-- T-09 / seccion 11: compromisos acordados el dia 8 y revisados a 7, 30 y 90
-- dias (Momento, Producto o compromiso, Situacion encontrada, Evidencia,
-- Accion de ajuste, Responsable, Fecha).
--
-- Generico: los productos y los momentos del seguimiento son CATALOGO del
-- paquete de programa; otro programa trae los suyos. Lo de cada junta va en
-- tablas por tenant con RLS.

-- ── Catalogo: productos de cada etapa ─────────────────────────────────
-- Antes los productos eran un arreglo de textos en process_stage.products;
-- ahora tienen codigo propio para poder registrar su estado por junta.
CREATE TABLE process_product (
    pack_id     text NOT NULL,
    code        text NOT NULL,
    stage_code  text NOT NULL,
    sort_order  integer NOT NULL,
    title       text NOT NULL,
    PRIMARY KEY (pack_id, code),
    FOREIGN KEY (pack_id, stage_code) REFERENCES process_stage(pack_id, code)
);
INSERT INTO process_product (pack_id, code, stage_code, sort_order, title)
SELECT s.pack_id, s.code || '-P' || lpad(p.n::text, 2, '0'), s.code, p.n::integer, p.title
FROM process_stage s CROSS JOIN LATERAL jsonb_array_elements_text(s.products) WITH ORDINALITY AS p(title, n);
ALTER TABLE process_stage DROP COLUMN products;

-- ── Catalogo: momentos del seguimiento ────────────────────────────────
CREATE TABLE follow_up_milestone (
    pack_id      text NOT NULL,
    code         text NOT NULL,
    stage_code   text NOT NULL,     -- etapa de la ruta donde se gestiona
    sort_order   integer NOT NULL,
    offset_days  integer NOT NULL CHECK (offset_days > 0),
    label        text NOT NULL,
    review       text NOT NULL,     -- que revisar (texto de la guia)
    evidence     text NOT NULL,     -- evidencia esperada (texto de la guia)
    PRIMARY KEY (pack_id, code),
    FOREIGN KEY (pack_id, stage_code) REFERENCES process_stage(pack_id, code)
);
INSERT INTO follow_up_milestone (pack_id, code, stage_code, sort_order, offset_days, label, review, evidence) VALUES
('EC-MUNICIPIOS-AZULES', 'D7', 'INT', 1, 7, '7 días',
 'Ordenar formatos y evidencias; completar datos faltantes; confirmar responsables inmediatos.',
 'Carpeta de productos y T-07.'),
('EC-MUNICIPIOS-AZULES', 'D30', 'INT', 2, 30, '30 días',
 'Verificar uso de bitácoras, registros, acuerdos, prácticas, documentos y acciones de corto plazo.',
 'T-09, fotografías autorizadas, actas y registros.'),
('EC-MUNICIPIOS-AZULES', 'D90', 'INT', 3, 90, '90 días',
 'Revisar indicadores del Plan de Mejora, cambios de prácticas y apoyos pendientes.',
 'Tablero Guía 6, T-09 y reunión de seguimiento.');

GRANT SELECT ON process_product, follow_up_milestone TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON process_product, follow_up_milestone FROM renfygrid_app;

-- ── Por junta: pasaporte ──────────────────────────────────────────────
CREATE TABLE product_record (
    tenant_id            uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id              text NOT NULL,
    product_code         text NOT NULL,
    status               text NOT NULL CHECK (status IN ('complete', 'to_validate', 'pending')),
    evidence             text,
    to_improvement_plan  boolean NOT NULL DEFAULT false,   -- "Pasa a G6"
    updated_at           timestamptz NOT NULL DEFAULT now(),
    updated_by           text NOT NULL,
    PRIMARY KEY (tenant_id, pack_id, product_code),
    FOREIGN KEY (pack_id, product_code) REFERENCES process_product(pack_id, code)
);

-- ── Por junta: seguimiento ────────────────────────────────────────────
-- Un ciclo por cada proceso formativo: los momentos se cuentan desde la
-- fecha de cierre (dia 8). Una junta puede tener varios ciclos (otra cohorte).
CREATE TABLE follow_up_cycle (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    pack_id      text NOT NULL REFERENCES pack(id),
    anchor_date  date NOT NULL,
    title        text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   text NOT NULL
);
CREATE INDEX follow_up_cycle_tenant_idx ON follow_up_cycle (tenant_id, anchor_date DESC);

-- Compromiso acordado (dia 8) y lo que se encontro al revisarlo.
CREATE TABLE follow_up_item (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    cycle_id           uuid NOT NULL REFERENCES follow_up_cycle(id) ON DELETE CASCADE,
    pack_id            text NOT NULL,
    milestone_code     text NOT NULL,
    commitment         text NOT NULL,
    responsible        text,
    due_date           date,
    status             text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'not_done')),
    situation          text,
    evidence           text,
    adjustment_action  text,
    created_at         timestamptz NOT NULL DEFAULT now(),
    created_by         text NOT NULL,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (pack_id, milestone_code) REFERENCES follow_up_milestone(pack_id, code)
);
CREATE INDEX follow_up_item_cycle_idx ON follow_up_item (cycle_id);

-- Revision de un momento: cuando se hizo y que se concluyo.
CREATE TABLE follow_up_review (
    tenant_id       uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    cycle_id        uuid NOT NULL REFERENCES follow_up_cycle(id) ON DELETE CASCADE,
    pack_id         text NOT NULL,
    milestone_code  text NOT NULL,
    reviewed_on     date NOT NULL,
    reviewed_by     text NOT NULL,
    summary         text,
    PRIMARY KEY (cycle_id, milestone_code),
    FOREIGN KEY (pack_id, milestone_code) REFERENCES follow_up_milestone(pack_id, code)
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['product_record', 'follow_up_cycle', 'follow_up_item', 'follow_up_review'] LOOP
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
