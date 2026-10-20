# Caso Energía: hoja de vida y mantenimiento de 2.000 medidores de un comercializador

2026-10-20. Pedido del usuario:
- **Quién:** una empresa del sector eléctrico, prospecto QI Energy (https://qienergy.co, comercializadora
  de energía con clientes industriales, comerciales y de alumbrado público).
- **Qué:** quiere controlar unos **2.000 medidores** de sus clientes mayoristas, industriales y
  comerciales, y llevar la **hoja de vida de cada equipo** con sus mantenimientos y calibraciones.
- **Cómo:** el usuario propone incluir **BayForce** para tener la bitácora de cada trabajo hecho
  sobre los activos.

Primero va la revisión de la industria, después qué tiene hoy RenfyGrid, el diseño del workspace y
las decisiones que tiene que tomar el usuario. Es la primera aplicación del Track F
(`09-multi-industria.md`).

## 1. Qué exige la regulación (Colombia, Código de Medida)

Fuentes:
- Resolución CREG 038 de 2014 (Código de Medida), con los conceptos CREG 4026 de 2018 y 6166 de 2023.
- Formato de hoja de vida de la Circular CREG 119 de 2014.
- Instructivo de Enel Colombia "Mantenimiento del Sistema de Medición en Fronteras".

- **La hoja de vida es del sistema de medición de cada frontera comercial**, no de un medidor suelto.
  - La lleva el **representante de la frontera (RF)**, que en usuarios no regulados suele ser el
    comercializador.
  - El formato de la Circular 119 tiene 18 secciones: novedades, información general, medidor
    activo principal, medidor reactivo, medidor de respaldo, transformadores de corriente (CT) y de
    tensión (PT), conductores, paneles, bornera de prueba, comunicaciones de cada medidor, registro
    de accesos de nivel 2, novedades, observaciones, diagrama unifilar y persona designada.
  - Su hoja "Definición de campos" trae unos 650 campos, cada uno con su tipo y si es obligatorio.
    Sirve para cargar el formato como **catálogo**, no como código.
- **Tipo de punto de medición** (art. 6), por consumo mensual o por capacidad instalada:

  | Tipo | Consumo (MWh-mes) | Capacidad instalada (MVA) |
  |---|---|---|
  | 1 | C ≥ 15.000 | CI ≥ 30 |
  | 2 | 15.000 > C ≥ 500 | 30 > CI ≥ 1 |
  | 3 | 500 > C ≥ 50 | 1 > CI ≥ 0,1 |
  | 4 | 50 > C ≥ 5 | 0,1 > CI ≥ 0,01 |
  | 5 | C < 5 | CI < 0,01 |

- **Calibración de medidores por un laboratorio acreditado.** Se hace en cuatro casos:
  - antes de la puesta en servicio;
  - después de cualquier intervención que retire los sellos de la tapa;
  - cuando lo pide el plan de mantenimiento;
  - cuando cambia una programación que afecta la calibración.
- **Frecuencia del plan de mantenimiento** (art. 28, tabla 4):
  - medidores: tipo 1 cada 2 años, tipos 2 y 3 cada 4 años, tipos 4 y 5 cada 10 años;
  - transformadores de medida (CT y PT): pruebas de rutina como máximo cada 12 años (Acuerdo CNO 981
    de 2017).
- **Plan anual.** El RF debe tener un plan anual de mantenimiento y recalibración que empiece por las
  fronteras con más tiempo en operación.
- **Novedades que obligan a actualizar la hoja de vida:**
  - cambio de medidor principal o de respaldo;
  - cambio de CT o de PT;
  - adecuaciones en la celda de medida;
  - lectura en sitio, parametrización o actualización de hora;
  - visita de verificación;
  - cambio de módem;
  - mantenimiento programado.
- **Registro ante XM (ASIC).** Varias de esas novedades exigen actualizar el registro de la frontera
  ante XM, con el anexo 10, los certificados de calibración del medidor y de los CT y PT, el
  certificado de conformidad y el unifilar.
- Enel lleva todo esto en un sistema propio de hojas de vida (STORIA). Un comercializador mediano
  normalmente lo lleva en hojas de cálculo.

Todo lo que depende del país (tipos de punto, frecuencias, tipos de novedad, campos de la hoja de
vida) va en un **paquete regulatorio** `CO-CREG-038`, igual que `EC-ARCA` para agua. No va en el
código.

## 2. Herramientas de la industria para mantenimiento de activos

| Categoría | Ejemplos | Qué aporta al diseño |
|---|---|---|
| **EAM empresarial para utilities** | IBM Maximo (Utilities), SAP S/4HANA Utilities *Device Management*, Hexagon EAM, Oracle Utilities WAM, IFS | Las guías independientes de 2026 ponen a Hexagon y Maximo como líderes en utilities, con despliegues de 12 a 24 meses. Son caros y lentos para una empresa de 2.000 medidores |
| **Gestión de dispositivos de SAP IS-U** (la referencia para medidores) | SAP S/4HANA Utilities | **Separa el equipo (número de serie) del lugar donde está instalado** y guarda el historial de instalación, retiro y reemplazo. Lleva la vigencia de certificación por equipo y los procedimientos de certificación: **por muestreo** de lotes (si la muestra aprueba, se extiende la vigencia de todo el lote) o **por reemplazo periódico** |
| **Gestión de calibración** | Fluke MET/TEAM, Beamex CMX, Ambrit Calibrate (bancos de prueba de medidores) | Historial auditable de cada calibración: patrón usado, error encontrado, tolerancia, técnico, certificado. La tendencia del error ayuda a decidir el plan de recalibración. Se integran con SAP y Maximo |
| **CMMS livianos** | Fiix, UpKeep, MaintainX, Limble | Órdenes, preventivo por calendario y app móvil, pero sin el modelo de frontera, el tipo de punto ni el formato regulatorio |
| **Ejecución en campo (FSM)** | Maximo Mobile, SAP FSM, Salesforce Field Service; **en el portafolio: BayForce** | Despacho, ruta y legalización en sitio con evidencias: es la bitácora del trabajo |

**Conclusión de la revisión:**
- El mercado separa tres cosas:
  - **el registro del activo y su hoja de vida**, con el modelo equipo e instalación y la
    certificación (lo que hace SAP IS-U);
  - **la planeación del mantenimiento y la calibración** (CMMS o EAM);
  - **la ejecución y la evidencia en campo** (FSM).
- Ningún CMMS liviano trae el formato de la CREG.
- Los EAM que sí podrían configurarlo son desproporcionados para 2.000 medidores.
- Ese espacio es la oportunidad de RenfyGrid.

## 3. Qué tiene hoy RenfyGrid para un tenant de energía

| Pieza | Estado | Brecha para este caso |
|---|---|---|
| `meter` (cuenta, serie, marca, modelo, protocolo, ubicación, estado) | Existe | Es "el medidor de una cuenta". No separa el equipo del punto, no tiene historial de instalación y no conoce el medidor de respaldo, los CT, los PT, los módems ni los sellos |
| MDM (HES DLMS, VEE, consumos, corte y reconexión) | Existe y nació para energía | Sirve si la empresa tiene telemedida; para la hoja de vida no hace falta |
| Gemelo digital `network_asset` | Existe | Los tipos de activo son de agua y no tiene catálogo por sector (`09` §3) |
| CMMS (órdenes, SLA, códigos de falla, PM por activo, cierre con horas y materiales, KPIs) | Existe | El preventivo es por activo y por tiempo fijo. Le falta generarlo **por tipo de punto** con la frecuencia del paquete |
| Motor de fichas y tablas desde catálogo (`form_spec`, `form_entry` versionado; Track E) | Existe | **Sirve para la hoja de vida**: cada sección de la Circular 119 es una ficha o una tabla del paquete, con versiones |
| Carga por Excel o CSV (Track E) | Existe | Sirve para cargar las 2.000 fronteras y sus equipos |
| Menú | Muestra los módulos de agua a cualquier tenant | Es el F1 y el F2 de `09` |
| BayForce | Es la ejecución de campo de RenFlow | **No tiene API para que otro producto le cree órdenes** (verificado de nuevo hoy en `bayforce/main.py`, 9.402 líneas) y es **de un solo tenant** (una base MySQL ligada a RenFlow y a la operación de cobro de ESSMAR) |

## 4. Diseño del workspace para el tenant de energía

Sector `electricity` y paquete `CO-CREG-038`. El menú sale de los datos (`09` §5); este tenant no
ve nada de agua.

```
Vista general
  KPIs: fronteras con hoja de vida al día · calibraciones vencidas y por vencer (90 días)
        · órdenes abiertas · novedades pendientes de reportar a XM · sellos retirados sin reinstalar

Energía                                  (módulo del sector)
  ├ Fronteras comerciales                lista y mapa; tipo de punto 1–5; estado ante el ASIC; cliente
  │   └ Hoja de vida de la frontera      las 18 secciones de la Circular 119, versionada, exportable
  ├ Plan de calibración y mantenimiento  generado por tipo de punto con la frecuencia del paquete
  ├ Calibraciones y certificados         laboratorio, certificado, error encontrado, vigencia
  ├ Novedades y registro ante XM         cola de novedades que exigen actualizar el registro y sus anexos
  └ Sellos y accesos de nivel 2

Activos                                  (transversal)
  └ Equipos                              medidores, CT, PT y módems por número de serie, con su historial:
                                         instalado en la frontera X (posición) → retirado → laboratorio → bodega

Mantenimiento                            (transversal, el CMMS que ya existe)
  ├ Órdenes                              calibración, prueba de rutina, cambio de equipo, visita de verificación
  ├ Preventivo                           alimentado por el plan
  └ Cuadrillas y contratistas

Trabajo de campo (BayForce)              despacho, app móvil y legalización con fotos, firma, GPS y lectura;
                                         el resultado vuelve a la hoja de vida como novedad

Medición (MDM)                           solo si la empresa tiene telemedida: lecturas, VEE, consumos
Organización                             usuarios, configuración, integraciones
```

**Modelo de datos (patrón de SAP IS-U, todo con RLS):**

| Tabla | Para qué sirve |
|---|---|
| `metering_point` | La frontera (el "lugar"): código SIC, NIU, cliente, tipo de punto, tensión, capacidad, estado ASIC y coordenadas |
| `equipment` | El equipo físico: clase (medidor, CT, PT, módem), serie, marca, modelo, año, propiedad (usuario, RF u OR), certificado de conformidad y estado (instalado, bodega, laboratorio, baja) |
| `equipment_installation` | Qué equipo estuvo en qué frontera, en qué **posición** (principal, reactivo, respaldo, CT fase R, …) y desde y hasta cuándo. La hoja de vida histórica sale de aquí |
| `equipment_event` | La **bitácora del activo**: calibración (laboratorio, certificado, error, vigencia), prueba de rutina, instalación y retiro de sellos, acceso de nivel 2, parametrización, cambio de batería, visita. Cada evento tiene adjuntos, orden de origen y autor |
| `metering_novelty` | La novedad sobre la frontera según el catálogo del paquete; marca si exige actualizar el registro ante XM y en qué estado va |
| Paquete `CO-CREG-038` | Tipos de punto con sus umbrales, frecuencias de calibración y de pruebas de rutina, tipos de novedad, y las secciones y campos de la hoja de vida como `form_spec`, cargados desde el Excel oficial de la Circular 119 |

La hoja de vida **no se escribe a mano entera**:
- se arma con la frontera, los equipos instalados y sus últimos eventos;
- lo que el formato pide y no está en esas tablas (conductores, paneles, bornera, observaciones) se
  llena en fichas del motor de formularios.

## 5. BayForce: qué haría falta y opciones

Para que BayForce sea la bitácora de cada trabajo sobre el activo, faltan tres cosas que no existen:
1. **Una API de recepción de órdenes externas**, pensada para varios dominios desde el inicio, con
   una referencia genérica al activo en lugar de `subscriber_id` y `execution_id` de cobro.
2. **Aislamiento por cliente.** Hoy BayForce es de un solo tenant y opera en vivo para ESSMAR.
3. **El retorno de la legalización a RenfyGrid**, para que el resultado, las fotos, la firma, el GPS,
   la lectura y los materiales queden como `equipment_event` y como novedad en la hoja de vida.

| Opción | Qué es | A favor | En contra |
|---|---|---|---|
| **A. BayForce como servicio compartido de plataforma** | API de recepción + varios tenants en la misma instancia | Una sola pieza de campo para todo el portafolio | Toca un producto en vivo de ESSMAR; agregar varios tenants a una base que no los tiene es el cambio más riesgoso |
| **B. Instancia de BayForce dedicada al cliente** con la API de recepción (diseñada desde el inicio para varios tenants y dominios) | Misma base de código, base de datos propia | No arriesga la operación de ESSMAR; el cliente queda aislado físicamente; la API queda lista para A después | Hay que operar otra instancia |
| **C. Bitácora de campo propia de RenfyGrid** (la app sin conexión del operador de Track D) | Sin BayForce | Lo más rápido | Duplica lo que BayForce ya resuelve (despacho, ruta, legalización); va contra la decisión del 2026-09-14 |

**Recomendación: B.**
- La API se construye una sola vez, bien diseñada.
- El cliente de energía no comparte base con la operación de cobro de ESSMAR.
- Pasar a A queda como decisión de negocio aparte.
- La decisión del 2026-09-14 (`contextos/renflow/docs/BAYFORCE_RENFYGRID_INTEGRATION_NOTE.md`) pide
  que el usuario autorice explícitamente tocar el código de BayForce.

## 6. Sprints propuestos (sobre el Track F)

| Sprint | Alcance |
|---|---|
| **Q1 — Sector y paquete** | F1 de `09` (sector y módulos como datos) + paquete `CO-CREG-038`: tipos de punto, frecuencias, novedades y hoja de vida cargada desde el Excel de la Circular 119 |
| **Q2 — Fronteras y equipos** | `metering_point`, `equipment`, `equipment_installation`, `equipment_event`; pantalla de la frontera con la hoja de vida; carga por Excel de las 2.000 fronteras con sus equipos |
| **Q3 — Plan y vencimientos** | Plan anual generado por tipo de punto, certificados de calibración con vigencia y alertas de vencimiento, cola de novedades para XM, exportación de la hoja de vida en el formato oficial |
| **Q4 — BayForce** | Según la opción elegida: API de recepción de órdenes, retorno de la legalización a la bitácora del equipo, instancia del cliente |
| **Demo** | Tenant de demostración con 2.000 fronteras sintéticas (tipos 1 a 5 con distribución realista) para mostrarle el workspace al prospecto |
