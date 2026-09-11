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
