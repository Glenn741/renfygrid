-- RenfyGrid -- 0004_validated_reading_channel.sql
-- Sprint 3 (F14/F15): gap encontrado al construir el motor VEE --
-- `validated_reading` no tenia columna `channel` (un medidor puede tener
-- varios canales, ej. active_energy/reactive_energy -- sin esto no se puede
-- saber a que lectura de raw_reading corresponde cada fila validada) ni
-- forma de marcar una lectura como invalida (`source` solo distingue
-- real/estimated/edited, no valido/invalido).

ALTER TABLE validated_reading
    ADD COLUMN channel text NOT NULL DEFAULT 'active_energy';
ALTER TABLE validated_reading
    ALTER COLUMN channel DROP DEFAULT;
-- El DEFAULT temporal es solo para no romper la migracion si la tabla ya
-- tuviera filas (no debería, Sprint 3 es el primero que escribe en ella) --
-- se quita enseguida para que toda fila futura tenga que declararlo.

ALTER TABLE validated_reading
    ADD COLUMN is_valid boolean NOT NULL DEFAULT true;
ALTER TABLE validated_reading
    ADD COLUMN validation_notes text;

ALTER TABLE validated_reading
    ADD CONSTRAINT validated_reading_unique_reading UNIQUE (meter_id, channel, "timestamp");
-- Evita reprocesar la misma lectura cruda dos veces -- ver
-- vee-engine/run_vee_pass.py, que usa esto como "ya procesada".
