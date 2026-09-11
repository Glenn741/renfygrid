-- RenfyGrid -- 0008_meter_event_detail.sql
-- Sprint 9 (F09): auditoria de comunicacion con dispositivos -- se reusa
-- `meter_event` (ya usada para F05 eventos/alarmas y F23 ordenes de
-- relectura/inspeccion) en vez de crear otra tabla, pero le faltaba una
-- columna libre para guardar contexto (duracion, operacion, error) --
-- mismo patron que `control_order_audit.detail`.

ALTER TABLE meter_event
    ADD COLUMN detail jsonb;
-- Ejemplo para un intento de comunicacion (F09):
-- {"operation": "poller_read", "duration_ms": 842, "error": null}
