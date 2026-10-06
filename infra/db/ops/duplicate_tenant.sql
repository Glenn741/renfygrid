-- RenfyGrid -- infra/db/ops/duplicate_tenant.sql
-- Duplica una organizacion (tenant) con TODOS sus datos en una organizacion
-- nueva: misma funcionalidad, datos propios. Pedido del usuario 2026-10-06
-- ("duplica el tenant jaas001 con el nombre asada001... funcionalmente es otro
-- tenant, solo son nuevos datos").
--
-- Generico: recorre toda tabla con `tenant_id` (no una lista escrita a mano),
-- da un UUID nuevo a cada fila y reasigna cada referencia: columnas uuid y
-- tambien los UUID escritos dentro de textos y jsonb (p. ej. el origen de un
-- hallazgo, "<run_id>:<item>"). Asi la copia nunca apunta a filas de la
-- organizacion original. Tambien copia las tablas sin `tenant_id` que cuelgan
-- de otras (conectividad de activos, medidor-concentrador).
--
-- No copia: los usuarios (sus claves son de la original; se crean aparte), la
-- membresia en agrupaciones (es una relacion con otra organizacion) ni el
-- respaldo historico de lecturas.
--
-- Uso (superusuario, una transaccion):
--   psql -v ON_ERROR_STOP=1 -1 -v src=jaas001 -v dst=asada001 -f duplicate_tenant.sql

SELECT set_config('dup.src', :'src', true), set_config('dup.dst', :'dst', true);
SET LOCAL session_replication_role = replica;   -- sin disparadores ni FK durante la copia (todo es una transaccion)

CREATE TEMP TABLE dup_idmap (old uuid PRIMARY KEY, new uuid NOT NULL) ON COMMIT DROP;

CREATE FUNCTION pg_temp.dup_remap_text(t text) RETURNS text LANGUAGE plpgsql AS $$
DECLARE m text; n uuid;
BEGIN
    IF t IS NULL OR t !~ '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' THEN
        RETURN t;
    END IF;
    FOR m IN SELECT DISTINCT (regexp_matches(t, '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 'g'))[1] LOOP
        SELECT new INTO n FROM dup_idmap WHERE old = m::uuid;
        IF n IS NOT NULL THEN
            t := replace(t, m, n::text);
        END IF;
    END LOOP;
    RETURN t;
END $$;

DO $$
DECLARE
    src uuid; dst uuid; tbl record; col record; cols text; exprs text; n bigint;
    skip text[] := ARRAY['app_user', 'raw_reading_pre_partition_backup', 'group_membership'];
BEGIN
    SELECT id INTO src FROM tenant WHERE lower(name) = lower(current_setting('dup.src'));
    IF src IS NULL THEN RAISE EXCEPTION 'No existe la organizacion %', current_setting('dup.src'); END IF;
    IF EXISTS (SELECT 1 FROM tenant WHERE lower(name) = lower(current_setting('dup.dst'))) THEN
        RAISE EXCEPTION 'Ya existe una organizacion llamada %', current_setting('dup.dst');
    END IF;
    INSERT INTO tenant (name, plan, is_active, config, kind)
    SELECT current_setting('dup.dst'), plan, is_active, config, kind FROM tenant WHERE id = src
    RETURNING id INTO dst;
    INSERT INTO dup_idmap VALUES (src, dst);

    -- 1. UUID nuevo para cada fila con clave `id` de las tablas de la organizacion
    FOR tbl IN
        SELECT c.relname FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
        WHERE ns.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relispartition
          AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
          AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'id' AND a.atttypid = 'uuid'::regtype AND NOT a.attisdropped)
          AND c.relname <> ALL (skip)
    LOOP
        EXECUTE format('INSERT INTO dup_idmap SELECT id, gen_random_uuid() FROM %I WHERE tenant_id = $1', tbl.relname) USING src;
    END LOOP;
    -- tablas hijas sin tenant_id con su propio `id`
    FOR tbl IN SELECT * FROM (VALUES ('asset_connectivity', 'source_asset_id'), ('meter_gateway', 'meter_id')) v(relname, fkcol)
    LOOP
        IF EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = tbl.relname::regclass AND a.attname = 'id' AND a.atttypid = 'uuid'::regtype) THEN
            EXECUTE format('INSERT INTO dup_idmap SELECT id, gen_random_uuid() FROM %I WHERE %I IN (SELECT old FROM dup_idmap)',
                           tbl.relname, tbl.fkcol);
        END IF;
    END LOOP;

    -- 2. Copiar cada tabla reasignando uuid, textos y jsonb
    FOR tbl IN
        SELECT c.oid, c.relname,
               EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped) AS has_tenant
        FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
        WHERE ns.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relispartition
          AND c.relname <> ALL (skip)
          AND (EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
               OR c.relname IN ('asset_connectivity', 'meter_gateway'))
    LOOP
        cols := ''; exprs := '';
        FOR col IN
            SELECT a.attname, a.atttypid FROM pg_attribute a
            WHERE a.attrelid = tbl.oid AND a.attnum > 0 AND NOT a.attisdropped AND a.attgenerated = ''
            ORDER BY a.attnum
        LOOP
            cols := cols || CASE WHEN cols = '' THEN '' ELSE ', ' END || quote_ident(col.attname);
            exprs := exprs || CASE WHEN exprs = '' THEN '' ELSE ', ' END || CASE
                WHEN col.attname = 'tenant_id' THEN quote_literal(dst) || '::uuid'
                WHEN col.atttypid = 'uuid'::regtype THEN format('coalesce((SELECT new FROM dup_idmap WHERE old = %1$I), %1$I)', col.attname)
                WHEN col.atttypid IN ('text'::regtype, 'varchar'::regtype) THEN format('pg_temp.dup_remap_text(%I)', col.attname)
                WHEN col.atttypid = 'jsonb'::regtype THEN format('pg_temp.dup_remap_text(%I::text)::jsonb', col.attname)
                WHEN col.atttypid = 'text[]'::regtype THEN format(
                    'CASE WHEN %1$I IS NULL THEN NULL ELSE coalesce((SELECT array_agg(pg_temp.dup_remap_text(x) ORDER BY o) '
                    'FROM unnest(%1$I) WITH ORDINALITY u(x, o)), ''{}''::text[]) END', col.attname)
                ELSE quote_ident(col.attname) END;
        END LOOP;
        IF tbl.has_tenant THEN
            EXECUTE format('INSERT INTO %I (%s) SELECT %s FROM %I WHERE tenant_id = $1', tbl.relname, cols, exprs, tbl.relname) USING src;
        ELSIF tbl.relname = 'asset_connectivity' THEN
            EXECUTE format('INSERT INTO %I (%s) SELECT %s FROM %I WHERE source_asset_id IN (SELECT old FROM dup_idmap)',
                           tbl.relname, cols, exprs, tbl.relname);
        ELSE
            EXECUTE format('INSERT INTO %I (%s) SELECT %s FROM %I WHERE meter_id IN (SELECT old FROM dup_idmap)',
                           tbl.relname, cols, exprs, tbl.relname);
        END IF;
        GET DIAGNOSTICS n = ROW_COUNT;
        IF n > 0 THEN RAISE NOTICE '% filas: %', tbl.relname, n; END IF;
    END LOOP;
    RAISE NOTICE 'Organizacion % creada: %', current_setting('dup.dst'), dst;
END $$;

-- 3. Verificacion: mismas filas por tabla en la original y en la copia
DO $$
DECLARE tbl record; a bigint; b bigint; src uuid; dst uuid; bad int := 0;
BEGIN
    SELECT id INTO src FROM tenant WHERE lower(name) = lower(current_setting('dup.src'));
    SELECT id INTO dst FROM tenant WHERE lower(name) = lower(current_setting('dup.dst'));
    FOR tbl IN
        SELECT c.relname FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
        WHERE ns.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relispartition
          AND EXISTS (SELECT 1 FROM pg_attribute x WHERE x.attrelid = c.oid AND x.attname = 'tenant_id' AND NOT x.attisdropped)
          AND c.relname NOT IN ('app_user', 'raw_reading_pre_partition_backup')
    LOOP
        EXECUTE format('SELECT count(*) FROM %I WHERE tenant_id = $1', tbl.relname) INTO a USING src;
        EXECUTE format('SELECT count(*) FROM %I WHERE tenant_id = $1', tbl.relname) INTO b USING dst;
        IF a <> b THEN bad := bad + 1; RAISE WARNING '% original % copia %', tbl.relname, a, b; END IF;
    END LOOP;
    IF bad > 0 THEN RAISE EXCEPTION '% tablas no cuadran', bad; END IF;
    -- ninguna referencia de la copia apunta a la original
    IF EXISTS (SELECT 1 FROM finding f WHERE f.tenant_id = dst AND f.source_ref ~ ANY (SELECT old::text FROM dup_idmap WHERE old <> src)) THEN
        RAISE EXCEPTION 'Quedaron referencias a la organizacion original en finding.source_ref';
    END IF;
    RAISE NOTICE 'Verificacion OK';
END $$;
