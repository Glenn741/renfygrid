-- RenfyGrid -- 0015_network_zone_centroid.sql
-- Track B: modulo de georreferenciacion (docs/07-track-b-alcance-funcional.md
-- SS7) -- una zona (DMA) necesita un punto donde mostrarse en el mapa.
-- Opcional (NULL = sin georreferenciar todavia, la zona sigue funcionando
-- igual para Balance de Red -- nunca se inventa un centroide).

ALTER TABLE network_zone ADD COLUMN centroid_lat numeric;
ALTER TABLE network_zone ADD COLUMN centroid_lon numeric;
