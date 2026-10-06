-- RenfyGrid -- 0022_tenant_session_ttl.sql
-- Duracion de la sesion del Portal como PARAMETRO POR ORGANIZACION, editable
-- en Configuracion -> Sesion (2026-10-05, a pedido del usuario: "eso debe
-- estar como un parametro configurable en el panel... No deben haber
-- parametros en archivos ni mucho menos en HARDCODE").
--
-- Antes: 3600 fijo en renmeter_common/auth.create_token, y despues una
-- variable de entorno en un drop-in de systemd. Ahora vive en
-- tenant.config.session_ttl_seconds (mismo lugar que el umbral de "medidor
-- caido", ver portal-api/tenant_settings.py).
--
-- 43200 s (12 h) es el valor que ya regia en produccion; se deja a cada
-- tenant existente y como valor inicial de los tenants nuevos (en el
-- esquema, no en el codigo). Cada organizacion lo cambia desde el Portal.

UPDATE tenant
SET config = config || jsonb_build_object('session_ttl_seconds', 43200)
WHERE NOT (config ? 'session_ttl_seconds');

ALTER TABLE tenant ALTER COLUMN config SET DEFAULT '{"session_ttl_seconds": 43200}'::jsonb;
