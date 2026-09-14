-- RenfyGrid -- 0019_maintenance_cmms_core.sql
-- Mantenimiento pasa de "generar orden + webhook a BayForce" a tener
-- sustancia real de CMMS (2026-09-14, a pedido directo del usuario:
-- "es un dibujo y nada mas" -- ver docs/04-plan-sprints.md SS9 y
-- docs/05-ejecucion.md para el analisis completo, grounded en Cityworks
-- y las metricas estandar MTTR/MTBF/% cumplimiento PM).
--
-- Decision de arquitectura: RenfyGrid construye el dominio propio
-- (prioridad/SLA, codigos de falla, PM programado, ciclo de vida,
-- cierre, KPIs) -- BayForce se mantiene como notificacion de salida
-- OPCIONAL (el webhook de B7, sin cambios), nunca la columna vertebral.
-- No se reconstruye ningun motor de despacho/ruteo -- la asignacion es
-- una cuadrilla simple, no un algoritmo de optimizacion.

-- ── Catalogos, patron semilla+catalogo (nunca un umbral/lista fija en codigo) ──

CREATE TABLE maintenance_sla_policy (
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    priority      text NOT NULL,   -- 'low'|'medium'|'high'|'emergency'
    target_hours  numeric NOT NULL,
    PRIMARY KEY (tenant_id, priority)
);
ALTER TABLE maintenance_sla_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_sla_policy FORCE ROW LEVEL SECURITY;
CREATE POLICY maintenance_sla_policy_tenant_isolation ON maintenance_sla_policy
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE maintenance_failure_code (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenant(id),
    code       text NOT NULL,
    label      text NOT NULL,
    is_active  boolean NOT NULL DEFAULT true,
    UNIQUE (tenant_id, code)
);
ALTER TABLE maintenance_failure_code ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_failure_code FORCE ROW LEVEL SECURITY;
CREATE POLICY maintenance_failure_code_tenant_isolation ON maintenance_failure_code
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE maintenance_crew (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  uuid NOT NULL REFERENCES tenant(id),
    name       text NOT NULL,
    is_active  boolean NOT NULL DEFAULT true
);
ALTER TABLE maintenance_crew ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_crew FORCE ROW LEVEL SECURITY;
CREATE POLICY maintenance_crew_tenant_isolation ON maintenance_crew
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Mantenimiento preventivo programado -- por activo especifico (no por
-- "tipo de activo" generico: cada tanque/valvula real tiene su propio
-- intervalo real, nunca un promedio inventado). `next_due_at` es lo que
-- decide si ya toca generar la orden -- nunca un cron adivinando.
CREATE TABLE maintenance_pm_plan (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          uuid NOT NULL REFERENCES tenant(id),
    asset_id           uuid NOT NULL REFERENCES network_asset(id),
    order_type         text NOT NULL,   -- 'preventive'|'inspection'
    priority           text NOT NULL,   -- 'low'|'medium'|'high'|'emergency'
    interval_days      integer NOT NULL,
    next_due_at        timestamptz NOT NULL,
    last_generated_at  timestamptz,
    is_active          boolean NOT NULL DEFAULT true
);
ALTER TABLE maintenance_pm_plan ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_pm_plan FORCE ROW LEVEL SECURITY;
CREATE POLICY maintenance_pm_plan_tenant_isolation ON maintenance_pm_plan
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ── Columnas nuevas en maintenance_order ──────────────────────────────

-- `priority` sin default: quien genera la orden lo declara explicito,
-- igual que `type`/`source` ya lo hacen -- nunca "medium" fabricado en
-- silencio para ordenes viejas (backfill explicito abajo, auditable).
ALTER TABLE maintenance_order ADD COLUMN priority text;
ALTER TABLE maintenance_order ADD COLUMN sla_due_at timestamptz;
ALTER TABLE maintenance_order ADD COLUMN failure_code_id uuid REFERENCES maintenance_failure_code(id);
ALTER TABLE maintenance_order ADD COLUMN scheduled_at timestamptz;
ALTER TABLE maintenance_order ADD COLUMN assigned_crew_id uuid REFERENCES maintenance_crew(id);
ALTER TABLE maintenance_order ADD COLUMN labor_hours numeric;
ALTER TABLE maintenance_order ADD COLUMN materials_used text;
ALTER TABLE maintenance_order ADD COLUMN root_cause text;
ALTER TABLE maintenance_order ADD COLUMN closed_at timestamptz;

-- Ordenes ya existentes (de antes de esta migracion) quedan con
-- priority NULL -- la UI las muestra como "sin prioridad asignada", real
-- y visible, nunca fabricado. `source` gana un valor nuevo posible
-- ('pm_schedule') validado en el servicio, no en un CHECK de esquema
-- (mismo criterio que 'type'/'source' ya usan).
