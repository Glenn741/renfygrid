-- RenfyGrid -- 0011_raw_reading_partitioning.sql
-- F10 (Sprint C11): `raw_reading` es la tabla de mayor volumen del sistema
-- (una fila por medidor/canal/ciclo de polling) -- el diseno original
-- (0001_init.sql) la declaraba como hypertable de TimescaleDB
-- (`create_hypertable`), pero esa extension nunca estuvo disponible ni en
-- desarrollo local (Postgres portable de Windows) ni en produccion
-- (essmarplapp02 solo tiene v2.10.3 para PG13, incompatible con el PG16
-- real del servidor -- causo una caida breve al intentarlo, revertida, ver
-- docs/05-ejecucion.md bitacora del buzon #106-107). Esa linea de
-- `create_hypertable` en 0001_init.sql es en realidad un bug latente: si
-- alguien corre las migraciones desde cero en una instancia sin Timescale
-- (que es la realidad de HOY en los dos entornos reales del proyecto),
-- falla ahi mismo.
--
-- Sustituto real, sin depender de una extension que no esta disponible:
-- **particionado declarativo nativo de Postgres por rango de tiempo**
-- (RANGE BY timestamp, una particion por mes). Da el mismo beneficio
-- practico que se buscaba con la hypertable -- poda de particiones en
-- consultas por rango de fecha, y poder DROPear una particion vieja entero
-- (retencion, F12) en vez de un DELETE fila por fila -- sin ninguna
-- extension de terceros.
--
-- Como `raw_reading` ya tiene filas reales (aunque pocas, en desarrollo y
-- en el piloto de produccion), esto reconstruye la tabla en vez de alterarla
-- in place -- Postgres no permite convertir una tabla normal en particionada
-- con ALTER TABLE. La tabla vieja queda renombrada (NO borrada) como red de
-- seguridad hasta confirmar que todo sigue funcionando igual.

-- 1. Tabla nueva, particionada por rango de "timestamp" -- misma forma,
--    mismas politicas RLS (que Postgres aplica de forma transparente para
--    TODAS las particiones cuando se consulta a traves de la tabla padre,
--    igual que el comentario que ya existia sobre el hypertable).
CREATE TABLE raw_reading_partitioned (
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    meter_id        uuid NOT NULL REFERENCES meter(id),
    "timestamp"     timestamptz NOT NULL,
    channel         text NOT NULL,
    value           numeric NOT NULL,
    source_quality  text NOT NULL DEFAULT 'real',
    PRIMARY KEY (meter_id, channel, "timestamp")
) PARTITION BY RANGE ("timestamp");

ALTER TABLE raw_reading_partitioned ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_reading_partitioned FORCE ROW LEVEL SECURITY;
CREATE POLICY raw_reading_partitioned_tenant_isolation ON raw_reading_partitioned
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- 2. Particion de respaldo (DEFAULT): cualquier fecha sin una particion
--    mensual explicita cae aca en vez de fallar el INSERT -- red de
--    seguridad si el mantenimiento de particiones (ver
--    services/common/partition_maintenance.py) se atrasa.
CREATE TABLE raw_reading_default PARTITION OF raw_reading_partitioned DEFAULT;

-- 3. Particiones explicitas: el mes de todas las filas que ya existen (si
--    "raw_reading" tenia datos) + el mes actual + el siguiente -- para que
--    el poller no dependa de que el mantenimiento ya corrio para poder
--    escribir hoy mismo. `partition_maintenance.py` crea las que falten mas
--    adelante (mismo patron de job corto/aparte que `refresh_obis_mapping_cache.py`).
DO $$
DECLARE
    earliest date;
    cursor_month date;
    last_month date;
BEGIN
    SELECT date_trunc('month', min("timestamp"))::date INTO earliest FROM raw_reading;
    cursor_month := COALESCE(earliest, date_trunc('month', now())::date);
    last_month := date_trunc('month', now() + interval '1 month')::date;
    WHILE cursor_month <= last_month LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF raw_reading_partitioned FOR VALUES FROM (%L) TO (%L)',
            'raw_reading_y' || to_char(cursor_month, 'YYYY') || '_m' || to_char(cursor_month, 'MM'),
            cursor_month,
            (cursor_month + interval '1 month')::date
        );
        cursor_month := (cursor_month + interval '1 month')::date;
    END LOOP;
END $$;

-- 4. Copiar los datos reales (si hay) a la tabla nueva.
INSERT INTO raw_reading_partitioned SELECT * FROM raw_reading;

-- 5. Intercambiar nombres -- la tabla vieja queda como respaldo, NO se
--    borra en esta migracion (borrarla es un paso aparte, una vez
--    confirmado en produccion que todo sigue funcionando igual).
ALTER TABLE raw_reading RENAME TO raw_reading_pre_partition_backup;
ALTER TABLE raw_reading_partitioned RENAME TO raw_reading;
ALTER TABLE raw_reading_default RENAME TO raw_reading_default_partition;
