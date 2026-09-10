-- RenfyGrid -- 0006_meter_event_consumption_link.sql
-- Sprint 5 (F23): las ordenes de relectura/inspeccion se representan como
-- filas de `meter_event` (type = 'reread_order'|'inspection_order', ver
-- consumption_anomaly_rule.action) -- se reusa la tabla existente en vez de
-- crear una nueva, pero le faltaba forma de saber DE QUE fila de
-- `consumption` salio la orden (trazabilidad, mismo principio que
-- vee_rule_id en validated_reading).

ALTER TABLE meter_event
    ADD COLUMN consumption_id uuid REFERENCES consumption(id);
-- Nullable a proposito: no todo meter_event nace de una anomalia de consumo
-- (ver F05, eventos/alarmas del medidor en si, que no tienen relacion con
-- Gestion de Consumos).
