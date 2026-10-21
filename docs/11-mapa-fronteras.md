# Mapa de fronteras comerciales: cómo debe operar (investigación y diseño)

2026-10-21. Pedido del usuario: el mapa de fronteras necesita mapas temáticos y capas que filtren
los medidores por estado técnico, estado comercial, tipo de cliente, PQRS (si tiene y de qué
tipo), rango de consumo, tipo y marca de medidor, y tipo y marca de módem. El usuario pidió
investigar primero cómo opera esto en el mercado. Este documento es la investigación y el diseño
propuesto. No hay código todavía.

## 1. Cómo lo resuelve el mercado

| Referencia | Qué muestra el mapa | Patrón que aporta |
|---|---|---|
| **GIS de utility con AMI integrado** (Esri ArcGIS / Utility Network, ArcFM; caso Saint John Energy) | El estado del medidor (corte, última lectura, alarmas de tensión) se simboliza sobre la red casi en tiempo real | El mapa es **una vista del dato operativo**, no un plano: cada punto se pinta por su estado actual |
| **Analítica de pérdidas no técnicas** (Itron Revenue Assurance, Trilliant NTL, Siemens EnergyIP) | Ubica en el mapa los medidores con anomalías (manipulación, consumo atípico, cero consumo) para enviar a verificar | Las **capas de excepción** (lo que hay que atender) se superponen a la base completa |
| **Operación AMI** (C3 AI AMI Operations, Landis+Gyr Command Center, Neptune N_SIGHT) | Salud de cada medidor y de la red de comunicaciones, con ficha emergente al pasar el cursor | Color por salud, **ficha corta al pasar** y enlace al detalle |
| **Caso de pérdidas con GIS** (Opelika Utilities con Insights for ArcGIS) | Cruce de medición, facturación y órdenes de trabajo en el mapa: encontró 3.000 de 14.000 medidores sin registro | El valor está en **cruzar fuentes** (técnica, comercial, órdenes) sobre el mismo punto |
| **Cartografía temática** (Axis Maps, GIS&T Body of Knowledge) | Valores categóricos con color, magnitudes con símbolos graduados, tasas por área en coropletas | Para puntos: **color = categoría, tamaño = magnitud (por rangos, no continuo), forma = otra categoría**. Las coropletas, solo con tasas |
| **Tableros con filtros cruzados** (Looker, Omni) | Filtros con conteos que se reducen entre sí; seleccionar en un gráfico filtra el mapa y viceversa | Filtros **por facetas con conteo**, filtros cruzados y estado de filtros visible |
| **Agrupamiento de puntos** (Leaflet.markercluster, Supercluster, PruneCluster) | Miles de puntos legibles: grupos al alejarse y puntos individuales al acercarse | Con 2.000 a 50.000 puntos el agrupamiento es obligatorio. El grupo debe mostrar **la composición** (p. ej. cuántos vencidos), no solo el total |

**Conclusión:** un mapa de fronteras útil no es "pintar puntos". Combina cinco cosas:

1. **Una variable temática a la vez para el color.** El usuario elige "pintar por" estado técnico,
   estado comercial, tipo de cliente, marca del medidor… La leyenda se arma sola con las
   categorías y su conteo.
2. **Tamaño por magnitud** (consumo, capacidad), en rangos fijos.
3. **Filtros por facetas** independientes del color (p. ej. pintar por marca, pero solo los
   tipos 1 y 2 con PQR abierta). Cada opción muestra cuántas fronteras tiene y la lista y los
   KPIs se filtran igual.
4. **Capas de excepción superpuestas:** calibración vencida, PQR abierta, novedad pendiente de
   XM, alarma o falta de comunicación. Se prenden y apagan encima de la base.
5. **Acción desde el mapa:**
   - ficha al pasar el cursor;
   - clic para ir a la hoja de vida;
   - seleccionar un área para ver la lista, exportarla o crear órdenes (Q4, BayForce);
   - vistas guardadas por rol (p. ej. "Calibraciones del trimestre", "PQR de facturación
     abiertas").

## 2. Las variables del usuario, mapeadas al dato

| Variable | ¿Existe hoy? | De dónde sale (o qué falta) |
|---|---|---|
| **Estado técnico** | Parcial | Calibración o prueba (al día, por vencer, vencida, sin registro) y estado ASIC de la frontera, ya existen. **Falta** cruzar con las alarmas y la última comunicación del MDM: el `meter` del HES y el `equipment` de la hoja de vida no están vinculados (se vinculan por número de serie) |
| **Estado comercial** | **No** | Al día, en mora, suspendida por cartera, en proceso de corte, retirada… Es dato del CIS o de facturación. Hace falta un campo con su catálogo, cargado por archivo o por la integración CIS |
| **Tipo de cliente** | Parcial | Está como campo 2.17 "Clase de servicio" de la Circular 119 (residencial, comercial, industrial, oficial, alumbrado…), dentro de una ficha. Debe pasar a **columna de la frontera**, junto con **mercado regulado o no regulado** |
| **Con PQRS / tipo de PQRS** | **No** | Entidad nueva `customer_request`. Usa la **taxonomía oficial de la Superservicios** (Resolución SSPD 20261000681915 de agosto de 2026): tipo de trámite (reclamación, queja, recurso), grupo de causal (F facturación, P prestación) y detalle de causal de 3 dígitos (100–136 reclamaciones, 200–208 quejas); además, estado y tipo de respuesta. Se liga a la frontera por el NIU o la cuenta, igual que en el reporte al SUI |
| **Rango de consumo** | Sí | `consumption_mwh_month`. Los rangos por defecto son los **umbrales del tipo de punto** del paquete (5, 50, 500, 15.000 MWh-mes): no se inventan cortes |
| **Tipo y marca de medidor** | Sí | `equipment.brand` y `model`, y la ficha técnica (3.9 tecnología, 3.10 conexión directa, semidirecta o indirecta) |
| **Tipo y marca de módem** | Sí | `equipment.brand` del módem y el campo 11.9 "Medio de comunicación" (GPRS, 3G, 4G, fibra, satelital…) |
| Otras que el mercado usa y conviene sumar | Sí o parcial | Tipo de punto (1–5), ciudad o departamento, operador de red, novedad pendiente de XM, antigüedad del medidor (año de fabricación), propiedad del medidor (usuario, RF u OR) |

**Pendiente de verificar:**
- Los códigos de causal salen del proyecto de resolución publicado en abril de 2026.
- La resolución final (20261000681915, 5 de agosto de 2026) figura como vigente en el SUI, pero no
  pude leer su texto. Se cargan como catálogo del paquete `CO-CREG-038` (o de un paquete
  `CO-SSPD`) para corregirlos sin tocar código.

## 3. Diseño propuesto (todo como catálogo, nada fijo)

**Catálogo `map_dimension`** (global, por paquete o sector). Cada variable por la que se puede
pintar o filtrar se define con:
- clave, nombre y grupo (Técnico, Comercial, Cliente, Equipos, PQRS);
- **origen**: columna de la frontera, campo de una ficha, atributo del equipo instalado en una
  posición, estado calculado (calibración) o agregado de PQR o de bitácora;
- **tipo**: categórica (colores del catálogo `code_label`) o numérica (rangos del catálogo);
- si se puede usar para **pintar**, para **filtrar** o para ambos.

Agregar una variable nueva es una fila, no una pantalla nueva.

**Endpoint `/assets/map`:**
- devuelve, por frontera, solo las claves de las dimensiones (compacto: 2.000 fronteras ≈ 150 KB);
- devuelve las facetas con su conteo para los filtros actuales;
- para 20.000 fronteras o más, se pasa a teselas o a agrupamiento en el servidor; no hace falta
  para 2.000.

**Pantalla "Mapa de fronteras"** (página propia del módulo Energía; no una sección del tablero):

- **Panel izquierdo:**
  - "Pintar por" (selector de dimensión), con la leyenda y el conteo de cada categoría; cada
    categoría se prende y apaga con clic.
  - "Tamaño por" (ninguno, consumo o capacidad).
  - Filtros por facetas con conteo.
  - Capas de excepción: vencidas, PQR abierta, XM pendiente.
  - Vistas guardadas.
- **Mapa:**
  - agrupamiento cuyo color es el de la categoría dominante y con su composición al pasar el
    cursor;
  - punto con color, tamaño y borde de alerta;
  - ficha al pasar y clic a la hoja de vida;
  - selección por rectángulo o polígono.
- **Debajo:** la lista de las fronteras que cumplen el filtro (sincronizada con el mapa y
  exportable a Excel) y los KPIs del filtro.

**Datos nuevos que necesita:**

| Dato | Para qué | Cómo se carga |
|---|---|---|
| `metering_point.customer_class` y `market` | Tipo de cliente y mercado regulado o no regulado | Plantilla de fronteras (columnas nuevas) |
| `metering_point.commercial_status` con su catálogo | Estado comercial | Plantilla o integración CIS |
| `customer_request` (PQR) con la taxonomía de la Superservicios como catálogo | PQRS por frontera | Plantilla nueva de PQR (el mismo archivo que se reporta al SUI) o registro en la hoja de vida |
| Vínculo `equipment` ↔ `meter` (HES) por serie | Alarmas, última comunicación y lecturas en el estado técnico | Automático por número de serie |
| `map_dimension`, `map_view` (vistas guardadas por organización o usuario) | Pintar, filtrar y guardar | Catálogo con semilla y lo que el usuario guarde |

## 4. Sprint propuesto: Q2.5 "Mapa de fronteras"

| Parte | Alcance |
|---|---|
| Datos | Columnas de tipo de cliente, mercado y estado comercial; `customer_request` con la taxonomía SSPD; vínculo equipo ↔ medidor del HES; plantillas de carga actualizadas |
| Catálogo | `map_dimension` con las variables de la tabla §2; `map_view` |
| API | `/assets/map` con facetas y conteos |
| Portal | Pantalla del mapa con pintar por, tamaño, facetas, capas de excepción, agrupamiento con composición, ficha emergente, selección por área, lista sincronizada exportable y vistas guardadas |
| Demo | `demoenergia` con tipo de cliente, estado comercial y unas 300 PQR ficticias con causales reales de la tabla SSPD |
| Pruebas | E2E de filtros y conteos; revisión visual |

## Fuentes

- [C3 AI AMI Operations](https://c3.ai/wp-content/uploads/2020/11/C3-AI-AMI-Operations-Data-Sheet.pdf)
- [Patente: visualización de red AMI sobre mapa](https://patents.justia.com/patent/20120101749)
- [Neptune N_SIGHT con Esri](https://www.wwdmag.com/utility-management/news/10926741/neptune-technology-group-inc-neptune-technology-group-partners-with-esri-3-gis-to-provide-host-software)
- [Esri: pérdida de ingresos con visualización simple (Opelika)](https://www.esri.com/about/newsroom/arcnews/pinpointing-revenue-loss-with-simple-data-visualization)
- [Trilliant Non-Technical Loss Analytics](https://trilliant.com/trilliant-non-technical-loss-analytics/)
- [Itron Revenue Assurance](https://it.itron.com/what-we-offer/revenue-assurance)
- [Siemens EnergyIP Revenue Protection](https://siemens.com/global/en/products/energy/grid-software/meter-data-management/revenue-protection.html)
- [Axis Maps: símbolos proporcionales](https://www.axismaps.com/guide/proportional-symbols)
- [Looker: filtros cruzados](https://docs.cloud.google.com/looker/docs/cross-filtering-dashboards?authuser=0)
- [Omni: interactividad de filtros](https://docs.omni.co/visualize-present/dashboards/filter-interactivity)
- [Leaflet.markercluster](https://github.com/bpavot/Leaflet.markercluster)
- [PruneCluster](https://cdn.jsdelivr.net/npm/prunecluster@2.1.0/README.md)
- [SUI: resoluciones vigentes (Res. SSPD 20261000681915 de 2026)](https://sui.superservicios.gov.co/Normativa/resoluciones-y-circulares)
- [Proyecto de resolución PQRS y canales de atención (abril de 2026)](http://www.superservicios.gov.co/sites/default/files/2026-04/Proyecto-resolucion-PQRS-canales-atencion-SUI.pdf)
