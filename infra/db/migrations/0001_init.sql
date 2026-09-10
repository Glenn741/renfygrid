-- RenfyGrid -- 0001_init.sql
-- Initial schema (Sprint 0): tenant, meter catalog, versioned configuration
-- (vee_rule, meter_protocol, control_approval_level, role_permission) and the
-- core operational tables, with Row-Level Security enabled on every table
-- that hangs off a tenant -- see docs/02-arquitectura-general.md SS5 and
-- docs/03-diseno.md SS1.
--
-- Naming convention (2026-09-10, per explicit user request): every software
-- identifier -- tables, columns, indexes, roles, enum values -- is English,
-- snake_case. Comments/docs stay in Spanish (see docs/, which is prose, not
-- a software identifier).
--
-- VERIFIED 2026-09-10 against a real PostgreSQL 16 instance (portable, no
-- Docker on this machine -- see infra/db/README-local-dev.md) with
-- infra/db/verify_rls.py: tenant isolation confirmed end-to-end. See
-- docs/05-ejecucion.md changelog for the real bug that showed up (and was
-- fixed) on that first run.
--
-- RLS convention in this file: every table with tenant_id enables RLS and
-- defines ONE FOR ALL policy requiring tenant_id = app.tenant_id from the
-- session, for both reads (USING) and writes (WITH CHECK). app.tenant_id is
-- set by the application layer per transaction -- see
-- services/common/renmeter_common/db.py::tenant_scope.
--
-- CRITICAL -- confirmed by a real failure on the first verification run
-- (see docs/05-ejecucion.md changelog, 2026-09-10): the policies above are
-- NOT enough by themselves.
--   1. The application must NEVER connect with a superuser role -- Postgres
--      always lets superusers bypass RLS, regardless of any policy. See
--      0002_app_role.sql for the (non-superuser) application role.
--   2. Every table also has FORCE ROW LEVEL SECURITY (not just ENABLE) --
--      without FORCE, the table OWNER also bypasses RLS. FORCE does not
--      protect against a superuser role (nothing does, except not using
--      one) but it does protect against a future application role that
--      ends up being the owner by a deployment mistake.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ══════════════════════════════════════════════════════════════════════════
-- Tenant
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE tenant (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    plan        text NOT NULL DEFAULT 'pilot',
    is_active   boolean NOT NULL DEFAULT true,
    config      jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);
-- tenant does NOT carry RLS: it is the table that defines who the tenants
-- are, queried by an administrative service with its own role, not by the
-- per-tenant application flow.

-- ══════════════════════════════════════════════════════════════════════════
-- Meter catalog
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE meter (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    account_number  text NOT NULL,              -- customer/account identifier
    serial_number   text NOT NULL,
    brand           text NOT NULL,
    model           text,
    protocol        text NOT NULL,                -- 'DLMS_COSEM' | 'ANSI_C12_19' | ...
    location        jsonb,
    status          text NOT NULL DEFAULT 'active',  -- active|suspended|retired
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, account_number)
);
ALTER TABLE meter ENABLE ROW LEVEL SECURITY;
ALTER TABLE meter FORCE ROW LEVEL SECURITY;
CREATE POLICY meter_tenant_isolation ON meter
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE gateway (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            uuid NOT NULL REFERENCES tenant(id),
    name                 text NOT NULL,
    transport_protocol   text NOT NULL,        -- 'MQTT' | 'TCP' | ...
    created_at           timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE gateway ENABLE ROW LEVEL SECURITY;
ALTER TABLE gateway FORCE ROW LEVEL SECURITY;
CREATE POLICY gateway_tenant_isolation ON gateway
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE meter_gateway (
    meter_id    uuid NOT NULL REFERENCES meter(id),
    gateway_id  uuid NOT NULL REFERENCES gateway(id),
    PRIMARY KEY (meter_id, gateway_id)
);
-- No tenant_id of its own: inherits isolation from meter/gateway via join;
-- no direct RLS since it has no tenant_id column to filter on.

-- ══════════════════════════════════════════════════════════════════════════
-- Versioned configuration -- source of truth for the "zero hardcode" pattern
-- (docs/03-diseno.md SS1.1 and SS2). A row is never updated in place: a new
-- version is inserted and the previous one gets valid_to set.
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE meter_protocol (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    brand         text NOT NULL,
    model         text NOT NULL,
    protocol      text NOT NULL,
    obis_mapping  jsonb NOT NULL,
    security_mode text,
    version       integer NOT NULL DEFAULT 1,
    valid_from    timestamptz NOT NULL DEFAULT now(),
    valid_to      timestamptz
);
ALTER TABLE meter_protocol ENABLE ROW LEVEL SECURITY;
ALTER TABLE meter_protocol FORCE ROW LEVEL SECURITY;
CREATE POLICY meter_protocol_tenant_isolation ON meter_protocol
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE INDEX meter_protocol_active_idx ON meter_protocol (tenant_id, brand, model)
    WHERE valid_to IS NULL;

CREATE TABLE vee_rule (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    type        text NOT NULL,             -- 'range'|'deviation'|'missing_interval'|'spike'
    params      jsonb NOT NULL,
    priority    integer NOT NULL DEFAULT 100,
    is_active   boolean NOT NULL DEFAULT true,
    version     integer NOT NULL DEFAULT 1,
    valid_from  timestamptz NOT NULL DEFAULT now(),
    valid_to    timestamptz
);
ALTER TABLE vee_rule ENABLE ROW LEVEL SECURITY;
ALTER TABLE vee_rule FORCE ROW LEVEL SECURITY;
CREATE POLICY vee_rule_tenant_isolation ON vee_rule
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE INDEX vee_rule_active_idx ON vee_rule (tenant_id, type)
    WHERE is_active AND valid_to IS NULL;

CREATE TABLE consumption_anomaly_rule (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    condition   jsonb NOT NULL,
    action      text NOT NULL,              -- 'inspection_order'|'reread_order'
    is_active   boolean NOT NULL DEFAULT true,
    version     integer NOT NULL DEFAULT 1,
    valid_from  timestamptz NOT NULL DEFAULT now(),
    valid_to    timestamptz
);
ALTER TABLE consumption_anomaly_rule ENABLE ROW LEVEL SECURITY;
ALTER TABLE consumption_anomaly_rule FORCE ROW LEVEL SECURITY;
CREATE POLICY consumption_anomaly_rule_tenant_isolation ON consumption_anomaly_rule
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE control_approval_level (
    id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 uuid NOT NULL REFERENCES tenant(id),
    order_type                text NOT NULL,   -- 'suspension'|'reconnection'|'disconnection'
    requires_human_approval   boolean NOT NULL DEFAULT true,
    min_required_role         text NOT NULL DEFAULT 'operator',
    version                   integer NOT NULL DEFAULT 1,
    valid_from                timestamptz NOT NULL DEFAULT now(),
    valid_to                  timestamptz,
    UNIQUE (tenant_id, order_type, valid_from)
);
ALTER TABLE control_approval_level ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_approval_level FORCE ROW LEVEL SECURITY;
CREATE POLICY control_approval_level_tenant_isolation ON control_approval_level
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE role_permission (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    role        text NOT NULL,
    permission  text NOT NULL,
    UNIQUE (tenant_id, role, permission)
);
ALTER TABLE role_permission ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permission FORCE ROW LEVEL SECURITY;
CREATE POLICY role_permission_tenant_isolation ON role_permission
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ══════════════════════════════════════════════════════════════════════════
-- Readings -- raw_reading is a TimescaleDB hypertable (high volume)
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE raw_reading (
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    meter_id        uuid NOT NULL REFERENCES meter(id),
    "timestamp"     timestamptz NOT NULL,
    channel         text NOT NULL,              -- 'active_energy'|'reactive_energy'|...
    value           numeric NOT NULL,
    source_quality  text NOT NULL DEFAULT 'real',
    PRIMARY KEY (meter_id, channel, "timestamp")
);
SELECT create_hypertable('raw_reading', by_range('timestamp'));
ALTER TABLE raw_reading ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_reading FORCE ROW LEVEL SECURITY;
CREATE POLICY raw_reading_tenant_isolation ON raw_reading
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
-- RLS applies transparently on hypertables: TimescaleDB rewrites the query
-- against the chunks, but the policy is evaluated against the logical table
-- raw_reading -- no need to declare the policy per chunk.

CREATE TABLE validated_reading (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenant(id),
    meter_id       uuid NOT NULL REFERENCES meter(id),
    "timestamp"    timestamptz NOT NULL,
    value          numeric NOT NULL,
    source         text NOT NULL,                -- 'real'|'estimated'|'edited'
    vee_rule_id    uuid REFERENCES vee_rule(id),  -- which rule version was applied
    user_name      text,                          -- only if source = 'edited'
    justification  text,                          -- only if source = 'edited'
    created_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE validated_reading ENABLE ROW LEVEL SECURITY;
ALTER TABLE validated_reading FORCE ROW LEVEL SECURITY;
CREATE POLICY validated_reading_tenant_isolation ON validated_reading
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE meter_event (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    meter_id    uuid NOT NULL REFERENCES meter(id),
    type        text NOT NULL,
    "timestamp" timestamptz NOT NULL DEFAULT now(),
    severity    text NOT NULL DEFAULT 'info'
);
ALTER TABLE meter_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE meter_event FORCE ROW LEVEL SECURITY;
CREATE POLICY meter_event_tenant_isolation ON meter_event
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ══════════════════════════════════════════════════════════════════════════
-- Control (SCR) -- see docs/03-diseno.md SS6, state flow
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE control_order (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    meter_id        uuid NOT NULL REFERENCES meter(id),
    type            text NOT NULL,       -- 'suspension'|'reconnection'|'disconnection'
    status          text NOT NULL DEFAULT 'requested',
        -- requested -> pending_approval -> approved -> sent -> confirmed | failed
    requested_by    text NOT NULL,
    justification   text,
    approved_by     text,
    requested_at    timestamptz NOT NULL DEFAULT now(),
    approved_at     timestamptz,
    confirmed_at    timestamptz,
    CONSTRAINT control_order_status_valid CHECK (
        status IN ('requested', 'pending_approval', 'approved', 'sent', 'confirmed', 'failed')
    )
);
ALTER TABLE control_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_order FORCE ROW LEVEL SECURITY;
CREATE POLICY control_order_tenant_isolation ON control_order
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- Immutable audit trail of control orders: append-only, no UPDATE/DELETE
-- allowed at the application level yet (no trigger enforcing it yet --
-- pending Sprint 6-7, see docs/05-ejecucion.md F30).
CREATE TABLE control_order_audit (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        uuid NOT NULL REFERENCES tenant(id),
    order_id         uuid NOT NULL REFERENCES control_order(id),
    previous_status  text,
    new_status       text NOT NULL,
    actor            text NOT NULL,
    "timestamp"      timestamptz NOT NULL DEFAULT now(),
    detail           jsonb
);
ALTER TABLE control_order_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE control_order_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY control_order_audit_tenant_isolation ON control_order_audit
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ══════════════════════════════════════════════════════════════════════════
-- Consumption (Gestión de Consumos)
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE consumption (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    meter_id        uuid NOT NULL REFERENCES meter(id),
    period          daterange NOT NULL,
    value           numeric NOT NULL,
    anomaly_status  text NOT NULL DEFAULT 'ok',  -- 'ok'|'under_review'|'resolved'
    created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE consumption ENABLE ROW LEVEL SECURITY;
ALTER TABLE consumption FORCE ROW LEVEL SECURITY;
CREATE POLICY consumption_tenant_isolation ON consumption
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ══════════════════════════════════════════════════════════════════════════
-- Network Balance + Network Model (docs/03-diseno.md SS1.3)
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE network_zone (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    name            text NOT NULL,
    type            text NOT NULL,   -- 'dma' | 'circuit' | 'district' | 'pressure_zone'
    parent_zone_id  uuid REFERENCES network_zone(id),
    data_source     text NOT NULL DEFAULT 'renfygrid'   -- 'renfygrid' | 'external'
);
ALTER TABLE network_zone ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_zone FORCE ROW LEVEL SECURITY;
CREATE POLICY network_zone_tenant_isolation ON network_zone
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE network_balance (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               uuid NOT NULL REFERENCES tenant(id),
    zone_id                 uuid NOT NULL REFERENCES network_zone(id),
    period                  daterange NOT NULL,
    inflow                  numeric NOT NULL,
    authorized_consumption  numeric NOT NULL,
    losses                  numeric NOT NULL,
    method                  text NOT NULL,   -- 'top_down' | 'bottom_up'
    version                 integer NOT NULL DEFAULT 1,
    calculated_at           timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE network_balance ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_balance FORCE ROW LEVEL SECURITY;
CREATE POLICY network_balance_tenant_isolation ON network_balance
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE network_model (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    name          text NOT NULL,
    format        text NOT NULL,   -- 'epanet_inp'
    version       integer NOT NULL DEFAULT 1,
    valid_from    timestamptz NOT NULL DEFAULT now(),
    file_ref      text NOT NULL
);
ALTER TABLE network_model ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_model FORCE ROW LEVEL SECURITY;
CREATE POLICY network_model_tenant_isolation ON network_model
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE simulation_result (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid NOT NULL REFERENCES tenant(id),
    network_model_id  uuid NOT NULL REFERENCES network_model(id),
    scenario          text NOT NULL,
    results           jsonb NOT NULL,
    calculated_at     timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE simulation_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE simulation_result FORCE ROW LEVEL SECURITY;
CREATE POLICY simulation_result_tenant_isolation ON simulation_result
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ══════════════════════════════════════════════════════════════════════════
-- Digital Twin + Maintenance Management (docs/03-diseno.md SS1.4)
-- ══════════════════════════════════════════════════════════════════════════

CREATE TABLE network_asset (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   uuid NOT NULL REFERENCES tenant(id),
    zone_id     uuid REFERENCES network_zone(id),
    type        text NOT NULL,   -- 'pipe'|'valve'|'tank'|'pump'|'meter'|'sensor'
    attributes  jsonb NOT NULL DEFAULT '{}'::jsonb,   -- material, diameter, capacity, install_year...
    geometry    jsonb,                                 -- PostGIS geometry later; jsonb placeholder for now
    status      text NOT NULL DEFAULT 'operational',   -- 'operational'|'out_of_service'|'maintenance'
    version     integer NOT NULL DEFAULT 1,
    valid_from  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE network_asset ENABLE ROW LEVEL SECURITY;
ALTER TABLE network_asset FORCE ROW LEVEL SECURITY;
CREATE POLICY network_asset_tenant_isolation ON network_asset
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE TABLE asset_connectivity (
    source_asset_id  uuid NOT NULL REFERENCES network_asset(id),
    target_asset_id  uuid NOT NULL REFERENCES network_asset(id),
    connection_type  text NOT NULL,
    PRIMARY KEY (source_asset_id, target_asset_id)
);
-- No tenant_id of its own: inherits isolation from network_asset via join.

CREATE TABLE maintenance_order (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenant(id),
    asset_id            uuid NOT NULL REFERENCES network_asset(id),
    type                text NOT NULL,   -- 'preventive'|'corrective'|'inspection'
    source              text NOT NULL,   -- 'asset_condition'|'simulation_result'|'balance_anomaly'|'manual'
    status              text NOT NULL DEFAULT 'generated',
        -- generated -> sent_to_bayforce -> in_progress -> completed | cancelled
    bayforce_order_ref  text,
    created_at          timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE maintenance_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_order FORCE ROW LEVEL SECURITY;
CREATE POLICY maintenance_order_tenant_isolation ON maintenance_order
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
