-- RenfyGrid -- 0025_default_packs.sql
-- Paquetes BASE de la plataforma (2026-10-05). Hallazgo del usuario al
-- cambiar de tenant: "noto un ambiente funcional diferente al cambiar del
-- tenant jaas001 al col001... la unica diferencia entre ellos son los datos".
-- Causa: el modelo ARCA (listas, reglas de calidad, ruta del programa) solo
-- existia en los tenants que habian adoptado los paquetes a mano; col001
-- nunca los adopto y veia la ruta vacia.
--
-- Ahora el catalogo marca que paquetes son base (`is_default`) y TODO tenant
-- los tiene: los existentes por esta migracion y los nuevos por un trigger
-- en `tenant` (cualquier camino de alta: Portal, onboarding, scripts). Un
-- tenant puede desactivar un paquete (p. ej. para usar el normativo de otro
-- pais) sin tocar codigo.

-- Al borrar un tenant, sus filas de tenant_pack se van con el (ahora todo
-- tenant tiene paquetes desde el alta; sin esto, borrar un tenant de prueba
-- fallaria por la FK).
ALTER TABLE tenant_pack DROP CONSTRAINT tenant_pack_tenant_id_fkey;
ALTER TABLE tenant_pack ADD CONSTRAINT tenant_pack_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON DELETE CASCADE;

ALTER TABLE pack ADD COLUMN is_default boolean NOT NULL DEFAULT false;
UPDATE pack SET is_default = true WHERE id IN ('EC-ARCA', 'EC-MUNICIPIOS-AZULES');

-- `tenant_pack` tiene FORCE ROW LEVEL SECURITY y el alta de un tenant no
-- corre bajo tenant_scope: la funcion es SECURITY DEFINER del dueno de la
-- migracion para poder insertar las filas del tenant recien creado.
CREATE FUNCTION adopt_default_packs() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO tenant_pack (tenant_id, pack_id)
    SELECT NEW.id, p.id FROM pack p WHERE p.is_default
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION adopt_default_packs() FROM PUBLIC;

CREATE TRIGGER tenant_adopt_default_packs
    AFTER INSERT ON tenant
    FOR EACH ROW EXECUTE FUNCTION adopt_default_packs();

INSERT INTO tenant_pack (tenant_id, pack_id)
SELECT t.id, p.id FROM tenant t CROSS JOIN pack p WHERE p.is_default
ON CONFLICT DO NOTHING;
