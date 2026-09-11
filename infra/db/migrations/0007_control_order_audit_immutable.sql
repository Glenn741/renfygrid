-- RenfyGrid -- 0007_control_order_audit_immutable.sql
-- Sprint 6 (avanza F30 parcialmente): `control_order_audit` ya existia
-- desde 0001_init.sql con un comentario explicito de que la inmutabilidad
-- quedaba pendiente ("no trigger enforcing it yet -- pending Sprint 6-7").
-- Mismo patron que `validated_reading_edit` (migracion 0005, Sprint 4):
-- inmutabilidad forzada por Postgres, no solo por convencion de codigo.

REVOKE UPDATE, DELETE ON control_order_audit FROM renfygrid_app;
-- renfygrid_app conserva SELECT/INSERT -- necesita insertar cada transicion,
-- nunca modificar ni borrar una ya escrita.
