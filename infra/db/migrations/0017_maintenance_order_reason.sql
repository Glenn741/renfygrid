-- RenfyGrid -- 0017_maintenance_order_reason.sql
-- Track B, Sprint B7 (Mantenimiento + integracion BayForce,
-- docs/07-track-b-alcance-funcional.md SS5) -- el operador necesita ver
-- POR QUE se genero una orden (que anomalia real la disparo), no solo su
-- `type`/`source` en codigo. Opcional (NULL en ordenes manuales sin
-- justificacion escrita).

ALTER TABLE maintenance_order ADD COLUMN reason text;
