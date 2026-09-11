-- RenfyGrid -- 0013_network_balance.sql
-- Track B, Sprint B1 (E8): Balance de Red -- ALTER, no CREATE. `network_zone`
-- y `network_balance` YA EXISTIAN desde `0001_init.sql` (Sprint 0 escribio
-- el esquema completo de Track B de una vez, junto con Track A -- el
-- codigo/servicio de Track B nunca se construyo encima, a proposito, hasta
-- ahora). El esquema original era la version APLANADA de la Fase 2/3
-- (03-diseno.md SS1.3: `inflow`/`authorized_consumption`/`losses`) --
-- insuficiente para calcular ILI (Infrastructure Leakage Index), el KPI
-- principal que usa el mercado de referencia (Bentley WaterGEMS, Innovyze
-- InfoWater) y el que exige en la practica la CRA en Colombia (IANC,
-- Resolucion 315/2005) via su equivalente regulatorio. Ver
-- docs/07-track-b-alcance-funcional.md SS1/SS4 para la investigacion
-- completa. Ambas tablas tienen 0 filas (nunca se uso el esquema viejo) --
-- ALTER seguro, sin migracion de datos.

-- network_zone: insumos reales para UARL/ILI. Nullable a proposito: sin
-- estos 3 (Lm/Nc/P), se puede seguir calculando NRW en volumen, pero ILI
-- queda en NULL (nunca se inventa un ILI sin insumos).
ALTER TABLE network_zone ADD COLUMN network_length_km numeric;              -- Lm: longitud de red de distribucion (km)
ALTER TABLE network_zone ADD COLUMN num_connections integer;                -- Nc: conexiones/acometidas activas
ALTER TABLE network_zone ADD COLUMN avg_pressure_mca numeric;               -- P: presion promedio de operacion (m.c.a.)
ALTER TABLE network_zone ADD COLUMN avg_service_connection_length_km numeric; -- Lp: opcional, se asume 0 si no se conoce

-- network_balance: matriz de Balance Hidrico IWA completa en vez del
-- agregado plano -- separa Perdidas Aparentes de Reales, y Consumo
-- Autorizado en sus 3 componentes reales (facturado medido/facturado no
-- medido/no facturado autorizado).
ALTER TABLE network_balance DROP COLUMN inflow;
ALTER TABLE network_balance DROP COLUMN authorized_consumption;
ALTER TABLE network_balance DROP COLUMN losses;

ALTER TABLE network_balance ADD COLUMN system_input_volume numeric NOT NULL DEFAULT 0;
ALTER TABLE network_balance ALTER COLUMN system_input_volume DROP DEFAULT;
ALTER TABLE network_balance ADD COLUMN billed_metered_consumption numeric NOT NULL DEFAULT 0;
ALTER TABLE network_balance ADD COLUMN billed_unbilled_consumption numeric NOT NULL DEFAULT 0;
ALTER TABLE network_balance ADD COLUMN unbilled_authorized_consumption numeric NOT NULL DEFAULT 0;
ALTER TABLE network_balance ADD COLUMN apparent_losses numeric NOT NULL DEFAULT 0;
ALTER TABLE network_balance ADD COLUMN real_losses numeric NOT NULL DEFAULT 0;
-- KPIs derivados, calculados y guardados al insertar (nunca recalculados
-- fila por fila en cada lectura del panel) -- `ili` NULL si la zona no
-- tiene los 3 insumos de UARL (fail-safe, nunca 0 ni inventado).
ALTER TABLE network_balance ADD COLUMN nrw numeric;
ALTER TABLE network_balance ADD COLUMN ili numeric;
