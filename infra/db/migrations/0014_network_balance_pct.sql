-- RenfyGrid -- 0014_network_balance_pct.sql
-- Track B, Sprint B1-2 (sobre B1): "que le falta a B1" -- el usuario penso
-- que faltaba algo real y tenia razon. NRW en volumen bruto no dice nada
-- sin el tamano del sistema -- se reporta y se compara SIEMPRE como %
-- (asi lo exige la CRA en Colombia: IANC <= 30%, Resolucion 315/2005, ver
-- docs/07-track-b-alcance-funcional.md SS2). El tope es CONFIGURABLE por
-- zona (cero hardcode -- otro pais/regulador tiene otro numero), no un
-- 30% fijo en codigo.

ALTER TABLE network_zone ADD COLUMN nrw_threshold_pct numeric;  -- NULL = sin tope configurado para esta zona

ALTER TABLE network_balance ADD COLUMN nrw_pct numeric;              -- NRW como % del System Input Volume
ALTER TABLE network_balance ADD COLUMN balance_check_pct numeric;    -- cuanto se aleja la suma de componentes del SIV declarado
ALTER TABLE network_balance ADD COLUMN exceeds_threshold boolean;    -- NULL si la zona no tiene nrw_threshold_pct configurado
