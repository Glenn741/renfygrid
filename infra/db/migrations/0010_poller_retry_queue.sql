-- RenfyGrid -- 0010_poller_retry_queue.sql
-- F08 (Sprint C11): cola persistente de reintentos ante caida de un
-- concentrador. Lo que ya existia (`poller.py::read_one_meter_with_retries`,
-- Sprint 2) son reintentos DENTRO del mismo ciclo -- si un medidor sigue
-- fallando despues de agotarlos, antes solo se registraba el error y se
-- esperaba al proximo ciclo normal (mismo `--interval-seconds` que todos
-- los demas medidores). Eso significa martillar un concentrador caido cada
-- pocos segundos igual que uno sano -- lo que falta de verdad es una
-- politica de reintento propia (backoff exponencial), independiente del
-- ciclo de polling normal.
--
-- Una fila por (tenant_id, meter_id) -- UNIQUE, no historico: mientras el
-- medidor sigue fallando se actualiza in place (failure_count sube,
-- next_retry_at se recalcula); cuando por fin responde, la fila se borra
-- (poller.py la limpia). El HISTORIAL de fallas ya existe en `meter_event`
-- (F09, auditoria de comunicacion) -- esta tabla es solo el estado actual
-- de la cola, no una bitacora aparte.

CREATE TABLE poller_retry_queue (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenant(id),
    meter_id       uuid NOT NULL REFERENCES meter(id),
    failure_count  integer NOT NULL DEFAULT 1,
    next_retry_at  timestamptz NOT NULL,
    last_error     text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, meter_id)
);
ALTER TABLE poller_retry_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE poller_retry_queue FORCE ROW LEVEL SECURITY;
CREATE POLICY poller_retry_queue_tenant_isolation ON poller_retry_queue
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE INDEX poller_retry_queue_due_idx ON poller_retry_queue (tenant_id, next_retry_at);
