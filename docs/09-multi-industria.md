# RenfyGrid: producto estándar para energía, gas y agua

2026-10-20. Pedido del usuario: RenfyGrid es un producto estándar para tres industrias
(energía, gas y agua). Lo propio de cada sector va en un módulo con el nombre del sector, y lo que
es común a las tres (como el MDM) es transversal. El ajuste aplica al workspace (el Portal), al
sitio rensoftlabs.com y a los briefs, con **un brief por industria**. Regla de siempre:
**nada de datos fijos en el código**.

Este documento evalúa el alcance y propone el ajuste del menú. No cambia código todavía.

## 1. De dónde partimos

- RenfyGrid nació como MDM/AMI para **energía**: la propuesta de 2024 a tres empresas de energía
  (`01-planteamiento.md` §1), con DLMS/COSEM, mapeo OBIS, VEE y corte y reconexión remota.
- Track B y el Track D lo **inclinaron hacia agua**: balance hídrico IWA, EPANET/WNTR, calidad del
  agua, dosificación, saneamiento y las guías de Municipios Azules.
- Hoy el menú del Portal es en la práctica un **producto de acueducto**: "Calidad del agua",
  "Saneamiento", "Dosificación", "Balance de Red (IWA)", "Modelado Hidráulico".
- `08-estandares-mundiales.md` ya separó **núcleo / paquete regulatorio / paquete de programa /
  terminología**. Falta el eje que pide este documento: el **sector**.

## 2. Alcance funcional: qué es transversal y qué es de cada sector

### 2.1 Transversal (núcleo, igual para las tres industrias)

| Módulo | Por qué es transversal | Lo que cambia por sector (como dato) |
|---|---|---|
| **MDM: HES / Ingesta** | DLMS/COSEM cubre los tres medios. El grupo A del código OBIS identifica el medio: 1 = electricidad, 7 = gas, 8 y 9 = agua fría y caliente | Canales y unidades de cada medio, en el mapeo OBIS (ya es dato por marca y modelo) |
| **MDM: VEE** | Validación, estimación y edición son el mismo proceso | Plantillas de reglas por sector (demanda kW y energía reactiva en energía; corrección PTZ en gas; caudal nocturno en agua) |
| **MDM: Consumo** | Agregar lecturas validadas por período | Unidad facturable (kWh, m³, m³ corregido o energía del gas) |
| **MDM: Control (SCR)** | Suspensión, corte y reconexión con aprobación y auditoría | El tipo de actuador (relé o válvula) es un atributo del medidor |
| **Gemelo digital** | Inventario georreferenciado de activos y su conectividad | **Tipos de activo por sector**: tubería, válvula y tanque; línea, transformador y alimentador; red, estación reguladora y válvula |
| **Balance de red** (motor) | Entrada menos consumo autorizado = pérdida, por zona | El **método** es del sector: balance IWA con ILI (agua), pérdidas técnicas y no técnicas (energía), gas no contabilizado con corrección de volumen (gas) |
| **Modelado de red** (motor) | Ciclo de vida de modelos: carga, versión, simulación, calibración | El **simulador** es del sector: EPANET/WNTR (agua), flujo de carga tipo OpenDSS o pandapower (energía), pandapipes (gas) |
| **Mantenimiento (CMMS)** | Órdenes, SLA, preventivo, códigos de falla | Códigos de falla y planes por sector (catálogo) |
| **Emergencias** | Plan por tipo, contactos, activaciones | Tipos de emergencia por sector (rotura, apagón, fuga de gas) |
| **Bodega y EPP** | Existencias, vencimientos, EPP por tarea | Artículos y EPP por sector |
| **Guías (punto de partida) y asesoría de la ONG** | El motor de paquetes, fichas y tablas es neutro | El **contenido** del paquete (hoy solo hay paquetes de agua) |
| **Mi sistema** (recorrido, semáforo, hallazgos) | Cadena de etapas con hallazgos | **Las etapas son del sector**: captación → tratamiento → distribución; subestación → alimentador → transformador → acometida; estación de entrada → regulación → distribución → acometida |
| **Operación diaria** (mediciones de campo y bitácora) | Medir parámetros en puntos y llevar la bitácora | Parámetros por sector (ya es catálogo `parameter`) |
| **Plan y mejora, Informe de cumplimiento** | Motor de plan y de informe | Formato de cada autoridad (paquete regulatorio) |
| **Organización** (usuarios, configuración, integraciones CIS, observabilidad, agrupación, plataforma) | Administración | — |

### 2.2 Específico de cada sector (un módulo con el nombre del sector)

| Módulo | Contenido | Estado hoy |
|---|---|---|
| **Agua** | Calidad del agua (plan de muestreo, laboratorio, valores de referencia), dosificación y tren de tratamiento, saneamiento, balance hídrico IWA (agua no facturada, ILI, caudal mínimo nocturno), modelo EPANET, nivel de servicio JMP | **Construido** (Tracks B y D) |
| **Energía** | Calidad del suministro (tensión, interrupciones, índices de continuidad tipo SAIDI/SAIFI de IEEE 1366), pérdidas técnicas y no técnicas por circuito y transformador, carga de transformadores, demanda y tarifas horarias, flujo de carga | **No construido.** Hoy solo existe lo del MDM, que nació para energía |
| **Gas** | Corrección de volumen (presión, temperatura, compresibilidad) y poder calorífico, gas no contabilizado, odorización (el equivalente de la dosificación), protección catódica, patrullaje y detección de fugas, estaciones de regulación, revisión periódica de instalaciones internas | **No construido** |

Las revisiones obligatorias, los plazos y los índices exigidos dependen de cada país, así que van
en el **paquete regulatorio** del país y no en el módulo del sector.

## 3. Valores fijos que hoy atan RenfyGrid a una industria

Auditoría del 2026-10-20 (además de la del 2026-10-06 en `08-estandares-mundiales.md` §4):

| Dónde | Valor fijo | Efecto |
|---|---|---|
| `services/consumption/billing_export.py:51` | `"unit": "kWh"` | **Error real hoy**: un acueducto exporta sus consumos de agua al CIS marcados como kWh |
| `component_type.service` (0021) | `CHECK (service IN ('water','sanitation','support'))` | Ningún componente de energía o gas cabe en el modelo |
| `network_asset.type`, `network_zone.type` (0001) | `pipe/valve/tank…`, `dma/circuit/district` en comentarios, sin catálogo | El gemelo no sabe qué tipos de activo son de cada sector |
| `network_model.format` | Solo `epanet_inp` | El modelado es solo hidráulico |
| `network_balance_engine.py` | Solo el método IWA (`WaterBalanceInputs`) | Correcto, pero se usa como si fuera **el** balance de red |
| Frontend | "m³" en 6 pantallas, "L/s" en 2, "agua" en 11 archivos, "Calidad del agua" y "Modelado Hidráulico" en `navigation.ts` | La interfaz es de acueducto para cualquier tenant |
| `navigation.ts` | `NAV_GROUPS` es un literal | Qué módulos ve cada sector y cada organización está en el código, no en datos |
| Tenant | No tiene sector; `kind` (provider, group, advisor, platform) es otro eje | No hay forma de decir "esta empresa es de energía" ni "es multiservicio" |
| Paquetes | `pack` no tiene sector | Un paquete de agua se puede adoptar en una empresa de gas |

## 4. Diseño propuesto (todo como catálogo, patrón semilla + catálogo)

1. **`sector`** (catálogo global): `water`, `electricity`, `gas`, con su nombre, ícono, unidad
   facturable por defecto y los valores del grupo A de OBIS que le corresponden. Agregar un sector
   después (por ejemplo, calor distrital) es una fila, no código.
2. **`tenant_sector`** (por organización, con RLS): los sectores que opera la organización. Es
   **muchos a muchos** porque en América Latina hay empresas multiservicio que dan agua, energía
   y gas.
3. **`meter.sector_code`**: cada medidor es de un medio. Se deduce del mapeo OBIS y se puede
   corregir a mano. Con esto VEE, consumo y balance filtran por sector.
4. **`unit`** (catálogo): unidad, magnitud (volumen, energía, potencia, caudal) y factor de
   conversión. Reemplaza "kWh", "m³" y "L/s" escritos en el código. La unidad del consumo sale
   del canal (mapeo OBIS) o, si no hay canal, del sector.
5. **`pack.sector_code`** (vacío = transversal): EC-ARCA y EC-MUNICIPIOS-AZULES quedan como `water`.
   Una organización solo ve paquetes de sus sectores.
6. **Etapas, tipos de componente y de activo, tipos de zona, tipos de emergencia, parámetros y
   códigos de falla** pasan a llevar `sector_code`. El `CHECK` de `component_type.service` se
   cambia por una FK al catálogo `service`, que pertenece a un sector (agua potable y saneamiento
   son servicios del sector agua).
7. **Métodos de balance y simuladores** se registran en un catálogo (`balance_method`,
   `model_engine`) con su sector. El código de cada método sigue siendo código porque las fórmulas
   son lógica, pero **qué método usa cada zona** es dato.
8. **`product_module`** (catálogo global) y **`tenant_module`** (por organización):
   - `product_module` tiene código, ruta, nombre, ícono, descripción, grupo del menú, orden,
     `sector_code` (vacío = transversal) y tipos de organización.
   - `tenant_module` es lo que la organización tiene habilitado, el "à la carte" de
     `01-planteamiento.md` §3, que hoy no existe en datos.
   - El frontend guarda solo el **registro de componentes** (código → pantalla y secciones). El
     menú se arma con `/modules` y deja de ser el literal `NAV_GROUPS`.
9. **Terminología por sector**: el catálogo `term` admite paquetes de sector (usuario, suscriptor o
   cliente; acueducto o distribuidora). Los textos de pantalla como "m³" o "agua" salen de la
   unidad y del término.

## 5. Ajuste del menú

El menú se arma con los datos de `product_module` y `tenant_module`. Una empresa solo de agua ve
el grupo "Agua"; una multiservicio ve los tres grupos de sector; una de gas no ve nada de agua.

```
Vista general
Punto de partida
  └ Guías                         (contenido según los paquetes de sus sectores)

Agua                              (solo si opera agua)
  ├ Calidad del agua              muestreo, laboratorio, alertas
  ├ Tratamiento y dosificación    tren de tratamiento, dosificación
  ├ Saneamiento
  └ Balance hídrico (IWA)         agua no facturada, ILI, caudal nocturno

Energía                           (solo si opera energía)
  ├ Calidad del suministro        tensión, interrupciones, SAIDI/SAIFI
  ├ Pérdidas de energía           técnicas y no técnicas por circuito y transformador
  └ Transformadores y demanda     carga, demanda, tarifas horarias

Gas                               (solo si opera gas)
  ├ Corrección y poder calorífico PTZ, energía del gas
  ├ Odorización
  ├ Integridad de la red          protección catódica, patrullaje y fugas
  └ Estaciones de regulación

Operación                         (transversal)
  ├ Operación diaria              mediciones de campo y bitácora
  ├ Mi sistema                    recorrido por etapas del sector, semáforo, hallazgos
  ├ Mantenimiento
  ├ Emergencias
  ├ Bodega y EPP
  ├ Plan mínimo y mejora
  └ Informe de cumplimiento

Medición (MDM)                    (transversal)
  ├ HES / Ingesta
  ├ VEE
  ├ Consumo
  └ Control (SCR)

Red                               (transversal; el método y el simulador salen del sector)
  ├ Gemelo digital
  ├ Balance de red                el de cada sector: IWA, pérdidas de energía, gas no contabilizado
  └ Modelado de red               EPANET, flujo de carga o simulación de gas

Asesoría (ONG) · Plataforma · Organización   (sin cambios)
```

Decisiones de diseño:

- **Balance de red** aparece en "Red" (motor transversal) y el detalle del método va en el módulo
  del sector. Para no duplicarlo, "Balance hídrico (IWA)" en el grupo Agua es la **sección** de
  ese método dentro de Balance de red, no otra pantalla.
- La **dosificación** sale de Operación diaria y pasa al grupo Agua. En gas su par es la
  odorización. Las dos usan el mismo motor de puntos de medición y parámetros.
- Una **multiservicio** con los tres sectores ve en Medición, Red y Mi sistema un filtro de
  sector. No ve tres copias del MDM.
- Los **tipos de organización** (prestador, agrupación, ONG, plataforma) siguen como hoy. El
  sector es otro eje: una ONG que asesora cooperativas eléctricas rurales ve "Guías" con
  paquetes de energía.

## 6. Sitio rensoftlabs.com y briefs

- **Tarjeta de producto** (índice, 6 idiomas): RenfyGrid deja de presentarse como "acueducto,
  pérdidas y mantenimiento". Pasa a ser "medición y operación de redes de energía, gas y agua",
  con **tres botones de brief**, uno por industria.
- **Un brief por industria**:
  - `renfygrid-agua-brief.html` lleva el contenido del brief actual (agua no facturada, IWA,
    EPANET). Las juntas y los programas siguen como briefs de segmento dentro de agua.
  - `renfygrid-energia-brief.html` es nuevo.
  - `renfygrid-gas-brief.html` es nuevo.
  - `renfygrid-brief.html` queda como **selector de industria**, para no romper los enlaces que
    ya se enviaron.
- **Honestidad del brief**: energía y gas dicen con claridad qué está construido hoy (el MDM
  multimarca, VEE, consumos, corte y reconexión con aprobación, CMMS y gemelo) y qué se
  construye con el piloto (los módulos de sector). No se anuncia como hecho lo que no existe.

## 7. Sprints propuestos (Track F)

| Sprint | Alcance | Riesgo |
|---|---|---|
| **F1 — Sector y módulos como datos** | Catálogos `sector`, `tenant_sector`, `unit`, `product_module` y `tenant_module`; `/modules`; menú armado desde datos. Los tenants actuales quedan como `water` y **no ven ningún cambio** | Bajo: no cambia lo que ve nadie |
| **F2 — Agua como módulo** | Agrupar Calidad, Tratamiento y dosificación, Saneamiento y Balance IWA en el grupo "Agua"; `sector_code` en paquetes, etapas, tipos de componente, activo y zona; corregir el `kWh` del export y las unidades fijas del frontend | Medio: hay que rehacer las rutas, los permisos (`ROUTE_RULES`) y los E2E |
| **F3 — MDM multimedio** | `meter.sector_code` deducido de OBIS; unidades por canal; plantillas VEE por sector; consumo y export con su unidad; balance y modelado con catálogo de métodos | Medio |
| **F4 — Módulo Energía (MVP)** | Pérdidas técnicas y no técnicas por circuito y transformador; interrupciones y SAIDI/SAIFI; carga de transformadores; tipos de activo y etapas de energía | Alto: alcance nuevo; conviene con un piloto real |
| **F5 — Módulo Gas (MVP)** | Corrección PTZ y poder calorífico; gas no contabilizado; odorización; protección catódica y patrullaje | Alto: alcance nuevo; conviene con un piloto real |
| **F0 — Sitio y briefs** | Tarjeta multi-industria en 6 idiomas; tres briefs; selector en `renfygrid-brief.html` | Bajo: se puede hacer ya, en paralelo |

**Orden recomendado:** F0 ya mismo; F1 y F2 después del taller del 22-oct, sin tocar lo que usa
APT; F3; y F4 o F5 cuando haya un piloto de esa industria. Sin piloto se construiría a ciegas.
