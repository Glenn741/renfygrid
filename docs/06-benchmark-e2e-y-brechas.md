# Benchmark E2E del proceso Meter-to-Cash y brechas de RenfyGrid

**Fecha:** 2026-09-11 · Complementa `00-benchmark-industria.md` (que comparaba RenfyGrid contra
SaaS-SMB comparables). Este documento responde una pregunta distinta y más específica que pidió
el usuario: **¿existe hoy una sola herramienta que cubra todo el camino, desde el medidor hasta
el CIS, incluido el camino de regreso (el CIS pidiendo o actuando sobre un medidor)?** Y, con esa
respuesta, qué le falta al alcance actual de RenfyGrid — no en el plan, en lo que se ve y se opera
de verdad.

Investigado con búsquedas reales (fuentes al final de cada sección), no con memoria de
entrenamiento — igual criterio que `00-benchmark-industria.md`.

---

## 1. El mapa real del proceso, por capa, y quién lo cubre

La cadena completa tiene 4 capas con dueños de mercado distintos:

| Capa | Qué hace | Quién la domina hoy |
|---|---|---|
| **HES (Head-End System)** | Habla el protocolo del medidor (DLMS/COSEM, ANSI C12, propietario), colecta lecturas crudas, gestiona la red de concentradores | Itron, Landis+Gyr, Aclara, Sensus — casi siempre **HES propietario ligado a su propio hardware de medidor** (candado de proveedor documentado como restricción real del mercado) |
| **MDM/VEE** | Valida, estima, edita — entrega datos "listos para facturar" | Itron Enterprise Edition, Landis+Gyr MDMS/Core MDMS, Siemens Gridscale X, Oracle Utilities MDM |
| **CIS/Facturación** | Cuentas, tarifas, facturación, atención al cliente | SAP IS-U (~1,500 clientes), Oracle CC&B, Gentrack, Hansen Technologies (HUB), CSG, Solteq |
| **Campo / Field Service** | Ejecuta órdenes de corte/reconexión/inspección en sitio | Por lo general un módulo aparte o integración con WFMS (mismo patrón que RenfyGrid con BayForce) |

**Hallazgo central, confirmado por la propia arquitectura de los líderes:** la mayoría de
utilities pequeñas/medianas **operan 3-4 sistemas separados** (CIS/billing, MDM/lectura, ERP,
procesador de pagos) — "cada frontera entre esos sistemas es un traspaso de datos donde algo se
exporta, transfiere y reconcilia; más sistemas en la cadena, más traspasos, más lugares donde
puede entrar o acumularse un error" ([CSA1](https://www.csa1.com/from-meter-read-to-customer-bill-how-native-mdm-and-cis-integration-works/)).
Es la norma de la industria, no una excepción.

### 1.1 Los dos intentos reales de romper esa fragmentación — y por qué ninguno llega hasta el HES

- **Oracle Utilities Customer to Meter (C2M)**: une CC&B (CIS) + MDM en **una sola instancia**, justamente para eliminar el traspaso CIS↔MDM. Pero **no incluye HES propio de protocolo** — sigue integrándose con el adaptador HES del fabricante del medidor por fuera. ([Oracle](https://www.oracle.com/utilities/meter-data-management/), [Oracle C2M brief](https://www.oracle.com/us/industries/utilities/oracle-utilities-c2m-brief-4072957.pdf))
- **Bynry SMART360**: "es la única plataforma de esta lista donde CIS, billing, MDM, pagos,
  portal de cliente y órdenes de trabajo están construidos nativamente en un solo código, no
  adquiridos y cosidos entre sí" ([Bynry](https://www.bynry.com/blog/best-cloud-utility-platform-2026)).
  Pero su MDM **no habla el protocolo del medidor directamente** — depende de integraciones con
  el AMI/HES existente del cliente (confirmado también en `00-benchmark-industria.md`).

**Respuesta directa a la pregunta:** no, no encontramos ningún vendor — ni enterprise (Oracle,
SAP) ni SaaS-SMB (Bynry, Kalki.io, Energyworx) — que hoy cubra nativamente **HES de protocolo +
MDM/VEE + CIS/facturación** en una sola pieza de software. Los dos que más se acercan resuelven
la fragmentación en un punto distinto de la cadena: Oracle desde MDM hacia arriba (CIS), Bynry
desde MDM hacia abajo (facturación/campo), ninguno desde el protocolo del medidor hacia arriba.

**Esto confirma con evidencia real lo que `00-benchmark-industria.md` ya proponía como apuesta:**
RenfyGrid, al construir su propio adaptador HES (Gurux/DLMS-COSEM) integrado al mismo modelo de
datos que VEE/Consumos/Control, **sí puede ser ese caso raro** — con la condición honesta de que
hoy no expone ese trayecto completo de forma visible ni gestionable (ver sección 3).

---

## 2. El término de industria que le falta a RenfyGrid: "Service Order"

Buscando específicamente cómo los sistemas de referencia modelan "el CIS le pide algo a un
medidor", aparece un patrón consistente y con nombre propio:

> "Una solicitud de servicio se crea en un CIS (ej. Oracle CC&B), que a su vez se envía a **Service
> Order Management**. Las órdenes de servicio se usan para rastrear estos eventos, y el sistema
> MDM **orquesta todas las actividades relacionadas con esas órdenes**."
> ([Oracle Service Order Management](https://docs.oracle.com/en/industries/energy-water/meter-solution-cloud-service/2510/mscs-user-guides/Topics/D1_AG_Understanding_Service_Order_Management.html))

Las "command activities" que un CIS puede pedir sobre un medidor real son un conjunto conocido y
acotado: **connect, disconnect, ping (estado), lectura bajo demanda**.

**Lo que esto confirma sobre RenfyGrid**: el concepto ya existe en el backend — `control_order`
(F26-F30, Sprint 6-7) y la lectura bajo demanda (F04, Sprint 8) son exactamente eso. **El gap no
es de arquitectura, es de que nunca se enmarcó ni se expuso como una sola cosa** ("Service
Order"/"petición del CIS"), y le falta una pieza puntual: **distinguir de dónde vino la petición**
(¿la disparó el CIS externo, o un operador desde el Portal?) y **un comando de "ping"/estado**
que hoy no existe (solo hay lectura completa o nada).

Fuentes: [enQuesta CIS+MDM](https://ssivt.com/blog/simplifying-utility-workflows-with-enq-cis),
[Oracle CC&B-MDM Implementation Guide](https://docs.oracle.com/cd/E41155_03/library/CCB-MDM_Implementation_Guide.pdf).

---

## 3. Brechas reales de RenfyGrid frente a este mapa (función por función)

Cruzando el mapa de arriba contra la matriz funcional actual (`05-ejecucion.md`, 51 funciones) y
las 3 pantallas de la propuesta visual ya mostrada:

| # | Brecha encontrada | Evidencia del mercado | Estado real en RenfyGrid |
|---|---|---|---|
| G1 | **Sin distinción de origen de la petición** (CIS externo vs Portal/operador) en `control_order` ni en lecturas bajo demanda | Todo MDM de referencia rastrea el origen de cada "service order" | `requested_by` es texto libre, sin convención — hoy no se puede filtrar "qué pidió el CIS" |
| G2 | **Sin comando de estado/"ping"** — solo lectura completa o nada | "command activities: connect, disconnect, **ping**, on-demand read" es el set estándar | No existe — F07/F29 solo cubren connect/disconnect/lectura |
| G3 | **Sin panel de "Service Orders"/Integraciones** unificado | Es una pantalla propia en toda arquitectura de referencia (Oracle Service Order Management) | Hoy `control_order` vive dentro de "Control (SCR)", sin visibilidad de las peticiones de lectura/rango de datos que también vienen del CIS |
| G4 | **Sin vista de flota por marca/modelo** | Todo MDM de referencia reporta por fabricante/modelo (multi-vendor es la norma, ver §1) | `meter.brand`/`meter.model` existen en el esquema desde Sprint 1 — nunca se agregaron en una vista |
| G5 | **Sin vista de la capa de agregación** (concentradores/gateways, su ciclo de polling, qué marcas agrupan) | Los concentradores son "el núcleo de gestión de datos y energía en un AMI... con herramientas de diagnóstico para monitoreo de red" ([EDN](https://www.edn.com/data-concentrators-and-the-smart-grid/), [TI](https://www.ti.com/lit/pdf/spry248)) | `gateway`/`meter_gateway` existen desde Sprint 0-1 — el Portal nunca los muestra, solo el medidor individual |
| G6 | **Editor de reglas sin el mapeo OBIS** | — | `meter_protocol.obis_mapping` (F06) es una tabla de configuración versionada igual que `vee_rule` — pero la pantalla Configuración (Sprint C3) solo cubre las otras 3, esta se sigue editando por SQL/script directo |
| G7 | **Sin navegación real** (jerarquía de pantallas visible) | Todo NOC/MDM de referencia usa un panel lateral con las etapas siempre visibles | El Portal hoy es un header simple con 2 links — confirmado por el propio usuario ("se ve básico") |

**Lo que NO es una brecha real** (para no inflar el alcance): el motor VEE de RenfyGrid ya hace
"exception management" igual que Landis+Gyr MDMS ("procesa las excepciones de validación y
estimación que las reglas VEE no resuelven solas" — [Landis+Gyr](https://www.landisgyr.com/product/mdms/)) — F14-F19 ya cubren esto, es la pantalla la que no lo comunica bien.

---

## 4. Sitio completo del Portal Web (propuesta, sitemap)

Con las brechas de arriba, el sitemap completo queda así — lo ya construido, sin tocar su lógica
interna, más lo nuevo:

```
Nivel 1  Vista general           [rediseño visual — mockup ya mostrado]
Nivel 2  HES / Ingesta           [rediseño — flota por marca/modelo + agregación — mockup ya mostrado]
Nivel 2  Validación (VEE)        [existente, sin cambios de lógica — solo el rebranding]
Nivel 2  Consumos                [existente, sin cambios de lógica — solo el rebranding]
Nivel 2  Control (SCR)           [existente — se reencuadra como "Órdenes de servicio manuales"]
Nivel 2  Integraciones (CIS)     [NUEVO — mockup ya mostrado — unifica control_order + lecturas
                                   bajo demanda de origen CIS, con el comando "ping" nuevo]
Nivel 2  Observabilidad          [existente, sin cambios de lógica]
—        Configuración           [existente + sección nueva: mapeo OBIS por marca/modelo (G6)]
Nivel 3  Detalle (medidor / lectura / orden / petición CIS)
```

---

## 5. Ajuste al plan de sprints

Los sprints nuevos se agregan a `04-plan-sprints.md` §9 (Track C), después de C4 (ya cerrado).
Ninguno reabre lógica de negocio ya construida y verificada — todos son: (a) una convención nueva
sobre un campo que ya existe, (b) un comando nuevo y acotado, o (c) una vista de agregación sobre
tablas que ya existen.

| Sprint | Objetivo | Entregable verificable |
|---|---|---|
| **C5** | Convención `requested_by` real (`cis:<sistema>` / `portal:<usuario>` / `system:<regla>`) aplicada en `control_order` y en la auditoría de lectura bajo demanda; comando de "ping"/estado (extensión menor de F07/F29); endpoint unificado `GET /integrations/service-orders` | Una petición simulada del CIS y una del Portal quedan diferenciables en un solo query, con el nuevo comando de ping probado contra el simulador real |
| **C6** | Pantalla **Integraciones (CIS)** real (mockup ya aprobado) sobre el endpoint de C5 | Un operador ve el log real, filtra por automático/manual, y el enlace a Configuración resuelve a la regla vigente real |
| **C7** | Endpoints de agregación: `GET /meters/fleet-summary` (por marca/modelo) y `GET /gateways` (con ciclo de polling y marcas agrupadas) — sobre tablas ya existentes, sin migración | Con datos reales de 2+ marcas y 2+ gateways, los conteos/porcentajes calculan correcto |
| **C8** | Pantalla **HES / Ingesta** rediseñada (mockup ya aprobado) sobre C7, tabla de medidores con columna de concentrador | La pantalla real muestra la flota agrupada y el estado real del último ciclo de cada gateway |
| **C9** | Rebranding: paleta/tipografía de rensoftlabs.com + navegación lateral real, aplicado a **todas** las pantallas existentes (VEE/Consumos/Control/Observabilidad/Configuración) sin tocar su lógica | Las 9 pantallas comparten el mismo shell visual; nada de lo ya verificado en Track A/C se rompe (correr de nuevo los `verify_*` existentes) |
| **C10** | Editor de mapeo OBIS (G6) en Configuración, mismo patrón que `vee_rule`/`consumption_anomaly_rule` | Un operador cambia el mapeo OBIS de una marca desde la UI (sin SQL) y el siguiente ciclo del poller ya lo usa — mismo criterio de verificación que ya se usó para F06 en Sprint 2 |

**Definition of Done igual que el resto del proyecto** (`04-plan-sprints.md` §5): nada de valores
fijos, prueba real contra el simulador o Postgres real, no solo diseñado.
