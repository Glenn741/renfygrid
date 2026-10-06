-- RenfyGrid -- 0033_roles_permissions.sql
-- Track D, D1.4b (2026-10-06): roles con permisos reales. Hasta aqui todo
-- usuario era `supervisor` y ningun endpoint revisaba permisos (la tabla
-- `role_permission` de 0001 quedo vacia y sin uso). Una junta necesita que el
-- operador registre y la directiva revise, sin que ninguno cambie la
-- configuracion.
--
-- Catalogo global (solo lectura para la app):
--   app_permission          -- que se puede hacer, por area
--   app_role                -- supervisor (administracion), board (directiva),
--                              operator (operador), integration (cuenta de
--                              servicio de un CIS, no asignable desde el Portal)
--   role_default_permission -- permisos por defecto de cada rol
-- Por junta: tenant_role_override reemplaza los permisos por defecto de un
-- rol en esa junta (puede quedar vacio a proposito). El control lo hace el
-- Portal/API en cada escritura (portal-api/permissions.py); una escritura no
-- mapeada exige settings.manage: lo nuevo nunca queda abierto por omision.

CREATE TABLE app_permission (
    code        text PRIMARY KEY,
    sort_order  integer NOT NULL,
    area        text NOT NULL,
    label       text NOT NULL
);
INSERT INTO app_permission (code, sort_order, area, label) VALUES
('operations.record',    1, 'Operación diaria', 'Registrar mediciones, bitácora y lecturas manuales de medidores'),
('operations.manage',    2, 'Operación diaria', 'Administrar puntos de medición y productos químicos'),
('checklists.apply',     3, 'Ruta y revisiones', 'Aplicar listas de revisión y cuestionarios'),
('findings.report',      4, 'Hallazgos', 'Reportar hallazgos y puntos críticos'),
('findings.manage',      5, 'Hallazgos', 'Gestionar hallazgos: prioridad, estado, cierre, plan de mejora'),
('program.manage',       6, 'Ruta y revisiones', 'Pasaporte de productos y seguimiento 7-30-90'),
('maintenance.manage',   7, 'Mantenimiento', 'Crear, programar, asignar, ejecutar y cerrar órdenes'),
('maintenance.configure',8, 'Mantenimiento', 'Configurar SLA, códigos de falla, cuadrillas y planes preventivos'),
('maintenance.webhook',  9, 'Mantenimiento', 'Recibir avances de un sistema externo de órdenes'),
('network.manage',      10, 'Red y pérdidas', 'Editar sectores, componentes, conexiones, modelos y balances'),
('metering.operate',    11, 'Medición', 'Leer o consultar un medidor a demanda'),
('metering.manage',     12, 'Medición', 'Corregir lecturas, resolver consumos y proteger cuentas'),
('control.request',     13, 'Medición', 'Solicitar órdenes de control (corte, reconexión)'),
('control.approve',     14, 'Medición', 'Aprobar órdenes de control'),
('settings.manage',     15, 'Plataforma', 'Configuración de la organización, paquetes y reglas'),
('users.manage',        16, 'Plataforma', 'Usuarios y permisos de la organización');

CREATE TABLE app_role (
    code        text PRIMARY KEY,
    sort_order  integer NOT NULL,
    label       text NOT NULL,
    description text NOT NULL,
    assignable  boolean NOT NULL DEFAULT true
);
INSERT INTO app_role (code, sort_order, label, description, assignable) VALUES
('supervisor',  1, 'Administración', 'Acceso completo: configuración, usuarios y toda la operación.', true),
('board',       2, 'Directiva', 'Revisa y decide: hallazgos, ruta del programa, mantenimiento y puntos de medición. No cambia la configuración.', true),
('operator',    3, 'Operador', 'Opera el sistema cada día: mediciones, bitácora, lecturas de medidores, listas de revisión y órdenes de mantenimiento.', true),
('integration', 4, 'Integración (CIS)', 'Cuenta de servicio de un sistema externo; no la usa una persona.', false);

CREATE TABLE role_default_permission (
    role_code        text NOT NULL REFERENCES app_role(code),
    permission_code  text NOT NULL REFERENCES app_permission(code),
    PRIMARY KEY (role_code, permission_code)
);
INSERT INTO role_default_permission (role_code, permission_code)
SELECT 'supervisor', code FROM app_permission;
INSERT INTO role_default_permission (role_code, permission_code) VALUES
('board', 'operations.manage'), ('board', 'checklists.apply'), ('board', 'findings.report'), ('board', 'findings.manage'),
('board', 'program.manage'), ('board', 'maintenance.manage'), ('board', 'maintenance.configure'),
('operator', 'operations.record'), ('operator', 'checklists.apply'), ('operator', 'findings.report'),
('operator', 'maintenance.manage'), ('operator', 'metering.operate'),
-- control.*: en el modulo MDM el aprobador por defecto de las ordenes de
-- control es `operator` (control_engine, control_approval_level); se mantiene.
('operator', 'control.request'), ('operator', 'control.approve'),
('integration', 'metering.operate'), ('integration', 'control.request'), ('integration', 'maintenance.webhook');

GRANT SELECT ON app_permission, app_role, role_default_permission TO renfygrid_app;
REVOKE INSERT, UPDATE, DELETE ON app_permission, app_role, role_default_permission FROM renfygrid_app;

-- Roles de usuario validados contra el catalogo (NOT VALID: no revalida
-- filas viejas; toda fila nueva o cambiada debe usar un rol del catalogo).
ALTER TABLE app_user ADD CONSTRAINT app_user_role_fkey FOREIGN KEY (role) REFERENCES app_role(code) NOT VALID;

CREATE TABLE tenant_role_override (
    tenant_id    uuid NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    role_code    text NOT NULL REFERENCES app_role(code),
    permissions  text[] NOT NULL,
    updated_at   timestamptz NOT NULL DEFAULT now(),
    updated_by   text NOT NULL,
    PRIMARY KEY (tenant_id, role_code)
);
ALTER TABLE tenant_role_override ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_role_override FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_role_override_tenant_isolation ON tenant_role_override FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_role_override TO renfygrid_app;
