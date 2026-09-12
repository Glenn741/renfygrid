# Track B — Alcance funcional profundo (Balance de Red, Modelado, Gemelo Digital, Mantenimiento)

**Fecha:** 2026-09-11 · Complementa `01-planteamiento.md` §4, `02-arquitectura-general.md` §3-4,
`03-diseno.md` §1.3-1.4/§7-8 y `04-plan-sprints.md` §8 (donde nació Track B, en fase de
diseño, sin implementar). El usuario pidió activarlo — *"vamos con el Track B. Haz una
investigación profunda del mercado... y luego sí implementas"* — con la condición explícita de
que "lo demás esté estable" (confirmado: Track A/C completos y verificados, ver `05-ejecucion.md`).

Investigado con búsquedas reales (fuentes al final de cada sección), mismo criterio que
`00-benchmark-industria.md` y `06-benchmark-e2e-y-brechas.md`.

---

## 1. El estándar real: la matriz de Balance Hídrico IWA

El diseño original (`03-diseno.md` §1.3) ya apuntaba a "metodología IWA Top-Down/Bottom-Up",
pero **sin la matriz completa** — y la matriz completa es literalmente el producto: es lo que
todo software de pérdidas de agua del mercado implementa como su pantalla principal.

La International Water Association estandarizó esta estructura desde 2000 (adoptada también
por AWWA):

| Componente | Definición |
|---|---|
| **System Input Volume (SIV)** | Volumen anual que entra al sistema (producción/tratamiento/importado) |
| **Authorized Consumption** | = Billed Authorized Consumption (medido + no medido) + Unbilled Authorized Consumption (medido + no medido — ej. hidrantes contra incendio, lavado de redes) |
| **Water Losses** | = SIV − Authorized Consumption = **Apparent Losses** + **Real Losses** |
| **Apparent Losses** | Consumo no autorizado (fraude/conexiones ilegales) + imprecisión de medición (medidores subregistrando) + errores de manejo de datos/facturación |
| **Real Losses** | Fugas físicas reales: en tubería de transmisión/distribución, en tanques de almacenamiento, en la acometida hasta el medidor del cliente |
| **Non-Revenue Water (NRW)** | = SIV − **Billed** Authorized Consumption (no toda el agua no facturada es "pérdida" — el agua autorizada no facturada tampoco genera ingreso) |
| **Infrastructure Leakage Index (ILI)** | = CARL / UARL — Current Annual Real Losses sobre Unavoidable Annual Real Losses (el mínimo técnicamente alcanzable, función de longitud de red, número de conexiones y presión promedio) — el KPI que de verdad compara desempeño entre sistemas de tamaños distintos |

**Hallazgo real que cambia el alcance:** el esquema de `03-diseno.md` §1.3
(`network_balance: inflow, authorized_consumption, losses`) es **una versión aplanada** de esta
matriz — agrupa Apparent+Real en un solo `losses`, y no separa billed/unbilled dentro de
`authorized_consumption`. Con esa granularidad se puede calcular NRW en volumen bruto, pero
**no se puede calcular ILI** (el KPI que todo el software de referencia expone como principal) —
para eso hace falta Real Losses aislado, más longitud de red/conexiones/presión de la zona. Ver
§4 para el ajuste de esquema propuesto.

Fuentes: [IWA Water Balance — LEAKSSuite](https://www.leakssuitelibrary.com/iwa-water-balance/),
[Infrastructure Leakage Index (ILI) as Water Losses Indicator](https://ced.petra.ac.id/index.php/civ/article/download/17230/17771/20016).

## 2. Marco regulatorio real — Colombia (mismo criterio que CREG para Control/SCR)

Igual que el hallazgo de la Resolución CREG 108/1997 para Control (Sprint C11-5), Balance de
Red toca una métrica **regulada de verdad** en Colombia, no solo una buena práctica:

- La **CRA** (Comisión de Regulación de Agua Potable y Saneamiento Básico) adoptó el **IANC**
  (Índice de Agua No Contabilizada) como indicador oficial de pérdidas desde las Resoluciones
  CRA 12 y 17 de 1995, formalizado en la Resolución CRA 315 de 2005/2009.
- **Tope regulatorio real**: el nivel máximo de agua no contabilizada aceptado para el cálculo
  de costos del servicio es **30%** (parámetro ≤ 0.30) — un acueducto por encima de ese umbral
  no puede trasladar el costo de esas pérdidas a la tarifa.
- El IANC colombiano agrupa "pérdidas técnicas" (planta + red, por deterioro) y "pérdidas
  comerciales" (usuarios sin medición real, no detectados, conexiones fraudulentas, errores de
  medición/facturación) — mapea directo a Real Losses / Apparent Losses de la matriz IWA (§1),
  así que implementar la matriz IWA completa **también resuelve el reporte regulatorio
  colombiano**, no son dos alcances distintos.

**Esto confirma el ICP correcto para el primer piloto de Track B**: un acueducto colombiano
mediano/grande que hoy reporta IANC a la CRA a mano o con hojas de cálculo.

Fuentes: [CRA — Resolución 487 de 2009](https://normas.cra.gov.co/gestor/docs/resolucion_cra_0487_2009.htm),
[Aspectos técnicos del IANC en Colombia — Uniandes](https://repositorio.uniandes.edu.co/bitstreams/e33cf102-2a7c-420a-ab5f-e34bf63be42a/download),
[MDS Ingeniería — Índice de Agua No Contabilizada](https://mdsingenieria.co/blog/IANC-Indice-de-Agua-No-Contabilizada).

## 3. Mapa de mercado por capa

| Capa | Quién lo domina hoy | Qué cubren que RenfyGrid todavía no |
|---|---|---|
| **Balance/Pérdidas (NRW)** | Software especializado (LEAKSSuite y equivalentes), consultoría IWA | Matriz completa de 4 columnas + ILI, benchmarking histórico por zona |
| **Modelado hidráulico** | **Bentley WaterGEMS/OpenFlows** e **Innovyze InfoWater** (ahora Autodesk) — los dos productos que de verdad usan la mayoría de utilities/consultoras en Norteamérica | Re-calibración con datos de campo, detección de fugas por ubicación, gestión de presión por DMA |
| **Gemelo Digital / GIS** | **Esri ArcGIS Utility Network**, Bentley iTwin, Qatium, Aquanuity (AquaTwin) | Integración SCADA+GIS+mantenimiento en una sola vista, análisis espacial de activos |
| **Mantenimiento (CMMS)** | **Cityworks** (nativo Esri, domina utilities de agua) e **IBM Maximo** (domina electricidad, marco NERC CIP) | Disparo de orden desde SCADA/condición de activo automático, ya decidido delegarse a BayForce (correcto, no se reconstruye) |

**Ningún vendor cubre las 4 capas + medición (HES/MDM) en un solo producto** — mismo patrón de
fragmentación que confirmó `06-benchmark-e2e-y-brechas.md` para el lado de energía. La apuesta
de RenfyGrid (cobertura multi-utility desde el mismo núcleo, `01-planteamiento.md` §5) sigue
siendo el diferenciador real, ahora confirmado también del lado de agua.

Fuentes: [Bentley — WaterGEMS vs InfoWater](https://blog.bentley.com/software/watergems-vs-infowater/),
[Sumble — WaterGEMS](https://sumble.com/tech/watergems),
[Esri — Digital Twins Bring Value to Water Utilities](https://www.esri.com/arcgis-blog/products/arcgis/water/digital-twins-water-utilities),
[ReliaMag — Best CMMS for Utilities 2026](https://reliamag.com/guides/best-cmms-utilities/).

## 4. Ajuste de esquema propuesto (antes de implementar)

Sobre `03-diseno.md` §1.3, con la granularidad real de §1:

```sql
network_zone (
  id, tenant_id, name, type,           -- 'dma' | 'circuit' | 'district' | 'pressure_zone'
  parent_zone_id,
  data_source,                          -- 'renfygrid' | 'external'
  -- NUEVO: insumos reales para ILI (sin esto, UARL no se puede calcular)
  network_length_km,                    -- longitud de red de distribución de la zona
  num_connections,                      -- número de acometidas/conexiones activas
  avg_pressure_mca                      -- presión promedio de operación (mca / m de columna de agua)
)

network_balance (
  id, tenant_id, zone_id, period, method,   -- 'top_down' | 'bottom_up'
  system_input_volume,
  -- NUEVO: matriz IWA completa, no un "losses" agregado
  billed_metered_consumption,
  billed_unbilled_consumption,          -- exportado a otro sistema, medido pero no facturado (caso raro, se deja en 0 por defecto)
  unbilled_authorized_consumption,      -- hidrantes, lavado de redes, uso propio del operador
  apparent_losses,
  real_losses,
  -- KPIs calculados (guardados, no recalculados cada lectura -- mismo patron que reporting_pct)
  nrw,                                  -- = system_input_volume - billed_metered_consumption - billed_unbilled_consumption
  ili,                                  -- = real_losses / UARL(zone) -- None si la zona no tiene los 3 insumos (§1)
  version, calculated_at
)
```

**Por qué ahora y no después:** cambiar esto en B2 (ya con datos reales cargados) sería una
migración con downtime real de un tenant piloto; hacerlo en B1 (esquema inicial, sin datos
todavía) no cuesta nada. Confirmar con el usuario antes de escribir la migración — es el único
punto de este documento que se aparta del diseño ya aprobado en Fase 2/3.

## 5. Sprints ajustados (sobre `04-plan-sprints.md` §8, mismos B1-B7, alcance más preciso)

| Sprint | Ajuste real sobre el original | Entregable verificable |
|---|---|---|
| **B1** | Esquema con la granularidad de §4 (no la aplanada de Fase 2/3) + endpoint de ingesta externa `POST /network-zones/{id}/external-readings` | Una zona real (con `network_length_km`/`num_connections`/`avg_pressure_mca`) recibe un balance calculado vía API, sin medidor RenfyGrid de por medio |
| **B2** | Cálculo Top-Down/Bottom-Up que llena los 5 componentes de la matriz + `nrw`/`ili` calculados, `None` (no 0) cuando falta un insumo — mismo criterio fail-safe que el resto del proyecto | Con datos de ejemplo de un acueducto real (o representativo), el NRW y el ILI calculados coinciden con el cálculo manual de referencia |
| **B3** | Carga/versionado de modelo `.inp`, integración WNTR (sin cambios sobre el plan original) | Un modelo EPANET real se simula y devuelve resultados |
| **B4** | Vínculo Modelo↔Balance: el escenario de simulación usa `network_balance.real_losses` (no el agregado viejo) como insumo de calibración | Escenario de simulación usa balance real, no datos de ejemplo hardcodeados |
| **B5** | Esquema `network_asset`/`asset_connectivity` + ingesta externa (SIG) — sin cambios sobre el plan original | Un activo cargado vía API queda visible con su conectividad |
| **B6** | `network_model` derivado de `network_asset`+conectividad (export EPANET) | Un modelo generado desde el Gemelo Digital simula igual que uno cargado a mano |
| **B7** | Reglas de generación de orden desde anomalía (balance con ILI fuera de umbral, o simulación) + integración BayForce | Una anomalía de prueba genera una orden, se envía a BayForce (sandbox) y se cierra al recibir el webhook |

**Decisión de arquitectura de despliegue** (aplicando el mismo aprendizaje de Track A/C, no lo
que decía la Fase 2/3 original sobre bus/k3s): Track B se construye como **el mismo monolito
modular** — servicios Python en `services/network-balance/`, `services/network-model/`,
`services/digital-twin/`, `services/maintenance/`, importados directo por `portal-api` (sin
bus de eventos, sin k3s) — mismo patrón systemd+Postgres compartido ya probado y desplegado.
La arquitectura de Fase 2/3 (`02-arquitectura-general.md` §3) es aspiracional de cuando el
proyecto todavía no existía; la real, verificada en producción, es la del monolito modular.

## 6. Qué NO se construye (mismos límites ya establecidos en Fase 1)

- Un motor de simulación hidráulica propio — se delega en WNTR (`02-arquitectura-general.md`
  §3.2), igual que Gurux para DLMS/COSEM.
- Un SIG completo — `network_asset`/`network_zone` con PostGIS es un catastro operativo
  mínimo, no reemplaza ArcGIS/QGIS para un cliente que ya lo tiene (ingesta externa cubre eso).
- Ruteo/dispatch/app móvil de campo — BayForce, sin duplicar.
- Adaptador de balance para energía/gas en el primer piloto — el motor es agnóstico de utility
  por diseño (`method`/unidades como parámetro), pero el primer caso de uso real y el que tiene
  marco regulatorio confirmado (§2) es agua.

## 7. Pendiente real: módulo de georreferenciación (transversal a B1/B3/B5)

**Hallazgo de esta ronda** (2026-09-12, al pedir muestras `.inp` de ciudades colombianas para
mostrar): tanto Balance de Red (zonas/DMA) como Modelado Hidráulico (nudos/tuberías de un
modelo `.inp`) y, más adelante, el Gemelo Digital (`network_asset`/`asset_connectivity`, B5) son
**inherentemente espaciales** — el panel actual de `NetworkModel.tsx` solo muestra tablas de
presión/caudal por ID de nudo/tubería, sin mapa. Un modelo cargado con `[COORDINATES]` reales
(como los dos modelos de demostración de este sprint, ver más abajo) no tiene hoy dónde
mostrarse sobre cartografía real — hueco real, no cosmético, para un producto que vende
"Balance de Red" y "Modelado Hidráulico" a utilities.

**Patrón ya probado en el portafolio — revisado antes de proponer nada nuevo**: el módulo
"Mapa de Deuda" de RenFlow (`core/renflow/frontend/js/modules/map.js`) resuelve exactamente este
tipo de problema (miles de puntos geo-referenciados, filtros, capas temáticas, selección) y es
la referencia a seguir, no reinventar:

- **Leaflet + `Leaflet.markercluster`**, tiles de OpenStreetMap (`{s}.tile.openstreetmap.org`,
  sin API key ni costo) — mismo stack, cero licencia nueva.
- **Backend expone GeoJSON**, no HTML/SVG armado en el servidor — un endpoint tipo
  `GET /network-models/{id}/geojson` (nudos como `Point`, tuberías como `LineString`, usando el
  `[COORDINATES]` que WNTR ya expone via `wn.get_node(id).coordinates`) es el equivalente directo
  de `/api/geo/heat-map` de RenFlow.
- **Color/tamaño por métrica real** (RenFlow: deuda/mora por contrato — aquí: presión por nudo,
  caudal por tubería, igual que ya se calcula en `network_model_engine.py`) — nunca un color fijo,
  siempre derivado del resultado calculado.
- **Capas temáticas tipo choropleth** (RenFlow: deuda/mora/densidad por zona vía círculos
  coloreados) — el equivalente en Track B es NRW%/ILI por `network_zone` sobre el mapa, no solo
  en la tabla de `NetworkBalance.tsx` actual.
- **Selección por polígono + mini-dashboard** (RenFlow) tiene un paralelo directo: seleccionar
  una sub-zona de la red simulada y ver sus KPIs agregados sin salir del mapa.
- Diferencia real a resolver, no presente en RenFlow: Track B necesita dibujar **líneas**
  (tuberías) además de puntos, y layout de grafo cuando un modelo no trae `[COORDINATES]` reales
  (`network_model_engine` tendría que exponer también la topología nudo↔tubería, no solo las
  estadísticas agregadas actuales).

**No iniciado** — pendiente de confirmación con el usuario antes de construirlo (alcance
propio: ¿un componente de mapa compartido entre Balance de Red/Modelado Hidráulico/futuro
Gemelo Digital, o uno por pantalla?).

**Modelos de demostración georreferenciados creados en esta ronda** (para tener algo real que
mostrar mientras este módulo no existe): dos redes `.inp` **ilustrativas** (no un levantamiento
real de EAAB/EMCALI — documentado así en el propio archivo, nunca presentado como dato real de
la utility) pero con coordenadas geográficas reales:

- `services/network-model/demo/bogota_chapinero_dma.inp` — ancla en Chapinero, Bogotá
  (lat 4.6454–4.6572, lon -74.0619 a -74.0464, elevación base 2643 msnm real de la localidad).
- `services/network-model/demo/cali_tres_cruces_dma.inp` — ancla entre el Cerro de las Tres
  Cruces (lat 3.4673, lon -76.5469, tanque elevado) y el centro/San Fernando de Cali (lat 3.45,
  lon -76.5346).

Parámetros de tubería/caudal (diámetros 100–250 mm, Hazen-Williams C=140, demandas 0.5–1.9 L/s
por nudo) inspirados en órdenes de magnitud reales de un DMA colombiano — el caso de Cartago,
Valle del Cauca (Universidad Tecnológica de Pereira, Mendeley Data, CC BY 4.0,
[data.mendeley.com/datasets/5h5rdkhyyz](https://data.mendeley.com/datasets/5h5rdkhyyz/1)), no
medidos en campo. Ambos modelos cargan y simulan de verdad con WNTR (presiones 14.9–64.7 mca,
caudales reales por tubería, sin fabricar nada) y quedan sembrados en el tenant de
demostración persistente ("RenfyGrid Demo") vía `services/network-model/seed_demo_networks.py`.

Otras fuentes reales de referencia encontradas (no usadas directamente por bloqueo de scraping
automático, quedan anotadas para quien quiera profundizar): geometría real de la red menor de
acueducto de Bogotá en [Datos Abiertos Bogotá (EAAB)](https://datosabiertos.bogota.gov.co/dataset/red-menor-acueducto)
(Shapefile/GeoJSON/DXF/KMZ, requiere conversión a `.inp`); caso de digitalización de Pamplona,
Norte de Santander, en *Water* (MDPI, open access, [doi.org/10.3390/w15213824](https://doi.org/10.3390/w15213824)).
