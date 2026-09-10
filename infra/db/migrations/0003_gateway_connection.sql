-- RenfyGrid -- 0003_gateway_connection.sql
-- Sprint 1 (F01/F03): gap encontrado al construir el poller programado --
-- ninguna tabla tenia todavia donde vivir la informacion de conexion de red
-- de un medidor/concentrador (host/puerto TCP, direccion DLMS del cliente y
-- del servidor). Sin esto, F03 (lectura programada) no tiene de donde leer
-- "a que meter conectarse y como" sin hardcodearlo -- ver docs/05-ejecucion.md.
--
-- Va en `gateway` (no en `meter`) porque el host/puerto es del concentrador
-- de red, no del medidor individual -- varios medidores pueden compartir un
-- mismo gateway. `server_address` si es por medidor (direccion DLMS logica
-- del medidor dentro de ese gateway), por eso va en `meter`.

ALTER TABLE gateway
    ADD COLUMN connection jsonb NOT NULL DEFAULT '{}'::jsonb;
-- Ejemplo de contenido para transport_protocol = 'TCP':
-- {"host": "10.0.0.5", "port": 4059, "client_address": 16}

ALTER TABLE meter
    ADD COLUMN server_address integer;
-- Direccion DLMS del servidor (medidor) dentro del gateway asignado -- NULL
-- hasta que el medidor este efectivamente enlazado a un gateway y listo para
-- polling (ver meter_registry.py::link_meter_to_gateway).
