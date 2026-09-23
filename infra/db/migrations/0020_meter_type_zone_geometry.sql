-- RenfyGrid -- 0020_meter_type_zone_geometry.sql
-- A pedido del usuario (2026-09-15): un medidor puede ser MICRO (de un
-- inmueble/cliente) o MACRO (medidor de bloque en la entrada de un sector
-- hidraulico/DMA, tipicamente junto a una valvula reguladora de presion --
-- ver docs/05-ejecucion.md para las referencias reales de mercado: KROHNE
-- "Equipping DMAs with electromagnetic water meters", McCrometer "Using
-- Flow Meters To Reduce Non-Revenue Water" -- el macro-medidor mide el
-- inflow TOTAL de un sector, los micro-medidores el consumo autorizado
-- individual; la diferencia es el NRW real de ese sector).
--
-- `meter_type` DEFAULT 'micro' (a nivel de columna, no del codigo): la
-- inmensa mayoria de los medidores de cualquier utility son de cliente
-- individual -- un macro-medidor es siempre la minoria (uno por sector),
-- se declara EXPLICITO al crearlo, nunca al reves.

ALTER TABLE meter ADD COLUMN meter_type text NOT NULL DEFAULT 'micro';
ALTER TABLE meter ADD COLUMN zone_id uuid REFERENCES network_zone(id);
-- Vincula el medidor a su sector hidraulico (DMA) real -- para un macro-
-- medidor, el sector que mide; para un micro-medidor, el sector donde
-- esta el inmueble (opcional -- no todo micro-medidor necesita estar
-- clasificado por sector para operar).

ALTER TABLE meter ADD COLUMN geometry jsonb;
-- GeoJSON Point real (mismo formato que network_asset.geometry, Sprint
-- B5) -- para el mapa de medidores. Nullable: un medidor sin
-- georreferenciar sigue funcionando en el resto del HES, solo no
-- aparece en el mapa.

CREATE INDEX meter_zone_idx ON meter (tenant_id, zone_id) WHERE zone_id IS NOT NULL;
CREATE INDEX meter_type_idx ON meter (tenant_id, meter_type);
