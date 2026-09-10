-- RenfyGrid -- 0005_validated_reading_edit.sql
-- Sprint 4 (F18): registro de auditoria de ediciones manuales -- append-only
-- de verdad, no solo por convencion: se le quita UPDATE/DELETE al rol de
-- aplicacion sobre esta tabla especifica, asi que ni siquiera un bug en el
-- servicio puede reescribir el historial de ediciones (ver
-- docs/03-diseno.md SS5: "registro no editable (append-only)").
--
-- `validated_reading` en si SIGUE siendo mutable (se actualiza `value` +
-- `source='edited'` in place) -- lo que nunca se puede tocar es el rastro de
-- quien cambio que, por que, y cual era el valor anterior.

CREATE TABLE validated_reading_edit (
    id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id              uuid NOT NULL REFERENCES tenant(id),
    validated_reading_id   uuid NOT NULL REFERENCES validated_reading(id),
    previous_value         numeric NOT NULL,
    new_value              numeric NOT NULL,
    user_name              text NOT NULL,
    justification          text NOT NULL,
    edited_at              timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE validated_reading_edit ENABLE ROW LEVEL SECURITY;
ALTER TABLE validated_reading_edit FORCE ROW LEVEL SECURITY;
CREATE POLICY validated_reading_edit_tenant_isolation ON validated_reading_edit
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

REVOKE UPDATE, DELETE ON validated_reading_edit FROM renfygrid_app;
-- renfygrid_app conserva SELECT/INSERT (necesita insertar el registro de
-- auditoria al editar) pero pierde UPDATE/DELETE sobre esta tabla puntual --
-- el resto de la aplicacion sigue con los permisos amplios de 0002_app_role.sql.
