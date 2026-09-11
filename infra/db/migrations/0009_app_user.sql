-- RenfyGrid -- 0009_app_user.sql
-- Sprint C1 (F47): usuarios reales con login -- hasta ahora el JWT (Sprint 0)
-- siempre se emitia a mano desde scripts de prueba, no habia ninguna tabla
-- de usuarios. Necesario para que el Portal Web tenga un login real.
--
-- UNIQUE por (tenant_id, email), no por email solo: el mismo email puede
-- existir en distintos tenants (ej. un consultor que opera dos pilotos) --
-- mismo criterio de aislamiento por tenant que el resto del esquema. El
-- login recibe `tenant_id` explicito junto con email/password (no hay
-- todavia un mecanismo de "un email -> que tenant" sin que el cliente lo
-- diga, como un subdominio por tenant).

CREATE TABLE app_user (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      uuid NOT NULL REFERENCES tenant(id),
    email          text NOT NULL,
    password_hash  text NOT NULL,   -- PBKDF2-HMAC-SHA256 salteado, ver renmeter_common/passwords.py -- nunca texto plano
    role           text NOT NULL,   -- mismo valor que ya usan role_permission/control_approval_level.min_required_role
    is_active      boolean NOT NULL DEFAULT true,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email)
);
ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_user FORCE ROW LEVEL SECURITY;
CREATE POLICY app_user_tenant_isolation ON app_user
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
