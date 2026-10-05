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
- **La plataforma opera el sistema; la guía es el método** (corrección del usuario,
  2026-10-05; reemplaza el principio anterior "cada formato = una pantalla"). Las pantallas se
  organizan por tarea: operar, medir, mantener, cobrar y rendir cuentas. Los formatos de la
  guía (7A-7H, 4A-4B) salen como reportes o evidencia exportable con su nombre, para el taller,
  el programa y ARCA. Una junta que no tomó el taller debe poder operar igual. Las páginas de
  presentación (briefs, `site/mapa-funcional.html`) son material comercial, no especificación
  de pantallas.
- Mensajería a la comunidad (avisos de emergencia, recordatorios de pago) por WhatsApp vía
  Renfy Vox, no un canal propio.

### 11.1 Revisión del plan tras leer las guías completas (2026-10-05)

Fuente: `C:\PCGM\RENSOFTLABS\Clientes\ARCA\Guia3_digital.pdf` (67 págs., texto hasta la 57) y
`Guia4_digital.pdf` (48 págs., texto hasta la 38). La versión del 23-sep se armó con un resumen
de las guías; esta revisión es contra el texto completo. Lo que cambió:

**Hallazgos de la Guía 3 (operación y mantenimiento) que el plan anterior no tenía:**
1. **Los productos salen de las 6 actividades participativas, no solo de los formatos 7A-7H.**
   El ítem 7H enumera 13 productos finales: mapa técnico (AP1), semáforo técnico (AP2), revisión
   del tren de tratamiento (AP3), cloro (AP4 + 7B), bitácora (7C), plan de mantenimiento (7D +
   7G), saneamiento (AP5 + 7E), lodos (7F), bodega (7G.1), plan de emergencia (AP6), **plan
   mínimo de O&M** (sección 4), insumos para la Guía 6 (7G.2) y calendario de calidad (7G). El
   plan anterior omitía el tren de tratamiento, el plan mínimo de O&M y el tablero 7H.
2. **Componentes comunitarios ≠ `network_asset.type`.** El tipo actual de `network_asset` es
   urbano (`pipe|valve|tank|pump|meter|sensor`). La guía organiza el sistema así:
   - Agua: fuente → captación → desarenador → conducción (cámaras, pasos elevados, cruces de
     quebrada) → etapas de tratamiento → reservorio → red.
   - Saneamiento: baños/letrinas → cajas de revisión → red sanitaria → trampa de grasa → fosa
     séptica → PTAR → punto de descarga.
   - Más bodega/EPP y bitácoras, que también son "componentes" del semáforo.

   Se modela como **catálogo de tipos de componente** (semilla, no un enum en código).
3. **Mantenimiento disparado por evento.** La tabla de frecuencias de la guía dice "semanal *y
   después de lluvias*", "mensual *y después de movimientos de tierra*", "mensual *y ante
   quejas*". `maintenance_pm_plan` hoy solo tiene `interval_days`; hace falta un disparador por
   evento (el operador o la directiva registra "lluvia fuerte" y se generan las órdenes de los
   planes ligados a ese evento).
4. **El tipo "emergente"** (preventivo / correctivo / emergente) no existe en
   `maintenance_order.type` (`preventive|corrective|inspection`). La prioridad `emergency` no
   lo reemplaza: en la guía es un tipo de trabajo, no una urgencia.
5. **Calculadora de dosificación de cloro**, con su fórmula explícita:
   `g/día = (Q [L/s] × 86.400 × dosis [mg/L]) ÷ (% cloro activo × 10)`. Verificada contra la
   tabla de la guía: 0,1 L/s a 1,5 mg/L con hipoclorito al 65 % → 19,9 g/día. Las guardas
   también son explícitas: "nunca aumentar la dosis por intuición ni para compensar agua
   turbia". Si turbiedad > 5 UTN y el cloro sale bajo, la herramienta debe decir "revisar
   desarenador/filtros", no "subir dosis". Es una sugerencia orientativa, marcada como tal.
6. **Rutina diaria en 5 momentos** (inicio, mañana, durante el día, tarde, cierre), cada uno
   con qué revisar y qué registrar. La bitácora 7C registra 3 tomas (06:00, 12:00, 18:00):
   nivel del tanque en %, cloro aplicado, cloro residual, color/turbiedad (clara / turbia /
   color) y estado (bueno / alerta).
7. **Bodega como inventario real**: químicos con vencimiento, repuestos por diámetro,
   herramientas, EPP; entradas y salidas; lista mensual 7G.1 donde cada "No" o "En proceso"
   genera una acción con responsable y fecha. El CMMS hoy solo anota materiales al cerrar la
   orden, no lleva existencias.
8. **Saneamiento tiene registros propios.** Descargas productivas (quesera, chanchera, camal,
   textilera, conexiones clandestinas) con seguimiento; destino seguro de los lodos (quién los
   retiró y adónde); DBO/DQO como resultados de laboratorio que interpreta un técnico, nunca la
   herramienta.
9. **Plan de emergencia con 6 tipos semilla**: lluvias, sequía, rotura principal,
   contaminación, rebose de aguas residuales, colapso de fosa/planta. Cada uno con señales,
   primera acción, a quién avisar (directiva, GAD, ARCA, MSP, COE cantonal, ECU 911) y mensaje a
   la comunidad. Un E. coli positivo debe activar automáticamente el plan de contaminación.
10. **"Evaluar antes de comprar" + exigencia mínima a proveedores** (manual, capacitación,
    costos, repuestos, energía, lodos, garantía). Se vuelven campos de la ficha del componente
    y del proveedor.

**Hallazgos de la Guía 4 (administración, finanzas y tarifa):**
11. **Control dual del gasto.** Nadie autoriza y paga solo: presidencia autoriza, tesorería
    registra, comprobante archivado. Es un flujo de aprobación, no solo un registro.
12. **Siete tipos de movimiento**, cada uno con su documento de soporte y quién lo guarda:
    tarifa, acometidas nuevas, reconexiones, multas, venta de materiales, aportes/convenios con
    el GAD y gastos.
13. **La planilla de costos** clasifica por servicio (agua / saneamiento / compartido) × tipo
    (operación, preventivo, correctivo, administración, reserva) × frecuencia → costo mensual
    equivalente. **Los costos de O&M que ya registra RenfyGrid (horas, materiales, análisis,
    cloro consumido) deben alimentar esa planilla.** Es el punto de integración RenfyGrid →
    `renfy_pool`.
14. **Tarifa: 4 modalidades** (plana, por consumo, diferenciada para familias vulnerables, cargo
    fijo + variable). Se calcula por servicio y se suma, se le agrega un % de reserva acordado,
    se compara con la tarifa actual (con opción de ajuste gradual) y la aprueba la asamblea con
    fecha de vigencia. **Los ejemplos de la guía son casos de prueba verificables:**
    - Tarifa plana: 460 ÷ 80 = 5,75 + 10 % = 6,33 (agua); 80 ÷ 80 = 1,00 + 10 % = 1,10
      (saneamiento); total **USD 7,43**.
    - Bloques: cargo fijo 4,50 con 0-15 m³ incluidos, 16-25 m³ a 0,30, más de 25 m³ a 0,50.
      Para 20 m³ → **USD 6,00**.
    - Planilla de costos del ejemplo: agua 730 + saneamiento 35 + compartidos 135 = 900/mes.
15. **Morosidad escalonada** (1 / 2 / 3 / >3 meses), con acción, responsable e instrumento
    (Reglamento Interno / Estatuto). Las medidas las aprueba la asamblea y respetan el
    **derecho humano al agua**: la herramienta no corta sola.
16. **POA por áreas de gestión** (ecológica, operativa, administrativa-financiera,
    socioorganizativa, institucional), con responsable, cuándo, recursos y "quién puede apoyar"
    (MAATE, GAD, MSP, cooperación). El presupuesto se arma desde el POA, y el resultado
    (superávit / equilibrio / déficit) lleva una decisión recomendada.
17. **El informe de rendición de cuentas tiene 9 contenidos**, todos derivables de datos ya
    registrados: padrón, cumplimiento del POA, ingresos, gastos, comprobantes, morosidad, fondo
    de reserva, logros/pendientes y plan del próximo año.
18. **Los cargos varían por territorio** (p. ej., los gobiernos comunitarios de Santa Elena).
    Los roles van como catálogo configurable; lo obligatorio es la separación de funciones, no
    el nombre del cargo.

**Hallazgo transversal: autodiagnóstico de madurez.** Ambas guías abren con una verificación
inicial (Sí / Más o menos / No) y cierran con autoevaluación. A eso se suman las listas 4A
(administración, 9 ítems) y 4B (transparencia, 6 ítems) y los productos finales (7H y el
producto final de la Guía 4). Juntos dan un **índice de madurez por junta**, medible antes y
después. Le sirve a la junta para ver su avance, a la agrupación de juntas para saber cuál
necesita apoyo y como evidencia ante el ente rector, así que pasa a ser un sprint propio (D12).

**Normativa citada por las guías** (semilla del catálogo de Ecuador, por verificar vigencia):
- NTE INEN 1108 (2014), requisitos del agua potable.
- DIR-ARCA-RG-012-2022 y ARCA-DE-016-2022, control de calidad y anexos de muestreo.
- DIR-ARCA-RG-011-2022, uso eficiente.
- AM 097-A, Anexo 1 Libro VI TULSMA, descargas de efluentes.

**Reuso confirmado en el código actual:** `network_asset` + `network_zone` + mapa por sector
(`meter_geo`) para el mapa técnico; CMMS Fase 1 (`maintenance_order`, `maintenance_pm_plan`,
cuadrillas, códigos de falla, KPIs) para O&M; estimación VEE para consumo sin medidor. En
`renfy_pool`: cuotas, cartera, asambleas/actas, presupuesto, plan de compras, contabilidad. **Antes
de D8-D11 hay que cruzar cada ítem contra lo que `renfy_pool` ya tiene**, para no duplicar.
Ojo: la contabilidad está montada sobre PUC colombiano y la junta ecuatoriana lleva libro de
caja simple en USD.

### 11.2 Sprints revisados (orden de valor para un piloto)

| Sprint | Dónde | Qué entrega | Productos de la guía que cubre |
|---|---|---|---|
| **D0** Motor de paquetes + base comunitaria | RenfyGrid | **Las piezas genéricas del motor** (ver §11.3): catálogo de tipos de componente, parámetros y reglas con fuente y vigencia, listas de verificación con acción por hallazgo, documentos con plantilla, jerarquía entidad → prestador y nivel de instrumentación por módulo. **Sobre ellas, el paquete Ecuador + Municipios Azules cargado como datos:** el sistema como recorrido encadenado, **mapa técnico** con puntos críticos, **semáforo por componente**, **revisión del tren de tratamiento**, verificación inicial de las dos guías | AP1, AP2, AP3, verificación inicial G3/G4 |
| **D1** Operación diaria (PWA sin conexión) | RenfyGrid | App del operador: rutina en 5 momentos; **bitácora 7C** (3 tomas/día); **cloro 7B** por punto (salida de tanque, medio, lejano, crítico) con rotación semanal e interpretación bajo/adecuado/alto según el catálogo del país; turbiedad, pH, color; **calculadora de dosificación** con guardas; alertas a la directiva; lectura manual de micro y macromedidor | 7B, 7C, AP4, sección 3.3-3.5 |
| **D2** Calidad y laboratorio | RenfyGrid | Resultados de laboratorio (E. coli, coliformes, químicos por catálogo); E. coli positivo → alerta crítica y activación del plan de contaminación (D5); plan de muestreo por categoría poblacional (requiere el documento de ARCA); calendario de calidad | 7G (calidad), sección 3.4 |
| **D3** O&M comunitario | RenfyGrid (CMMS) | Tipo **emergente**; **planes por evento** (lluvia, movimiento de tierra, quejas) además de por tiempo; los 5 pasos del mantenimiento como checklist de cierre; **7A** y **7D**; mingas como recurso (participantes, horas donadas); **calendario anual 7G** con % de cumplimiento; ficha de proveedor/equipo ("evaluar antes de comprar"); timer systemd de `generate_due_pm_orders` (pendiente ya conocido) | 7A, 7D, 7G, sección 3.6 |
| **D4** Bodega y EPP | RenfyGrid | Inventario (químicos con vencimiento, repuestos, herramientas, EPP); entradas y salidas; cruce entre el cloro aplicado (bitácora) y las salidas de bodega; **lista 7G.1** mensual donde cada hallazgo genera una acción | 7G.1, sección 3.9 |
| **D5** Emergencias | RenfyGrid | Plan con los 6 tipos semilla, editable; contactos institucionales; activación manual o automática (por E. coli, turbiedad extrema o rebose); mensaje a la comunidad por WhatsApp vía Renfy Vox; revisión anual antes de lluvias | AP6, sección 3.11 |
| **D6** Saneamiento | RenfyGrid | Componentes de saneamiento; **7E**; **7F** con destino seguro de lodos; registro de descargas productivas con seguimiento; DBO/DQO como resultado de laboratorio; frecuencias propias (lodos al menos anual) | 7E, 7F, AP5, secciones 3.7-3.8 |
| **D7** Plan mínimo y Plan de Mejora | RenfyGrid | **Plan mínimo de O&M** (8 filas, precargado con los hallazgos); **ficha 7G.2** generada desde la evidencia: semáforo rojo, cloro bajo repetido en el punto lejano, "No" de 7A/7E/7G.1, etc.; **tablero 7H** de productos completos/pendientes | Sección 4, 7G.2, 7H |
| **D8** Padrón y caja | `renfy_pool` | Padrón con los campos de la guía, ligado a las conexiones de RenfyGrid; libro de caja con los 7 tipos de movimiento y su soporte; **control dual** (autoriza / registra / comprobante); recibos numerados; conciliación caja vs. banco | AP padrón, AP caja |
| **D9** Costos y tarifa | `renfy_pool` + integración | **Planilla de costos** (servicio × tipo × frecuencia → mensual), alimentada con los costos de O&M de RenfyGrid; **calculadora de tarifa** con las 4 modalidades (los ejemplos de la guía como pruebas); comparación con la tarifa actual y ajuste gradual; propuesta para la asamblea y vigencia | Planilla de costos, cálculo de tarifa |
| **D10** Recaudación y morosidad | `renfy_pool` | Día fijo de cobro; escalera 1/2/3/>3 meses configurable desde el reglamento; acuerdos de pago; incentivos aprobados por la asamblea; recordatorios por WhatsApp; sin corte automático | Sección de recaudación |
| **D11** POA, presupuesto y rendición | `renfy_pool` | POA por áreas de gestión; presupuesto desde el POA con superávit/déficit y decisión recomendada; **informe de rendición de cuentas** generado (9 contenidos); listas **4A** y **4B** | POA, presupuesto, rendición, 4A, 4B |
| **D12** Tablero de la agrupación + reporte al ente rector | RenfyGrid (vista multi-tenant) | Para una agrupación de juntas (asociación, ACC) que comparte técnico, compras o laboratorio: índice de madurez inicial vs. actual, alertas de calidad abiertas, cumplimiento del calendario, tarifa frente a costos, morosidad agregada. Para ARCA, reportes de cumplimiento exportables que la junta decide enviar (no acceso directo a los datos operativos) | Verificaciones inicial/final de G3 y G4 |

**Orden sugerido (revisado 2026-10-05, el cliente es la junta):** D0 → D1 → D2 → D3 → D8 →
D9 → D5 → D4 → D6 → D10 → D11 → D7 → D12. Primero lo que la junta usa todos los días (operar,
cloro, mantener), después lo que la sostiene (padrón, caja, tarifa), y al final la vista de la
agrupación. D8-D11 van en `renfy_pool`, después de cruzarlos con lo que ya existe allí. D9
depende de D3 para que los costos de O&M reales lleguen a la planilla.

### 11.3 Diseño agnóstico (2026-10-05)

Diseño funcional completo publicado para el asesor de negocio en
`https://renfygrid.rensoftlabs.com/plan/mapa-funcional.html` (fuente: `site/mapa-funcional.html`).
Parte de los briefs de rensoftlabs.com (`renfygrid-brief.html`,
`renfygrid-programas-brief.html`, `renfygrid-juntas-brief.html`) y de las Guías 3 y 4. El
cliente ya vio los briefs y la idea le suena; este diseño la vuelve funcionalidad. Requisito
del usuario: **debe servir para ARCA y también para otra entidad en otro país.**

**Tres fuentes de configuración sobre un motor único:**
1. **Motor común** (se programa una vez): componentes y su recorrido, puntos de control,
   parámetros con reglas, listas de verificación, registros de campo sin conexión, órdenes y
   planes por tiempo o evento, movimientos financieros con soporte, indicadores, alertas con
   canal y documentos generados desde plantilla.
2. **Paquete normativo, por país o regulador:** umbrales con fuente y vigencia, parámetros de
   laboratorio, plan de muestreo por población e instituciones a notificar. El paquete
   Ecuador/ARCA es el primero.
3. **Paquete de programa, por entidad:** nombres de los formatos, listas de verificación,
   autodiagnóstico de madurez, productos esperados y plantillas de informe y plan de mejora.
   El paquete Municipios Azules es el primero.

**Consecuencias para la construcción:**
- **Ningún formato de la guía se programa como pantalla propia.** 7A, 7E, 7G.1, 4A y 4B son
  la misma pieza (lista de verificación) con distinto contenido. 7G.2 y la rendición de cuentas
  son documentos con plantilla. Si una funcionalidad solo sirve con el nombre de un formato
  ecuatoriano, está mal ubicada.
- **Actores (aclarado por el usuario, 2026-10-05):**
  - **El cliente es la junta (JAAPS) o una agrupación de juntas.** Es quien opera y quien usa
    la plataforma.
  - **ARCA es el ente rector:** fija la norma e impulsa los programas, pero no opera ni compra.
  - **Los programas (p. ej., Agua Para Todos / Municipios Azules) capacitan y acompañan.**
  - Las agrupaciones tienen figura en la normativa ecuatoriana: la Guía 4 cita la *Guía para la
    conformación de Alianzas Público-Comunitarias (APC) y Comunitarias-Comunitarias (ACC)*
    (ARCA/CAF/GIZ/BMZ, 2023). No la tenemos; la citamos solo como referencia.
- **Jerarquía:** agrupación (opcional) → junta → sistema (agua y/o saneamiento) → componente.
  - Cada junta es un tenant aislado y dueña de sus datos.
  - La agrupación ve indicadores de sus juntas miembro solo con la adhesión de cada una. Hoy el
    aislamiento por RLS es por tenant; esa vista es nueva y debe diseñarse sin abrir el
    aislamiento entre juntas.
  - **Propuesta (por confirmar con el usuario):** ARCA y los programas reciben reportes que la
    junta decide enviar, en lugar de acceso directo a sus datos operativos.
- **Un producto con niveles, no dos productos.** Cada módulo tiene nivel básico (sin
  medidores), intermedio (macromedidor y lectura manual) y avanzado (telemedida, SIG,
  EPANET), configurable por prestador. Lo construido en los Tracks A–C es el nivel avanzado.
- **Una sola experiencia para la junta:** cobro y finanzas siguen en el motor de `renfy_pool`,
  integrados por debajo, sin que la junta vea dos aplicaciones.
- **El tablero de la agrupación (D12) va al final.** Como el cliente es la junta, primero va lo
  que ella usa a diario.

**Sin las Guías 1, 2, 5 y 6 (el usuario no las tiene, 2026-10-05). Decisión: no bloquean;
cada parte que dependía de ellas se resuelve así:**
- **G1 (diagnóstico, mapa, usuarios):** D0 hace su propio levantamiento con el mapa técnico
  (AP1 de la G3) y el padrón (G4). Con eso alcanza para operar.
- **G2 (gobernanza, Estatuto, Reglamento Interno):** cargos y escalera de morosidad son
  configurables por cada junta según su propio reglamento. La plantilla por defecto es la tabla
  de la G4 (1 / 2 / 3 / más de 3 meses).
- **G5 (ambiente, salud, higiene):** fuera del alcance inicial. La protección de fuentes entra
  como actividad del POA (gestión ecológica).
- **G6 (Plan de Mejora):** matriz genérica con las columnas de la ficha 7G.2 (problema,
  evidencia, acción, qué hace la junta, apoyo, costo, plazo/prioridad). Se ajusta si llega la
  G6.

**Decisiones abiertas:**
- **Plan de muestreo vigente de ARCA.**
- **Contabilidad:** si cada paquete de país trae su plan de cuentas. El motor de `renfy_pool`
  usa el PUC colombiano; la junta lleva libro de caja en USD.
- **Qué reportes y con qué frecuencia espera ARCA de una junta** (si existe un formato
  oficial).

### 11.4 D0 — diseño detallado y estado (iniciado 2026-10-05)

El usuario confirmó la propuesta de reportes a ARCA (la junta decide qué envía) y autorizó
arrancar D0.

**Principio de modelado:** catálogos globales para lo que define un paquete; tablas por tenant
(con RLS) para lo que hace cada junta.
- Los catálogos globales no tienen `tenant_id`. El rol de aplicación solo puede leerlos
  (`REVOKE INSERT, UPDATE, DELETE`): una junta no puede alterar el paquete de otra.
- Los paquetes se cargan por migración o semilla versionada, nunca desde la UI de una junta.

**Modelo de datos (migración `0021_community_packs.sql`):**

| Tabla | Alcance | Para qué |
|---|---|---|
| `pack` | global | Paquete: `core`, `EC-ARCA` (normativo), `EC-MUNICIPIOS-AZULES` (programa). Tipo, país, versión, nota de fuente |
| `tenant_pack` | tenant (RLS) | Qué paquetes adoptó cada junta. `core` siempre aplica |
| `component_type` | global | Catálogo de tipos de componente: servicio (agua / saneamiento / soporte), orden en el recorrido, si es etapa de tratamiento. **Reemplaza el conjunto fijo `ASSET_TYPES` de `asset_service.py`**; los 6 tipos urbanos quedan como filas del paquete `core`. `network_asset.type` pasa a ser FK a este catálogo |
| `parameter` / `parameter_rule` | global | Parámetro (unidad, campo o laboratorio) y regla por paquete: bandas ordenadas (valor máximo, código, etiqueta, severidad), cita de la fuente y vigencia. Ecuador: cloro residual 0,3–1,5 mg/L, turbiedad ≤ 5 UTN, pH 6,5–8,5, E. coli ausente |
| `checklist_template` | global | Lista de verificación: escala de respuesta (cuáles generan hallazgo) e ítems. Semillas del programa: 7A, 7E, 7G.1, semáforo (AP2), verificación inicial G3 y G4, 4A, 4B, con el texto literal de las guías |
| `checklist_run` / `checklist_answer` | tenant (RLS) | Aplicación de una lista por la junta: respuesta, observación, acción, responsable, fecha |
| `finding` | tenant (RLS) | **Hallazgo**, la pieza que conecta todo: punto crítico del mapa técnico, respuesta "No" de una lista, lectura fuera de rango (D1). Tiene prioridad, nivel de apoyo (comunidad / gobierno local / especializado), estado y la marca "pasa al plan de mejora". Es la fuente de 7G.2 (D7) |

**Reportes que salen de la operación (no pantallas):** el recorrido del sistema (activos +
`asset_connectivity`), el tren de tratamiento (AP3: etapas registradas, estado y hallazgos
abiertos), el semáforo vigente (última aplicación de AP2) y el mapa técnico (GeoJSON de
componentes + hallazgos con ubicación).

**Nivel de instrumentación por módulo:** en `tenant.config` (`instrumentation`:
`basic` / `intermediate` / `advanced` por módulo), sin migración, mismo patrón que
`tenant_settings.py`.

**Fuera de D0:** la agrupación de juntas (D12) y los roles de operador/directiva con permisos
(llegan con la app del operador en D1; hoy `role_permission` está vacía y los roles en uso son
`supervisor` e `integration`).

| Subsprint | Entrega | Estado |
|---|---|---|
| **D0.1** | Migración 0021 + semillas de los 3 paquetes + motor puro (`services/community/pack_engine.py`: evaluar regla, respuesta → hallazgo, validar aplicación, tren de tratamiento) con pruebas unitarias + servicio con BD + E2E local contra Postgres | ✅ Hecho 2026-10-05 (local) |
| **D0.2** | Endpoints en `portal-api` (paquetes, tipos, reglas y evaluación, listas y aplicaciones, hallazgos, reportes, nivel de instrumentación) + `asset_service` leyendo el catálogo | ✅ Hecho 2026-10-05 (local) |
| **D0.3** | Portal Web: "Mi sistema" (recorrido, semáforo, tren de tratamiento, hallazgos), "Revisiones" (aplicar una lista, historial) y paquetes/niveles en Configuración | 🔶 Construido, compila; falta revisión visual en navegador |
| **D0.4** | Junta demo (caso ficticio de la Guía 3) + despliegue a producción con respaldo previo (`pg_dump`) + verificación en vivo + bitácora en `05-ejecucion.md` | 🔶 Semilla lista y probada en local; despliegue pendiente de autorización |

### 11.5 Modelo comercial, criterio de éxito y pendientes

**Modelo comercial (revisado 2026-10-05; reemplaza la hipótesis "la junta no paga").** El
cliente es la junta o la agrupación.
- **Presupuesto real:** una junta como la de la G4 maneja ~USD 7.000/año. La suscripción tiene
  que caber en sus **costos de administración**, la misma categoría donde la guía pone
  papelería, recibos y trámites, y reemplaza parte de ellos.
- **Por qué paga:** la plataforma le ayuda a calcular una tarifa que cubra sus costos reales,
  incluida la propia herramienta.
- **Precio:** por conexión o por tramo de tamaño. A la agrupación le conviene comprar para
  varias juntas y compartir técnico, compras y laboratorio.
- **Subsidio:** programas, GAD o cooperación pueden financiar el arranque, pero el modelo no
  depende de ellos.
- **Precio sin definir:** no se cita cifra hasta validarla en el piloto.
- **Desalineación con el sitio:** los briefs públicos de rensoftlabs.com
  (`renfygrid-programas-brief.html`, `renfygrid-juntas-brief.html`) todavía dicen "licencia
  por programa / la junta no paga". Están desalineados; actualizarlos es decisión del usuario.

**Criterio de éxito del piloto (3-5 juntas, idealmente de una misma agrupación).** Que el operador registre
cloro y bitácora desde el celular sin conexión, que la directiva vea el semáforo y el calendario
cumplidos, y que la tesorería llegue a la asamblea con la tarifa calculada y la rendición de
cuentas generada por la herramienta, no en papel.

**Pendiente de verificar antes de construir:**
- Cuántas JAAPS hay en Ecuador y en qué programas están (no se cita cifra sin fuente).
- El plan de muestreo vigente de ARCA por categoría poblacional (anexos de ARCA-DE-016-2022).
- Contacto real en Corporación Agua Para Todos.
- Guías 1, 2, 5 y 6: el usuario no las tiene (2026-10-05); ya no bloquean (ver §11.3). Si
  llegan, se ajustan D0, D10 y D7.
- Págs. 58-67 (G3) y 39-48 (G4) no tienen texto extraíble; probablemente son imágenes o
  contraportada. Revisarlas visualmente.

Estado: **aprobado, plan revisado 2026-10-05, D0 en curso** (ver §11.4).
