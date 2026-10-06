-- RenfyGrid -- 0032_manual_meter_reading.sql
-- Track D, D1.4a (2026-10-06): lectura manual de micro y macromedidor por el
-- operador (juntas sin telemetria; Guia 3 la pide en la rutina diaria y la
-- Guia 4 la necesita para facturar por consumo).
--
-- La lectura entra a `raw_reading` con source_quality = 'manual' y sigue el
-- MISMO camino que una lectura de telemetria: el pase VEE la valida y de ahi
-- sale el consumo y el balance. Esta tabla guarda lo propio de la toma manual:
-- quien la hizo, el `client_id` del dispositivo (la app sin conexion puede
-- reenviarla sin duplicar), la lectura anterior con que se comparo y si el
-- operador confirmo que el registro bajo (medidor cambiado o reiniciado).
CREATE TABLE manual_meter_reading (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    meter_id        uuid NOT NULL REFERENCES meter(id),
    channel         text NOT NULL,
    value           numeric NOT NULL CHECK (value >= 0),
    read_at         timestamptz NOT NULL,
    read_by         text NOT NULL,
    previous_value  numeric,
    lower_confirmed boolean NOT NULL DEFAULT false,
    notes           text,
    client_id       uuid,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, client_id)
);
CREATE INDEX manual_meter_reading_meter_idx ON manual_meter_reading (tenant_id, meter_id, read_at DESC);
ALTER TABLE manual_meter_reading ENABLE ROW LEVEL SECURITY;
ALTER TABLE manual_meter_reading FORCE ROW LEVEL SECURITY;
CREATE POLICY manual_meter_reading_tenant_isolation ON manual_meter_reading FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON manual_meter_reading TO renfygrid_app;
