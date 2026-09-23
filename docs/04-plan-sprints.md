# Plan de Desarrollo Ágil por Sprints — RenfyGrid (MDM/AMI)

**Fecha:** 2026-09-09 · **Estado:** Fase 4 de 4 (Planteamiento ✅ → Arquitectura general ✅ → Diseño ✅ → **Plan de sprints**)

Cierra el ciclo de planeación. A partir de acá, cualquier trabajo es implementación real —
nada de código se toca hasta que este plan se valide.

---

## 1. Alcance del MVP / piloto

Para no repetir el patrón de 2024 (propuesta grande, ninguna oportunidad avanzó), el MVP se
acota a lo mínimo que demuestra el ciclo completo Meter-to-Cash con un solo tenant real:

**Entra al MVP:**
- Un (1) protocolo de medidor: **DLMS/COSEM** vía Gurux (el más común en el mercado
  eléctrico colombiano).
- Un (1) tenant piloto.
- Pipeline VEE completo (validación → estimación → edición), reglas ya parametrizadas en BD.
- Gestión de Consumos básica (agregación + reglas de crítica simples).
- Módulo SCR con **aprobación humana obligatoria en el 100% de las órdenes** (default más
  seguro; se evalúa automatizar reconexión de bajo riesgo después de validar el piloto).
- Portal/API mínima multi-tenant (medidores, consumos, eventos, solicitud de control).
- Bus de eventos: **Redis Streams** (menor costo operativo que RabbitMQ/Kafka para el
  volumen de un piloto; se reevalúa si el volumen real lo exige).
- Autenticación: JWT propio (sin Keycloak todavía — se suma si un tenant exige SSO).

**No entra al MVP** (documentado ya en el planteamiento, Fase 1 §4): CIS/facturación
completo, GIS/SCADA/ADMS/OMS, app móvil de campo, BI avanzado, adaptadores de agua/gas.

**Balance de Red y Modelado de Red** (agregados al alcance 2026-09-10, ver
`01-planteamiento.md` §3-4) **tampoco entran a este MVP** — no porque estén descartados, sino
porque responden a una motion comercial distinta (venta modular a utilities grandes, no al
piloto SMB). Van como **Track B**, en paralelo y sin bloquear el Track A (§3-4 de este
documento) — ver §8.

## 2. Supuestos de equipo y cadencia (ajustable)

- **Equipo asumido**: 2 desarrolladores backend + 1 QA a medio tiempo + el usuario como
  Product Owner / arquitecto. Si el equipo real es distinto, los sprints se comprimen o
  alargan proporcionalmente — la secuencia de épicas no cambia.
- **Sprint**: 2 semanas, con planning, daily async, review y retro al cierre de cada uno.
- **Duración estimada del MVP completo**: 10 sprints (~5 meses) hasta piloto en producción
  con el primer tenant real.

## 3. Épicas

| # | Épica | Objetivo |
|---|---|---|
| E0 | Fundaciones de plataforma | Multi-tenant, auth, esquema BD base, patrón "config cacheada" (cero hardcode), **clúster k3s** |
| E1 | Adaptador HES (DLMS/COSEM) | Lectura remota real de medidores, normalización con mapeo OBIS |
| E2 | Motor VEE | Validación, estimación, edición — reglas versionadas en BD |
| E3 | Gestión de Consumos | Agregación, reglas de crítica, preparación de facturación |
| E4 | Módulo SCR | Flujo de aprobación y ejecución de órdenes de control |
| E5 | Portal/API multi-tenant | Único punto de entrada para el tenant piloto |
| E6 | Hardening + Observabilidad | Seguridad del canal de control, métricas, alertas |
| E7 | Piloto en producción | Despliegue real, acompañamiento, ajuste con datos reales |

## 4. Roadmap de sprints

| Sprint | Épica(s) | Objetivo del sprint | Entregable verificable |
|---|---|---|---|
| **0** | E0 | Repo, CI/CD, **clúster k3s bootstrapeado** (ver `02-arquitectura-general.md` principio 4), esquema BD inicial (`tenant`, `meter`, `meter_protocol`, `vee_rule` versionadas) corriendo fuera del clúster, auth JWT, librería compartida del patrón "config loader → snapshot cacheado" | Un servicio dummy desplegado como pod en k3s lee su config desde snapshot, no desde código |
| **1** | E1 | Adaptador HES conecta a un medidor/simulador DLMS/COSEM real vía Gurux | Lectura real ingresa a `raw_reading` (Timescale) |
| **2** | E1 | Mapeo OBIS configurable por marca/modelo (desde BD, cacheado), manejo de reintentos/caída de concentrador | Cambiar el mapeo en BD sin desplegar código cambia el parseo |
| **3** | E2 | Motor VEE: validación (rangos, formato, coherencia) sobre lecturas reales del piloto | Lecturas fuera de rango quedan marcadas, con regla trazable |
| **4** | E2 | Motor VEE: estimación (método configurable) + edición manual auditada | Historias de usuario de diseño (Fase 3 §5) verificadas una a una |
| **5** | E3 | Gestión de Consumos: agregación de lecturas validadas + reglas de crítica simples | API de consumo facturable responde para el tenant piloto |
| **6** | E4 | Módulo SCR: modelo de estados de orden + flujo de aprobación humana | Una orden de prueba pasa por `requested→pending_approval→approved` con auditoría |
| **7** | E4 | SCR: ejecución real del comando vía adaptador HES + confirmación | Suspensión/reconexión real (o en simulador si el piloto aún no tiene medidor con switch) |
| **8** | E5 | Portal/API: medidores, consumos, eventos, solicitud de control — con RLS end-to-end | Un usuario del tenant piloto solo ve sus propios datos, verificado con un segundo tenant de prueba |
| **9** | E6 | Hardening: auditoría inmutable end-to-end, métricas de ingesta, alertas de caída | Panel de observabilidad mínimo funcionando |
| **10** | E7 | Piloto real: despliegue con el tenant, ajuste de reglas VEE con datos de producción | Primer ciclo de facturación completo corrido con datos reales |

## 5. Definition of Ready / Definition of Done

**Ready** (una historia entra a un sprint si):
- Tiene criterios de aceptación claros y **ningún valor hardcodeado propuesto** (si una
  historia implica un umbral/mapeo fijo, se rechaza en refinamiento hasta que se modele como
  configuración en BD).
- Depende solo de historias ya cerradas en sprints previos.

**Done** (una historia se cierra si):
- Pasa pruebas automatizadas + revisión de código.
- Si toca el motor VEE o el módulo SCR: tiene prueba de auditoría (que quede registro
  trazable de la acción).
- Si introduce una nueva configuración: existe su tabla en BD y su snapshot cacheado — no
  queda un valor "temporal" en código.

## 6. Riesgos y dependencias por sprint

- **Sprint 0 (k3s)**: es scope agregado a lo que originalmente era "solo esquema BD + config
  cacheada" (decisión de K8s día 1, ver `02-arquitectura-general.md` principio 4, tomada
  2026-09-10). Ningún integrante del equipo tiene experiencia previa de K8s en el portafolio
  — dejar tiempo real de aprendizaje/bootstrap en el sprint, no asumir que es trivial.
- **Sprint 1-2 (Adaptador HES)**: el riesgo mayor es no tener acceso a un medidor físico o
  simulador DLMS/COSEM confiable a tiempo — mitigar consiguiendo el simulador de Gurux desde
  el Sprint 0 en paralelo.
- **Sprint 6-7 (SCR)**: depende de que el medidor del piloto realmente soporte comando de
  corte/reconexión remoto — confirmar esto **antes** de comprometer el sprint, no durante.
- **Sprint 8 (Portal/RLS)**: probar aislamiento multi-tenant con un segundo tenant ficticio
  desde este sprint, no dejarlo para el final.

## 7. Criterios de éxito del piloto

- Ciclo Meter-to-Cash corrido de punta a punta con datos reales de al menos un medidor.
- Cero datos hardcodeados verificables en auditoría de código (todo trazable a una tabla de
  configuración).
- Al menos una orden de control ejecutada y confirmada end-to-end con auditoría completa.
- Feedback del tenant piloto documentado para decidir automatizar (o no) el nivel de
  aprobación del SCR en la siguiente iteración.

## 8. Track B — Balance de Red, Modelado de Red, Gemelo Digital y Mantenimiento (agregado 2026-09-10)

Corre **en paralelo** al Track A (§3-4), no antes ni después — son motions comerciales
distintas (SMB con paquete completo vs. utility grande comprando solo estos módulos) y
comparten poca superficie de código con el Track A (todos son servicios nuevos, independientes
de HES/VEE por diseño — `03-diseno.md` §7-8). Se activa cuando haya una oportunidad comercial
concreta que lo justifique, no por fecha fija. Orden interno del track: E8/E9 (Balance/Modelado)
antes de E10 (Gemelo Digital) porque son útiles solos con un modelo `.inp` cargado a mano; E10
los enriquece (deriva el modelo del inventario real) pero no los bloquea. E11 (Mantenimiento)
depende de E10 — necesita `network_asset` para saber sobre qué activo generar la orden.

| # | Épica | Objetivo |
|---|---|---|
| E8 | Motor de Balance de Red | `network_zone` jerárquica, ingesta externa, cálculo IWA Top-Down/Bottom-Up |
| E9 | Motor de Modelado de Red | Versionado de `network_model` (`.inp`), integración WNTR, simulaciones |
| E10 | Gemelo Digital | Inventario de activos (`network_asset`) y conectividad, sincronizable con SIG del cliente |
| E11 | Gestión de Mantenimiento | Generación de órdenes desde anomalías + integración con BayForce |

| Sprint | Épica | Objetivo | Entregable verificable |
|---|---|---|---|
| **B1** | E8 | Esquema `network_zone`/`network_balance` + endpoint de ingesta externa | Un balance calculado a partir de datos insertados vía API, sin medidor RenfyGrid de por medio |
| **B2** | E8 | Cálculo Top-Down y Bottom-Up configurable por zona | Balance reproducible con datos de ejemplo de una zona real (agua) |
| **B3** | E9 | Carga/versionado de modelo `.inp`, integración WNTR | Un modelo EPANET real se simula y devuelve resultados |
| **B4** | E9 | Vínculo Modelo↔Balance (calibración con datos de consumo real) | Escenario de simulación usa `network_balance` como insumo |
| **B5** | E10 | Esquema `network_asset`/`asset_connectivity` + ingesta externa (SIG) | Un activo cargado vía API queda visible con su conectividad |
| **B6** | E10 | `network_model` se puede **derivar** de `network_asset`+conectividad (export EPANET) | Un modelo generado desde el Gemelo Digital simula igual que uno cargado a mano |
| **B7** | E11 | Reglas de generación de orden desde anomalía + integración BayForce (`POST /integraciones/bayforce/ordenes`, webhook de vuelta) | Una anomalía de prueba genera una orden, se envía a BayForce (sandbox) y se cierra al recibir el webhook |

**Definition of Ready/Done igual que el Track A** (§5) — ningún umbral/fórmula de pérdida fijo
en código, todo trazable a `network_balance.method` o configuración de zona.

## 9. Track C — Portal Web (agregado 2026-09-10)

Corre **en paralelo** al Track A, igual que el Track B — pero a diferencia del Track B (que
depende de una oportunidad comercial concreta), el Track C responde a una necesidad ya
confirmada: hoy no existe ninguna UI para operar RenfyGrid (solo DBeaver y la API en crudo), y
el usuario confirmó que esta capa **es parte del producto real**, no una herramienta interna
temporal. Ver la investigación y las decisiones de arquitectura en `02-arquitectura-general.md`
§9 y el diseño de pantallas en `03-diseno.md` §9.

| # | Épica | Objetivo |
|---|---|---|
| E12 | Autenticación real + fundaciones del Portal Web | `app_user` + `POST /auth/login`; esqueleto React/Vite/Tailwind; Nivel 1 (Overview) |
| E13 | Pantallas de Nivel 2 (colas de excepción) | Medidores/HES, Validación (VEE), Consumos, Control (SCR), Observabilidad |
| E14 | Editor de reglas (Configuración) | Alta/versionado de `vee_rule`, `consumption_anomaly_rule`, `control_approval_level` desde la UI |
| E15 | Detalle y acciones (Nivel 3) | Aprobar/rechazar orden, editar lectura VEE, forzar lectura bajo demanda — todo accionable desde la UI, no solo lectura |
| 🆕 E16 | *(agregada 2026-09-11)* Integraciones (CIS) | Convención real de origen de la petición (`requested_by`: CIS externo / Portal / sistema) + comando de "ping"/estado nuevo + panel unificado de "Service Orders" — ver `06-benchmark-e2e-y-brechas.md` §2-3 |
| 🆕 E17 | *(agregada 2026-09-11)* HES / Ingesta — flota y agregación | Vista de flota por marca/modelo + capa de agregación (concentradores/gateways, ciclo de polling) — hoy el esquema ya tiene `brand`/`model`/`gateway` desde Sprint 0-1, nunca se agregaron en una vista |
| 🆕 E18 | *(agregada 2026-09-11)* Rebranding y navegación real | Paleta/tipografía de rensoftlabs.com + navegación lateral real en las 9 pantallas — hoy el Portal es un header simple con 2 links |
| 🆕 E19 | *(agregada 2026-09-11)* Editor de mapeo OBIS | `meter_protocol.obis_mapping` (F06) es una tabla de configuración versionada como las otras 3, pero nunca entró al editor de reglas (Sprint C3) — se sigue editando por SQL/script directo |
| 🆕 E20 | *(agregada 2026-09-11)* Cierre de los parciales del MVP | F08 (cola persistente de reintentos), F10 (particionado de `raw_reading`, sustituto real de TimescaleDB), F15 (coherencia entre canales), F17 (métodos de estimación restantes) — los 4 huecos parciales que quedaban en Track A después del benchmark E2E |
| 🆕 E21 | *(agregada 2026-09-11)* Paneles operativos por etapa, con benchmark real | El usuario pidió repetir el ejercicio de benchmark de mercado (E16-E19) pero **por módulo operativo** (VEE, HES, Control, Consumo) en vez de por el proceso E2E completo — cada panel pasa de "cola de excepciones sin contexto" a 3-4 KPIs reales + historial, grounded en fuentes reales de la industria (Oracle Utilities MDM, Itron, Landis+Gyr, Bynry, Grid/EPRI, CREG) |

| Sprint | Épica | Objetivo | Entregable verificable |
|---|---|---|---|
| **C1** | E12 | `app_user` + login real + esqueleto del SPA + tablero Nivel 1 | Un usuario real (no un JWT emitido a mano) inicia sesión y ve el tablero general con conteos reales de un tenant de prueba |
| **C2** | E13 | Los 5 tableros de Nivel 2, cada uno con sus propios KPIs y alertas | Cada tablero de etapa muestra solo lo anormal (medidor caído, lectura inválida, consumo en revisión, orden pendiente) — un tenant sin anomalías ve un tablero "limpio" |
| **C3** | E14 | Editor de reglas para las 3 tablas de configuración versionada | Un operador crea una nueva versión de `vee_rule` desde la UI (sin SQL) y el siguiente pase de validación ya la usa |
| **C4** | E15 | Pantallas de detalle (Nivel 3) con la acción de cada entidad | Un operador aprueba una orden de control y edita una lectura VEE, ambas desde la UI, sin usar `curl`/Postman/DBeaver |
| 🆕 **C5** | E16 | *(agregado 2026-09-11)* Convención `requested_by` (`cis:<sistema>` / `portal:<usuario>` / `system:<regla>`) aplicada en `control_order` y en la auditoría de lectura bajo demanda; comando de ping/estado (extensión menor de F07/F29); endpoint `GET /integrations/service-orders` | Una petición simulada del CIS y una del Portal quedan diferenciables en un solo query; el ping nuevo se prueba contra el simulador real |
| 🆕 **C6** | E16 | *(agregado 2026-09-11)* Pantalla **Integraciones (CIS)** real (mockup ya aprobado por el usuario) sobre el endpoint de C5 | Un operador ve el log real, filtra por automático/manual, y el enlace a Configuración resuelve a la regla vigente real |
| 🆕 **C7** | E17 | *(agregado 2026-09-11)* Endpoints de agregación: `GET /meters/fleet-summary` (por marca/modelo) y `GET /gateways` (ciclo de polling, marcas agrupadas) — sobre tablas ya existentes, sin migración | Con datos reales de 2+ marcas y 2+ gateways, los conteos/porcentajes calculan correcto |
| 🆕 **C8** | E17 | *(agregado 2026-09-11)* Pantalla **HES / Ingesta** rediseñada (mockup ya aprobado) sobre C7, tabla de medidores con columna de concentrador | La pantalla real muestra la flota agrupada y el estado real del último ciclo de cada gateway |
| 🆕 **C9** | E18 | *(agregado 2026-09-11)* Rebranding + navegación lateral aplicados a las 9 pantallas existentes, sin tocar su lógica | Las 9 pantallas comparten el mismo shell visual; todos los `verify_*` de Track A/C existentes siguen pasando sin cambios |
| 🆕 **C10** | E19 | *(agregado 2026-09-11)* Editor de mapeo OBIS en Configuración, mismo patrón que las otras 3 tablas versionadas | Un operador cambia el mapeo OBIS de una marca desde la UI (sin SQL) y el siguiente ciclo del poller ya lo usa — mismo criterio de verificación que F06 en Sprint 2 |
| 🆕 **C11** | E20 | *(agregado 2026-09-11)* Cola persistente de reintentos (F08, `poller_retry_queue`), particionado nativo de `raw_reading` (F10, sustituto real de TimescaleDB), coherencia entre canales (F15, `channel_consistency`), 2 métodos de estimación restantes (F17) | Los 4 `verify_*_end_to_end.py` nuevos pasan contra Postgres real; regresión completa de Track A/C sigue en verde |
| 🆕 **C11-2/3** | E21 | *(agregado 2026-09-11)* Panel de Validación (VEE) por etapa V/E/E, cada una con sus KPIs reales (tasa de excepción con banda de color, tendencia 7 días, % de la serie estimada por método, historial real de ediciones) | El usuario confirma que el panel ya no "se ve como un bosquejo" — 3 secciones reales, no una tabla plana |
| 🆕 **C11-4** | E21 | *(agregado 2026-09-11)* Panel de HES/Ingesta: eventos/alarmas reales (F05) + auditoría de comunicación (F09) + cola de reintentos (F08) expuestas por primera vez | KPIs de alarmas/éxito de comunicación/medidores en cola, feed filtrable por tipo, todo sobre datos reales ya escritos por el backend, cero hardcode |
| 🆕 **C11-5** | E21 | *(agregado 2026-09-11)* Panel de Control (SCR): tasa de éxito de comando + historial real + **lista de cuentas protegidas contra suspensión/desconexión** (Ley 142 + normas CRA/CREG, migración `0012_meter_protection.sql`) con bloqueo real (422) salvo override auditado | Una orden de suspensión contra una cuenta protegida se rechaza de entrada; con override real, queda trazada con su propio motivo en la auditoría |
| 🆕 **C11-6** | E21 | *(agregado 2026-09-11)* Panel de Consumo: KPIs (tasa de anomalía, % listo para facturar) + feed real de órdenes de relectura/inspección (F23, invisible desde Sprint 5) + acción real de "Resolver" (`anomaly_status='resolved'`, en el esquema desde Sprint 0, nunca escrito) | Una anomalía investigada se cierra desde la UI; intentar resolverla dos veces da 404, no un éxito falso |

**Definition of Ready/Done igual que el Track A** (§5), con un agregado propio de UI: ninguna
pantalla de Nivel 2/3 puede mostrar una tabla cruda como su vista por defecto — el patrón
"exception-first" (§9 de `02-arquitectura-general.md`) es un criterio de aceptación, no una
sugerencia de diseño. Los sprints **C5-C11-6** (agregados 2026-09-11) siguen el mismo criterio;
ninguno reabre lógica ya verificada — ver `06-benchmark-e2e-y-brechas.md` para el benchmark
E2E de mercado (C5-C10) y `05-ejecucion.md` (bitácora de Sprint C11 en adelante) para las
fuentes del benchmark por módulo (C11-2 a C11-6).

## 10. Próximos pasos

**Estado real (actualizado 2026-09-10, ver `docs/05-ejecucion.md` para el detalle verificado):**
Track A (Sprints 0-10) está construido y verificado end-to-end salvo lo que depende
explícitamente de un tenant piloto real (F05/F07). Track B (§8) sigue sin iniciar, a la espera
de una oportunidad comercial concreta. **Track C (§9), el Portal Web, es el próximo trabajo de
desarrollo real** — parte de una necesidad ya confirmada por el usuario, no de una oportunidad
por confirmar como el Track B.

**Actualización 2026-09-11**: Track C (C1-C4) se cerró y se desplegó a producción
(`docs/05-ejecucion.md`). El usuario pidió un benchmark E2E del proceso completo Meter-to-Cash
contra las herramientas líderes del mercado (`docs/06-benchmark-e2e-y-brechas.md`) — de ahí
salieron las épicas **E16-E19** y los sprints **C5-C10**, ya incorporados a la tabla de §9.

**Actualización 2026-09-11 (cierre de sesión)**: C5-C10 se cerraron y desplegaron. El usuario
pidió cerrar los 4 parciales que quedaban en Track A (**C11**, épica E20) — no Track B, que
sigue sin una oportunidad comercial concreta — y después repetir el benchmark de mercado, esta
vez módulo por módulo (**C11-2 a C11-6**, épica E21): VEE, HES/Ingesta, Control (SCR) y Consumo.
De Control salió un hallazgo real fuera del alcance de UI — la lista de cuentas protegidas
contra suspensión (Ley 142/CREG), confirmada y construida con el usuario. **Con esto, Track A y
Track C están completos salvo lo que depende de un piloto real (F05 operando en producción,
F07) o de elegir un CIS real (F25)** — ninguno de los dos es trabajo de desarrollo pendiente,
son bloqueos externos ya documentados. Track B sigue siendo el único bloque grande sin empezar,
deliberadamente pospuesto hasta que haya una oportunidad comercial real.

**Actualización 2026-09-11/14: Track B activado y completado (B1-B7)**. El usuario confirmó
activar Track B ("vamos con el Track B... investigación profunda de mercado... y luego sí
implementas") — investigación real de mercado y alcance funcional documentados en
`docs/07-track-b-alcance-funcional.md` antes de escribir código. Las 7 épicas (E8-E11, sprints
B1-B7) se construyeron completas: Balance de Red (Top-Down/Bottom-Up reales, AWWA M36/IWA),
Modelado Hidráulico (WNTR/EPANET real), un módulo de georreferenciación nuevo (compartido entre
módulos, patrón tomado de "Mapa de Deuda" de RenFlow), calibración real Modelo↔Balance,
Gemelo Digital (inventario de activos + conectividad), generación de modelo desde el Gemelo
Digital, y Gestión de Mantenimiento con el contrato real de integración BayForce (probado de
punta a punta contra un sandbox local real). Todo con E2E real, regresión completa verde en
cada sprint, y desplegado a producción.

**Estado real al cierre de esta ronda: los tres tracks (A, B, C) están completos.** Lo único que
queda en la matriz funcional sin cerrar son 3 ítems bloqueados por dependencias externas, no por
trabajo de desarrollo pendiente: **F07** (comandos SCR contra un medidor real — necesita un
piloto real operando), **F25** (contrato de entrega a CIS — depende de elegir un CIS real),
**F45** (conexión viva a BayForce — necesita su URL/credenciales de sandbox o producción
reales). Ninguno de los tres se puede avanzar con más código desde esta sesión; los tres
requieren un insumo externo concreto del usuario.

## 9. Corrección real sobre F45/Mantenimiento + CMMS propio de RenfyGrid (2026-09-14)

**El usuario señaló, viendo el panel real, que Mantenimiento "es un dibujo y nada más" — sin
parametrización de órdenes, planeación ni despacho.** Al investigar a fondo (pedido explícito:
"analiza los estándares de industria... y pule lo que sea relevante" sobre usabilidad, extendido
después a un análisis serio de alcance de Mantenimiento), se encontró que la descripción de F45
como "bloqueado solo por credenciales" **era inexacta**:

- Leído `core/renflow/bayforce/main.py` completo (9400 líneas, otro producto del portafolio):
  BayForce **no tiene ningún endpoint de creación de orden externa genérico** — todo lo que
  entra a `field_orders` viene del workflow de cobro propio de RenFlow (`subscriber_id`/
  `execution_id`, numeración `RF-...`). El contrato que `order_service.send_to_bayforce()`
  asume (`POST` con `{renfygrid_order_id, tenant_id, asset_id, type, source, reason}`) no tiene
  nada real del otro lado que lo reciba, con o sin credenciales. Detalle completo y decisión en
  `contextos/renflow/docs/BAYFORCE_RENFYGRID_INTEGRATION_NOTE.md` (repo de contextos local, no
  en este repo — cruza a otro producto).
- Además, Mantenimiento nunca tuvo la sustancia real de un CMMS (grounded en Cityworks —
  referencia dominante en acueducto/alcantarillado — y las métricas estándar MTTR/MTBF/%
  cumplimiento PM): sin prioridad/SLA, sin códigos de falla, sin mantenimiento preventivo
  programado (`preventive` era solo una etiqueta, nunca se auto-generaba nada), sin
  planeación/asignación de cuadrilla, sin cierre con horas/materiales, sin KPIs.

**Decisión de arquitectura (con el usuario, evaluando si esto viola la filosofía de
microservicios — no la viola si se separa correctamente en dos capas):**

| Capa | Naturaleza | Decisión |
|---|---|---|
| Parametrización del dominio (prioridad/SLA, códigos de falla, PM programado, ciclo de vida, cierre, KPIs) | Dominio propio real de RenfyGrid — activos de red, zonas, NRW, EPANET; BayForce nunca lo sabrá | **RenfyGrid lo construye y lo posee**, mismo patrón que Balance de Red/Gemelo Digital |
| Motor de despacho/ruteo (cuadrillas, turnos, OR-Tools, ejecución móvil) | Tecnología genérica y cara, BayForce ya la tiene resuelta y bien construida | **RenfyGrid NO la reconstruye** — usa algo proporcionado (cuadrilla/técnico simple + calendario), nunca un motor de ruteo propio |
| Consolidar BayForce como servicio de plataforma compartido (API de intake genérica multi-dominio) | Decisión de negocio/arquitectura que toca otro producto en vivo | **Explícitamente diferida, NO autorizada** — requiere conversación aparte con el usuario antes de tocar `core/renflow/bayforce` |

**Alcance real de la capa de dominio a construir (F45 se reformula — deja de ser "conexión
BayForce" como única pieza pendiente):**
- Prioridad (`low`/`medium`/`high`/`emergency`) con SLA objetivo configurable por tenant/prioridad
  (nunca un umbral fijo en código).
- Catálogo de códigos de falla (tabla, no un `dict` — mismo patrón semilla+catálogo del resto
  del proyecto).
- Mantenimiento preventivo programado: plan por tipo de activo con disparador por tiempo
  (calendario), genera la orden solo cuando el plan vence de verdad.
- Ciclo de vida real: `generated → scheduled → assigned → in_progress → completed | cancelled`
  (más rico que el actual `generated → sent_to_bayforce → in_progress → completed`).
- Cierre con horas de mano de obra, materiales usados y causa raíz.
- Asignación simple a cuadrilla/técnico (lista configurable) + vista de calendario en el Portal.
- KPIs reales: MTTR, backlog (abiertas + antigüedad), % cumplimiento PM, órdenes vencidas de SLA.
- BayForce se mantiene como notificación de salida OPCIONAL (el webhook actual), nunca como la
  columna vertebral del módulo.

Pendiente de implementar — siguiente sesión/ronda de trabajo sobre Mantenimiento.

## 11. Track D — Prestadores comunitarios / juntas de agua (aprobado 2026-09-23)

**Origen.** El usuario compartió las Guías 3 y 4 del Proyecto Municipios Azules (Corporación
Agua Para Todos, Ecuador): capacitación para las JAAPS (Juntas Administradoras de Agua Potable
y Saneamiento). Guía 3 = operación y mantenimiento técnico; Guía 4 = administración, finanzas
y tarifa. Cada guía termina en formatos concretos que la junta debe llevar (7A-7H, 4A-4B) y
que alimentan un Plan de Mejora (Guía 6). Esos formatos son la especificación de este track.

**Por qué es un track aparte.** Los tracks A-C suponen una empresa de acueducto con medición
inteligente (DLMS), SIG y modelo EPANET. La junta típica de los ejemplos de la guía (ficticios,
pero representativos) tiene 80-120 conexiones, tarifa de USD 5-7/mes, presupuesto de ~USD
7.000/año, muchas sin medidores (tarifa plana), sistemas por gravedad, energía limitada y
registros en papel. Sin este track, RenfyGrid no le sirve a ese segmento.

**Decisiones aprobadas por el usuario (2026-09-23):**
1. Se agrega este track al roadmap.
2. La capa administrativa/financiera (padrón, libro de caja, tarifa, morosidad, POA,
   presupuesto, rendición de cuentas, asambleas) **se construye sobre el motor `renfy_pool`**
   (el de Renfy Home: cuotas, cartera, asambleas), no dentro de RenfyGrid. Una junta de agua
   funciona igual que una copropiedad: asamblea, directiva, tesorería, cuota mensual,
   morosidad, reglamento interno. `renfy_pool` lo trabaja otro agente/sesión — **coordinar por
   el buzón antes de tocarlo** (tema `RENFY_POOL`).
3. **Excepción a la regla "RenfyGrid no construye app móvil" (§9 de este documento y `03-diseno.md`):** para
   este segmento se construye una app ligera del operador (PWA, **funciona sin conexión** y
   sincroniza al volver la señal). No es despacho ni ruteo (eso sigue siendo BayForce): son
   formularios de bitácora, lectura, cloro e inspección. Patrón de referencia en el
   portafolio: la PWA residente de `renfy_pool` (PLT-04).
4. Se preparan briefs propios para juntas y para programas/GAD (en el repo `rnsftlbs`).

**Principios del track:**
- Lenguaje sencillo, el mismo de las guías (operador, directiva, minga, bitácora, semáforo).
- Umbrales y reglas como **catálogo por país** (tabla semilla, nunca en código): Ecuador
  (NTE INEN 1108, lineamientos de ARCA), Colombia, etc. Los valores de referencia de la guía
  (cloro residual 0,3-1,5 mg/L en red, turbiedad ≤ 5 UTN, pH 6,5-8,5) son la semilla de
  Ecuador, marcados como "referencia operativa", no como la norma completa.
- Cada formato de la guía = una pantalla o un reporte exportable con el mismo nombre, para
  que lo aprendido en el taller se reconozca en la herramienta.
- Mensajería a la comunidad (avisos de emergencia, recordatorios de pago) por WhatsApp vía
  Renfy Vox, no un canal propio.

**Sprints propuestos (orden de valor para un piloto):**

| Sprint | Épica | Qué entrega | Formatos de la guía que cubre |
|---|---|---|---|
| **D1** | E22 Operación sin medición inteligente | Lectura manual (app del operador y carga por planilla), macromedidor del reservorio, balance simple agua producida vs. facturada por sector; modo tarifa plana (sin micromedición, consumo estimado) | Mapa técnico (Act. 1), base del cálculo de tarifa por consumo (G4) |
| **D2** | E23 Calidad del agua | Registro de cloro residual por punto (salida de tanque, punto medio, punto lejano/crítico) con interpretación automática bajo/adecuado/alto y alerta; turbiedad, pH, color; resultados de laboratorio (E. coli); calendario de muestreo | 7B, 7C (parte de calidad), 7G (análisis) |
| **D3** | E24 O&M comunitario | Sobre el CMMS existente: tipos preventivo/correctivo/emergente, componentes del sistema (captación → conducción → tratamiento → reservorio → red, y saneamiento), bitácora diaria, listas de inspección con semáforo verde/amarillo/rojo, calendario anual, mingas como recurso, bodega y EPP | 7A, 7C, 7D, 7G, 7G.1, semáforo (Act. 2) |
| **D4** | E25 Emergencias | Plantilla de plan de emergencia (lluvias, sequía, rotura, contaminación, rebose), activación, mensaje a la comunidad por WhatsApp e institución a notificar | Act. 6 |
| **D5** | E26 Saneamiento | Fosas, cajas de revisión, redes, PTAR, extracción de lodos con destino seguro, descargas productivas (queseras, chancheras, camales) | 7E, 7F, Act. 5 |
| **D6** | E27 Administración y tarifa (en `renfy_pool`) | Padrón de usuarios, libro de caja con comprobantes, costos reales (operación / mantenimiento preventivo / correctivo / administración / reserva, agua y saneamiento por separado), calculadora de tarifa (plana y cargo fijo + variable por bloques, con la fórmula de la guía), morosidad escalonada (1 / 2 / 3 / >3 meses), POA por área de gestión, presupuesto, informe de rendición de cuentas | 4A, 4B, productos finales de la Guía 4 |
| **D7** | E28 Plan de Mejora | Exporta la ficha de insumos para la Guía 6 desde los hallazgos de D1-D6 (problema, evidencia, acción, qué hace la junta, apoyo requerido, costo, plazo) | 7G.2, 7H |

**Modelo comercial (hipótesis a validar en el piloto).** La junta no compra software con un
presupuesto de ~USD 7.000/año. Paga el programa o el territorio: Corporación Agua Para Todos /
Municipios Azules, GAD municipales, ARCA o cooperación (CAF y GIZ aparecen en la bibliografía de
la Guía 4). Licencia por programa/GAD que cubre N juntas; la junta usa la herramienta sin costo.

**Criterio de éxito del piloto (3-5 juntas de un mismo programa).** Que el operador registre
cloro y bitácora desde el celular sin conexión, que la directiva vea el semáforo y el calendario
cumplidos, y que la tesorería llegue a la asamblea con la tarifa calculada y la rendición de
cuentas generada por la herramienta, no en papel.

**Pendiente de verificar antes de construir:** cuántas JAAPS hay en Ecuador y en qué programas
están (no se cita cifra sin fuente); el plan de muestreo vigente de ARCA por categoría
poblacional; contacto real en Corporación Agua Para Todos. Estado: **aprobado, sin iniciar**.
