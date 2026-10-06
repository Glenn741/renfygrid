-- RenfyGrid -- 0029_tenant_timezone.sql
-- Zona horaria como PARAMETRO POR ORGANIZACION (2026-10-05), editable en
-- Configuracion -> Zona horaria. La necesita el seguimiento 7-30-90 (0028):
-- "hoy" para una junta en Ecuador no es la fecha UTC del servidor (a las 19:00
-- de Guayaquil ya es el dia siguiente en UTC y un momento se veia vencido un
-- dia antes).
--
-- Nombre IANA (America/Guayaquil). Se fija solo donde se sabe:
--   col001 (demo MDM Bogota/Cali)                  -> America/Bogota
--   jaas001 (Gualaceo) y la junta de ejemplo G3    -> America/Guayaquil
-- Un tenant sin zona horaria recibe un aviso claro (409) en lo que la
-- necesita, nunca una zona adivinada.
UPDATE tenant SET config = config || '{"timezone": "America/Bogota"}'::jsonb
WHERE name = 'col001' AND NOT (config ? 'timezone');
UPDATE tenant SET config = config || '{"timezone": "America/Guayaquil"}'::jsonb
WHERE (name = 'jaas001' OR name LIKE 'Junta de Agua de ejemplo%') AND NOT (config ? 'timezone');
