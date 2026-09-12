-- RenfyGrid -- 0016_network_model_zone_link.sql
-- Track B, Sprint B4: vinculo Modelo<->Balance
-- (docs/07-track-b-alcance-funcional.md SS5) -- un modelo EPANET puede
-- (opcionalmente) representar una zona de Balance de Red real, para que
-- `network_balance.real_losses` se use como insumo REAL de calibracion
-- de fugas al simular (nunca datos de ejemplo hardcodeados).

ALTER TABLE network_model ADD COLUMN zone_id uuid REFERENCES network_zone(id);  -- NULL = modelo sin vincular a una zona
