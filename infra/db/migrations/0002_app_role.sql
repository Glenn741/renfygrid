-- RenfyGrid -- 0002_app_role.sql
-- Rol de aplicacion, sin privilegios de superusuario -- ver la nota CRITICO en
-- 0001_init.sql y docs/05-ejecucion.md (bitacora 2026-09-10): conectar la
-- aplicacion con un rol superusuario hace que Postgres se salte RLS por completo,
-- sin importar las politicas. Este rol es el que deben usar TODOS los servicios
-- de RenfyGrid para conectarse a la base de datos -- nunca el rol de migraciones.
--
-- VERIFICADO 2026-09-10 (ver infra/db/verify_rls.py): con este rol + FORCE ROW
-- LEVEL SECURITY (0001_init.sql), el aislamiento entre tenants se confirma
-- correctamente.
--
-- La contraseña de este ejemplo es SOLO para desarrollo local (ver
-- infra/db/README-local-dev.md). En un entorno real, la contraseña se genera e
-- inyecta vía el mecanismo de secretos del entorno (variable de entorno /
-- secreto de k8s), nunca se deja como literal en un archivo versionado.

CREATE ROLE renfygrid_app LOGIN PASSWORD 'CAMBIAR_EN_CADA_ENTORNO' NOSUPERUSER NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO renfygrid_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO renfygrid_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO renfygrid_app;

-- Para que las tablas creadas en migraciones FUTURAS tambien queden accesibles
-- a este rol sin tener que volver a correr los GRANT de arriba a mano:
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO renfygrid_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO renfygrid_app;
