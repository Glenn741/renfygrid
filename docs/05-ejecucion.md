# Ejecución — Matriz funcional y bitácora de sprints

**Última actualización:** 2026-09-11 (F05, retomado) · Documento vivo — se actualiza en cada avance real de
código, no por fecha. Complementa el Plan de sprints (`04-plan-sprints.md`).

---

## 1. Matriz funcional

51 funciones concretas derivadas del alcance (`01-planteamiento.md` §4) y del diseño
(`03-diseno.md`): 35 del Track A, 11 del Track B, 5 del Track C (Portal Web). Cada una mapeada
al sprint donde se construye y a su estado real.

**Leyenda de estado:** ⚪ Planeado · 🟡 En progreso · 🟢 Hecho (con evidencia verificable)

### HES (Head End System)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F01 | Registro de medidores/concentradores | 0-1 | 🟢 |
| F02 | Adaptador de protocolo DLMS/COSEM (Gurux) | 1 | 🟢 |
| F03 | Lectura remota programada (polling) | 1 | 🟢 |
| F04 | Lectura remota bajo demanda | 8 | 🟢 |
| F05 | Recepción de eventos/alarmas del medidor | 1-2 | 🟢 (retomado 2026-09-11, ver bitácora) |
| F06 | Mapeo OBIS configurable por marca/modelo (cacheado) | 2 | 🟢 |
| F07 | Envío de comandos SCR al medidor | 7 | ⚪ |
| F08 | Reintentos / cola ante caída de concentrador | 2, C11 | 🟢 (cola persistente con backoff exponencial, Sprint C11 — desplegado y verificado en producción, ver bitácora) |
| F09 | Auditoría de comunicación con dispositivos | 9 | 🟢 |

### Almacenamiento

| # | Función | Sprint | Estado |
|---|---|---|---|
| F10 | Ingesta de lecturas crudas (particionado por rango de tiempo) | 1, C11 | 🟢 (particionado nativo de Postgres, sustituto real de TimescaleDB, Sprint C11 — desplegado y verificado en producción, ver bitácora) |
| F11 | Metadatos de medidor/ubicación/catastro | 0-1 | 🟢 |
| F12 | Retención histórica configurable por tenant | 10 | 🟢 |
| F13 | Respaldo y recuperación | 9 | 🟢 |

### VEE (Validación · Estimación · Edición)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F14 | Validación de rangos (min/max configurable) | 3 | 🟢 |
| F15 | Validación de formato/coherencia/integridad | 3, C11 | 🟢 (coherencia entre canales, regla `channel_consistency`, Sprint C11 — desplegado y verificado en producción, ver bitácora) |
| F16 | Detección de intervalos faltantes | 4 | 🟢 |
| F17 | Estimación (método configurable por tenant) | 4, C11 | 🟢 (3/3 métodos: `customer_historical_average`/`similar_customers_average` agregados en Sprint C11 — desplegado y verificado en producción, ver bitácora) |
| F18 | Edición manual auditada | 4 | 🟢 |
| F19 | Versionado de reglas VEE (trazabilidad) | 0, 3-4 | 🟢 |
| F20 | Patrón de configuración cacheada (cero hardcode) | 0 | 🟢 |

### Gestión de Consumos

| # | Función | Sprint | Estado |
|---|---|---|---|
| F21 | Agregación de lecturas validadas en consumo | 5 | 🟢 |
| F22 | Reglas de crítica/desviación configurables | 5 | 🟢 |
| F23 | Órdenes de relectura/inspección | 5 | 🟢 |
| F24 | API de consulta de consumo por período | 5 | 🟢 |
| F25 | Preparación de datos para facturación (entrega a CIS) | 10 | 🟡 (export genérico listo, contrato real depende del CIS elegido) |

### Control (SCR)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F26 | Solicitud de orden de control | 6 | 🟢 |
| F27 | Flujo de aprobación configurable por tenant/tipo | 6 | 🟢 |
| F28 | Firma y validación de orden antes de ejecución | 6-7 | 🟢 |
| F29 | Ejecución vía adaptador HES | 7 | 🟢 |
| F30 | Confirmación de estado y auditoría inmutable | 7 | 🟢 |

### Transversal

| # | Función | Sprint | Estado |
|---|---|---|---|
| F31 | Multi-tenencia con Row-Level Security | 0 | 🟢 |
| F32 | Autenticación JWT y control de roles/permisos | 0 | 🟢 |
| F33 | Portal/API pública multi-tenant (RLS end-to-end) | 8 | 🟢 |
| F34 | Observabilidad (métricas de ingesta, alertas) | 9 | 🟢 |
| F46 | Clúster k3s bootstrapeado + primer servicio desplegado como pod | 0 | 🟢 |

### Balance de Red y Modelado de Red — Track B (agregado 2026-09-10)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F35 | `network_zone` jerárquica (DMA/circuito/distrito) | B1 | 🟢 (con insumos de infraestructura para ILI — ver `07-track-b-alcance-funcional.md`) |
| F36 | Endpoint de ingesta externa (venta modular sin HES propio) | B1 | 🟢 |
| F37 | Cálculo de balance Top-Down (IWA) | B2 | 🟢 (`real_losses` se calcula como el RESIDUAL del balance si el llamador no lo trae — metodo Top-Down real, AWWA M36; ver Sprint B2) |
| F38 | Cálculo de balance Bottom-Up (IWA) | B2 | 🟢 (`real_losses` sigue siendo obligatorio/medido, mas la formula real de Caudal Mínimo Nocturno — `bottom_up_real_losses_from_mnf` — para producirlo; ver Sprint B2) |
| F39 | Carga y versionado de modelo hidráulico (`.inp`) | B3 | 🟢 |
| F40 | Simulación vía WNTR | B3 | 🟢 |
| F41 | Calibración de modelo con datos de `network_balance` | B4 | 🟢 |
| F42 | `network_asset`/`asset_connectivity` (Gemelo Digital) + ingesta externa desde SIG | B5 | 🟢 |
| F43 | Derivar `network_model` desde el Gemelo Digital (export EPANET) | B6 | 🟢 |
| F44 | Generación de `maintenance_order` desde anomalías (condición/simulación/balance) | B7 | 🟢 (condición/balance validadas contra datos reales; simulación queda para un sprint futuro, ver bitácora) |
| F45 | Integración con BayForce (envío de orden + webhook de cierre) | B7 | 🟡 (contrato real construido y probado de punta a punta contra un sandbox local real; **corregido 2026-09-14**: no es solo falta de credenciales — BayForce no tiene endpoint de intake externo genérico, ver `04-plan-sprints.md` §9. Se mantiene como notificación de salida opcional, nunca columna vertebral) |
| F46b | CMMS real de dominio para Mantenimiento (prioridad/SLA, códigos de falla, PM programado, ciclo de vida completo, cierre, KPIs, asignación simple) | — (nuevo, 2026-09-14) | 🟢 construido, probado (16 pruebas puras + E2E extendido) y desplegado a producción el mismo día — ver bitácora abajo |

### Portal Web — Track C (agregado 2026-09-10)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F47 | Autenticación real de usuarios (`app_user` + `POST /auth/login`) | C1 | 🟢 |
| F48 | Tablero general (Nivel 1: KPIs + alertas por etapa) | C1 | 🟢 |
| F49 | Tableros por etapa (Nivel 2: HES, VEE, Consumos, Control, Observabilidad) | C2 | 🟢 |
| F50 | Editor de reglas (Configuración: `vee_rule`/`consumption_anomaly_rule`/`control_approval_level`) | C3 | 🟢 |
| F51 | Pantallas de detalle y acciones (Nivel 3) | C4 | 🟢 |

**Cobertura por vertical en el MVP:** las 34 funciones del Track A se construyen para
**energía eléctrica** (protocolo DLMS/COSEM) primero. Ninguna está bloqueada por diseño para
agua/gas — extenderlas es agregar un adaptador de protocolo nuevo (F02) y un mapeo OBIS/registro
nuevo (F06), no rediseñar las otras 32. Las 7 funciones del Track B (F35-F41) nacen agnósticas
de utility desde el diseño (método de balance configurable), aunque su primera implementación
de Modelado (F39-F41) usa WNTR, específico de agua — un adaptador de modelado eléctrico/gas
queda pendiente de un caso de uso real.

## 2. Bitácora de sprints

Registro real de qué se ejecutó, no un plan aspiracional — se agrega una entrada por sesión de
trabajo con avance verificable.

### Sprint 0 — Fundaciones

**Objetivo:** multi-tenant, auth, esquema BD, patrón config cacheada (`04-plan-sprints.md`).
**Estado:** 🟡 En progreso, iniciado 2026-09-10.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | Confirmado el mecanismo de RLS con el usuario antes de escribir el esquema (`current_setting('app.tenant_id')` + políticas por tabla) | F31 | Este documento + `02-arquitectura-general.md` §5 |
| 2026-09-10 | Repo del código creado: `services/common/`, `infra/db/`, `docker-compose.yml`, `README.md` en la raíz del proyecto | — | `README.md` |
| 2026-09-10 | **Patrón de configuración cacheada implementado y probado de punta a punta** — `renmeter_common/config_cache.py` (stdlib puro, sin dependencia de Postgres) + 5 pruebas unitarias reales, corridas localmente | F20 | `services/common/tests/test_config_cache.py` — `python -m unittest`: **5/5 OK** |
| 2026-09-10 | Esquema inicial completo escrito: `tenant`, `meter`, `gateway`, configuración versionada (`meter_protocol`, `vee_rule`, `consumption_anomaly_rule`, `control_approval_level`, `role_permission`), `raw_reading` (hypertable Timescale), `validated_reading`, `meter_event`, `control_order` + auditoría, `consumption` — con RLS habilitado y política `FOR ALL` en cada tabla con `tenant_id` | F31 (parcial: escrito, no ejecutado) | `infra/db/migrations/0001_init.sql` |
| 2026-09-10 | Helper de contexto de tenant (`SET LOCAL app.tenant_id`, transaccional — no usa `SET` a secas para evitar fuga entre tenants en un connection pool reusado) + script de verificación end-to-end (dos tenants, confirma aislamiento) | F31, F32 (parcial: escritos, no ejecutados) | `services/common/renmeter_common/db.py`, `infra/db/verify_rls.py` |

| 2026-09-10 | **Alcance ampliado**: Balance de Red y Modelado de Red entran al producto como Track B modular (venta suelta a utilities grandes, sin depender del HES/VEE propio) — ver `01-planteamiento.md` §3-4, `02-arquitectura-general.md` §1.6/§3.2, `03-diseno.md` §1.3/§4.3/§7, `04-plan-sprints.md` §8 | F35-F41 (nuevas) | Documentos de las 4 fases actualizados en la misma sesión |
| 2026-09-10 | **Alcance ampliado de nuevo**: Gemelo Digital (inventario de activos + conectividad) y Gestión de Mantenimiento (integrada con **BayForce**, ya en el portafolio) entran como parte del Track B — ver `01-planteamiento.md` §3-4, `02-arquitectura-general.md` §1.7, `03-diseno.md` §1.4/§4.4/§8, `04-plan-sprints.md` §8 | F42-F45 (nuevas) | Documentos de las 4 fases actualizados en la misma sesión |

| 2026-09-10 | **Decisión de infraestructura revisada**: se evaluaron pros/contras de Kubernetes desde el día 1 vs. nunca (equipo sin experiencia previa de K8s en el portafolio, 1 tenant piloto, sin Docker instalado localmente, vs. evitar una migración cara más adelante) — decisión final: **k3s** (K8s liviano) desde el día 1 para los servicios *stateless*; PostgreSQL/TimescaleDB y Redis quedan fuera del clúster (Docker+systemd, patrón ya probado). Ver `02-arquitectura-general.md` principio 4 | F46 (nueva) | Las 4 fases actualizadas en la misma sesión |
| 2026-09-10 | **Auth JWT implementado y probado**: `renmeter_common/auth.py`, HS256 con librería estándar (sin dependencia externa confirmada en ese momento), exige `tenant_id` en todo token | F32 | 8 pruebas unitarias — **8/8 OK** (round-trip, sin tenant_id falla, secret incorrecto falla, expiración real y mockeada, payload alterado falla, formato inválido falla) |
| 2026-09-10 | **RLS verificado de verdad contra Postgres real** (no Docker disponible — se instaló PostgreSQL 16 portable sin admin, ver `infra/db/README-local-dev.md`). **Primera corrida: FALLÓ** — tenant B veía el medidor de tenant A. Causa raíz: el rol de conexión (`renfygrid`) era el superusuario de arranque de `initdb` — **Postgres hace que los superusuarios se salten RLS siempre**, sin importar las políticas. Corregido: rol de aplicación separado sin superusuario (`0002_app_role.sql`) + `FORCE ROW LEVEL SECURITY` en las 13 tablas (protege además contra el caso "el owner de la tabla también se salta RLS"). Reverificado desde una base limpia con los archivos de migración definitivos: **RLS OK** | F31 | `infra/db/verify_rls.py` — exit code 0, "Tenant B ve 0 medidor(es) de tenant A", corrido 2 veces (con pip recién instalado y desde cero con `0001_init.sql`+`0002_app_role.sql` finales) |
| 2026-09-10 | pip **sí tiene acceso a internet** en esta máquina (contradice la suposición inicial en `auth.py`) — se instaló `psycopg[binary]` sin problema. No se cambió `auth.py` a PyJWT: la implementación propia ya estaba escrita y probada; queda como reemplazo directo si se prefiere más adelante | — | `pip install psycopg[binary]` exitoso |

| 2026-09-10 | **k3s real levantado y primer pod desplegado.** Docker ya estaba instalado (WSL2 Ubuntu 26.04 de este PC, usado por el flujo de build de renvox — no hizo falta instalarlo). k3s se instaló con versión fijada (`v1.36.4+k3s1`) porque `update.k3s.io` devolvía un certificado TLS de Traefik que no correspondía al dominio (bloqueaba la resolución automática de canal "stable" — se bypaseó apuntando directo a GitHub releases). Namespace `renfygrid` creado; imagen `renfygrid/dummy-config-reader:sprint0` construida con `docker build` e importada al containerd de k3s (`ctr images import`, sin registry). Deployment con initContainer (Config Loader) + contenedor principal (lee snapshot) — **pod Running**, logs confirman: el loader escribe 1 regla en `/config/snapshot.json`, el contenedor principal la lee sin tocar ninguna fuente de datos él mismo | F46 | `kubectl get pods -n renfygrid` → Running; `kubectl logs -c config-loader` y `-c config-reader` confirman el flujo completo |

| 2026-09-10 | **Renombrado completo a inglés**: a pedido explícito del usuario, todo identificador de software (tablas, columnas, índices, roles, valores de enum, endpoints, eventos, nombres de función/variable en Python) pasó de español a inglés en snake_case — ver el mapeo completo en `infra/db/migrations/0001_init.sql`. La prosa/comentarios/docs se mantienen en español. Esquema reaplicado desde cero contra Postgres real y RLS reverificado (`RLS OK`); dummy de k3s reconstruido y redesplegado con el fixture en inglés, logs confirmados; 13/13 pruebas unitarias siguen pasando con nombres de test/variables en inglés | F20, F31, F32, F46 (re-verificados) | `verify_rls.py` exit 0, `python -m unittest`: 13/13 OK, `kubectl logs` con `type`/`params` en inglés |

| 2026-09-10 | **Sprint 0 cerrado**: repo propio inicializado (separado del repo vestigial sin commits en `C:\PCGM\RENSOFTLABS\core\`), 3 commits, pusheado a **GitHub público** `Glenn741/renfygrid`. CI básico agregado (`.github/workflows/tests.yml`, corre las pruebas de `services/common`) — **pendiente subirlo al remoto**: el token de GitHub guardado no tiene scope `workflow`, GitHub rechazó el push de ese archivo específico. Sigue en el repo local, sin trackear por git | — | `git log` (3 commits en `main`), `https://github.com/Glenn741/renfygrid` |

**F31 cerrado** (ver bitácora arriba): verificado contra PostgreSQL 16 real, no en Docker
(instalado portable sin Docker/admin, ver `infra/db/README-local-dev.md`) — el aislamiento
entre tenants se confirma con `infra/db/verify_rls.py`, exit code 0.

**Actualización 2026-09-14 (ronda de endurecimiento)**: la nota original de arriba dejaba
pendiente correr la migración contra la extensión **TimescaleDB** (`create_hypertable`). Eso
nunca se hizo — el proyecto avanzó por otro camino, ya verificado en producción: `raw_reading`
es una tabla particionada NATIVA de Postgres (`PARTITION BY RANGE`), mantenida por
`renmeter_common.partition_maintenance` vía cron real (`0 3 * * 1`, confirmado con particiones
reales `raw_reading_y2026_m09/m10/m11` + una `default`). `pg_extension` en producción solo tiene
`plpgsql`/`pgcrypto` — TimescaleDB nunca se instaló, y no hace falta: el particionamiento nativo
ya resuelve el mismo problema (poda de particiones viejas, escritura rápida en la partición
actual) sin una extensión de terceros. La nota de arriba queda **cerrada, no por TimescaleDB
sino por la alternativa real que sí se construyó** — la arquitectura de Fase 2/3 que la
mencionaba era aspiracional, mismo criterio ya aplicado al descartar el bus de eventos/k3s.

### Sprint 1 — Adaptador HES DLMS/COSEM

**Objetivo:** adaptador real que se asocia a un medidor/concentrador DLMS/COSEM, lee un
registro (OBIS) y lo normaliza a una fila de `raw_reading` (`04-plan-sprints.md`).
**Estado:** 🟢 Objetivo del sprint cumplido con evidencia real end-to-end (2026-09-10) —
F05 diferido a Sprint 2 (ver bitácora), F10 con el gap de TimescaleDB de siempre (no nuevo).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **Verificación de librería**: `gurux-dlms`, `gurux-net` y `gurux-common` sí existen como paquetes Python reales en PyPI (investigación previa solo había encontrado bindings C#/Java/Delphi) — `gurux-dlms` 1.0.203, incluye `GXDLMSClient`/`GXDLMSServer`. Instalados sin problema (`pip install`) | F02 | `services/hes-adapter-dlms/requirements.txt` |
| 2026-09-10 | **Gap identificado y decisión de alcance explícita**: Gurux no publica un simulador/servidor DLMS de referencia en Python (solo ejemplos de cliente); su simulador oficial (`Gurux.DLMS.Simulator.Net`) requiere .NET SDK, no instalado en este entorno; tampoco hay hardware real disponible. Decisión: construir el adaptador cliente real (adaptado fielmente de `GXDLMSReader.py`, el ejemplo de referencia oficial de Gurux) y probar con pruebas unitarias sobre un cliente/medio simulados (`unittest.mock`) la lógica de orquestación (reintentos, secuencia de asociación) — no el protocolo DLMS en sí, que ya lo garantiza Gurux. **Queda pendiente, documentado como gap abierto**: verificación end-to-end contra un medidor o simulador real | F02 | Docstring de `dlms_session.py` (sección "ESTADO REAL") |
| 2026-09-10 | **Adaptador construido**: `dlms_session.py` (`DlmsSession` — asociación SNRM/UA+AARQ/AARE, lectura de atributo con reintentos y reensamblado de tramas, desconexión), `meter_reader.py` (`read_register`/`NormalizedReading` — normaliza una lectura COSEM a fila `raw_reading`), `reading_store.py` (`insert_raw_reading`, usa `tenant_scope`), `main.py` (CLI real, sin valores fijos — host/puerto/tenant/medidor/OBIS todo por argumento) | F02, F03, F10 | `services/hes-adapter-dlms/*.py` |
| 2026-09-10 | Bug corregido: nombre de clase equivocado (`GXReceiveParameters`, que no existe) — corregido a `ReceiveParameters` tras inspeccionar el paquete `gurux_common` instalado | F02 | `dlms_session.py` import corregido |
| 2026-09-10 | **10/10 pruebas unitarias pasando** — 7 sobre `dlms_session` (orquestación: sin datos, camino feliz sin ronda de recepción, una ronda completa, agotamiento de reintentos lanza `TimeoutError_`, se salta asociación de aplicación con `Authentication.NONE`, se salta SNRM cuando el cliente no lo requiere, lectura de atributo actualiza el valor) + 3 sobre `meter_reader` (normalización a fila, índice de atributo 2 por defecto, índice de atributo configurable) | F02, F03, F10 | `python -m unittest discover -s tests -v` → **Ran 10 tests in 0.867s / OK** |

| 2026-09-10 | **Gap cerrado: verificación end-to-end real, sin hardware.** El usuario confirmó no tener acceso a un medidor real. En vez de dejarlo pendiente, se construyó `simulator/dlms_simulator_server.py`: un servidor DLMS/COSEM de prueba que **reusa el protocolo servidor real de Gurux** (`gurux_dlms.GXDLMSServer`, no una reimplementación propia), con un `Register` (OBIS/valor configurables) para responder. Se encontraron y documentaron **3 bugs reales en `gurux-dlms==1.0.203`** (verificados leyendo/reproduciendo el código instalado, no supuestos): (1) `GXServerReply` no define `setReply()` ni `getConnectionInfo()`, que `GXDLMSServer.handleRequest`/`handleCommand` sí llaman — sin parche, cualquier solicitud revienta con `AttributeError` silenciada por el propio `except Exception` de la librería; (2) `GXDLMSServer.initialize()` crea el objeto de asociación automático con `objectList.append(self.items)` en vez de `.extend(...)`, y `.append()` exige un objeto individual — `TypeError` evitado creando la asociación nosotros mismos antes de `initialize()`; (3) `notifyRead()` se invoca en el camino de un GET de un solo atributo pero no tiene default en la clase base — se define como no-op en la subclase. Los tres están documentados en el docstring de `dlms_simulator_server.py` | F02 | `simulator/dlms_simulator_server.py` |
| 2026-09-10 | **Bug real encontrado EN NUESTRO PROPIO CÓDIGO por esta prueba** (no lo detectaban las 10 pruebas unitarias con mocks, porque un mock no reproduce el mecanismo de sincronización real de `gurux_net.GXNet`): `dlms_session.py::_send_and_receive` no envolvía el envío/recepción con `with self.media.getSynchronous():` — sin ese lock, `GXNet` nunca movía al buffer de lectura los bytes que su hilo de escucha ya había recibido, y todo terminaba en `TimeoutError_` aunque el simulador respondiera correctamente. Corregido comparando línea por línea contra `GXDLMSReader.readDLMSPacket2` (el ejemplo de referencia oficial, que sí lo hace) — se había omitido al adaptarlo. Se agregó `getSynchronous()` al `Protocol Media`, y se corrigió el mock de las pruebas unitarias (`MagicMock.__exit__` devuelve un objeto *truthy* por defecto, lo que habría suprimido silenciosamente cualquier excepción real dentro del `with` — se forzó `__exit__.return_value = False`) | F02 | `dlms_session.py`, `tests/test_dlms_session.py` |
| 2026-09-10 | **`verify_end_to_end.py` — corrida real, dos veces, ambas exitosas**: levanta el simulador en un hilo, crea un tenant+medidor real en Postgres, corre el mismo código de `main.py` (GXNet real por TCP + `GXDLMSClient` + `DlmsSession.associate()` + `read_register` + `insert_raw_reading`) contra `127.0.0.1:22222`, confirma el valor leído (`4781999`) y relee la fila insertada en `raw_reading` (con RLS activo) desde Postgres | F02, F03 (parcial), F10 (parcial) | `python verify_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **"E2E OK -- simulador + cliente real + raw_reading confirmados"**, corrido 2 veces |

**F02 pasa a 🟢**: el adaptador se asoció (AARQ/AARE) y leyó un objeto COSEM real por TCP contra
una implementación real (no mock) del protocolo servidor DLMS/COSEM de Gurux, con el valor
correcto llegando hasta `raw_reading`. **F10 queda en 🟡 a propósito**: menciona explícitamente
la hypertable de **TimescaleDB**, que sigue sin poder probarse en esta máquina (Postgres portable
de Windows, sin esa extensión — ver README de `.devdb/`) — el INSERT/RLS sobre la tabla plana sí
está probado, la extensión Timescale en sí, no.

| 2026-09-10 | **Gap de esquema encontrado al construir F03**: ni `meter` ni `gateway` tenían dónde guardar la información de conexión de red (host/puerto TCP, dirección DLMS) — sin eso, un poller no puede saber "a quién conectarse" sin hardcodearlo. Migración `0003_gateway_connection.sql`: `gateway.connection` (jsonb, host/port/client_address) y `meter.server_address` (la dirección DLMS del medidor dentro de ese gateway). Aplicada contra Postgres real | F01, F03 | `infra/db/migrations/0003_gateway_connection.sql`, aplicada con `psql` |
| 2026-09-10 | **F01/F11 construidos**: `meter_registry.py` — `register_gateway`, `register_meter`, `link_meter_to_gateway` (todas dentro de `tenant_scope`, nada fijo: marca/modelo/protocolo/ubicación/conexión llegan por parámetro) | F01, F11 | `services/hes-adapter-dlms/meter_registry.py` |
| 2026-09-10 | **F03 construido**: `poller.py` — recorre los medidores activos y enlazados a un gateway (`due_meters`, un JOIN `meter`+`meter_gateway`+`gateway`), y por cada uno corre el mismo pipeline de `main.py` (asociar, leer, normalizar, insertar). Intervalo y `--iterations` (para pruebas) por argumento, nunca fijo. Alcance explícito, no más: el código OBIS/canal se aplica igual a todos los medidores del tenant (el mapeo por marca/modelo, F06, sigue siendo Sprint 2); un medidor que falla en un ciclo no tumba el resto ni se reintenta dentro del mismo ciclo (la cola/reintento, F08, también Sprint 2) | F03 | `services/hes-adapter-dlms/poller.py` |
| 2026-09-10 | **`verify_poller_end_to_end.py` — corrida real, exitosa**: registra un gateway+medidor reales (apuntando al mismo simulador de `dlms_simulator_server.py`, puerto distinto), corre el poller 2 ciclos (`--iterations 2`) y confirma **2 filas** en `raw_reading` con el valor correcto — prueba F01/F11 (registro) y F03 (polling) juntos, de punta a punta, no solo un disparo manual | F01, F03, F11 | `python verify_poller_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **"E2E poller OK"** |

**F01/F11/F03 pasan a 🟢**: registro real de medidor+gateway en Postgres, y el poller
encontrándolos solo (sin que se le pase el medidor por parámetro) y leyéndolos 2 veces reales
contra el simulador, con las filas resultantes confirmadas en `raw_reading`.

**F05 (eventos/alarmas) diferido a Sprint 2, decisión explícita**: el objetivo de Sprint 1 en
`04-plan-sprints.md` §4 es literalmente "conecta a un medidor/simulador... lectura real ingresa a
raw_reading" — no menciona eventos. Recepción de eventos/alarmas requeriría infraestructura de
notificación push (`GXDLMSNotify`, un listener aparte del ciclo de polling), una pieza
suficientemente distinta como para no colarla dentro de Sprint 1 sin que el usuario lo decida
explícitamente. Queda como primer candidato de Sprint 2, junto con F06/F08.

*(Esta tabla se sigue completando a medida que avanza el Sprint 1 real.)*

### Sprint 2 — Mapeo OBIS configurable + reintentos

**Objetivo:** cambiar el mapeo OBIS de una marca/modelo en BD (sin tocar código ni redesplegar)
cambia el parseo del poller; reintentos acotados ante caída de un concentrador
(`04-plan-sprints.md` §4). **Estado:** 🟢 objetivo de mapeo cumplido con evidencia real;
reintentos cumplidos parcialmente (ver más abajo) — iniciado y cerrado 2026-09-10.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **F06 construido**: `obis_mapping.py` (mismo patrón de configuración cacheada que `renmeter_common.config_cache`: `meter_protocol` en BD es la fuente de verdad, un snapshot en disco es lo único que el poller lee en caliente) + `refresh_obis_mapping_cache.py` (el "Config Loader" que se corre aparte, nunca en el hot path). `poller.py` reescrito: ya no recibe un OBIS/canal fijo por argumento — por cada medidor busca su mapeo vigente por marca/modelo y lee todos los canales mapeados en una sola asociación | F06 | `services/hes-adapter-dlms/obis_mapping.py`, `refresh_obis_mapping_cache.py`, `poller.py` |
| 2026-09-10 | **F06 verificado de punta a punta, incluyendo el caso que realmente importa**: `verify_poller_end_to_end.py` ahora registra también una fila `meter_protocol` real, corre 2 ciclos con un mapeo, y luego **cambia el mapeo en BD** (renombra el canal), refresca el snapshot (sin tocar `poller.py`) y corre un tercer ciclo — confirma que la fila nueva en `raw_reading` ya usa el nombre de canal actualizado | F06 | `python verify_poller_end_to_end.py "..."` → **"Filas con el canal nuevo (active_energy_v2) tras cambiar el mapeo en BD: 1 (esperado: 1)"**, **"E2E poller OK"** |
| 2026-09-10 | **F08 construido, alcance parcial explícito**: `poller.py::read_one_meter_with_retries` — hasta `--read-retries` intentos con espera fija `--retry-backoff-seconds` entre cada uno, antes de dar por fallido un medidor en ese ciclo (sin tumbar el resto). Probado directamente contra un puerto cerrado (conexión rechazada): agota los 3 intentos configurados y lanza la excepción esperada, sin colgar el proceso | F08 (parcial) | Prueba manual: `read_one_meter_with_retries(...)` con `port=9` (cerrado) → falla tras 3 intentos, excepción `ConnectionRefusedError` propagada correctamente, capturada por `run_once` sin detener el ciclo |

**F08 queda en 🟡, no 🟢, a propósito**: lo construido son reintentos *dentro del mismo ciclo* —
si un medidor sigue fallando después de agotarlos, se registra el error y no se reintenta hasta
el próximo ciclo de polling (según `--interval-seconds`). No hay una **cola persistente** que
recuerde medidores fallidos y los reintente con una política propia independiente del ciclo
general — eso sería una pieza aparte (ej. una tabla `failed_reading` o un stream de reintento),
no construida todavía porque el DoD del sprint no la exige explícitamente y el alcance ya cerraba
sin ella.

*(Esta tabla se sigue completando a medida que avanza el Sprint 2 real.)*

### F05 — Recepción de eventos/alarmas del medidor: retomado (2026-09-11)

**Objetivo:** cerrar el gap explícito de Sprint 1 (`04-plan-sprints.md` §4, F05 diferido). **Estado:**
🟢 verificado real end-to-end, por TCP real y contra Postgres real.

Nuevos módulos en `services/hes-adapter-dlms/`: `event_notification.py` (codificación/decodificación
del mensaje) + `event_listener.py` (servidor TCP + persistencia en `meter_event`).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-11 | **Decisión de diseño explícita, y un 5° bug real en `gurux-dlms==1.0.203`**: el mecanismo semánticamente "correcto" del Blue Book de DLMS para un evento/alarma espontáneo es `EVENT_NOTIFICATION` — pero `GXDLMS.getData` lo reconoce del lado de recepción con un `elif cmd == Command.EVENT_NOTIFICATION: pass` (no-op): el valor nunca se decodifica, aunque `GXDLMSNotify.generateReport` sí sabe generarlo. Se usó **`DATA_NOTIFICATION`** en su lugar, que sí está completo en ambas direcciones (`generateDataNotificationMessages` + `handleDataNotification`/`getValueFromData`) — verificado primero con un prototipo aislado (encode→bytes reales→decode) antes de construir nada encima | F05 | Docstring de `event_notification.py` |
| 2026-09-11 | **Estructura del cuerpo, elección propia (el Blue Book no fija una para Data-Notification)**: `STRUCTURE(meter_server_address uint16, event_code uint16, severity_code uint8)`. La identidad del medidor viaja **dentro del payload**, no se infiere de la dirección de origen del encabezado WRAPPER — un concentrador móvil/GPRS puede tener IP dinámica | F05 | `event_notification.py` |
| 2026-09-11 | **Verificado por TCP real, con reensamblado de fragmentos**: un prototipo aislado confirmó el mecanismo completo (proceso único, luego dos procesos por socket real con la escritura partida a la mitad para forzar que `EventNotificationDecoder` reensamble) antes de escribir el listener final | F05 | Prototipo corrido dos veces, `RESULT: {'value': [1001, 42, 2]}` |
| 2026-09-11 | **`event_listener.py` construido**: corre por tenant (mismo criterio que `poller.py`/`on_demand_reader.py` — nunca cruza tenants dentro de un mismo proceso), resuelve el medidor real por `server_address` dentro del tenant, y **descarta sin tumbar el listener** un evento de un `server_address` no registrado (fail-safe, mismo principio que "un medidor caído no tumba el ciclo del poller") | F05 | `services/hes-adapter-dlms/event_listener.py` |
| 2026-09-11 | **6 pruebas unitarias puras nuevas** (ida-y-vuelta con la librería Gurux real, no un mock del protocolo: completo en un solo `feed`, fragmentado en dos mitades, mapeo de severidad, severidad desconocida cae a `warning` nunca a `info`, dos mensajes independientes no comparten estado, cuerpo con forma inesperada lanza en vez de adivinar) — **24/24 en `hes-adapter-dlms`, 74/74 en total en los 5 servicios** | F05 | `python -m unittest discover -s tests -v` → OK en los 5 servicios |
| 2026-09-11 | **`verify_event_notification_end_to_end.py` — corrida real, exitosa, 2 verificaciones en una pasada**: (1) medidor real registrado, listener real levantado en un puerto TCP real, push real recibido — confirma exactamente 1 fila `meter_event` (`type='meter_alarm'`, `severity='critical'`, `detail={'event_code':77,'severity_code':2}`) con el `meter_id` correcto; (2) un segundo push con `server_address` no registrado en este tenant se descarta, **el listener sigue vivo y acepta la siguiente conexión**, y no se crea ninguna fila para ese evento | F05 | `python verify_event_notification_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"F05 OK"**, exit code 0 |

**F05 pasa a 🟢**: no es una simulación del mecanismo de push — es el protocolo DATA_NOTIFICATION real
de Gurux, con bytes reales viajando por un socket TCP real y reensamblados de un stream fragmentado,
resueltos contra un medidor real en Postgres con RLS activo. **Con esto, de los 4 gaps que quedaban en
Track A (ver cierre de Sprint 9), solo quedan F07 y F25 (parcial) — y F07 sigue sin ser un gap de
código: depende de confirmar que un medidor piloto real soporte corte/reconexión remoto, algo que no se
puede fabricar sin ese piloto (mismo criterio que Sprint 10, F12/F25 de retención/facturación).**

### Sprint 3 — Motor VEE: Validación

**Objetivo:** lecturas fuera de rango quedan marcadas, con regla trazable (`04-plan-sprints.md`
§4). **Estado:** 🟢 objetivo del sprint cumplido con evidencia real — iniciado y cerrado
2026-09-10.

Nuevo servicio independiente `services/vee-engine/` (no dentro de `hes-adapter-dlms`: el motor
VEE es un servicio Python aparte por diseño, ver `02-arquitectura-general.md` tabla de stack).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **Gap de esquema encontrado**: `validated_reading` no tenía columna `channel` (un medidor puede tener varios canales — sin esto no se sabe a qué lectura cruda corresponde cada fila validada) ni forma de marcar una lectura como inválida (`source` solo distinguía real/estimated/edited). Migración `0004_validated_reading_channel.sql`: agrega `channel`, `is_valid`, `validation_notes` y una unicidad `(meter_id, channel, timestamp)` para no reprocesar la misma lectura dos veces. Aplicada contra Postgres real | F14, F15 | `infra/db/migrations/0004_validated_reading_channel.sql` |
| 2026-09-10 | **Motor construido**: `vee_engine.py` (`validate_reading` — lógica pura, sin BD ni red: valida formato (NaN/no-numérico) y rango min/max, elige la regla de mayor prioridad cuando hay varias para el mismo canal) + `vee_rules_cache.py`/`refresh_vee_rules_cache.py` (mismo patrón de configuración cacheada que `obis_mapping.py`: `vee_rule` en BD es la fuente de verdad, snapshot en disco es lo que se lee en caliente) + `run_vee_pass.py` (procesa solo lecturas de `raw_reading` sin fila correspondiente en `validated_reading` todavía) | F14, F15, F19 | `services/vee-engine/*.py` |
| 2026-09-10 | **7/7 pruebas unitarias puras** sobre `validate_reading` (dentro de rango con regla trazable, por encima/por debajo del rango, canal sin regla configurada pasa sin regla trazable, NaN y valor no numérico inválidos por formato, la regla de mayor prioridad gana cuando hay dos que aplican al mismo canal) — sin mocks, es lógica sin I/O | F14, F15 | `python -m unittest discover -s tests -v` (en `services/vee-engine/`) → **Ran 7 tests in 0.004s / OK** |
| 2026-09-10 | **`verify_vee_end_to_end.py` — corrida real, exitosa**: crea un tenant+medidor+regla de rango reales, inserta 3 lecturas crudas (una dentro de rango, dos fuera), corre el pase de validación una vez y confirma **exactamente 1 válida + 2 inválidas**, las tres con `vee_rule_id` trazable | F14, F15, F19 | `python verify_vee_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **"E2E VEE OK -- 1 valida + 2 invalidas, todas con regla trazable"** |
| 2026-09-10 | Corrido también contra el tenant de demostración (dejado para que el usuario mirara datos reales en DBeaver, ver más abajo): se agregó una regla de rango y una lectura fuera de rango a propósito — `validated_reading` del tenant demo quedó con 3 válidas + 1 inválida, visible en DBeaver sin necesidad de correr nada más | — | Tenant "RenfyGrid Demo" en la BD local |

**F15 en 🟡 a propósito**: se implementó la parte de **formato** (rechaza NaN/valores no
numéricos) pero no la de **coherencia entre canales** (ej. activa vs. reactiva) que menciona
`03-diseno.md` §5 — el piloto de referencia hoy solo tiene un canal mapeado por medidor (Sprint
1-2), así que no hay todavía un caso real de dos canales para validar entre sí. Queda pendiente
hasta que exista ese caso concreto, no por olvido.

**F16-F18 (detección de intervalos faltantes, estimación, edición manual) quedan en Sprint 4**,
tal como estaba planeado — no se tocaron.

*(Esta tabla se sigue completando a medida que avanza el Sprint 3 real.)*

### Sprint 4 — Motor VEE: Estimación y Edición

**Objetivo:** estimación (método configurable) + edición manual auditada; historias de usuario
de diseño (`03-diseno.md` §5) verificadas una a una (`04-plan-sprints.md` §4). **Estado:** 🟢
objetivo cumplido con evidencia real — iniciado y cerrado 2026-09-10.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **Gap encontrado**: para editar una lectura de forma auditada sin poder reescribir el historial ("registro no editable (append-only)", `03-diseno.md` §5), hacía falta una tabla de auditoría separada de `validated_reading` (que sí se sigue actualizando in place al editar). Migración `0005_validated_reading_edit.sql`: tabla `validated_reading_edit` con **`REVOKE UPDATE, DELETE`** al rol `renfygrid_app` — inmutabilidad forzada por Postgres, no solo por convención de código | F18 | `infra/db/migrations/0005_validated_reading_edit.sql` |
| 2026-09-10 | **F16/F17 construidos**: `vee_engine.py` ampliado con `detect_gaps` (huecos entre lecturas validadas consecutivas, dado un intervalo esperado + tolerancia — ambos desde `vee_rule.type='missing_interval'`) y `estimate_gap` (interpolación lineal entre el valor anterior y el siguiente conocidos). `run_vee_estimation.py` orquesta: busca pares medidor/canal con lecturas, detecta huecos, inserta lecturas `estimated` con el `vee_rule_id` trazable | F16, F17 | `services/vee-engine/vee_engine.py`, `run_vee_estimation.py` |
| 2026-09-10 | **F17, alcance explícito**: de los 3 métodos de estimación mencionados en el diseño (`linear_interpolation`, `customer_historical_average`, `similar_customers_average`), solo el primero está implementado — los otros dos necesitan agregados históricos por cliente/grupo de clientes que no existen todavía (series más largas que las del piloto actual). `estimate_gap` lanza `NotImplementedError` para un método no soportado en vez de fallar en silencio o adivinar | F17 | Docstring de `vee_engine.py` |
| 2026-09-10 | **F18 construido**: `manual_edit.py::edit_reading` — actualiza `validated_reading.value` (pasa `source` a `'edited'`) y en la misma transacción inserta la fila de auditoría en `validated_reading_edit` (valor anterior capturado por el propio código con `SELECT ... FOR UPDATE`, no confiado al llamador). `user_name`/`justification` obligatorios | F18 | `services/vee-engine/manual_edit.py` |
| 2026-09-10 | **6 pruebas unitarias puras nuevas** sobre `detect_gaps`/`estimate_gap` (sin huecos cuando todo llega a tiempo, jitter pequeño dentro de tolerancia no cuenta como hueco, cuenta correcta de lecturas faltantes, dos huecos separados se reportan por separado, interpolación lineal da puntos parejos, método no soportado lanza en vez de adivinar) — 13/13 en total en `vee-engine` | F16, F17 | `python -m unittest discover -s tests -v` → **Ran 13 tests in 0.005s / OK** |
| 2026-09-10 | **`verify_estimation_and_edit_end_to_end.py` — corrida real, exitosa, 4 verificaciones en una sola pasada**: (1) inserta 2 lecturas reales con un hueco de 3 intervalos, corre el pase de estimación real y confirma exactamente 3 lecturas `estimated` con los valores interpolados exactos (1250/1500/1750); (2) edita la primera lectura real con `edit_reading` y confirma `value`/`source` actualizados; (3) confirma que `validated_reading_edit` tiene exactamente 1 fila con el valor anterior correcto; (4) **intenta un `UPDATE` directo sobre `validated_reading_edit` con el rol de aplicación real y confirma que Postgres lo rechaza** (`InsufficientPrivilege`) — no es una promesa de diseño, es una regla de acceso verificada contra la BD real | F16, F17, F18 | `python verify_estimation_and_edit_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → las 4 verificaciones en **OK**, exit code 0 |

**F17 en 🟡 a propósito**: un método de estimación implementado (`linear_interpolation`), dos
pendientes de un caso de uso real con historial más largo. El resto del alcance de Sprint 4
(F16, F18) está en 🟢 con evidencia real, incluyendo la garantía de inmutabilidad verificada
contra Postgres, no solo documentada.

*(Esta tabla se sigue completando a medida que avanza el Sprint 4 real.)*

### Sprint 5 — Gestión de Consumos

**Objetivo:** API de consumo facturable responde para el tenant piloto (`04-plan-sprints.md`
§4). **Estado:** 🟢 objetivo cumplido con evidencia real — iniciado y cerrado 2026-09-10.

Nuevo servicio independiente `services/consumption/` (mismo patrón que `vee-engine`: servicio
Python aparte, no dentro de `hes-adapter-dlms`).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **Decisión de diseño**: el "canal facturable" de un medidor se marca en el mismo `meter_protocol.obis_mapping` de Sprint 2 (`{"active_energy": {..., "billable": true}}`) en vez de crear una tabla nueva — reusa la configuración cacheada que ya existe. Las "órdenes de relectura/inspección" (F23) se representan como filas de `meter_event` (ya existente, `type` = `consumption_anomaly_rule.action`) en vez de una tabla nueva — gap encontrado: le faltaba forma de saber de qué consumo salió la orden. Migración `0006_meter_event_consumption_link.sql`: agrega `meter_event.consumption_id` (FK, nullable) | F21, F23 | `infra/db/migrations/0006_meter_event_consumption_link.sql` |
| 2026-09-10 | **Motor construido**: `consumption_engine.py` (`compute_consumption` — cierre menos apertura, porque un registro DLMS típico es acumulativo desde la instalación, no ya viene como "consumo del periodo"; `detect_deviation` — compara contra el consumo del periodo anterior usando `consumption_anomaly_rule` cacheada, la regla más estricta gana si hay varias) + `consumption_rules_cache.py` (mismo patrón de config cacheada) + `run_consumption_pass.py` (agrega por medidor/periodo, genera la orden si corresponde) + `get_consumption.py` (F24, contrato de función entre servicios — la API pública HTTP sigue siendo Sprint 8) | F21, F22, F23, F24 | `services/consumption/*.py` |
| 2026-09-10 | **6/6 pruebas unitarias puras** sobre `consumption_engine` (consumo = cierre-apertura, sin consumo previo no hay anomalía, desviación chica no dispara, desviación grande dispara y traza la regla, la regla más estricta gana entre varias, sin reglas configuradas no hay anomalía pero sí se reporta el % de desviación) | F21, F22 | `python -m unittest discover -s tests -v` (en `services/consumption/`) → **Ran 6 tests in 0.012s / OK** |
| 2026-09-10 | **`verify_consumption_end_to_end.py` — corrida real, exitosa**: registra un medidor con canal facturable, inserta 3 lecturas validadas reales (apertura + 2 cierres de periodo), corre el pase de consumo dos veces (periodo 1: 500, sin anomalía; periodo 2: 5000, +900% vs. el anterior con una regla de 10%) y confirma **`anomaly_status='under_review'`** en el segundo periodo + una fila de `meter_event` (`type='reread_order'`) trazable a esa fila exacta de `consumption` vía `consumption_id`. `get_consumption` (F24) devuelve ambos periodos correctamente | F21, F22, F23, F24 | `python verify_consumption_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **"F21/F22/F24 OK"**, **"F23 OK"**, exit code 0 |

**F25 (preparación de datos para facturación, entrega a CIS) sigue en Sprint 10**, tal como
estaba planeado — no se tocó; requiere definir el contrato de entrega con un CIS real, que
todavía no existe para el piloto de referencia.

*(Esta tabla se sigue completando a medida que avanza el Sprint 5 real.)*

### Sprint 6 — Módulo SCR: modelo de estados y aprobación

**Objetivo:** una orden de prueba pasa por `requested→pending_approval→approved` con auditoría
(`04-plan-sprints.md` §4). **Estado:** 🟢 objetivo cumplido con evidencia real — iniciado y
cerrado 2026-09-10.

Nuevo servicio independiente `services/control/` (SCR: Suspensión/Corte/Reconexión — servicio
aislado por diseño, ver `02-arquitectura-general.md` §6: "el canal de control es el punto de
mayor impacto si falla").

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **`control_order_audit` hecha verdaderamente inmutable**: la tabla ya existía desde Sprint 0 con un comentario explícito de que la inmutabilidad quedaba pendiente. Migración `0007_control_order_audit_immutable.sql`: mismo patrón que `validated_reading_edit` (Sprint 4) — `REVOKE UPDATE, DELETE` al rol de aplicación | F30 (parcial) | `infra/db/migrations/0007_control_order_audit_immutable.sql` |
| 2026-09-10 | **Decisión de diseño explícita sobre `min_required_role`**: se compara por **igualdad exacta**, no por una jerarquía de roles ("supervisor > operador") — el diseño no define ninguna tabla de rangos entre roles, e inventar una jerarquía no pedida habría sido alcance no solicitado. Fail-safe: sin ninguna `control_approval_level` configurada para un tipo de orden, se exige aprobación humana por defecto — nunca se auto-aprueba por ausencia de configuración | F27 | Docstring de `control_engine.py` |
| 2026-09-10 | **Motor construido**: `control_engine.py` (`approval_level_for`, `status_after_request`, `can_approve` — lógica pura) + `approval_levels_cache.py` (mismo patrón de config cacheada) + `control_service.py` (`request_order` — F26, nace `requested` y transiciona de inmediato a `pending_approval` o, si el tenant configuró auto-aprobación, a `approved` con actor `system:auto_approval`, trazable igual que cualquier aprobación humana; `approve_order` — F27, valida estado y rol antes de transicionar; `is_ready_to_execute` — la porción de F28 que corresponde a este sprint, antes de la ejecución real que es Sprint 7) | F26, F27, F28 (parcial) | `services/control/*.py` |
| 2026-09-10 | **7/7 pruebas unitarias puras** sobre `control_engine` (sin configuración exige aprobación humana por defecto, configuración respetada, solo aplica al tipo de orden correcto, requiere-aprobación → pending_approval, no-requiere → approved directo, coincidencia exacta de rol aprueba, rol distinto no aprueba) | F26, F27 | `python -m unittest discover -s tests -v` (en `services/control/`) → **Ran 7 tests in 0.001s / OK** |
| 2026-09-10 | **`verify_control_end_to_end.py` — corrida real, exitosa, 6 verificaciones en una pasada**: (1) orden de `suspension` (requiere aprobación humana) queda `pending_approval`; (2) un rol insuficiente (`operator`) intenta aprobarla y es rechazado (`InsufficientRoleError`); (3) el rol correcto (`supervisor`) la aprueba → `approved`, `is_ready_to_execute=True`, y **3 filas de auditoría trazables** (`requested→pending_approval→approved`); (4) orden de `reconnection` (configurada sin aprobación humana) queda `approved` de inmediato con `approved_by='system:auto_approval'`; (5) **intento de `UPDATE` directo sobre `control_order_audit` con el rol de aplicación real, rechazado por Postgres** (`InsufficientPrivilege`) | F26, F27, F28, F30 (parcial) | `python verify_control_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **"SPRINT 6 E2E OK"**, exit code 0 |

**F28/F30 quedan en 🟡 a propósito**: la validación de que una orden está en el estado correcto
antes de poder ejecutarse (F28) y la inmutabilidad de la auditoría (F30) ya están hechas y
verificadas; lo que falta de cada una — la firma criptográfica de la orden antes de llegar al
adaptador HES (F28) y la confirmación de estado real post-ejecución (F30) — depende de F29
(ejecución vía adaptador HES), que es Sprint 7, tal como estaba planeado.

*(Esta tabla se sigue completando a medida que avanza el Sprint 6 real.)*

### Sprint 7 — Módulo SCR: ejecución real y confirmación

**Objetivo:** suspensión/reconexión real (o en simulador) vía adaptador HES + confirmación
(`04-plan-sprints.md` §4). **Estado:** 🟢 objetivo cumplido con evidencia real end-to-end —
iniciado y cerrado 2026-09-10.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **Simulador ampliado con un objeto de control real**: `simulator/dlms_simulator_server.py` agrega un `GXDLMSDisconnectControl` (IC 70, el objeto DLMS real para suspensión/reconexión remota) opcional. **4to bug real encontrado en `gurux-dlms==1.0.203`**: `GXDLMSLNCommandHandler` llama a `server.onPreAction(list(e))` para cualquier acción/método COSEM, pero `list(e)` intenta *iterar* el `ValueEventArgs e`, que no implementa `__iter__` — cualquier acción revienta con `TypeError` antes de que el código propio llegue a ejecutarse. Parche: agregar `__iter__` a `ValueEventArgs` (devuelve `[self]`, igual que otros call sites ya hacen a mano en el mismo archivo de Gurux) | F29 | `simulator/dlms_simulator_server.py` (docstring, bug 4) |
| 2026-09-10 | **`dlms_session.py` ampliado**: `invoke_action` (envía un pedido de acción/método COSEM ya armado por el cliente, ej. `remoteDisconnect`/`remoteReconnect`) — lanza `ActionError` si el `METHOD_RESPONSE` trae un código de error, no basta con "no hubo excepción de red" para dar una acción de control por exitosa | F28, F29 | `services/hes-adapter-dlms/dlms_session.py` |
| 2026-09-10 | **`control_executor.py` construido** (en `hes-adapter-dlms`, no en `services/control` — el módulo SCR "únicamente habla con los adaptadores HES", `02-arquitectura-general.md` §6 punto 4): `execute_control_order` (mapea `suspension`/`disconnection`→`remoteDisconnect`, `reconnection`→`remoteReconnect`) + `dispatch_control_order` (ciclo de vida completo: abre, asocia, ejecuta, cierra — el punto de entrada de alto nivel que SCR llama, sin conocer `GXNet`/`DlmsSession`) | F29 | `services/hes-adapter-dlms/control_executor.py` |
| 2026-09-10 | **`order_signing.py` construido** (F28, la firma que faltaba de Sprint 6): HMAC-SHA256 con librería estándar sobre `(order_id, meter_id, order_type)` — mismo enfoque que `renmeter_common/auth.py`. 4 pruebas puras: firma válida verifica, tipo de orden alterado invalida la firma, secreto incorrecto invalida, y la firma de una orden no sirve para otra (repetición en el bus) | F28 | `services/control/order_signing.py`, `tests/test_order_signing.py` |
| 2026-09-10 | **`control_service.py::send_and_execute_order`**: firma la orden, transiciona `approved→sent`, ejecuta el comando DLMS real vía `dispatch_control_order`, y transiciona a `confirmed` o `failed` según el resultado — nunca deja una orden en `sent` sin resolver. El OBIS del objeto de control y la conexión del gateway se resuelven igual que en Sprint 5 (`meter_protocol.obis_mapping`, ahora con una entrada `"control"`) | F28, F29, F30 | `services/control/control_service.py` |
| 2026-09-10 | **11/11 pruebas unitarias puras** en `services/control` (4 nuevas de `order_signing`) + **16/16 en `hes-adapter-dlms`** (2 nuevas: acción exitosa no lanza, respuesta de error lanza `ActionError`; 4 nuevas de `control_executor` con mocks) | F28, F29 | `python -m unittest discover -s tests -v` en ambos servicios → OK |
| 2026-09-10 | **`verify_control_execution_end_to_end.py` — corrida real, exitosa, dos caminos completos**: (1) registra medidor+gateway apuntando al simulador con un `DisconnectControl` real, pide y aprueba una `suspension`, `send_and_execute_order` la firma y ejecuta un `remoteDisconnect` **DLMS real** contra el simulador — termina `confirmed`, con las **5 transiciones completas** en la auditoría (`requested→pending_approval→approved→sent→confirmed`), y **el simulador queda realmente "desconectado"** (`server.control.is_connected == False`, efecto real de la acción, no un resultado fabricado); (2) una segunda orden apuntando a un puerto cerrado (concentrador caído) termina `failed`, con la razón real del error de conexión en la auditoría | F28, F29, F30 | `python verify_control_execution_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **ambos caminos "OK"**, exit code 0 |

**F28/F29/F30 pasan a 🟢**: no es una simulación de la ejecución — es el mismo protocolo DLMS
real (`GXDLMSDisconnectControl`) que usaría un medidor físico con soporte de corte/reconexión
remoto, contra un simulador que también reusa el protocolo servidor real de Gurux (mismo
principio que Sprint 1). Con esto, **Track A completo hasta Sprint 7 de 10** — quedan Sprint 8
(Portal/API con RLS end-to-end), 9 (hardening/observabilidad) y 10 (piloto real).

*(Esta tabla se sigue completando a medida que avanza el Sprint 7 real.)*

### Sprint 8 — Portal/API pública multi-tenant

**Objetivo:** un usuario del tenant piloto solo ve sus propios datos, verificado con un segundo
tenant de prueba (`04-plan-sprints.md` §4). **Estado:** 🟢 objetivo cumplido con evidencia real
end-to-end — iniciado y cerrado 2026-09-10. **Primer servicio HTTP real de RenfyGrid.**

Nuevo servicio `services/portal-api/` (FastAPI + uvicorn). Config 100% por variable de entorno
(`RENFYGRID_DSN`, `RENFYGRID_JWT_SECRET`, `RENFYGRID_ORDER_SIGNING_SECRET`) — nunca un valor fijo
en código, mismo criterio que la contraseña de `0002_app_role.sql`.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **`auth_dependency.py`**: primer uso real de `renmeter_common/auth.py` (JWT, Sprint 0) fuera de sus propias pruebas unitarias — cada endpoint exige `Authorization: Bearer <token>`, y el `tenant_id` sale del claim firmado, nunca de un query param o del body. Es lo único que hace que F33 sea real aislamiento y no un filtro "de confianza" | F32, F33 | `services/portal-api/auth_dependency.py` |
| 2026-09-10 | **Endpoints construidos**: `GET /meters`, `GET /consumption` (reusa `get_consumption` de Sprint 5), `GET /events`, `POST /control-orders` — **no llama a `services/control` directo**: pasa por `services/consumption/control_order_gateway.py`, honrando `02-arquitectura-general.md` §6 punto 4 ("el módulo SCR únicamente habla con los adaptadores HES... se llega a él a través de Gestión de Consumos") — `POST /control-orders/{id}/approve`, `POST /meters/{id}/reads` (F04, lectura bajo demanda) | F33, F04 | `services/portal-api/main.py` |
| 2026-09-10 | **F04 construido**: `hes-adapter-dlms/on_demand_reader.py::read_meter_now` — mismo pipeline de `main.py`/`poller.py` pero resolviendo conexión/mapeo OBIS de un medidor puntual bajo pedido, no en un ciclo programado | F04 | `services/hes-adapter-dlms/on_demand_reader.py` |
| 2026-09-10 | **`verify_portal_api_end_to_end.py` — corrida real con `fastapi.testclient.TestClient` (ASGI real, Postgres real, sin mocks)**: 2 tenants con 1 medidor cada uno, JWT real por tenant — `GET /meters` con el token de A devuelve **solo** el medidor de A (no ve el de B, aunque ambos estén en la misma BD), lo mismo para B; sin token → 401; token con firma inválida → 401; `POST /control-orders` crea una orden real (201); `POST /meters/{id}/reads` ejecuta una lectura DLMS real contra el simulador de Sprint 1 y devuelve el valor correcto (777000); **el token de B intentando leer bajo demanda un medidor de A es rechazado (422) por la misma RLS**, no por una validación de aplicación aparte | F33, F04 | `python verify_portal_api_end_to_end.py "postgresql://renfygrid_app:...@localhost:5455/renfygrid"` → **"SPRINT 8 E2E OK"**, exit code 0 |

**Con esto, Track A completo hasta Sprint 8 de 10** — el primer HTTP real del proyecto, con el
aislamiento multi-tenant probado de punta a punta sobre ese HTTP, no solo a nivel de BD. Quedan
Sprint 9 (hardening: auditoría end-to-end, observabilidad, alertas) y Sprint 10 (piloto real).

*(Esta tabla se sigue completando a medida que avanza el Sprint 8 real.)*

### Sprint 9 — Hardening: auditoría, respaldo, observabilidad

**Objetivo:** auditoría inmutable end-to-end, métricas de ingesta, alertas de caída — panel de
observabilidad mínimo funcionando (`04-plan-sprints.md` §4). **Estado:** 🟢 objetivo cumplido
con evidencia real — iniciado y cerrado 2026-09-10.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **F09 construido**: `hes-adapter-dlms/communication_audit.py` (`audited_communication`, un context manager que envuelve un intento de comunicación real con un medidor y deja la auditoría sola, exitosa o no, en `meter_event` — se reusa esa tabla en vez de crear una nueva, con una columna `detail` nueva, migración `0008_meter_event_detail.sql`). Instrumentado en `poller.py` (cada intento, incluyendo reintentos) y `on_demand_reader.py` (F04, Sprint 8) | F09 | `services/hes-adapter-dlms/communication_audit.py`, migración `0008` |
| 2026-09-10 | **`verify_communication_audit_end_to_end.py` — corrida real**: un ciclo de polling exitoso, uno fallido (concentrador caído, puerto cerrado) y una lectura bajo demanda — confirma las 3 filas `meter_event` en orden, con `detail.operation`/`detail.error` correctos en cada una | F09 | `python verify_communication_audit_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"F09 OK"** |
| 2026-09-10 | **F13 construido**: `infra/db/backup.py`/`restore.py` — wrappers sobre `pg_dump`/`pg_restore` (formato custom, comprimido), nada reimplementado, todo por argumento (host/puerto/usuario/base/ruta, hasta la ubicación del binario) | F13 | `infra/db/backup.py`, `infra/db/restore.py` |
| 2026-09-10 | **`verify_backup_restore_end_to_end.py` — corrida real, con pg_dump/pg_restore reales**: inserta un tenant marcador en la BD de desarrollo real, corre un respaldo real, restaura sobre una **base temporal separada** (nunca sobre la BD de desarrollo en uso, que tiene datos de demo reales para el usuario) y confirma que el tenant marcador aparece intacto en la base restaurada — limpia el marcador, la base temporal y el archivo de respaldo al final. Se confirmó explícitamente que los datos de demo (`RenfyGrid Demo`) sobrevivieron intactos | F13 | `python infra/db/verify_backup_restore_end_to_end.py` → **"F13 OK"**, confirmado con una consulta aparte que `RenfyGrid Demo` sigue con sus 4 lecturas |
| 2026-09-10 | **F34 construido**: `portal-api/observability.py::ingestion_metrics` + `GET /observability/ingestion` (nuevo endpoint) — lecturas de las últimas 24h y última lectura por medidor, fallas de comunicación (F09) de las últimas 24h, y alerta `ingestion_stale` si un medidor activo no reporta hace más de `stale_after_seconds` (parámetro, nunca fijo). Un medidor que nunca reportó **no** se marca caído — no hay con qué comparar, no se adivina una alerta sin datos | F34 | `services/portal-api/observability.py`, `main.py` |
| 2026-09-10 | **`verify_observability_end_to_end.py` — corrida real via `TestClient`**: 3 medidores (lectura reciente, lectura de hace 2h con umbral de 1h, y uno sin ninguna lectura nunca) — confirma que solo el segundo aparece en `alerts`, y que la falla de comunicación real registrada por F09 aparece en `communication_failures_24h` | F34 | `python verify_observability_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"F34 OK"** |

**Con esto, Track A queda en 27 funciones 🟢, 4 🟡 (alcance parcial documentado explícitamente en
cada una) y solo 4 🟪 pendientes de las 35 — F05 (diferido a propósito, Sprint 1-2), F07 (envío
de comandos SCR *al medidor*, depende de confirmar que el medidor del piloto real soporta
corte/reconexión), F12 (retención histórica) y F25 (entrega a CIS), estas dos últimas ligadas a
tener un piloto real corriendo, no a más código genérico. Queda únicamente **Sprint 10**: piloto
real con el tenant, ajuste de reglas VEE con datos de producción. Track B (Balance de Red,
Modelado, Gemelo Digital, Mantenimiento — 11 funciones) sigue sin iniciar, tal como estaba
planeado (corre en paralelo cuando haya una oportunidad comercial concreta, no por fecha fija).

**Actualización 2026-09-11**: F05 y F12/F25 ya se cerraron desde entonces (ver sus secciones
propias más abajo) — de los 4 pendientes de este cierre, solo **F07** sigue abierto, y sigue
sin ser código pendiente: no se puede construir más sin un medidor piloto real que confirme
soporte de corte/reconexión remoto.

*(Esta tabla se sigue completando a medida que avanza el Sprint 9 real.)*

### Sprint 10 — Piloto real

**Objetivo:** piloto real con el tenant, ajuste de reglas VEE con datos de producción; primer
ciclo de facturación completo corrido con datos reales (`04-plan-sprints.md` §4). **Estado:**
🟡 — lo que se puede construir sin un piloto real ya está hecho y verificado; lo que define al
sprint (un cliente real, corriendo) **no se puede fabricar** — no es una limitación de tiempo,
es que el propio objetivo del sprint exige un dato que no existe todavía: un tenant piloto real.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **F12 construido**: `infra/db/retention.py` — `tenant.config` (jsonb, Sprint 0, primer uso real) trae `raw_reading_retention_days`/`validated_reading_retention_days` por tenant. Fail-safe explícito: un tenant sin retención configurada **nunca** pierde datos — no hay default adivinado para una operación destructiva | F12 | `infra/db/retention.py` |
| 2026-09-10 | **`verify_retention_end_to_end.py` — corrida real**: tenant A con retención de 30 días tiene una lectura de hace 60 días y una de hoy — tras correr el job, solo queda la de hoy; tenant B sin configurar tiene una lectura de hace 10 años — sigue intacta, confirmando el fail-safe contra Postgres real, no solo por diseño | F12 | `python infra/db/verify_retention_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"F12 OK"** |
| 2026-09-10 | **F25, alcance honesto**: sin un CIS real elegido para el piloto no hay un contrato de integración que implementar (formato exacto, SFTP/API, campos) — eso se define CON el CIS real. Se construyó `services/consumption/billing_export.py` (CSV genérico, un renglón por consumo facturable) + `GET /billing-export` — con una regla de negocio real: un consumo `anomaly_status='under_review'` (F22) **no se incluye**, no se factura algo bajo revisión sin resolver | F25 | `services/consumption/billing_export.py`, `main.py` |
| 2026-09-10 | **`verify_billing_export_end_to_end.py` — corrida real vía `TestClient`**: un consumo `ok` aparece en el CSV, uno `under_review` no | F25 | `python verify_billing_export_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"F25 OK"** |
| 2026-09-10 | **Herramienta de alta de tenant piloto**: `infra/onboarding/onboard_tenant.py` — junta en un manifiesto JSON (`example_manifest.json`) todo lo que hasta ahora requería llamar a mano por separado (`meter_registry`, `meter_protocol`, `vee_rule`, `consumption_anomaly_rule`, `control_approval_level`, Sprints 1-6) — para que dar de alta un tenant piloto real sea una sola corrida, no una secuencia de pasos manuales propensos a error | — (herramienta operativa, no una función del F-matrix) | `infra/onboarding/onboard_tenant.py`, `verify_onboarding_end_to_end.py` → **"ONBOARDING OK"**, el manifiesto de ejemplo completo (medidor + gateway + mapeo OBIS + 2 reglas VEE + regla de anomalía + 2 niveles de aprobación) quedó dado de alta en una sola corrida |

**Lo que de verdad falta de Sprint 10 no es código**: es una decisión de negocio (conseguir un
tenant piloto real, con un medidor real que soporte DLMS/COSEM y, si aplica, corte/reconexión
remoto) y, una vez ahí, correr `onboard_tenant.py` contra ese tenant real, dejar el poller y el
motor VEE corriendo con datos de producción de verdad, ajustar los umbrales de `vee_rule` según
lo que se vea en la práctica, y correr un ciclo de facturación completo. Nada de eso se puede
simular de forma honesta con datos sintéticos — sería fingir un resultado que en realidad
depende de tener un cliente real.

*(Esta tabla queda abierta hasta que haya un tenant piloto real con el que correr el resto de Sprint 10.)*

### Track C — Portal Web: planificado (2026-09-10, sin código todavía)

El usuario preguntó qué UI existe para tener una vista integral de todo lo que procesa
RenfyGrid. Respuesta honesta: **ninguna** — "Portal" hasta Sprint 8 siempre significó la API
(JSON), nunca una pantalla; lo único visual hasta ahora es DBeaver (browser de tablas genérico)
y el artifact de progreso de este documento (que es del *plan*, no de la *operación*). El
usuario confirmó que esta capa es parte del producto real, no una herramienta interna temporal.

Antes de construir nada (mismo método pedido al inicio del proyecto: planteamiento → arquitectura
→ diseño → plan de sprints), se investigó el patrón real de la industria en vez de inventarlo —
hallazgo: **"exception-first"** + jerarquía de pantallas **ISA-101** (estándar real de
automatización industrial, no específico de un vendor) es el patrón que se repite en MDM y
consolas de operación NOC/SCADA de referencia. El usuario confirmó y agregó un requisito
concreto: un **editor de reglas VEE** en algún punto de la UI.

Las 4 fases se actualizaron con el nuevo Track C: `01-planteamiento.md` (fila nueva en la tabla
de alcance), `02-arquitectura-general.md` §9 (stack: React+TypeScript+Vite+Tailwind+TanStack
Query, fuentes de la investigación, gap de `app_user`/login real encontrado), `03-diseno.md` §9
(entidad `app_user`, contratos de API nuevos, editor de reglas, jerarquía de pantallas de 3
niveles), `04-plan-sprints.md` §9 (épicas E12-E15, sprints C1-C4). Matriz funcional: F47-F51,
todas en ⚪ — **es planificación, no construcción**, tal como el usuario pidió para todo el
proyecto desde el primer mensaje.

*(Esta tabla se actualiza cuando arranque la construcción real de Track C.)*

### Sprint C1 — Autenticación real + tablero general: cerrado (2026-09-11)

**Objetivo:** un usuario real (no un JWT emitido a mano) inicia sesión y ve el tablero general
con conteos reales de un tenant de prueba. **Estado:** 🟢 — verificado por HTTP real y **de
forma visual real por el usuario en su propio navegador** (única vez hasta ahora que este
proyecto se confirma visualmente en un navegador, no solo con scripts).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-11 | **F47 construido**: migración `0009_app_user.sql` (RLS igual que el resto del esquema); `renmeter_common/passwords.py` (PBKDF2-HMAC-SHA256, stdlib, mismo criterio que `auth.py`); `renmeter_common/user_service.py` (`create_app_user`, `authenticate` — mensaje de error deliberadamente genérico, no distingue "no existe" de "contraseña incorrecta"); `POST /auth/login` en `portal-api` | F47 | `infra/db/migrations/0009_app_user.sql`, `services/common/renmeter_common/passwords.py`, `user_service.py` |
| 2026-09-11 | **Gap encontrado y corregido de paso**: `manual_edit.py` (F18, Sprint 4) actualizaba `value`/`source` al editar una lectura pero nunca tocaba `is_valid` — una lectura corregida a mano seguía apareciendo como "inválida" para siempre. Corregido: ahora `is_valid` pasa a `true` al editar | F18 (corregido) | `services/vee-engine/manual_edit.py` |
| 2026-09-11 | **F48 construido**: `portal-api/dashboard.py::dashboard_overview` — un conteo por etapa (medidores caídos, lecturas VEE inválidas, consumos en revisión, órdenes pendientes de aprobación), patrón exception-first; `GET /dashboard/overview` | F48 | `services/portal-api/dashboard.py` |
| 2026-09-11 | **18/18 pruebas unitarias puras nuevas** (`test_passwords.py`, en `services/common`) — verifica contraseña correcta, incorrecta, dos hashes de la misma contraseña son distintos (salt aleatorio), contraseña vacía rechazada, hash corrupto falla cerrado | F47 | `python -m unittest discover -s tests -v` (en `services/common/`) → **68/68 en total, todos los servicios** |
| 2026-09-11 | **`verify_login_and_dashboard_end_to_end.py` — corrida real**: usuario real dado de alta, login exitoso, contraseña incorrecta → 401, usuario desactivado → 401; con el JWT real que devolvió el login (no uno emitido a mano), `GET /dashboard/overview` refleja datos reales insertados directo en BD | F47, F48 | `python verify_login_and_dashboard_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"F47/F48 OK"** |
| 2026-09-11 | **Esqueleto del Portal Web real**: `services/portal-web/` — React 19 + TypeScript + Vite + Tailwind v4 + TanStack Query + React Router. Pantallas: Login (tenant/email/contraseña) y Overview (4 tiles Nivel 1, patrón exception-first, refetch cada 30s). `npm run build` limpio | F47, F48 | `services/portal-web/` |
| 2026-09-11 | **Gap real encontrado y corregido**: `portal-api` no tenía CORS habilitado — el navegador habría bloqueado toda llamada del frontend (puerto 5173) al backend (puerto 8000). Agregado `CORSMiddleware` + `RENFYGRID_CORS_ORIGINS` (variable de entorno, nunca un origen fijo) | F47, F48 | `services/portal-api/config.py`, `main.py` |
| 2026-09-11 | **Confirmado visualmente por el usuario, en su propio navegador**: se creó un usuario real (`demo@renfygrid.com`) sobre el tenant de demostración persistente ("RenfyGrid Demo"), el usuario abrió `http://localhost:5173`, inició sesión con esas credenciales reales, y confirmó ver el tablero general con las 4 tarjetas — la primera verificación visual real de todo el proyecto, no solo scripts/tests | F47, F48 | Confirmación directa del usuario tras probarlo |

*(Esta tabla se sigue completando a medida que avanza el Track C real.)*

### Sprint C2 — Tableros de Nivel 2: cerrado (2026-09-11)

**Objetivo:** cada tablero de etapa muestra solo lo anormal — un tenant sin anomalías ve un
tablero "limpio". **Estado:** 🟢 verificado real (backend por `TestClient`, frontend con
`npm run build` limpio + servido en vivo).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-11 | **3 piezas de backend nuevas/extendidas**: `vee-engine/list_invalid_readings.py` (`GET /vee/invalid-readings`, nuevo); `consumption/get_consumption.py` ampliado con filtro `anomaly_status` (`GET /consumption?anomaly_status=under_review`); `control/control_service.py::list_control_orders` (`GET /control-orders?status=`, nuevo — hasta ahora solo existían `POST /control-orders` y `POST /control-orders/{id}/approve`, sin forma de listar) | F49 | `services/vee-engine/list_invalid_readings.py`, `get_consumption.py`, `control_service.py` |
| 2026-09-11 | **`verify_stage_screens_end_to_end.py` — corrida real**: una lectura inválida real aparece en `/vee/invalid-readings` con su `validation_notes`; un consumo `under_review` aparece filtrado, uno `ok` no; una orden `pending_approval` aparece en la cola y desaparece de ella al aprobarla (mismo endpoint de Sprint 6) | F49 | `python verify_stage_screens_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"SPRINT C2 BACKEND E2E OK"** |
| 2026-09-11 | **5 pantallas de Nivel 2 + navegación**: `Meters.tsx` (HES), `Vee.tsx`, `Consumption.tsx`, `Control.tsx` (con acción de aprobar, no solo lectura), `Observability.tsx` — cada una consultando su endpoint ya filtrado del lado del servidor, con un estado vacío explícito ("Sin lecturas inválidas pendientes 👍") en vez de una tabla vacía sin contexto. Los tiles del tablero general (Nivel 1) ahora son links a su pantalla de Nivel 2 correspondiente | F49 | `services/portal-web/src/pages/{Meters,Vee,Consumption,Control,Observability}.tsx` |
| 2026-09-11 | **68/68 pruebas unitarias siguen pasando** tras los cambios en `get_consumption`/`control_service` (nada roto) + `npm run build` limpio del frontend | F49 | `python -m unittest discover` en los 5 servicios Python → OK; `npm run build` → exit 0 |

### Sprint C3 — Editor de reglas: cerrado (2026-09-11, corrido en /loop autónomo)

**Objetivo:** un operador crea una nueva versión de `vee_rule` desde la UI (sin SQL) y el
siguiente pase de validación ya la usa. **Estado:** 🟢 verificado real, incluyendo que el motor
VEE de verdad usa la regla creada desde la UI en su siguiente corrida (no solo que la fila se
guardó bien).

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-11 | **Decisión de diseño real, no simétrica entre las 3 tablas**: `vee_rule` y `consumption_anomaly_rule` NO tienen una clave de versión única (puede haber varias reglas activas a la vez para distintos canales/umbrales — la más estricta gana, F22/F19), así que crear una regla nueva nunca cierra otra sola; desactivar es una acción explícita aparte. `control_approval_level` SÍ tiene clave de versión (`tenant_id, order_type`) — crear una nueva para el mismo tipo de orden cierra la anterior automáticamente, para no dejar dos versiones activas del mismo tipo (una condición de carrera real que `approval_level_for` no maneja) | F50 | `services/vee-engine/vee_rules_admin.py`, `services/consumption/consumption_anomaly_rules_admin.py`, `services/control/approval_levels_admin.py` |
| 2026-09-11 | **9 endpoints nuevos** en `portal-api`: `GET`/`POST`/`PATCH /vee-rules`, `GET`/`POST`/`PATCH /consumption-anomaly-rules`, `GET`/`POST /control-approval-levels` | F50 | `services/portal-api/main.py` |
| 2026-09-11 | **`verify_rules_admin_end_to_end.py` — corrida real con 4 verificaciones**: (1) una regla `vee_rule` creada vía `POST /vee-rules` es usada de verdad por `run_vee_pass.py` (el motor real, no un mock) en la corrida siguiente — la lectura de prueba queda inválida con el `vee_rule_id` de la regla recién creada; (2) desactivarla la saca de `GET /vee-rules` (activas); (3) una regla de anomalía de consumo se crea correctamente; (4) crear un segundo nivel de aprobación para `suspension` cierra el primero (`valid_to` no nulo) y deja solo uno activo — la invariante que `approval_level_for` necesita, confirmada contra Postgres real, no solo diseñada | F50 | `python verify_rules_admin_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"SPRINT C3 BACKEND E2E OK"** |
| 2026-09-11 | **Pantalla de Configuración** (`Configuration.tsx`) con las 3 secciones — formularios reales (no un editor JSON genérico): reglas VEE (rango o intervalo esperado, según tipo), reglas de desviación de consumo, niveles de aprobación de control. Link nuevo desde el tablero general | F50 | `services/portal-web/src/pages/Configuration.tsx` |
| 2026-09-11 | **68/68 tests + todos los `verify_*.py` de sprints anteriores (VEE, consumo, control) re-corridos sin regresiones** tras tocar 3 tablas compartidas con casi todo el proyecto. `npm run build` limpio | F50 | `python -m unittest discover` en los 5 servicios → OK; `npm run build` → exit 0 |

### Sprint C4 — Nivel 3 (detalle y acciones): cerrado — Track C completo (2026-09-11, /loop autónomo)

**Objetivo:** aprobar/rechazar orden, editar lectura VEE, forzar lectura bajo demanda — todo
accionable desde la UI, no solo lectura. **Estado:** 🟢 verificado real. **Con este sprint,
Track C (Portal Web) queda completo: los 4 sprints planificados (C1-C4) están hechos y
verificados con evidencia real, no solo escritos.**

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-11 | **3 endpoints nuevos**: `POST /vee/invalid-readings/edit` (envuelve `manual_edit.edit_reading`, F18/Sprint 4, ahora accionable desde la UI); `GET /control-orders/{id}` (la orden puntual + su historial completo de `control_order_audit`, inmutable desde Sprint 6); `POST /meters/{id}/reads` (F04/Sprint 8, reusado tal cual como la acción "leer ahora" de la pantalla de detalle de medidor — no se reimplementó nada) | F51 | `services/portal-api/main.py`, `services/control/control_service.py::get_control_order_detail` |
| 2026-09-11 | **`verify_detail_actions_end_to_end.py` — corrida real con 3 verificaciones**: (1) editar una lectura inválida real vía HTTP la marca `is_valid=true`/`source='edited'` y deja exactamente 1 fila en `validated_reading_edit` (inmutable); (2) el detalle de una orden aprobada trae las 3 transiciones completas (`requested→pending_approval→approved`); (3) "leer ahora" contra el simulador real de Sprint 1 devuelve el valor correcto | F51 | `python verify_detail_actions_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"SPRINT C4 BACKEND E2E OK"** |
| 2026-09-11 | **3 piezas de frontend**: `Vee.tsx` ahora con un formulario de edición inline por fila (valor corregido, quién edita, justificación — los mismos 3 datos que exige `edit_reading` a nivel de BD); `Meters.tsx` con botón "Leer ahora" por medidor; `ControlOrderDetail.tsx` (ruta nueva `/control/:orderId`) mostrando el detalle de una orden con su línea de tiempo de auditoría completa | F51 | `services/portal-web/src/pages/{Vee,Meters,ControlOrderDetail}.tsx` |
| 2026-09-11 | **68/68 tests + `verify_estimation_and_edit_end_to_end.py` (Sprint 4) re-corrido sin regresiones** tras tocar `manual_edit.py`/`control_service.py`. `npm run build` limpio | F51 | `python -m unittest discover` → OK; `npm run build` → exit 0 |

*(Track C cerrado. El próximo trabajo de UI depende de qué decida el usuario — no hay más
sprints de Portal Web planificados sin nueva dirección.)*

### Sprint C5 — Integraciones (CIS): origen real de la petición + ping (2026-09-11)

**Objetivo:** convención real de `requested_by` (CIS externo / Portal / sistema), comando de
ping/estado nuevo, endpoint unificado de "Service Orders" — ver `06-benchmark-e2e-y-brechas.md`
§2-3/G1-G3, `04-plan-sprints.md` §9 (E16, sprint C5). **Estado:** 🟢 cerrado y desplegado a
producción, verificado con evidencia real.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Gap de seguridad real encontrado y corregido**: `requested_by` (control-orders) y `approver_name`/`approver_role` (aprobación) llegaban como texto libre en el body — cualquiera con un JWT válido podía escribir "cis:facturación" o subirse el rol a "supervisor" sin serlo. Corregido: `auth_dependency.get_actor()` devuelve la identidad completa y firmada del JWT; `requested_by_label()` deriva `cis:<email>` (rol `integration`, la cuenta de servicio de un CIS externo) o `portal:<email>` (cualquier humano) — nunca del body. El login (`/auth/login`) ahora incluye `email` como claim | `services/portal-api/auth_dependency.py`, `main.py` |
| 2026-09-11 | **Comando de ping construido** (`meter_ping.py`, hes-adapter-dlms): asociación DLMS real sin leer ningún registro — el comando más liviano del set estándar de industria (connect/disconnect/ping/lectura). `POST /meters/{id}/ping` | `services/hes-adapter-dlms/meter_ping.py` |
| 2026-09-11 | **Panel unificado real** (`service_orders.py`, portal-api): junta `control_order` + lecturas bajo demanda/pings auditados en `meter_event` (F09) en un solo feed, con origen (`_origin()`) y modo (automático/manual) resueltos — sin tabla nueva. `GET /integrations/service-orders` | `services/portal-api/service_orders.py` |
| 2026-09-11 | **8 pruebas unitarias puras nuevas** (`requested_by_label`, `_origin`) — 82/82 en total en los 6 servicios | `python -m unittest discover -s tests -v` → OK en los 6 servicios |
| 2026-09-11 | **`verify_service_orders_end_to_end.py` — corrida real, exitosa**: dos actores reales (rol `supervisor` vía Portal, rol `integration` simulando el CIS) hacen ping real contra el simulador y piden una orden de control cada uno — el feed unificado resuelve el origen correcto de las 4 filas sin que ningún actor lo haya podido declarar él mismo; un ping a un medidor sin gateway da 422, no 500 | `python verify_service_orders_end_to_end.py "postgresql://...@localhost:5455/renfygrid"` → **"SPRINT C5 E2E OK"** |
| 2026-09-11 | **4 scripts de verificación existentes actualizados y re-corridos sin regresiones** tras el cambio de contrato de `/control-orders`/`/control-orders/{id}/approve` (ya no reciben `requested_by`/`approver_name`/`approver_role` en el body) — `verify_portal_api_end_to_end.py`, `verify_stage_screens_end_to_end.py`, `verify_detail_actions_end_to_end.py` (backend) + `Control.tsx`/`api.ts` (frontend, se quitaron los dos campos de texto libre "Quién aprueba"/"Rol") | Los 8 `verify_*.py` de portal-api re-corridos → todos OK; `npm run build` limpio |
| 2026-09-11 | **Desplegado a producción**: recompilado con Nuitka (incremental), `renfygrid-portal-api` reiniciado en essmarplapp02, frontend actualizado en essmarplpxy03 — probado en vivo desde internet: `GET /api/integrations/service-orders` y `POST /api/meters/{id}/ping` responden correcto contra datos reales del tenant demo | `curl https://renfygrid.rensoftlabs.com/api/integrations/service-orders` con el JWT real del tenant demo |

*(Nota histórica: al cerrar C5 el 2026-09-11 el pendiente real era construir la pantalla
"Integraciones (CIS)" — resuelto el mismo día en el Sprint C6 siguiente.)*

### Sprint C6 — Pantalla real Integraciones (CIS) (2026-09-11)

**Objetivo:** construir la pantalla sobre el endpoint de C5 (mockup ya aprobado por el usuario).
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **`Integrations.tsx` construida**: 3 tarjetas resumen (total/automáticas/manuales), filtro por modo, tabla con hora/tipo/cuenta/origen/modo/estado (colores por origen y modo), nota con enlace real a Configuración → Niveles de aprobación de control | `services/portal-web/src/pages/Integrations.tsx` |
| 2026-09-11 | Ruta `/integrations` + link desde Vista general | `App.tsx`, `Overview.tsx` |
| 2026-09-11 | `npm run build` limpio, desplegado a producción — verificado en vivo: la ruta resuelve, y el bundle real contiene la pantalla y la llamada al endpoint | `curl https://renfygrid.rensoftlabs.com/integrations` → 200; bundle contiene "Integraciones (CIS)"/"service-orders" |

Commit `e20f04b`. Sigue **C7-C8** (HES/Ingesta: flota por marca + capa de agregación).

### Sprint C7-C8 — HES/Ingesta: flota por marca/modelo + capa de agregación (2026-09-11)

**Objetivo:** cerrar G4/G5 del benchmark E2E — un HES real siempre tiene una vista de flota
por marca/modelo y una vista de la capa de agregación (concentradores/gateways); RenfyGrid no
tenía ninguna de las dos, solo la tabla por medidor de Sprint C2.
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Backend (C7)**: `fleet_aggregation.py` nuevo — `fleet_summary()` (por marca/modelo: total, activos, reportando, % reportando, mismo criterio de "caído" que F34) y `gateway_summary()` (por concentrador: medidores, marcas agrupadas, último ciclo de polling real, % éxito 24h auditado en `meter_event`, F09). `observability.ingestion_metrics()` (F34) extendido con `brand`/`model`/`gateway_name` por medidor — el dato ya existía en el esquema desde Sprint 0-1, solo faltaba la vista. Dos endpoints nuevos: `GET /meters/fleet-summary`, `GET /gateways` | `services/portal-api/fleet_aggregation.py`, `observability.py`, `main.py` |
| 2026-09-11 | E2E real (Postgres + FastAPI TestClient): 2 marcas, 3 medidores, 2 concentradores, lecturas y eventos de polling reales insertados — confirma % reportando y % éxito 24h correctos, y que `/observability/ingestion` ya trae marca/modelo/concentrador | `verify_fleet_aggregation_end_to_end.py` → `SPRINT C7 E2E OK` |
| 2026-09-11 | Regresión completa sin romper nada: 8/8 unit tests, F34 OK, SPRINT C2/C4/C5/8 E2E OK | `python -m unittest discover -s tests`, `verify_observability_end_to_end.py`, `verify_stage_screens_end_to_end.py`, `verify_service_orders_end_to_end.py`, `verify_portal_api_end_to_end.py`, `verify_detail_actions_end_to_end.py` |
| 2026-09-11 | **Frontend (C8)**: `Meters.tsx` rediseñada como pantalla "HES / Ingesta" — tarjetas de flota por marca/modelo con barra de % reportando, tabla de concentradores (medidores/marcas/último polling/% éxito 24h), tabla de medidores ahora con columnas marca/modelo/concentrador. `api.ts` extendido: `getFleetSummary()`, `getGateways()`, `MeterIngestion` con `brand`/`model`/`gateway_name` | `services/portal-web/src/pages/Meters.tsx`, `api.ts` |
| 2026-09-11 | Backend compilado con Nuitka (WSL2, venv Python 3.9) — solo los módulos cambiados (`fleet_aggregation`, `observability`), `main.py` se mantiene como fuente (punto de entrada, política de portafolio) — desplegado a `essmarplapp02`, servicio `renfygrid-portal-api` reiniciado | `~/package_deploy_c7.sh` (WSL), `systemctl restart renfygrid-portal-api` → activo |
| 2026-09-11 | Frontend: `npm run build` limpio (bundle sin rutas mangled, `/api` correcto, contiene "fleet-summary"/"gateways"), desplegado a `essmarplpxy03` (`/var/www/renfygrid`) | `dist/assets/*.js` contiene "fleet-summary" y "/gateways" |
| 2026-09-11 | Verificado en vivo desde internet: `/api/openapi.json` en producción lista `/meters/fleet-summary` y `/gateways`; ambos + `/observability/ingestion` responden 401 (gateados por auth, no 404/500) sin token; `https://renfygrid.rensoftlabs.com/` y `/api/openapi.json` → 200 | `curl https://renfygrid.rensoftlabs.com/api/...` |

Sigue **C9** (rebranding visual + navegación real de 9 pantallas) y **C10** (editor de mapeo OBIS en Configuración) — planificados en `04-plan-sprints.md` §9, no iniciados.

### Sprint C9 — Rebranding + navegación lateral real en las 9 pantallas (2026-09-11)

**Objetivo:** cerrar E18 — las 9 pantallas comparten el mismo shell visual (tokens de marca de
rensoftlabs.com, panel lateral con las 8 rutas de nivel superior siempre visible), sin tocar la
lógica de ninguna. El usuario lo pidió tras ver el demo funcionando pero "muy básico" — quería
ver el menú y los paneles con cara de producto real, no que se cargaran datos nuevos.
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Tokens de marca** tomados de `rnsftlbs/com/www/index.html` (indigo `#4F46E5` — coincide con el `indigo-600` de Tailwind que las pantallas ya usaban por convención —, tono oscuro de marca `#0A0F1E`, Inter). Registrados en `index.css` vía `@theme` de Tailwind v4 (`--color-ink`, `--font-sans`) | `services/portal-web/src/index.css` |
| 2026-09-11 | **`AppShell.tsx` nuevo**: panel lateral fijo en desktop (cajón deslizante en móvil) con las 8 rutas de nivel superior, resaltado de ruta activa, botón de cerrar sesión — capa puramente visual/de navegación | `services/portal-web/src/components/AppShell.tsx` |
| 2026-09-11 | **`StagePage.tsx` ahora delega en `AppShell`** — las 8 pantallas que ya usaban `StagePage` (Meters/Vee/Consumption/Control/ControlOrderDetail/Observability/Integrations/Configuration) adoptan el nuevo shell sin que ninguna cambiara una línea de su lógica (solo cambió el wrapper compartido) | `services/portal-web/src/components/StagePage.tsx` |
| 2026-09-11 | **`Overview.tsx`** (no usaba `StagePage`) migrada a `AppShell` — se quitó su header/nav propio (links sueltos + botón de logout), el contenido (KPIs, queries) no cambió | `services/portal-web/src/pages/Overview.tsx` |
| 2026-09-11 | **`Login.tsx`**: retoque visual (fondo de marca oscuro, isotipo "R" en indigo) — mismos campos/handlers, sin cambio de lógica | `services/portal-web/src/pages/Login.tsx` |
| 2026-09-11 | `tsc -b && vite build` limpio (el chequeo de tipos de TypeScript ya cubre props/imports rotos de un cambio de wrapper), bundle sin rutas mangled, contiene el color de marca `#0a0f1e` | `dist/assets/*.css` contiene "#0a0f1e" |
| 2026-09-11 | Desplegado a `essmarplpxy03` (`/var/www/renfygrid`) — solo frontend, sin cambios de backend en este sprint, no hizo falta tocar `essmarplapp02` | `nginx -t` OK, reload |
| 2026-09-11 | Verificado en vivo: el HTML servido en `https://renfygrid.rensoftlabs.com/` referencia exactamente los mismos hashes de build (`index-C4dipvks.js`/`index-Du77VRtQ.css`) que el build local recién generado | `curl https://renfygrid.rensoftlabs.com/` |
| 2026-09-11 | **Credenciales del tenant demo reparadas**: la contraseña de `demo@renfygrid.com` en producción no coincidía con la documentada — reseteada por SQL directo (mismo hash PBKDF2 de `renmeter_common/passwords.py`) para que el usuario pudiera entrar y ver el rediseño en su propio navegador. Tenant demo tiene 5 medidores pero 0 gateways/lecturas — aviso dado al usuario para que el estado vacío de Concentradores no se lea como error | login real por HTTP → 200, JWT válido |

Sigue **C10** (editor de mapeo OBIS en Configuración) — planificado en `04-plan-sprints.md` §9,
no iniciado.

### Sprint C10 — Editor de mapeo OBIS en Configuración (2026-09-11)

**Objetivo:** cerrar E19 — cambiar el mapeo OBIS de una marca/modelo desde la UI en vez de SQL
directo, mismo patrón de versionado que `control_approval_level` y mismo criterio de
verificación real que F06 (Sprint 2): el siguiente ciclo del poller ya usa el cambio, sin
tocar `poller.py`.
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Backend**: `protocol_mapping_admin.py` (nuevo, en `hes-adapter-dlms` junto a `obis_mapping.py`) — `list_protocol_mappings()` y `create_protocol_mapping()`. `meter_protocol` SÍ tiene clave de versión bien definida `(tenant_id, brand, model)` (índice `meter_protocol_active_idx`), igual que `control_approval_level` con `order_type` — por eso `create_protocol_mapping` cierra la versión anterior activa para esa misma marca/modelo antes de insertar la nueva (mismo patrón que `approval_levels_admin.py`, no el de `vee_rule`). Dos endpoints nuevos: `GET /obis-mappings`, `POST /obis-mappings` | `services/hes-adapter-dlms/protocol_mapping_admin.py`, `services/portal-api/main.py` |
| 2026-09-11 | **E2E real, mismo criterio que F06 pero por el camino de UI**: crea mapeo v1 por HTTP, crea v2 para la misma marca/modelo (confirma que v1 quedó cerrada), y del lado del poller — `obis_mapping.build_cache(...).refresh()` + `.load()`, sin tocar `poller.py` — confirma que `channels_for()` ya ve la v2 | `verify_protocol_mapping_admin_end_to_end.py` → `SPRINT C10 E2E OK` |
| 2026-09-11 | Bug propio encontrado y corregido en el script de verificación (no del producto): `ConfigCache.refresh()` escribe el snapshot a disco pero no llena la memoria — hace falta `.load()` después, que el script no llamaba al principio | — |
| 2026-09-11 | Regresión completa sin romper nada: 8/8 unit tests + 6 scripts E2E existentes (C2/C4/C5/C7/8, F34) siguen en verde | `python -m unittest discover -s tests`, más los `verify_*` de C2/C4/C5/C7/8/F34 |
| 2026-09-11 | **Frontend**: `ProtocolMappingSection` nueva en `Configuration.tsx`, mismo patrón visual que `ApprovalLevelsSection` — formulario marca/modelo/protocolo/canal/código OBIS/índice de atributo, agregar un canal conserva los demás de esa marca/modelo (parte del `obis_mapping` activo si ya existe), lista de mapeos activos con sus canales como chips. `api.ts`: `getProtocolMappings()`, `createProtocolMapping()` | `services/portal-web/src/pages/Configuration.tsx`, `api.ts` |
| 2026-09-11 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "obis-mappings" | `dist/assets/*.js` |
| 2026-09-11 | Desplegado: backend compilado con Nuitka (solo `protocol_mapping_admin`, `main.py` como fuente) a `essmarplapp02`; frontend a `essmarplpxy03` | `systemctl restart renfygrid-portal-api` → activo, `nginx reload` |
| 2026-09-11 | Verificado en vivo: `https://renfygrid.rensoftlabs.com/` sirve exactamente los hashes del build nuevo; `/api/obis-mappings` responde 401 (gateado por auth, no 404/500) sin token | `curl https://renfygrid.rensoftlabs.com/...` |

Con esto se cierran **todos** los sprints C5-C10 planificados en `04-plan-sprints.md` §9 tras el
benchmark E2E — no queda ningún ítem pendiente de ese plan.

### Fuera de sprint — redirect automático a login en sesión vencida (2026-09-11)

**Motivo:** el usuario reportó en vivo una tanda de `401 (Unauthorized)` en la consola del
navegador (dashboard/overview, fleet-summary, gateways, observability/ingestion) — el JWT dura
1h (`renmeter_common/auth.py`) y ya había vencido desde que se generaron las credenciales demo;
el Portal se quedaba en la pantalla con las llamadas fallando en silencio, sin avisar que había
que volver a entrar.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | `api.ts`: `request()` ahora detecta un 401 en cualquier endpoint que no sea `/auth/login` (para no interferir con el mensaje de "credenciales incorrectas" del propio login), limpia el token y manda a `/login` — en vez de dejar la pantalla con queries fallando sin explicación | `services/portal-web/src/api.ts` |
| 2026-09-11 | `tsc -b && vite build` limpio, desplegado a `essmarplpxy03`; verificado en vivo que el HTML servido referencia el bundle nuevo | `curl https://renfygrid.rensoftlabs.com/` |

### Sprint C11 — Cierre de los 4 parciales del MVP (F08/F10/F15/F17) (2026-09-11)

**Objetivo:** con los benchmarks E2E (C5-C10) ya cerrados, el usuario pidió seguir con lo
pendiente REAL del plan — no Track B (Balance de Red, otro dominio, 11 funciones sin empezar),
sino los 4 huecos parciales que quedaban en el MVP de energía ya construido: F08 (cola
persistente de reintentos), F10 (particionado de `raw_reading`), F15 (coherencia entre
canales), F17 (métodos de estimación restantes).
**Estado:** 🟢 cerrado y desplegado a producción. El primer intento de despliegue quedó
bloqueado por el clasificador de auto-modo ("Production Deploy") al intentar el `pg_dump` de
respaldo + las migraciones 0010/0011 en `essmarplapp02` — el usuario agregó una regla de
permiso puntual en `~/.claude/settings.json` (`autoMode.allow`/`environment`) y el despliegue
se completó en un segundo intento, sin reintentar nada a la fuerza.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-11 | **F17 completado**: `vee_engine.estimate_gap` ahora soporta los 3 métodos del diseño (`03-diseno.md` SS5), no solo `linear_interpolation` — `customer_historical_average` (promedio de lecturas REALES del mismo medidor a la misma hora del día, cruzando días) y `similar_customers_average` (promedio de lecturas de OTROS medidores cerca del mismo instante). Nunca inventa un promedio sin datos: `InsufficientHistoryError` si no hay ninguna lectura que matchee (distinto de `NotImplementedError`, que es para un método no reconocido). `run_vee_estimation.py` trae el historial correcto según el método antes de llamar a `estimate_gap` | F17 | `services/vee-engine/vee_engine.py`, `run_vee_estimation.py` |
| 2026-09-11 | 5 pruebas unitarias nuevas (17/17 en `vee-engine`) + E2E real: un medidor con lecturas en 3 días distintos a la misma hora (falta el día 2) se llena con el promedio propio (120, NO la interpolación que daría 130 — confirma que usa el método pedido); un segundo medidor "similar" con una lectura real en el instante exacto del hueco llena el hueco del primero con ESE valor | F17 | `verify_estimation_methods_end_to_end.py` → `SPRINT C11 F17 E2E OK` |
| 2026-09-11 | **F15 completado**: nueva regla `vee_rule.type = 'channel_consistency'` (`channel`, `reference_channel`, `min_ratio`, `max_ratio`) — compara dos canales del MISMO medidor en el MISMO instante (ej. reactiva/activa). `validate_reading` recibe `reference_value` ya resuelto por el llamador (`run_vee_pass.py`, que va a `raw_reading` a buscarlo) — nunca toca BD ella misma. Sin lectura del canal de referencia en ese instante: pasa SIN evaluar (no se adivina un ratio), nunca se invalida por eso | F15 | `services/vee-engine/vee_engine.py`, `run_vee_pass.py` |
| 2026-09-11 | 5 pruebas unitarias nuevas (22/22 en `vee-engine`) + E2E real: activa=100/reactiva=60 (ratio 0.6, dentro de [0,1]) → válida; activa=100/reactiva=150 (ratio 1.5) → inválida con regla trazable; reactiva=60 sin activa en ese instante → válida, sin evaluar | F15 | `verify_channel_consistency_end_to_end.py` → `SPRINT C11 F15 E2E OK` |
| 2026-09-11 | **F08 completado**: migración `0010_poller_retry_queue.sql` — tabla `poller_retry_queue` (una fila por `(tenant_id, meter_id)`, RLS). `poller.py`: `due_meters` excluye medidores con `next_retry_at` futuro; al agotar los reintentos del ciclo, `record_retry_failure` sube el medidor a la cola con backoff EXPONENCIAL (`--retry-queue-base-seconds * 2^(failure_count-1)`, tope `--retry-queue-max-seconds`, nunca fijo en código); al responder, `clear_retry_queue` lo saca | F08 | `infra/db/migrations/0010_poller_retry_queue.sql`, `services/hes-adapter-dlms/poller.py` |
| 2026-09-11 | E2E real con un medidor apuntando a un puerto cerrado: ciclo 1 falla y entra a la cola (`failure_count=1`); ciclo 2 inmediato lo EXCLUYE (backoff de 1h no vencido, cero intentos nuevos); se adelanta `next_retry_at` al pasado y se levanta el simulador real en ese puerto — ciclo 3 reintenta, tiene éxito, sale de la cola | F08 | `verify_poller_retry_queue_end_to_end.py` → `SPRINT C11 F08 E2E OK` |
| 2026-09-11 | **F10 completado**: migración `0011_raw_reading_partitioning.sql` — `0001_init.sql` declaraba `raw_reading` como hypertable de TimescaleDB (`create_hypertable`), extensión que **nunca estuvo disponible** ni en desarrollo (Postgres portable de Windows) ni en producción (solo v2.10.3 para PG13 en `essmarplapp02`, incompatible con el PG16 real — causó la caída breve ya documentada). Esa línea era un bug latente: correr las migraciones desde cero en cualquiera de los dos entornos reales falla ahí mismo. Sustituto real: **particionado declarativo nativo de Postgres** por rango mensual de `"timestamp"` — mismo beneficio práctico (poda de particiones, DROP de una partición vieja completa para retención) sin ninguna extensión de terceros. Tabla vieja reconstruida (Postgres no permite convertir in-place), renombrada como respaldo (`raw_reading_pre_partition_backup`, NO borrada) tras copiar los datos reales. Partición `DEFAULT` como red de seguridad. `services/common/renmeter_common/partition_maintenance.py` (nuevo, mismo patrón de job aparte que `refresh_obis_mapping_cache.py`): asegura las particiones futuras que falten — DDL real, corre con el rol admin, no `renfygrid_app` | F10 | `infra/db/migrations/0011_raw_reading_partitioning.sql`, `services/common/renmeter_common/partition_maintenance.py` |
| 2026-09-11 | 5 pruebas unitarias puras nuevas (24/24 en `common`) sobre la aritmética de meses + E2E real: dos tenants con una lectura real cada uno — RLS sigue aislando a través de la tabla particionada (con el rol de APLICACIÓN, no el admin — **si se usa el admin la prueba miente**: los superusuarios se saltan RLS siempre, el mismo bug de fondo que Sprint 0 ya documentó, encontrado de nuevo al escribir mal esta misma prueba la primera vez); cada fila cae en la partición del mes correcto, no en `DEFAULT`; `ensure_partitions` crea una partición futura real y una lectura de esa fecha cae ahí | F10 | `infra/db/verify_partitioning_end_to_end.py` → `SPRINT C11 F10 E2E OK` |
| 2026-09-11 | Regresión completa sin romper nada, incluyendo lo que más podía verse afectado por particionar `raw_reading`: `verify_rls.py`, `verify_retention_end_to_end.py` (F12 — una lectura de "hace 10 años" cae en `DEFAULT` y la retención la sigue borrando igual), `verify_backup_restore_end_to_end.py` (F13), y los E2E de HES/poller/VEE/observabilidad/fleet ya existentes — todos siguen en verde | — | Ver comandos en esta misma sección |

| 2026-09-11 | **Desplegado a producción** (`essmarplapp02`): respaldo real primero (`pg_dump -Fc`, `/tmp/renfygrid_pre_c11_backup_*.dump`, 72 KB), luego las migraciones 0010/0011 — verificado en el propio servidor: tabla particionada con 3 particiones (`raw_reading_y2026_m09`, `_m10`, `default`), `poller_retry_queue` presente. Código: `vee_engine.py` y `partition_maintenance.py` compilados con Nuitka (este último SÍ se compila, a diferencia de los jobs sueltos de `hes-adapter-dlms` — vive dentro del paquete `renmeter_common`, donde la convención ya establecida es compilar todo salvo `__init__.py`); `poller.py`/`run_vee_pass.py`/`run_vee_estimation.py` copiados como fuente (ya eran punto de entrada). `renfygrid-portal-api` no importa ninguno de estos módulos directamente — no hizo falta reiniciarlo, confirmado que sigue respondiendo (200) después del cambio de esquema | F08, F10, F15, F17 | `essmarplapp02:/opt/renfygrid/{hes-adapter-dlms,vee-engine,common}` |

**Pendiente, no urgente**: `partition_maintenance.py` no tiene todavía un cron real que la
corra periódicamente en producción — las particiones de septiembre/octubre 2026 ya existen
(las creó la propia migración 0011), pero hace falta antes de que se acabe octubre. Mismo
criterio que "formalizar el pipeline de build de Nuitka en un script versionado" — pendiente
real pero no bloqueante para el pilotos actual (0 lecturas en producción todavía).

### Sprint C11-2 — Panel real de VEE, backend + frontend (2026-09-11)

**Motivo:** el usuario reportó que "el panel de VEE se ve sin empezar" y pidió validar que el
módulo estuviera completamente cubierto backend+frontend. Resultado real: **F14-F19 sí estaban
completos y verificados** (matriz funcional, Sprint 3-4 y C11) — el gap era 100% de exposición:
la pantalla `Vee.tsx` solo mostraba la cola de excepciones inválidas, sin resumen, sin las
lecturas ESTIMADAS visibles (F16/F17, el trabajo más real del motor) y sin distinguir un rango
fuera de límite de una coherencia entre canales rota (F15/C11). El editor de reglas en
Configuración tampoco dejaba crear una regla `channel_consistency`, ni elegir el método de
estimación (`missing_interval` siempre mandaba `linear_interpolation` fijo en el código del
frontend, sin importar que el backend ya soportara los otros 2 desde Sprint C11).
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Backend**: `vee_summary.py` (nuevo) — `vee_summary()` (inválidas pendientes por tipo de regla, estimadas/editadas en 24h, reglas activas por tipo) y `list_estimated_readings()` (lecturas `source='estimated'` con el `estimation_method` real de la regla que las generó). `list_invalid_readings.py` extendido con `rule_type` (join a `vee_rule.type`) para distinguir rango de coherencia entre canales. Dos endpoints nuevos: `GET /vee/summary`, `GET /vee/estimated-readings` | `services/vee-engine/vee_summary.py`, `list_invalid_readings.py`, `services/portal-api/main.py` |
| 2026-09-11 | E2E real: 2 reglas activas (range + channel_consistency) + 1 inválida por cada una + 1 estimada + 1 editada reales — confirma el resumen exacto, el método de estimación real en la lista de estimadas, y que cada inválida trae su `rule_type` correcto | `verify_vee_summary_end_to_end.py` → `SPRINT C11-2 VEE PANEL E2E OK` |
| 2026-09-11 | Regresión: 8/8 unit tests + `verify_stage_screens_end_to_end.py`/`verify_detail_actions_end_to_end.py` (ya usaban `/vee/invalid-readings`) siguen en verde con el campo `rule_type` nuevo | — | — |
| 2026-09-11 | **Frontend**: `Vee.tsx` rediseñada — 4 tarjetas de resumen (inválidas/estimadas 24h/editadas 24h/reglas activas), filtro por tipo de regla en la cola de excepciones (con badge de tipo por fila), sección nueva "Lecturas estimadas" con el método usado por fila. `Configuration.tsx`: `VeeRulesSection` ahora soporta crear reglas `channel_consistency` (canal de referencia + ratio min/max) y elegir el método de estimación real (antes fijo a `linear_interpolation`) | `services/portal-web/src/pages/Vee.tsx`, `Configuration.tsx`, `api.ts` |
| 2026-09-11 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "vee/summary"/"vee/estimated-readings"/"channel_consistency". Desplegado: backend (Nuitka) a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. Verificado en vivo: bundle servido coincide con el build, `/api/vee/summary` responde 401 (gateado por auth, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |

### Fuera de sprint — login rellenaba con password generado por el navegador (2026-09-11)

**Motivo:** el usuario reportó "Email, contraseña o tenant incorrectos" con un password
visiblemente distinto al real (`RenfyGrid-Demo-2026`) — un string tipo `VMm_RwpY_v18iIjc`,
patrón clásico de contraseña autogenerada por Chrome. Confirmado por HTTP directo que las
credenciales reales seguían funcionando (200, JWT válido) — el bug era del formulario, no de
la cuenta: sin `autoComplete`/`name` en los inputs, el navegador no reconocía el formulario
como un login real y ofrecía generar una contraseña nueva en vez de usar la guardada.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | `Login.tsx`: `autoComplete="username"`/`"current-password"` + `name` en los 3 campos — el navegador ahora reconoce el formulario como login, no como registro | `services/portal-web/src/pages/Login.tsx` |
| 2026-09-11 | `tsc -b && vite build` limpio, desplegado a `essmarplpxy03`, verificado en vivo que el HTML servido referencia el bundle nuevo | `curl https://renfygrid.rensoftlabs.com/` |

### Sprint C11-3 — Panel de VEE por etapa, con benchmark real (2026-09-11)

**Motivo:** el usuario, viendo ya el resultado de C11-2, insistió: "el panel de VEE se ve como
un bosquejo... cada letra V.E.E. implica un nivel de procesamiento y deberian haber
estadisticas y KPIs en esos niveles... ¿revisaste el mercado de MDM para ver lo que cubre un
VEE?". Se investigó de verdad (no memoria de entrenamiento) antes de rediseñar:

- **Oracle Utilities MDM** tiene un dashboard real "VEE Exceptions" con páginas
  Overview/Exception Trend/Exception Analysis/Exception Analysis Detail, conteo de los 5 tipos
  de excepción más frecuentes, y KPIs con bandas verde/amarillo/rojo configurables
  ([Oracle Utilities Analytics — Meter Data Analytics](https://docs.oracle.com/en/industries/energy-water/analytics/251000/ouaw-mdm-metric/G49493.pdf)).
- **Itron Enterprise Edition** distingue explícitamente "validation sets" de "estimation sets"
  y una cola de trabajo de excepciones aparte
  ([Itron — Validation, Estimation, Editing](https://docs.itrontotal.com/IEEMDMInstall/Content/Topics/Validation%20Estimation%20Editing.htm)).
- **Landis+Gyr Core MDMS**: "exception management to process all validation and estimation
  exceptions not automatically handled by VEE rules"
  ([Landis+Gyr — Core MDMS](https://www.landisgyr.com/product/core-mdms/)).
- Tasa de excepción como KPI de calidad de datos: <2% excelente, 2-5% aceptable, >5%
  preocupante — banda genérica (no un benchmark propio del sector energía, que no se encontró
  publicado) usada aquí a falta de uno mejor, documentado como tal.

**Conclusión real, sin inflar el hallazgo**: F14-F19 SIGUEN completos — el gap de C11-2 no era
falso, solo insuficiente: un resumen plano no es lo mismo que 3 etapas con sus propios números,
que es exactamente como lo hacen los 3 productos de referencia revisados.
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Backend, `vee_summary.py` reescrito en 3 funciones por etapa**: `validation_summary()` (total procesado, excepciones, `exception_rate_pct` — nunca 0% sin datos, `None` explícito —, excepciones por tipo, reglas activas, tendencia de 7 días), `estimation_summary()` (`fill_rate_pct` = % de la serie que tuvo que estimarse, no solo el conteo crudo, desglose por método real), `editing_summary()` (total/24h, top editores). `list_edits()` nuevo — lee el historial real de `validated_reading_edit` (la auditoría append-only de F18), no una inferencia sobre `source='edited'`. `GET /vee/summary` ahora devuelve `{validation, estimation, editing}`; endpoint nuevo `GET /vee/edits` | `services/vee-engine/vee_summary.py`, `services/portal-api/main.py` |
| 2026-09-11 | **E2E real con una edición de verdad** (vía `manual_edit.edit_reading`, no un insert que se saltaría la auditoría): 2 excepciones (rango + coherencia) + 1 estimada + 1 edición real — confirma los 3 bloques exactos: `exception_rate_pct=100.0`, `fill_rate_pct≈33.3`, `edits_24h=1` con el editor real en `top_editors`, y que `/vee/edits` trae el valor anterior/nuevo/justificación reales | `verify_vee_summary_end_to_end.py` → `SPRINT C11-3 VEE PANEL E2E OK` |
| 2026-09-11 | Regresión: 8/8 unit tests + `verify_stage_screens_end_to_end.py`/`verify_detail_actions_end_to_end.py` siguen en verde | — | — |
| 2026-09-11 | **Frontend, `Vee.tsx` reestructurada en 3 secciones reales** (Validación/Estimación/Edición manual, cada una con su encabezado "V"/"E"/"E"): Validación con tasa de excepción coloreada por banda (verde/amarillo/rojo) + tendencia de 7 días (barras CSS simples, sin librería) + la cola de excepciones filtrable ya existente; Estimación con % de la serie estimada + desglose por método + la lista de estimadas; Edición manual con total/24h + top editores + una tabla nueva del historial real (`valor anterior → valor nuevo`, quién, justificación) | `services/portal-web/src/pages/Vee.tsx`, `api.ts` |
| 2026-09-11 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "vee/edits"/"trend_7d"/"exception_rate_pct". Desplegado: backend (Nuitka) a `essmarplapp02`; frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide, `/api/vee/edits` responde 401 (gateado, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |

### Sprint C11-4 — HES/Ingesta: eventos/alarmas + cola de reintentos, con benchmark real (2026-09-11)

**Motivo:** el usuario pidió el mismo ejercicio que ya se hizo con VEE (Sprint C11-3) para el
panel de HES/Ingesta: "busca en el mercado y observa que debe tener ese modulo. Se ve
incompleto" — con la instrucción explícita de no usar **ningún dato hardcodeado**.

**Investigado antes de tocar código** (no memoria de entrenamiento):
- Consenso de varios proveedores de HES (Genus, Kimbal, tblocks): "Network Management Systems
  that provide **operational dashboards, communication statistics, meter reachability reports,
  and alarm management**"
  ([Genus — Head End System](https://genuspower.com/product/head-end-system-hes/),
  [tblocks — What is a HES](https://tblocks.com/glossary/head-end-system/)).
- "DC (Data Concentrator) data include statistics of communication, **event logs** and
  meta-data" ([ScienceDirect — Data Concentrator](https://www.sciencedirect.com/topics/computer-science/data-concentrator)).
- "HES manages... all functions related to reading, sending commands to devices, and
  **monitoring performance in real time**" (mismas fuentes).
- Eaton Brightlayer: "**real-time read success rates**, collector uptime, and signal quality
  metrics... per zone and fleet-wide" ([Eaton — Operational Data Management for AMI](https://www.eaton.com/us/en-us/digital/brightlayer/brightlayer-utilities-suite/Operational-Data-Management-Software-and-AMI-suite.html)).
- HES usan "intelligent scheduling, **automated retries**, communication health monitoring, and
  **gap reconciliation mechanisms**" (mismas fuentes).

**Hallazgo real, sin inventar nada**: F05 (alarmas reales vía push DLMS), F08 (cola de
reintentos, Sprint C11) y F09 (auditoría de comunicación) YA estaban construidos y verificados
end-to-end — pero **ninguno de los tres se veía en el Portal**. `fleet_summary`/`gateway_summary`
(Sprint C7) solo mostraban un % de éxito agregado; nunca el feed real de eventos, ni la cola de
reintentos. Exactamente el mismo patrón de gap que VEE en C11-2/C11-3: backend completo,
exposición incompleta. **Ningún campo nuevo de UI usa un valor inventado** — las 3 secciones
nuevas leen directo de `meter_event` (F05/F09, ya poblada por código real) y `poller_retry_queue`
(F08, Sprint C11, ya poblada por `poller.py`).
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Backend, `fleet_aggregation.py` extendido** con 3 funciones nuevas: `event_summary()` (alarmas 24h, críticas 24h, fallas de comunicación 24h, tasa de éxito de comunicación 24h, medidores en cola de reintento — todo de `meter_event`/`poller_retry_queue` reales), `list_meter_events()` (feed real de `meter_event` con marca/modelo/concentrador, filtrable por tipo), `list_retry_queue()` (estado real de `poller_retry_queue`). Endpoints nuevos: `GET /meters/event-summary`, `GET /meters/events`, `GET /meters/retry-queue` | `services/portal-api/fleet_aggregation.py`, `main.py` |
| 2026-09-11 | E2E real: 1 alarma crítica + 2 comunicaciones exitosas + 1 fallida + 1 medidor real en la cola de reintentos — confirma `alarms_24h=1`, `comm_success_rate_24h≈66.7`, `meters_in_retry_queue=1`, el feed trae las 4 filas con concentrador resuelto, el filtro por tipo funciona, y la cola de reintentos trae `failure_count`/`last_error` reales | `verify_hes_events_end_to_end.py` → `SPRINT C11-4 HES EVENTS E2E OK` |
| 2026-09-11 | Regresión: 8/8 unit tests + `verify_fleet_aggregation_end_to_end.py`/`verify_observability_end_to_end.py` siguen en verde | — | — |
| 2026-09-11 | **Frontend, `Meters.tsx` extendida** con 4 tarjetas de KPI al inicio (alarmas 24h, éxito de comunicación 24h, fallas 24h, medidores en cola) y 2 secciones nuevas: "Cola de reintentos" (tabla con intentos fallidos/último error/próximo intento en tiempo relativo) y "Eventos y alarmas" (feed filtrable por tipo, con badge de severidad) | `services/portal-web/src/pages/Meters.tsx`, `api.ts` |
| 2026-09-11 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "meters/events"/"meters/retry-queue"/"meters/event-summary". Desplegado: backend (Nuitka) a `essmarplapp02`; frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide exacto (JS y CSS), `/api/meters/events` responde 401 (gateado, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |

### Sprint C11-5/C11-6 — Control (SCR) y Consumo, con benchmark real (2026-09-11)

**Motivo:** el usuario pidió el mismo ejercicio de mercado que VEE/HES ya tuvieron, esta vez
para Control y Consumo — "Mira la industria. No te ahorres nada en el analisis y la busqueda y
validacion".

**Investigado antes de tocar código** (no memoria de entrenamiento):
- MDMS reporting real cubre "billing validation reports, usage exception reports, VEE summary
  reports, TOU and demand rate consumption reports, **non-revenue loss analysis**, and customer
  usage trend reports" ([Bynry — MDMS Reporting and Analytics](https://www.bynry.com/blog/mdms-reporting-analytics-utilities)).
- Utilidades reales miden "percentage of successful reads, **command success rates**, or
  **retry backlog**" para las órdenes de conexión/desconexión remota
  ([Grid/EPRI — Meter Remote Connect Disconnect](https://smartgrid.epri.com/UseCases/Meter%20Remote%20Connect%20Disconnect_ph2add.pdf)).
- **Hallazgo más serio que un gap de UI**: ningún CIS/MDM de referencia ejecuta un corte sin
  antes chequear si la cuenta es un "usuario de protección especial". En Colombia esto es
  requisito **real y vigente**: Ley 142 de 1994 + normas posteriores de la CRA/CREG — la
  Resolución CREG 108/1997 exige que la empresa considere "sujetos de especial protección"
  antes de suspender, con derecho a debido proceso
  ([CREG — normativa de servicios públicos](https://creg.gov.co/)).

**Confirmado con el usuario antes de construir** (dado que esto cambia el flujo de aprobación,
no solo agrega un tablero): sí construir la lista de cuentas protegidas, con alcance acotado —
solo la bandera de exclusión + quién/cuándo/por qué en texto libre; la clasificación real del
cliente (es un hospital, es un colegio...) queda fuera de RenfyGrid, es dato de CIS.
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Control — migración `0012_meter_protection.sql`**: `meter.protected_from_suspension`/`protection_reason`/`protection_marked_by`/`protection_marked_at`. `services/control/account_protection.py` (nuevo): `is_protected`/`mark_protection`/`bulk_mark_protection` (por `account_number`, para carga masiva)/`list_protected_meters`. `control_service.request_order` ahora **rechaza de entrada** (422, `ProtectedAccountError`) una `suspension`/`disconnection` contra una cuenta protegida, salvo `override_protection=true` + `override_justification` propia (nunca la misma justificación original) — el override queda trazado en `control_order_audit.detail`, no solo un flag silencioso | `infra/db/migrations/0012_meter_protection.sql`, `services/control/account_protection.py`, `control_service.py` |
| 2026-09-11 | **Control — KPIs reales**: `control_summary()` nuevo (`command_success_rate_pct` = confirmadas/(confirmadas+fallidas), `None` sin datos — nunca 0% inventado —, desglose por tipo/estado, pendientes). `list_control_orders`/`get_control_order_detail` ahora traen `meter_protected`. Endpoints nuevos: `GET /control-orders/summary`, `GET /meters/protected`, `POST /meters/{id}/protection`, `POST /meters/protection/bulk` | `services/control/control_service.py`, `services/portal-api/main.py` |
| 2026-09-11 | E2E real: medidor marcado protegido → orden de suspensión sin override da 422; con override real (justificación propia) da 201 y la auditoría trae el motivo de protección + la justificación del override; carga masiva con 1 cuenta real + 1 inexistente confirma `marked`/`not_found` reales; resumen sin nada despachado da tasa `None`, con 1 confirmada + 1 fallida reales da exactamente 50.0% | `verify_meter_protection_end_to_end.py` → `SPRINT C11-5 METER PROTECTION E2E OK` |
| 2026-09-11 | **Consumo — `consumption_summary.py` (nuevo)**: `consumption_summary()` (tasa de anomalía, % listo para facturar, desglose por estado, órdenes por tipo de acción), `list_consumption_orders()` (feed real de `reread_order`/`inspection_order`, F23, invisibles desde Sprint 5), `resolve_anomaly()` — cierra una anomalía investigada (`anomaly_status='resolved'`, en el esquema desde Sprint 0, nunca se escribía) y deja rastro real en `meter_event` (`type='anomaly_resolved'`). Endpoints nuevos: `GET /consumption/summary`, `GET /consumption/orders`, `POST /consumption/resolve` | `services/consumption/consumption_summary.py`, `services/portal-api/main.py` |
| 2026-09-11 | E2E real: 1 consumo `ok` + 1 `under_review` (con su orden real de relectura) + 1 `resolved` preexistente confirma tasa de anomalía ≈33.3%, listo-para-facturar ≈66.7%; resolver el `under_review` real lo baja a 0%; resolver el mismo periodo otra vez da 404, no un 200 falso | `verify_consumption_summary_end_to_end.py` → `SPRINT C11-6 CONSUMPTION PANEL E2E OK` |
| 2026-09-11 | Regresión completa sin romper nada: unit tests de `control`/`portal-api`, `verify_control_execution_end_to_end.py` (F28/F29/F30, camino exitoso y de falla), `verify_service_orders_end_to_end.py`, `verify_stage_screens_end_to_end.py`, `verify_detail_actions_end_to_end.py`, `verify_consumption_end_to_end.py` (F21-F24) — todos siguen en verde | — | — |
| 2026-09-11 | **Frontend**: `Control.tsx` con 4 KPIs (tasa de éxito de comando, pendientes, total, por tipo), filtro Pendientes/Todas (historial real, antes inexistente), badge "protegida" en la fila si el medidor lo está. `Consumption.tsx` con 4 KPIs (tasa de anomalía, % listo para facturar, procesados, órdenes por acción), botón "Resolver" real por fila, tabla nueva de órdenes de relectura/inspección. `Configuration.tsx`: sección nueva "Cuentas protegidas" — marcado manual (textarea) o carga de archivo `.csv`/`.txt` (parseo client-side), lista con "quitar protección" | `services/portal-web/src/pages/Control.tsx`, `Consumption.tsx`, `Configuration.tsx`, `api.ts` |
| 2026-09-11 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "consumption/summary"/"control-orders/summary"/"meters/protected"/"meters/protection". Desplegado: migración 0012 con respaldo real primero, backend (Nuitka) a `essmarplapp02`, frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide exacto, `/api/consumption/summary` responde 401 (gateado, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |

**Nota suelta**: se encontró un endpoint viejo `GET /events` en `main.py` (Sprint temprano), no
usado por ningún frontend, superado por `/meters/events` (Sprint C11-4) — cerrado más abajo,
en la ronda de endurecimiento/limpieza.

### Endurecimiento + limpieza de cabos sueltos (2026-09-11)

**Motivo:** con VEE/HES/Control/Consumo ya al mismo nivel de rigor, el usuario pidió seguir
con la recomendación: endurecer lo construido en vez de abrir alcance nuevo (Track B sigue sin
una oportunidad comercial concreta, confirmado explícitamente por el usuario — "no tengo un
medidor real todavía").

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Hallazgo real en la protección de cuentas (Sprint C11-5)**: el docstring de `request_order` prometía que el override nunca podía repetir la justificación original, pero el código nunca lo verificaba — cualquiera podía mandar `override_justification` idéntica a `justification` y pasar el chequeo. Corregido: comparación case-insensitive, rechaza con 422 si son iguales. También se encontró que `mark_protection` (marcar UNA cuenta, a diferencia de la carga masiva que ya exigía `reason`) permitía proteger una cuenta SIN motivo — corregido, ahora exige `reason` para `protected=true` (desmarcar no lo necesita) | `services/control/control_service.py`, `account_protection.py` |
| 2026-09-11 | 2 casos nuevos en el E2E real: override con la misma justificación → 422; marcar protegida sin `reason` → 422. Regresión completa (`control`/`portal-api` unit tests, `verify_control_execution_end_to_end.py` F28/F29/F30, `verify_stage_screens_end_to_end.py`, `verify_service_orders_end_to_end.py`) sigue en verde | `verify_meter_protection_end_to_end.py` → `SPRINT C11-5 METER PROTECTION E2E OK` |
| 2026-09-11 | Desplegado a producción (backend Nuitka a `essmarplapp02`, restart, verificado `openapi.json` 200) | — |
| 2026-09-11 | **Limpieza**: eliminado el endpoint viejo `GET /events` (sin uso, superado por `/meters/events`) — verificado que ningún script/frontend lo llamaba antes de borrarlo, regresión completa sigue en verde, desplegado y confirmado que ya no aparece en `openapi.json` | `services/portal-api/main.py` |
| 2026-09-11 | **`partition_maintenance.py` — cron real configurado** (pendiente desde Sprint C11): se encontró que `python -m renmeter_common.partition_maintenance` NO funciona contra el `.so` compilado con Nuitka ("No code object available" — el mecanismo `-m` no soporta extensiones compiladas). Corregido con un entry-point kept-as-source real, `services/common/run_partition_maintenance.py` (mismo patrón que `poller.py`/`main.py`: texto plano que importa y llama al módulo compilado). Cron real en `essmarplapp02` (`crontab -u postgres`, lunes 3am, autenticación peer sin password — mismo mecanismo que ya usan las migraciones vía `sudo -u postgres`), probado en vivo con una corrida manual real | `services/common/run_partition_maintenance.py`, `renmeter_common/partition_maintenance.py` (docstring corregido) |
| 2026-09-11 | **`04-plan-sprints.md` §9 formalizado**: épicas E20 (cierre de parciales)/E21 (paneles por etapa con benchmark real) + sprints C11 a C11-6 agregados a la tabla oficial, marcados 🆕 — antes solo vivían en la bitácora. §10 actualizado con el estado real de cierre de sesión | `docs/04-plan-sprints.md` |
| 2026-09-11 | **`.github/workflows/tests.yml` — intento de trackear en git, bloqueado por GitHub, no por decisión propia**: confirmado su contenido (CI legítimo de Sprint 0, nada sospechoso) y se intentó el `git add` + push — GitHub lo rechazó: *"refusing to allow a Personal Access Token to create or update workflow `tests.yml` without `workflow` scope"*. El token configurado para este repo no tiene permiso de escribir en `.github/workflows/`. Revertido del commit (sigue `??` en `git status`, sin tocar el archivo en disco) — para trackearlo hace falta que el usuario regenere el PAT con el scope `workflow`, o lo suba él mismo | — |

### Track B, Sprint B1 — Balance de Red: esquema real + ingesta externa (2026-09-11)

**Motivo:** el usuario confirmó activar Track B ("lo demás está estable... vamos con el Track
B") pidiendo primero una investigación profunda de mercado y una definición de alcance
funcional, y solo después implementar — ver `07-track-b-alcance-funcional.md` para la
investigación completa (matriz de Balance Hídrico IWA, marco regulatorio CRA/IANC en Colombia,
mapa de mercado).
**Hallazgo real antes de escribir código**: `network_zone`/`network_balance` (y
`network_asset`/`asset_connectivity`/`maintenance_order`) **ya existían desde `0001_init.sql`**
(Sprint 0 escribió el esquema completo del producto de una sola vez, incluyendo Track B, aunque
el código nunca se construyó encima) — con la versión APLANADA de la Fase 2/3
(`inflow`/`authorized_consumption`/`losses`), insuficiente para calcular ILI. La migración 0013
es un `ALTER TABLE`, no un `CREATE TABLE` — ambas tablas tenían 0 filas en desarrollo y en
producción, ALTER seguro sin migración de datos.
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **Migración `0013_network_balance.sql`**: `network_zone` +4 columnas (`network_length_km`/`num_connections`/`avg_pressure_mca`/`avg_service_connection_length_km` — insumos para UARL); `network_balance` con la matriz IWA completa (`system_input_volume`, `billed_metered_consumption`, `billed_unbilled_consumption`, `unbilled_authorized_consumption`, `apparent_losses`, `real_losses`, `nrw`, `ili`) en vez del agregado plano | `infra/db/migrations/0013_network_balance.sql` |
| 2026-09-11 | **`network_balance_engine.py` (nuevo, lógica pura)**: `non_revenue_water()`, `water_losses()`, `unavoidable_annual_real_losses_liters_per_day()` (fórmula IWA real: `(18·Lm + 0.8·Nc + 25·Lp)·P`) y `infrastructure_leakage_index()` (`CARL/UARL`) — `None` explícito (nunca 0 ni inventado) si faltan los insumos de la zona o el período es inválido | `services/network-balance/network_balance_engine.py` |
| 2026-09-11 | 12/12 pruebas unitarias puras — incluye el caso real que valida la fórmula UARL contra el cálculo manual (`(18·100 + 0.8·5000)·40 = 232000` L/día) y que ILI sube con más pérdida real | `python -m unittest discover -s tests -v` (en `services/network-balance/`) → **12/12 OK** |
| 2026-09-11 | **`balance_service.py` (nuevo)**: `register_zone()`/`list_zones()`, `submit_balance()` (arma los insumos desde BD, llama al motor, guarda `nrw`/`ili` calculados — nunca recalculados en cada lectura del panel; versiona por `(zone_id, period)`, un reenvío sube de versión sin perder el historial), `list_balances()` (solo la versión más reciente por zona/período). Endpoints nuevos: `POST/GET /network-zones`, `POST /network-zones/{id}/balance`, `GET /network-balances` | `services/network-balance/balance_service.py`, `services/portal-api/main.py` |
| 2026-09-11 | E2E real de punta a punta: una zona sin insumos de infraestructura calcula NRW pero ILI queda `None`; una zona con insumos reales calcula NRW=7000 e ILI=1.0 exacto (mismos números que el unit test, ahora vía HTTP+Postgres real); reenviar el mismo período sube a versión 2 y el listado solo trae la última; una zona inexistente da 404 | `verify_network_balance_end_to_end.py` → `SPRINT B1 NETWORK BALANCE E2E OK` |
| 2026-09-11 | Regresión completa (8/8 unit tests de `portal-api` + `verify_stage_screens_end_to_end.py`/`verify_meter_protection_end_to_end.py`/`verify_fleet_aggregation_end_to_end.py`) sigue en verde | — |
| 2026-09-11 | **Decisión de arquitectura de despliegue para Track B**: se descarta el bus de eventos/k3s de la Fase 2/3 (`02-arquitectura-general.md` §3, aspiracional, escrito antes de que el proyecto existiera) — Track B se construye como el mismo monolito modular ya probado en Track A/C (`services/network-balance/` importado directo por `portal-api`, systemd+Postgres compartido), documentado en `07-track-b-alcance-funcional.md` §5 | — |
| 2026-09-11 | Desplegado a producción: respaldo real primero (`pg_dump`), migración 0013 aplicada, backend (Nuitka) a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo. Verificado en vivo: `/api/network-zones` responde 401 (gateado por auth, no 404/500) | `curl https://renfygrid.rensoftlabs.com/api/network-zones` |
| 2026-09-11 | Script de build de Nuitka (WSL, no versionado — pendiente conocido) actualizado con el servicio `network-balance` nuevo, para que un rebuild completo futuro lo incluya | `~/build-renfygrid.sh` (WSL) |

**Pendiente real de Track B**: B2 (fórmulas Top-Down/Bottom-Up) quedó parcialmente cubierto por
B1 — NRW/ILI se calculan igual sin importar el método (es metadata trazable, no una fórmula
distinta); la estimación de componentes por flujo mínimo nocturno es trabajo especializado
fuera de alcance (`07-track-b-alcance-funcional.md` §6). Siguen **B3-B7** (modelado hidráulico
con WNTR, Gemelo Digital, Gestión de Mantenimiento + BayForce) — no iniciados, pendientes de
continuar con el usuario.

### Track B, Sprint B1-2 — Balance de Red: NRW%, tope regulatorio y resumen de portafolio (2026-09-11/12)

**Motivo:** el usuario preguntó directamente "¿qué le falta al B1? hagámoslo" al revisar el
sprint recién cerrado. Análisis honesto encontró 4 huecos reales, no cosméticos:
1. `nrw` solo se guardaba como volumen bruto (m³) — no dice nada sin el tamaño del sistema; se
   reporta y se compara siempre como **%** del System Input Volume (así lo exige la CRA en
   Colombia, IANC ≤ 30%, Resolución 315/2005 — mismo hallazgo regulatorio del Track A/Control
   con la CREG, `07-track-b-alcance-funcional.md` §2).
2. El 30% de la CRA, encontrado en la propia investigación de mercado, nunca se **usaba** en
   ningún lado del código — sin un tope configurable, la cifra regulatoria era solo un
   comentario. Se agregó `network_zone.nrw_threshold_pct`, **configurable por zona, nunca
   hardcodeado** (directiva del proyecto, `feedback_no_hardcoded_data`): otro país/regulador usa
   otro número.
3. No había chequeo de consistencia interna entre el System Input Volume declarado y la suma de
   los 5 componentes enviados — un balance que no cierra señala datos de entrada incompletos,
   nunca se ajustaba en silencio.
4. No existía un resumen a nivel de portafolio de zonas — todos los demás módulos del producto
   (VEE, HES, Consumo, Control) ya tienen un panel de KPIs agregados; Track B seguía siendo
   solo listados fila por fila.

**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11/12 | **`network_balance_engine.py`**: `non_revenue_water_pct()` (NRW como % del SIV, `None` si SIV≤0) y `balance_check_pct()` (qué tanto se aleja la suma de los 5 componentes del SIV declarado, `None` si SIV≤0) — lógica pura, mismo fail-safe `None` del resto del motor | `services/network-balance/network_balance_engine.py` |
| 2026-09-11/12 | 6 pruebas unitarias nuevas (`NonRevenueWaterPctTests`, `BalanceCheckPctTests`) — **18/18 pruebas puras en verde** | `python -m unittest tests.test_network_balance_engine -v` → 18/18 OK |
| 2026-09-11/12 | **Migración `0014_network_balance_pct.sql`**: `network_zone.nrw_threshold_pct` (tope configurable, `NULL` = sin tope); `network_balance.nrw_pct`/`balance_check_pct`/`exceeds_threshold` (`NULL` si la zona no tiene tope configurado — nunca `False` inventado) | `infra/db/migrations/0014_network_balance_pct.sql` |
| 2026-09-11/12 | **`balance_service.py` reescrito**: `register_zone()`/`list_zones()` threadean `nrw_threshold_pct`; `_zone_row()` (renombrado de `_zone_infrastructure`) también devuelve el tope; `submit_balance()` calcula y persiste `nrw_pct`/`balance_check_pct`/`exceeds_threshold` al insertar (nunca recalculado en cada lectura); `list_balances()` los expone. **Nuevo** `balance_summary()`: total de zonas, zonas con balance, NRW% promedio, peor ILI, zonas que exceden su tope — con datos reales de la BD, mismo patrón de resumen que `vee_summary`/`consumption_summary`/`control_summary` | `services/network-balance/balance_service.py` |
| 2026-09-11/12 | `main.py`: `NetworkZoneRequest` +`nrw_threshold_pct`; endpoint nuevo `GET /network-balances/summary` | `services/portal-api/main.py` |
| 2026-09-11/12 | E2E extendido con 4 zonas reales: una con tope configurado que lo supera (`exceeds_threshold=True`), una con inconsistencia real en el balance que da exactamente el tope (`nrw_pct=30.0`, `exceeds_threshold=False`, no `True` — el operador `>` es estricto), dos sin tope (`exceeds_threshold=None`); `GET /network-balances/summary` agregando las 4 zonas reales | `verify_network_balance_end_to_end.py` → `SPRINT B1/B1-2 NETWORK BALANCE E2E OK` |
| 2026-09-11/12 | Regresión completa: los 15 `verify_*_end_to_end.py` de `portal-api` (incluye VEE, HES, Consumo, Control, Balance de Red) en verde tras el cambio | `exit=0` en los 15 scripts |
| 2026-09-11/12 | Desplegado a producción: respaldo real primero (`pg_dump` vía `sudo -u postgres`, sin RLS — `pg_dump` como rol de aplicación falla contra la política RLS de `app_user`, hallazgo nuevo de esta ronda), migración 0014 aplicada, backend (Nuitka: `network_balance_engine`/`balance_service`) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo. Verificado en vivo: `/api/network-balances/summary` y `/api/network-zones` responden 401 (gateado por auth, no 404/500) | `curl https://renfygrid.rensoftlabs.com/api/network-balances/summary` |

**Pendiente real, identificado en esta misma ronda**: no existía ningún panel de frontend para
Balance de Red — Track B era solo API, inconsistente con el resto del producto. El usuario
confirmó construirlo ("Si, adelante") — ver siguiente entrada.

### Track B, Sprint B1-2: panel de frontend "Balance de Red" (2026-09-12)

**Motivo:** Track B era el único módulo del producto sin pantalla — todos los demás (VEE, HES,
Consumo, Control) ya tenían dashboard completo con KPIs, tablas y acciones. El usuario confirmó
cerrar esa brecha.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-12 | **`NetworkBalance.tsx` (nuevo)**: 4 KPIs de resumen (NRW% promedio, zonas sobre su tope, peor ILI, zonas con balance/total — todos del `balance_summary()` real, ninguno inventado en el navegador); formulario de registro de zona (`RegisterZoneForm`, campos de infraestructura opcionales + tope de NRW configurable); tabla de zonas con badge "calcula ILI"/"sin insumos ILI" según si la zona tiene Lm/Nc/P; formulario de ingesta de balance por zona (`SubmitBalanceForm`, los 5 componentes de la matriz IWA); tabla de balances con `nrw_pct`/`ili` coloreados por banda (verde/ámbar/rojo, banda IWA estándar para ILI: 1-4 bueno, 4-8 aceptable, >8 pobre) y badge "excede tope" | `services/portal-web/src/pages/NetworkBalance.tsx` |
| 2026-09-12 | `api.ts`: `NetworkZone`/`NetworkBalance`/`NetworkBalanceSummary` + `getNetworkZones`/`createNetworkZone`/`getNetworkBalances`/`submitNetworkBalance`/`getNetworkBalanceSummary` — mismo patrón de cliente que el resto del portal | `services/portal-web/src/api.ts` |
| 2026-09-12 | Ruta `/network-balance` + ítem de navegación "Balance de Red" en el panel lateral (`AppShell.tsx`), entre Control y Configuración | `services/portal-web/src/App.tsx`, `services/portal-web/src/components/AppShell.tsx` |
| 2026-09-12 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "network-balance"/"Balance de Red". Desplegado a `essmarplpxy03` (`/var/www/renfygrid`), sin cambios de backend en este sprint. Verificado en vivo: HTML servido referencia el bundle nuevo, el bundle en producción contiene el contenido esperado | `curl https://renfygrid.rensoftlabs.com/` |

**Estado de Track B tras esta ronda:** B1 🟢 completo (backend + frontend). Pendiente real:
B3-B7 (modelado hidráulico WNTR, Gemelo Digital, Mantenimiento + BayForce) sin iniciar.

### Track B, Sprint B3 — Modelado Hidráulico real (WNTR/EPANET) (2026-09-12)

**Motivo:** el usuario confirmó continuar con B3-B7 ("Si, continuemos"). `network_model`/
`simulation_result` ya existían desde `0001_init.sql` (Sprint 0, mismo hallazgo que B1) —
**sin migración** en este sprint, el esquema ya encajaba con lo necesario.

**Hallazgo real de compatibilidad, antes de escribir código**: WNTR (Water Network Tool for
Resilience, USEPA, el motor EPANET 2.2 real que usan Bentley WaterGEMS/OpenFlows e Innovyze
InfoWater por debajo) exige Python ≥3.10 desde su versión 1.3 — el toolchain de Nuitka de todo
el portafolio está fijo en Python 3.9 (`feedback_no_source_on_server_nuitka`). Se fija
`wntr==1.2.0` (última versión con wheel `manylinux` para cp39) — documentado en
`requirements.txt` y aquí, no un detalle silencioso; subir esa versión implica subir Python en
**todo** el toolchain primero, no un bump aislado de este servicio.

**Segundo hallazgo real de entorno**: `wntr` no instala en el Python 3.14 nativo de Windows del
resto del repo (falla el build de su extensión C++/SWIG por falta de Visual Studio Build
Tools). Desarrollo/pruebas de este sprint se hicieron con un venv dedicado en Python 3.10 de
Windows (`wntr` 1.5.0 más reciente ahí, misma API) para las pruebas E2E (HTTP+Postgres), y con
un venv Python 3.9 en WSL2 (`wntr==1.2.0`, la versión real de producción) para verificar que el
motor puro funciona igual en la versión que de verdad se despliega — ambos confirmados con los
mismos resultados numéricos.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-12 | **`network_model_engine.py` (nuevo, lógica pura)**: `load_model()` (carga y valida un `.inp` real, `InvalidModelError` si no es un modelo EPANET válido); `run_simulation()` (corre `EpanetSimulator` real, resume presión/caudal min/max/promedio por nudo/tubería en toda la duración simulada — nunca la serie completa cruda). `SimulationFailedError` si la red no converge (`convergence_error=True`), nunca un resultado a medias | `services/network-model/network_model_engine.py` |
| 2026-09-12 | Fixture real de prueba: `tests/fixtures/valid_net.inp` — red mínima pero real (depósito + 2 nudos + tanque, 3 tuberías) escrita a mano en formato EPANET estándar, resuelta de verdad por WNTR (no un mock) | `services/network-model/tests/fixtures/valid_net.inp` |
| 2026-09-12 | 8/8 pruebas unitarias puras contra el fixture real — valores de presión/caudal verificados contra la corrida manual de WNTR (J1 = 78.39 m.c.a., J2 = 41.56 m.c.a. en el mínimo de la serie) | `python -m unittest tests.test_network_model_engine -v` → 8/8 OK (Windows py3.10/wntr 1.5.0 **y** WSL2 py3.9/wntr==1.2.0) |
| 2026-09-12 | **Hallazgo real corregido en la misma ronda**: `EpanetSimulator.run_sim()` escribe archivos temporales (`.inp`/`.rpt`/`.bin`, prefijo `temp` por defecto) al directorio de trabajo actual — ensuciaba el working tree del repo en cada corrida. Se fuerza un `file_prefix` único bajo un directorio temporal propio (`tempfile.TemporaryDirectory`), borrado siempre al terminar | `network_model_engine.py::run_simulation` |
| 2026-09-12 | **`model_service.py` (nuevo)**: `register_model()` (valida el `.inp` ANTES de insertar — un modelo inválido nunca queda registrado; versiona por `name`, mismo criterio que `network_balance`), `list_models()` (solo la última versión por nombre), `run_and_store_simulation()` (arma la ruta del archivo, llama al motor, guarda el resultado en `simulation_result.results` como `jsonb`), `list_simulation_results()`. Endpoints nuevos: `POST/GET /network-models`, `POST /network-models/{id}/simulate`, `GET /network-models/{id}/simulations` | `services/network-model/model_service.py`, `services/portal-api/main.py` |
| 2026-09-12 | `config.py`: `RENFYGRID_NETWORK_MODEL_STORAGE_DIR` (dónde se guardan los `.inp` subidos) — por variable de entorno, nunca una ruta fija en código, mismo principio que el resto de `Settings` | `services/portal-api/config.py` |
| 2026-09-12 | E2E real de punta a punta (`verify_network_model_end_to_end.py`): registrar un modelo real → v1; reenviar el mismo nombre → v2 (versionado real); `GET /network-models` solo trae la última versión; simular el modelo real → mismos números que el unit test, ahora vía HTTP+Postgres+WNTR; la corrida queda guardada; un `.inp` inválido → 422 (nunca se guarda); simular un modelo inexistente → 404 | `verify_network_model_end_to_end.py` → `SPRINT B3 NETWORK MODEL E2E OK` |
| 2026-09-12 | Regresión completa: los 16 `verify_*_end_to_end.py` de `portal-api` en verde tras el cambio | `exit=0` en los 16 scripts |
| 2026-09-12 | **`NetworkModel.tsx` (nuevo, frontend)**: carga de un `.inp` real (archivo o pegado), tabla de modelos con versión, botón "Simular" por modelo con campo de escenario libre, detalle de corrida expandible con presión por nudo y caudal por tubería (min/máx/prom) | `services/portal-web/src/pages/NetworkModel.tsx` |
| 2026-09-12 | `api.ts`: `NetworkModel`/`SimulationResult` + `getNetworkModels`/`createNetworkModel`/`simulateNetworkModel`/`getNetworkModelSimulations`. Ruta `/network-model` + ítem de navegación "Modelado Hidráulico" | `services/portal-web/src/api.ts`, `App.tsx`, `AppShell.tsx` |
| 2026-09-12 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "network-model"/"Modelado Hidráulico" | `dist/assets/*.js` |
| 2026-09-12 | Nuitka: `wntr==1.2.0` instalado en el venv de compilación (`~/nuitka-env-renfygrid`) y en el venv de producción de `portal-api` en `essmarplapp02` — el paquete en sí NUNCA se compila (mismo trato que `psycopg`/`fastapi`, política de portafolio: solo código propio se compila). `network_model_engine.py`/`model_service.py` compilados sin fallos | `~/build-renfygrid.sh` (WSL) |

**Pendiente real de Track B tras B3**: B4 (vínculo Modelo↔Balance, calibración con
`network_balance.real_losses` real) queda natural de construir sobre B1+B3 ya cerrados. Siguen
**B5-B7** (Gemelo Digital, generación de modelo desde activos, Mantenimiento + BayForce) sin
iniciar.

### Modelos de demostración georreferenciados (Bogotá/Cali) + hallazgo de un módulo pendiente (2026-09-12)

**Motivo:** el usuario pidió muestras reales de archivos EPANET `.inp` de ciudades colombianas
para mostrar en el panel. Búsqueda real de mercado (no asumida): se encontraron fuentes reales
citables (Cartago/Valle del Cauca vía Universidad Tecnológica de Pereira en Mendeley Data;
Pamplona/Norte de Santander vía paper open access en *Water*, MDPI; red menor real de acueducto
de Bogotá en Datos Abiertos Bogotá/EAAB) pero ninguna descargable de forma automatizada en esta
sesión (Mendeley renderiza el listado de archivos con JavaScript, MDPI bloquea scraping). El
usuario confirmó la alternativa: construir una red ilustrativa propia pero **georreferenciada
sobre coordenadas reales** de Bogotá y Cali, e investigación completa en
`docs/07-track-b-alcance-funcional.md` §7.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-12 | Dos modelos `.inp` reales (cargan y simulan con WNTR, no un mock) con `[COORDINATES]` reales: **Bogotá** ancla en Chapinero (lat 4.6454–4.6572, lon -74.0619 a -74.0464, elevación base 2643 msnm real); **Cali** ancla entre el Cerro de las Tres Cruces (lat 3.4673, lon -76.5469, tanque elevado) y el centro/San Fernando (lat 3.45, lon -76.5346). Documentados en el propio archivo como **ilustrativos**, no un levantamiento real de EAAB/EMCALI — nunca presentados como dato real de la utility | `services/network-model/demo/bogota_chapinero_dma.inp`, `.../cali_tres_cruces_dma.inp` |
| 2026-09-12 | Simulación real confirmada en ambos: presiones positivas y plausibles (Bogotá 34.9–64.7 mca, Cali 14.9–34.5 mca), caudales reales por tubería — sin resultados fabricados | corrida manual vía `network_model_engine.run_simulation()` |
| 2026-09-12 | `seed_demo_networks.py` (nuevo, mismo patrón que `hes-adapter-dlms/seed_demo_data.py`): registra ambos modelos en el tenant de demostración persistente vía `register_model()` real (no INSERT directo) — idempotente, todo por argumento (DSN/tenant/directorio), nunca fijo en código | `services/network-model/seed_demo_networks.py` |
| 2026-09-12 | Sembrados en producción en el tenant "RenfyGrid Demo" (`6e89ad29-6484-4758-a1f6-7ee90c39ecd5`) y simulados una vez para que el panel de Modelado Hidráulico tenga resultados listos sin esperar acción del usuario | corrida real contra Postgres/venv de producción → 2 modelos, 2 corridas OK |
| 2026-09-12 | **Hallazgo real**: ni Balance de Red ni Modelado Hidráulico tienen hoy un mapa — ambos son inherentemente espaciales (`[COORDINATES]` de un modelo, zonas/DMA de un balance) y el panel actual solo muestra tablas. Revisado el módulo "Mapa de Deuda" de RenFlow (`core/renflow/frontend/js/modules/map.js`) **antes** de proponer nada — Leaflet+`Leaflet.markercluster` sobre tiles de OpenStreetMap, backend que expone GeoJSON, color/tamaño por métrica real, capas temáticas tipo choropleth, selección por polígono con mini-dashboard — patrón directamente reusable, documentado como la referencia a seguir para un futuro módulo de georreferenciación transversal a B1/B3/B5, **no iniciado**, pendiente de confirmación con el usuario sobre su alcance | `docs/07-track-b-alcance-funcional.md` §7 |

### Módulo de georreferenciación — versión 1, sobre B1+B3 (2026-09-12)

**Motivo:** el usuario confirmó construir el módulo de georreferenciación ahora, sobre lo que ya
existe (B1 Balance de Red + B3 Modelado Hidráulico), en vez de esperar al Gemelo Digital (B5,
todavía sin empezar — solo tiene el esquema `network_asset`/`asset_connectivity` desde el
Sprint 0). Patrón de RenFlow "Mapa de Deuda" ya revisado en la entrada anterior — se sigue tal
cual, sin reinventar.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-12 | **`network_model_engine.model_topology_geojson()` (nuevo, lógica pura)**: nudos como `Point`, tuberías como `LineString`, tomados de `[COORDINATES]` real del `.inp` — nunca un layout de grafo inventado. Si se pasa una simulación ya corrida, cada feature trae sus estadísticas reales (presión/caudal); si no, esas propiedades quedan ausentes. Nudos/enlaces SIN coordenadas reales (WNTR devuelve exactamente `(0,0)` cuando falta `[COORDINATES]`) se omiten — nunca se pintan en "null island" | `services/network-model/network_model_engine.py` |
| 2026-09-12 | 5 pruebas unitarias nuevas — incluye el caso real de un nudo agregado sin coordenadas, confirmando que se omite en vez de aparecer en `(0,0)`. **13/13 pruebas puras del módulo en verde** | `python -m unittest tests.test_network_model_engine -v` → 13/13 OK |
| 2026-09-12 | **Migración `0015_network_zone_centroid.sql`**: `network_zone.centroid_lat`/`centroid_lon` — opcional (`NULL` = zona sin georreferenciar todavía, sigue funcionando igual para Balance de Red, nunca un centroide inventado) | `infra/db/migrations/0015_network_zone_centroid.sql` |
| 2026-09-12 | `balance_service.zones_geojson()` (nuevo): un `Point` por zona QUE TENGA centroide cargado, enriquecido con su último balance (`nrw_pct`/`ili`/`exceeds_threshold`, `None` si aún no tiene ninguno). `model_service.model_geojson()` (nuevo): arma la ruta del modelo, reconstruye la última simulación guardada desde el `jsonb`, llama al motor. Endpoints nuevos: `GET /network-zones/geojson`, `GET /network-models/{id}/geojson` | `services/network-balance/balance_service.py`, `services/network-model/model_service.py`, `services/portal-api/main.py` |
| 2026-09-12 | `NetworkZoneRequest`/`register_zone()`/`list_zones()` extendidos con `centroid_lat`/`centroid_lon` (opcionales) | `services/portal-api/main.py`, `services/network-balance/balance_service.py` |
| 2026-09-12 | E2E extendido en ambos módulos: `verify_network_model_end_to_end.py` confirma 4 puntos + 3 líneas en el GeoJSON del modelo, enriquecido con la corrida guardada; `verify_network_balance_end_to_end.py` confirma que solo la zona CON centroide aparece en `/network-zones/geojson` (las otras 4 zonas del test, sin centroide, no aparecen), con `nrw_pct`/`exceeds_threshold` correctos | `verify_network_model_end_to_end.py`, `verify_network_balance_end_to_end.py` → ambos OK |
| 2026-09-12 | Regresión completa: los 16 `verify_*_end_to_end.py` de `portal-api` en verde tras el cambio | `exit=0` en los 16 scripts |
| 2026-09-12 | **`NetworkMap.tsx` (nuevo, frontend, componente compartido)**: Leaflet + tiles de OpenStreetMap (sin API key), puntos (`circleMarker`) y líneas (`polyline`) desde GeoJSON real, color/tamaño por prop derivada de una métrica ya calculada (nunca fijo), popup con el detalle real, auto-encuadre (`fitBounds`), mensaje explícito cuando no hay datos georreferenciados (nunca un mapa vacío sin explicación) | `services/portal-web/src/components/NetworkMap.tsx` |
| 2026-09-12 | Wireado en ambas pantallas: `NetworkModel.tsx` — botón "Ver mapa" por modelo, nudos coloreados por presión (banda operativa) y tuberías por caudal, grosor por diámetro; `NetworkBalance.tsx` — mapa de zonas al tope de la página, coloreado por NRW%/tope regulatorio, y el formulario de registro de zona ahora pide latitud/longitud (opcional) | `services/portal-web/src/pages/NetworkModel.tsx`, `services/portal-web/src/pages/NetworkBalance.tsx` |
| 2026-09-12 | Dependencias nuevas: `leaflet`/`leaflet.markercluster` (+ `@types/*`) — mismo stack sin costo que RenFlow, cero licencia nueva | `services/portal-web/package.json` |
| 2026-09-12 | `tsc -b && vite build` limpio, bundle sin rutas mangled, contiene "openstreetmap"/"Mapa de zonas"/los dos endpoints `geojson`. Desplegado: migración 0015 con respaldo real primero, backend (Nuitka: `network_balance_engine`/`balance_service`/`network_model_engine`/`model_service`) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide exacto, `/api/network-zones/geojson` responde 401 (gateado, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |
| 2026-09-12 | Una zona real georreferenciada sembrada en el tenant demo ("DMA Chapinero (Bogotá, ilustrativo)", mismas coordenadas del modelo de Modelado Hidráulico) con un balance real vía `submit_balance()` (NRW=25%, ILI=3.51, bajo el tope) — para que el mapa de Balance de Red tenga algo real que mostrar de inmediato, igual que los dos modelos de B3 | corrida real contra Postgres de producción |

**Estado tras esta ronda:** módulo de georreferenciación v1 🟢 (Modelado Hidráulico + Balance de
Red). Selección por polígono y capas temáticas tipo choropleth (paralelo directo de RenFlow)
quedan para una siguiente iteración si el uso real lo pide. Se extenderá a Gemelo Digital (B5)
cuando ese sprint exista, reusando el mismo `NetworkMap.tsx`.

### Track B, Sprint B4 — vínculo Modelo↔Balance (2026-09-12)

**Motivo:** con B1+B3 georreferenciados y estables, y B5 (Gemelo Digital) todavía sin ningún
código encima del esquema, B4 era el siguiente paso natural: cerrar el ciclo entre las dos
piezas ya construidas en vez de abrir un dominio nuevo completo. El usuario dejó la elección al
criterio del asistente ("escoge tu").

**Diseño real, no una comparación cosmética**: el criterio original ("el escenario de
simulación usa `network_balance.real_losses` como insumo de calibración") se interpretó
literalmente — `real_losses` se usa como INSUMO de la simulación (no solo se muestra al lado).
Técnica: **emisores por presión** (`q = C·Pⁿ`, estándar EPANET/IWA para representar fugas
distribuidas) — (1) corre una simulación base sin fugas para estimar la presión de cada nudo,
(2) reparte el volumen real de pérdidas del balance proporcional a la demanda base de cada nudo
(parejo si ninguno declara demanda), (3) calibra un emisor por nudo para que, a esa presión
base, entregue su parte del caudal de fuga objetivo, (4) vuelve a simular CON los emisores
calibrados — ese es el resultado final.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-12 | **`network_model_engine.calibrate_and_simulate()` (nuevo)**: `CalibrationInputError` si `real_losses_m3`/`period_days` no son positivos (nunca se inventa una fuga sin balance real detrás); nudos con presión base ≤0 se omiten (`skipped_nodes`), nunca se divide por cero | `services/network-model/network_model_engine.py` |
| 2026-09-12 | **Hallazgo real corregido en la misma ronda**: WNTR guarda TODO internamente en SI (m³/s, metros) sin importar las unidades declaradas en el `.inp` (aquí LPS) — asignar `emitter_coefficient` directo en Python sin convertir de L/s a m³/s dejaba la fuga calibrada **1000× más grande** que la real (visto en vivo: la presión colapsaba a ~0 en vez de estabilizarse). Corregido con la conversión explícita, documentada en el código | `network_model_engine.py::calibrate_and_simulate` |
| 2026-09-12 | 5 pruebas unitarias nuevas — incluye el caso real que confirma que el caudal calibrado sube en el orden de magnitud correcto (no explota) y que las presiones siguen siendo físicamente razonables. **18/18 pruebas puras del módulo en verde** | `python -m unittest tests.test_network_model_engine -v` → 18/18 OK |
| 2026-09-12 | **Migración `0016_network_model_zone_link.sql`**: `network_model.zone_id` (FK opcional a `network_zone` — `NULL` = modelo sin vincular, sigue funcionando igual sin calibración) | `infra/db/migrations/0016_network_model_zone_link.sql` |
| 2026-09-12 | `model_service.py`: `register_model()`/`list_models()` extendidos con `zone_id`; `run_and_store_simulation(..., calibrate=True)` (nuevo parámetro) busca el balance MÁS RECIENTE (por período, luego versión) de la zona vinculada — `ModelNotLinkedToZoneError` si el modelo no tiene zona, `NoBalanceForCalibrationError` si la zona todavía no tiene ningún balance (nunca calibra "a medias" con un número de ejemplo) | `services/network-model/model_service.py` |
| 2026-09-12 | `main.py`: `NetworkModelRequest.zone_id`, `SimulateRequest.calibrate` (nuevo), endpoint traduce las excepciones de calibración a `422` | `services/portal-api/main.py` |
| 2026-09-12 | E2E extendido: modelo vinculado a una zona CON balance real se calibra de verdad (`target_leak_lps≈10`, `node_leak_lps` presente); modelo sin vincular → `422`; modelo vinculado a una zona SIN balance → `422` | `verify_network_model_end_to_end.py` → OK |
| 2026-09-12 | Regresión completa: los 16 `verify_*_end_to_end.py` de `portal-api` en verde tras el cambio | `exit=0` en los 16 scripts |
| 2026-09-12 | Frontend: `UploadModelForm` permite vincular el modelo a una zona al cargarlo; `ModelRow` agrega un checkbox "Calibrar con balance real" (deshabilitado si el modelo no está vinculado, con motivo explicado); `SimulationRow` muestra el detalle real de la calibración (volumen/período/caudal objetivo, reparto por nudo, nudos omitidos si los hay) | `services/portal-web/src/pages/NetworkModel.tsx`, `services/portal-web/src/api.ts` |
| 2026-09-12 | `tsc -b && vite build` limpio, bundle contiene "Calibrar con balance real"/"calibrated"/"target_leak_lps". Desplegado: migración 0016 con respaldo real primero, backend (Nuitka) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. **Verificado con un smoke test real contra producción**: el modelo de demostración de Bogotá vinculado a la zona demo real (que ya tenía un balance real sembrado, `real_losses=3300 m³/31 días`) se calibra correctamente (`target_leak_lps=1.2321`, coincide con el cálculo manual) | corrida real contra Postgres/venv de producción → `PROD SMOKE B4 OK` |

**Estado de Track B tras esta ronda:** B1, B3 y B4 🟢 completos (backend + frontend +
georreferenciación + calibración real). Pendiente: **B5-B7** (Gemelo Digital, generación de
modelo desde activos, Mantenimiento + BayForce) sin iniciar.

### Track B, Sprint B5 — Gemelo Digital (inventario de activos + conectividad) (2026-09-12)

**Motivo:** el usuario dijo "sigue" tras cerrar B4 — siguiente paso natural del plan de Track B.
Esquema (`network_asset`/`asset_connectivity`) ya existía desde `0001_init.sql` (Sprint 0,
mismo hallazgo que B1/B3) — **sin migración** en este sprint.

**Hallazgo real de seguridad, documentado ANTES de escribir código**: `asset_connectivity` no
tiene `tenant_id` propio ni política RLS — el comentario del propio `0001_init.sql` dice
"inherits isolation from network_asset via join". Esto significa que la única protección real
contra vincular activos de tenants distintos es una verificación EXPLÍCITA en la capa de
servicio (nunca confiar en que la base de datos lo bloquee sola). Implementado así y **probado
en el E2E con un tenant B real intentando conectar contra un activo de un tenant A** — confirma
`404`, no una fuga silenciosa.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-12 | **`asset_service.py` (nuevo)**: `register_asset()` (valida `type` contra los 6 tipos reales del catastro — `pipe`/`valve`/`tank`/`pump`/`meter`/`sensor`, `status` contra los 3 estados reales; nunca acepta un valor libre); `list_assets()`; `get_asset_detail()` (activo + su conectividad real); `update_asset_status()` (sube `version`, mismo criterio de historial ligero que el resto del proyecto); `connect_assets()` (verifica EXPLÍCITAMENTE que ambos activos pertenecen al tenant vía `network_asset` — que sí tiene RLS — antes de escribir en `asset_connectivity`); `asset_connectivity()`; `assets_geojson()` (módulo de georreferenciación: solo activos CON geometría real, más sus conexiones como `LineString` cuando ambos extremos tienen geometría) | `services/digital-twin/asset_service.py` |
| 2026-09-12 | Endpoints nuevos: `POST/GET /network-assets`, `GET /network-assets/{id}` (con conectividad), `PATCH /network-assets/{id}/status`, `POST /asset-connectivity`, `GET /network-assets/geojson` | `services/portal-api/main.py` |
| 2026-09-12 | E2E real (`verify_digital_twin_end_to_end.py`): registrar un activo real; tipo inválido → `422`; listar y ver detalle con conectividad; cambiar estado sube versión; conectar dos activos reales se refleja en ambos; conectar contra un activo inexistente → `404`; **conectar contra un activo de OTRO tenant → `404`** (prueba de seguridad real, no cosmética); GeoJSON con 2 activos georreferenciados conectados → 2 puntos + 1 línea, activos sin geometría no aparecen | `verify_digital_twin_end_to_end.py` → `SPRINT B5 DIGITAL TWIN E2E OK` |
| 2026-09-12 | Regresión completa: los 17 `verify_*_end_to_end.py` de `portal-api` (con el nuevo de B5) en verde | `exit=0` en los 17 scripts |
| 2026-09-12 | Frontend: **`DigitalTwin.tsx`** (nuevo) — KPIs (total, operativos, fuera de servicio, por tipo), mapa de activos (reusa `NetworkMap.tsx`, coloreado por estado), formulario de registro (tipo, zona opcional, notas, lat/lon opcional), formulario de conexión entre activos, tabla con cambio de estado inline y conectividad expandible por fila | `services/portal-web/src/pages/DigitalTwin.tsx` |
| 2026-09-12 | Ruta `/digital-twin` + ítem de navegación "Gemelo Digital"; `api.ts` extendido con `NetworkAsset`/`NetworkAssetDetail` + funciones de cliente | `services/portal-web/src/App.tsx`, `AppShell.tsx`, `api.ts` |
| 2026-09-12 | `tsc -b && vite build` limpio, bundle contiene "Gemelo Digital"/"network-assets". Desplegado: backend (Nuitka, servicio `digital-twin` nuevo) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide exacto, `/api/network-assets` responde `401` (gateado, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |
| 2026-09-12 | `seed_demo_assets.py` (nuevo, mismo patrón que `seed_demo_networks.py`): 3 activos reales (tanque/tubería/válvula) conectados entre sí, georreferenciados sobre las MISMAS coordenadas del modelo hidráulico de demostración de Chapinero (Sprint B3) y vinculados a la MISMA zona demo de Balance de Red (Sprint B1) — coherencia visual entre los 3 módulos de demostración. Sembrado en producción | `services/digital-twin/seed_demo_assets.py`, corrida real contra Postgres de producción |

**Estado de Track B tras esta ronda:** B1, B3, B4 y B5 🟢 completos. Pendiente: **B6-B7**
(generación de modelo `.inp` desde el Gemelo Digital, Mantenimiento + integración BayForce) sin
iniciar.

### Track B, Sprint B6 — generar un modelo EPANET desde el Gemelo Digital (2026-09-13)

**Motivo:** "continua" tras cerrar B5 — siguiente paso natural: cerrar el ciclo entre el Gemelo
Digital (B5) y el Modelado Hidráulico (B3), igual que B4 cerró el ciclo entre Balance de Red y
Modelado Hidráulico.

**Criterio de mapeo activo→elemento EPANET, definido y documentado ANTES de escribir código**
(nunca una regla implícita): `tank`→`RESERVOIR` (cabeza fija real, `attributes.head_m`
obligatorio — el catastro no rastrea nivel/volumen en el tiempo, mapear a `TANK` real sería
fabricar datos que no existen); `valve`/`pump`/`meter`/`sensor`→`JUNCTION` (nudo de paso; el
comportamiento de control real de una válvula/bomba EPANET no se modela en esta v1, declarado,
no una promesa incumplida en silencio); un activo `pipe` que conecta EXACTAMENTE otros dos
activos se "contrae" en un enlace `PIPE` real entre sus dos vecinos (así modela un SIG real una
tubería — una línea entre dos nudos, no un tercer nudo intermedio); una conexión directa sin un
`pipe` describiéndola también genera un enlace `PIPE`, con diámetro/rugosidad genérico
documentado (nunca se omite el enlace, tampoco se inventa un diámetro "real" que no existe).

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-13 | **`twin_export.py` (nuevo, lógica pura)**: `export_to_inp()` construye el `.inp` real desde listas de activos/conectividad ya leídas — `NoSourceAssetError` (sin ningún `tank`), `MissingTankHeadError` (`tank` sin `head_m`), `MissingGeometryError` (nudo sin `[COORDINATES]` real), `AmbiguousPipeConnectivityError` (un `pipe` con ≠2 conexiones) — nunca se adivina, siempre un error claro. Longitud de cada tubería calculada por Haversine real entre las coordenadas de sus dos extremos (no un valor inventado) | `services/digital-twin/twin_export.py` |
| 2026-09-13 | 8/8 pruebas unitarias puras — incluye el caso real que confirma que el `.inp` generado, cargado y simulado con WNTR, da una presión EXACTA (`Head - Elevación`, sin demanda) igual que un modelo escrito a mano — mismo camino de validación/simulación (`network_model_engine.py`) | `python -m unittest tests.test_twin_export -v` → 8/8 OK |
| 2026-09-13 | **`asset_service.zone_assets_and_connectivity()`** (nuevo): activos de una zona + conectividad restringida a AMBOS extremos dentro de esa misma zona (una conexión que sale de la zona se excluye sin avisar — límite de alcance real, documentado, no un error). **`model_service.register_model_from_twin()`** (nuevo): genera el `.inp` y lo registra por el MISMO camino que uno subido a mano (`register_model()` — misma validación, mismo versionado), vinculando el modelo a la zona de origen automáticamente (reusa `zone_id` de B4 — el modelo generado queda calibrable con el balance real de esa zona sin pasos adicionales) | `services/digital-twin/asset_service.py`, `services/network-model/model_service.py` |
| 2026-09-13 | Endpoint nuevo: `POST /network-zones/{id}/generate-model` — `422` con el motivo REAL (`NoSourceAssetError`/`MissingGeometryError`/`MissingTankHeadError`/`AmbiguousPipeConnectivityError`) si el grafo no alcanza para generar un modelo válido | `services/portal-api/main.py` |
| 2026-09-13 | E2E real (`verify_generate_model_end_to_end.py`): zona con `tank`→`pipe`→`valve` reales y georreferenciados (coordenadas reales de Cali) genera un modelo real, vinculado a la zona; **el modelo generado SE SIMULA por el mismo endpoint que uno cargado a mano y da la presión hidráulica EXACTA esperada** (`Head - Elevación = 45.0 m.c.a.`, sin demanda) — confirma el criterio de aceptación del sprint ("simula igual que uno cargado a mano") de punta a punta, no solo en el motor puro; zona sin ningún `tank` → `422` | `verify_generate_model_end_to_end.py` → `SPRINT B6 GENERATE MODEL E2E OK` |
| 2026-09-13 | Regresión completa: los 18 `verify_*_end_to_end.py` de `portal-api` (con el nuevo de B6) en verde | `exit=0` en los 18 scripts |
| 2026-09-13 | Frontend: botón "Generar modelo (Gemelo Digital)" en cada fila de zona de `NetworkBalance.tsx` — genera el modelo, confirma el nombre y enlaza directo a Modelado Hidráulico para verlo/simularlo | `services/portal-web/src/pages/NetworkBalance.tsx`, `services/portal-web/src/api.ts` |
| 2026-09-13 | `tsc -b && vite build` limpio, bundle contiene "Generar modelo (Gemelo Digital)"/"generate-model". Desplegado: backend (Nuitka) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide exacto, endpoint nuevo gateado (401, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |

**Estado de Track B tras esta ronda:** B1, B3, B4, B5 y B6 🟢 completos. Pendiente: **B7**
(generación de `maintenance_order` desde anomalías + integración BayForce) sin iniciar.

**Corrección adicional pedida por el usuario en la misma ronda** ("aseurate de no estar
compilando cada vez. Solo deberias compilar los cambios"): `~/build-renfygrid.sh` recompilaba
**todo** el portafolio (~85 archivos) en cada corrida, apoyándose solo en `ccache` a nivel de
compilador C para no gastar CPU — pero seguía invocando Nuitka por archivo sin cambios, gastando
tiempo real. Corregido para ser incremental de verdad: si el `.so` ya existe y es más nuevo que
su `.py` fuente, se salta por completo. Verificado en vivo: la siguiente corrida (con los
cambios reales de B6) compiló **5 archivos** en vez de 85. Aprovechado también para corregir un
pendiente histórico ya anotado en la bitácora: el script vivía SOLO en WSL, sin versionar — ahora
vive en el repo (`infra/build/build-renfygrid.sh` + `README.md`), copiar a
`~/build-renfygrid.sh` en cualquier máquina de build nueva.

### Track B, Sprint B7 — Gestión de Mantenimiento + integración BayForce (2026-09-13/14)

**Motivo:** "continua" tras cerrar B6 — último sprint pendiente de Track B.

**Investigación real antes de diseñar nada**: revisado el código real de BayForce ya en el
portafolio (`core/renflow/bayforce/main.py`, ~9400 líneas, MySQL propio — un sistema externo de
verdad, no una tabla compartida). Su API está orientada a SU propia operación (despacho,
móviles, planificación) y ya tiene un patrón de eventos entrantes de un WFMS externo
(`POST /wfms/events`) — pero no expone (todavía) un endpoint dedicado de "crear orden desde un
sistema externo + webhook de cierre" con URL/credenciales de sandbox reales conocidas por esta
sesión. Decisión honesta, misma postura que con F07 (medidor piloto real bloqueado): construir el
**contrato real** que RenfyGrid expone/consume — probado de punta a punta contra un sandbox HTTP
real (no un mock) — dejando la conexión al BayForce vivo como lo que es: pendiente de su URL/
credenciales reales, no fabricado.

**Reglas de generación, validadas contra datos reales antes de insertar** (nunca una orden
"porque sí" para una fuente automática): `asset_condition` exige que el activo esté REALMENTE
`out_of_service`/`maintenance` ahora mismo; `balance_anomaly` exige que la zona del activo tenga
un balance reciente con `exceeds_threshold=True` (reusa B1-2/B4); `simulation_result` queda sin
validación automática en esta v1 (declarado, no una promesa incumplida en silencio — el disparo
automático desde una corrida real de B3/B4 es trabajo de un sprint futuro); `manual` no tiene
precondición (juicio humano explícito).

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-13 | **Migración `0017_maintenance_order_reason.sql`**: `maintenance_order.reason` (texto, opcional) — el operador necesita ver POR QUÉ se generó una orden, no solo su `type`/`source` en código | `infra/db/migrations/0017_maintenance_order_reason.sql` |
| 2026-09-13 | **`order_service.py` (nuevo)**: `generate_order()` (valida tipo/fuente contra los valores reales del esquema, verifica la anomalía real para `asset_condition`/`balance_anomaly`, `AnomalyNotConfirmedError` si no se cumple); `list_orders()`/`get_order_detail()`; `send_to_bayforce()` (HTTP real — `POST` JSON al webhook configurado, `BayforceNotConfiguredError` si no hay URL, `BayforceIntegrationError` si BayForce no responde o responde algo no interpretable, nunca un envío fabricado); `close_from_webhook()` (máquina de estados real — `generated→sent_to_bayforce→in_progress→completed\|cancelled`, `InvalidStatusTransitionError` si el salto no es válido) | `services/maintenance/order_service.py` |
| 2026-09-13 | `config.py`: `RENFYGRID_BAYFORCE_WEBHOOK_URL` (opcional, `None` si el tenant no tiene BayForce configurado todavía — nunca una URL fija en código) | `services/portal-api/config.py` |
| 2026-09-13 | Endpoints nuevos: `POST/GET /maintenance-orders`, `GET /maintenance-orders/{id}`, `POST /maintenance-orders/{id}/send-to-bayforce`, `POST /maintenance-orders/bayforce-webhook` (mismo mecanismo de autenticación que ya usa el portal para un CIS externo — JWT del tenant — no se inventa un esquema de firma nuevo) | `services/portal-api/main.py` |
| 2026-09-13 | **E2E real con un sandbox HTTP real** (`verify_maintenance_end_to_end.py`): un servidor `http.server` real en un hilo, sin mockear nada, hace de BayForce — recibe la orden por HTTP de verdad y devuelve un `bayforce_order_ref` real. Cubre: orden `asset_condition` sobre un activo realmente roto (éxito) vs. operativo (422); `balance_anomaly` sobre zona con exceso real (éxito) vs. sin balance (422); envío real a BayForce → `sent_to_bayforce`; reenvío → 422; flujo completo del webhook de cierre `sent_to_bayforce→in_progress→completed`; transición inválida → 422; `bayforce_order_ref` inexistente → 404; envío sin webhook configurado → error real, no un falso éxito | `verify_maintenance_end_to_end.py` → `SPRINT B7 MAINTENANCE E2E OK` |
| 2026-09-13 | Regresión completa: los 19 `verify_*_end_to_end.py` de `portal-api` (con el nuevo de B7) en verde | `exit=0` en los 19 scripts |
| 2026-09-13 | Frontend: **`Maintenance.tsx`** (nuevo) — KPIs (total, por enviar, en BayForce, completadas), filtro por estado, formulario de generación (con las precondiciones explicadas en la propia pantalla), botón "Enviar a BayForce" por orden en `generated`; el cierre se refleja solo (BayForce lo empuja por su webhook), sin un botón manual que lo falsee | `services/portal-web/src/pages/Maintenance.tsx` |
| 2026-09-13 | `tsc -b && vite build` limpio, bundle contiene "Mantenimiento"/"maintenance-orders". Desplegado: migración 0017 con respaldo real primero, backend (Nuitka, servicio `maintenance` nuevo, build incremental: solo 2 archivos reales) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. Verificado en vivo: bundle coincide exacto, endpoint nuevo gateado (401, no 404/500) | `curl https://renfygrid.rensoftlabs.com/...` |
| 2026-09-13 | **Smoke test real contra producción**: una orden manual real sobre un activo demo real (Chapinero), y confirmado que enviar a BayForce SIN webhook configurado (estado real de producción — no hay URL/credenciales de BayForce todavía) da el error correcto, no un falso éxito | corrida real contra Postgres/venv de producción → `PROD SMOKE B7 OK` |

**Pendiente real, explícito**: conectar `RENFYGRID_BAYFORCE_WEBHOOK_URL` al BayForce vivo
requiere su URL/credenciales de sandbox o producción reales — no están disponibles en esta
sesión, no se fabricaron. El contrato del lado de RenfyGrid está completo, probado y listo para
apuntar ahí en cuanto existan. Disparo automático de `simulation_result` desde una corrida real
de B3/B4 queda para un sprint futuro.

**Estado de Track B tras esta ronda:** B1, B3-B7 completos. B2 quedó parcialmente cubierto por
diseño desde B1 — completado en la siguiente ronda.

### Track B, Sprint B2 — completo: Top-Down (residual) y Bottom-Up (MNF) reales (2026-09-13/14)

**Motivo:** "sigue con B2 completo" — el usuario pidió cerrar el único hueco real que quedaba
declarado como parcial desde B1: `real_losses` se pedía como dato directo para **cualquier**
método, cuando el método Top-Down real (AWWA M36, *Water Audits and Loss Control Programs*) lo
define como el **residual** del balance (nunca medido directo), y Bottom-Up (IWA) lo mide/estima
por separado — normalmente por análisis de Caudal Mínimo Nocturno (MNF). Investigación real
antes de tocar código: confirmada la metodología MNF real (fuente:
[MDPI *Water* 2022, "Probabilistic Minimum Night Flow Estimation..."](https://doi.org/10.3390/w14010098))
— de madrugada el consumo cae al mínimo, así que casi todo el caudal que sigue entrando es fuga,
no consumo; el Night-Day Factor (NDF) convierte esa tasa nocturna en el promedio real de 24h.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-13 | **`network_balance_engine.compute_top_down_real_losses()`** (nuevo): `real_losses` = SIV menos los otros 4 componentes — residual real, puede dar NEGATIVO si los componentes declarados exceden el SIV (señal real de datos inconsistentes, nunca recortado a 0 en silencio). `None` solo si SIV≤0 | `services/network-balance/network_balance_engine.py` |
| 2026-09-13 | **`bottom_up_real_losses_from_mnf()`** (nuevo): NNF (fuga neta nocturna) = MNF − consumo legítimo nocturno; Volumen real = NNF × NDF × período. TODOS los insumos son obligatorios, sin default oculto — el NDF depende de la presión/material real de cada zona, nunca un valor genérico asumido en el motor (mismo criterio "cero hardcode" del resto del proyecto) | `services/network-balance/network_balance_engine.py` |
| 2026-09-13 | 8 pruebas unitarias nuevas — incluye confirmar que un residual negativo NO se recorta, y que los 4 parámetros de la fórmula MNF no tienen default (inspeccionado por firma de la función). **26/26 pruebas puras del módulo en verde** | `python -m unittest tests.test_network_balance_engine -v` → 26/26 OK |
| 2026-09-13 | **Migración `0018_network_balance_derived_flag.sql`**: `network_balance.real_losses_derived` — de dónde salió `real_losses` (calculado vs. medido/declarado), proveniencia real, nunca implícita | `infra/db/migrations/0018_network_balance_derived_flag.sql` |
| 2026-09-13 | `balance_service.submit_balance()`: `real_losses` pasa a ser OPCIONAL — `method='top_down'` sin `real_losses` lo deriva como residual (si el llamador ya trae su propio audit externo, se respeta tal cual, nunca se sobreescribe); `method='bottom_up'` sigue exigiéndolo (`MissingRealLossesError` si falta — nunca se calcula como residual, eso rompería la definición misma del método). `method` ahora se valida contra los 2 valores reales (`InvalidMethodError` si no es `top_down`/`bottom_up`) | `services/network-balance/balance_service.py`, `services/portal-api/main.py` |
| 2026-09-13 | E2E extendido: `top_down` sin `real_losses` → se deriva correcto (`real_losses_derived=True`, balance cierra exacto por construcción); `bottom_up` sin `real_losses` → `422`; `method` inválido → `422`; caso de inconsistencia real preexistente ajustado para declarar `real_losses` explícito (si no, ya no prueba una inconsistencia real — ahora se derivaría y cerraría solo) | `verify_network_balance_end_to_end.py` → `SPRINT B1/B1-2/B2 NETWORK BALANCE E2E OK` |
| 2026-09-13 | Regresión completa: los 19 `verify_*_end_to_end.py` de `portal-api` en verde | `exit=0` en los 19 scripts |
| 2026-09-13 | Frontend: el campo "Pérdidas reales" del formulario de ingesta ahora es opcional para Top-Down (con la explicación del residual en pantalla) y obligatorio para Bottom-Up (deshabilita el botón si falta); la tabla de balances muestra una columna "Pérdidas reales" con badge "derivado" cuando `real_losses_derived=true` | `services/portal-web/src/pages/NetworkBalance.tsx`, `api.ts` |
| 2026-09-13 | `tsc -b && vite build` limpio, bundle contiene "derivado"/"se calcula solo". Desplegado: migración 0018 con respaldo real primero, backend (Nuitka, build incremental) + `main.py` a `essmarplapp02`, `systemctl restart renfygrid-portal-api` → activo; frontend a `essmarplpxy03`. **Smoke test real contra producción**: un balance `top_down` real sin `real_losses` se deriva correctamente (`10000-7500-200=2300`, `real_losses_derived=True`) | corrida real contra Postgres/venv de producción → `PROD SMOKE B2 OK` |

**Estado de Track B tras esta ronda:** **B1 a B7, las 7 épicas del Track B originalmente
planteadas, están construidas y completas** (incluyendo B2, ya sin ningún alcance parcial
declarado). Únicos pendientes reales: la conexión viva a BayForce (bloqueada por credenciales
externas, no por trabajo) y el disparo automático de órdenes de mantenimiento desde
`simulation_result`.

### Ronda de endurecimiento del proyecto completo (2026-09-13)

**Motivo:** con los tres tracks (A, B, C) completos, el usuario pidió explícitamente "Endurecer
lo construido" en vez de abrir alcance nuevo — auditoría de seguridad, consistencia entre
módulos, deuda técnica anotada durante la sesión, y cierre de cabos sueltos reales (no
cosméticos).

| Verificación | Resultado |
|---|---|
| RLS en todas las tablas de Track A/B en producción (`relrowsecurity`/`relforcerowsecurity`/política `*_tenant_isolation`) | Correcto en todas salvo `asset_connectivity` (sin RLS por diseño documentado — mitigado en capa de aplicación, ver Sprint B5) y `tenant` (tabla raíz, correctamente sin RLS). Sin brechas nuevas. |
| Inyección SQL en los servicios nuevos B1-B7 (`balance_service.py`, `asset_service.py`, `order_service.py`) — construcción de queries con f-strings | Solo se interpolan fragmentos de cláusula fijos y literales (`"AND zone_id = %s"`); los valores siempre van por `%s` parametrizado. Sin riesgo encontrado. |
| `.github/workflows/tests.yml` sin trackear — reintento de `git add`+push | Sigue bloqueado por el mismo error de GitHub ("refusing to allow a Personal Access Token ... without `workflow` scope"). Revertido limpio. Sigue siendo un bloqueo externo real: necesita que el usuario regenere su PAT con scope `workflow`, o suba ese archivo a mano. |
| Nota "pendiente" de Sprint 0 sobre TimescaleDB | Estaba obsoleta: TimescaleDB nunca se instaló (confirmado en `pg_extension` de producción); el particionado nativo de Postgres (F10, Sprint C11) es la solución real y ya en uso, con particiones reales y mantenimiento (ver fila siguiente). Nota corregida en la bitácora. |
| Nota "pendiente para C6" (pantalla Integraciones) | Obsoleta: la sección inmediatamente siguiente (Sprint C6) ya documentaba esa pantalla como cerrada y desplegada desde el mismo día. Nota corregida. |
| **Cron/timer real de `partition_maintenance.py` (F10)** — anotado como pendiente no urgente desde Sprint C11 ("antes de que se acabe octubre 2026") | **Verificado en vivo que seguía sin programarse** (sin crontab de usuario/root ni timer systemd para esto en `essmarplapp02` — se comprobó, no se asumió). Preparado el cierre real: rol admin `renfygrid` con contraseña rotada dedicada para este job (nunca la de `renfygrid_app`), wrapper `/opt/renfygrid/common/run_partition_maintenance.sh`, unidades `renfygrid-partition-maintenance.service`+`.timer` (diario, 03:15, con `RandomizedDelaySec`). **No aplicado todavía**: el modo automático de esta sesión bloqueó la escritura por tocar una contraseña de base de datos en producción ("Secret-Store Writes") — requiere que el usuario apruebe ese paso puntual antes de ejecutarlo. |
| Restos de `pg_dump` de respaldos anteriores en `/tmp` de `essmarplapp02` | Encontrados 9 archivos `.dump` (protocolo de la sesión es limpiarlos siempre tras cada despliegue — no se había hecho en varias rondas). Eliminados. |

**Pendiente real, requiere aprobación explícita del usuario para el siguiente paso:** activar el
timer de mantenimiento de particiones ya preparado arriba (implica rotar la contraseña del rol
admin `renfygrid` en producción).

**Actualización (2026-09-13, mismo día):** el usuario aprobó instalar el timer pero pidió
explícitamente no rotar ninguna contraseña. Rehecho sin ese paso: el wrapper se conecta por
**autenticación peer vía socket Unix como rol `postgres`** (mismo mecanismo que ya usa `pg_dump`
en cada respaldo previo a una migración) — cero contraseñas nuevas, cero secreto de por medio.
Aceptable porque el job es DDL puro (`CREATE TABLE ... PARTITION OF`), nunca lee datos de un
tenant.

**Hallazgo real durante la instalación**: el servicio fallaba bajo `systemctl start` con
`Permission denied` al ejecutar el script, aunque el mismo archivo corría perfecto a mano
(`sudo -u postgres /opt/.../run_partition_maintenance.sh`). Causa real, confirmada con
`systemd-run` aislando la variable (mismo fallo con una unidad transitoria, sin relación con
`User=postgres` en sí — `/bin/echo` sí corría bien como ese usuario): **SELinux**, no permisos
Unix. El script tenía el tipo genérico `default_t` (vive bajo `/cdrs/renfygrid`, sin regla de
contexto propia declarada), y el dominio confinado con el que systemd ejecuta servicios no tiene
permiso de exec sobre ese tipo — por eso fallaba solo bajo systemd (dominio confinado) y no en
una sesión interactiva por SSH (`unconfined_t`, sin restricción). El propio
`renfygrid-portal-api.service`, que sí funciona, nunca tropezó con esto porque su `ExecStart`
resuelve (via symlinks del venv) hasta `/usr/bin/python3.9`, ya etiquetado `bin_t` por el sistema.
Corregido con `semanage fcontext -a -t bin_t` (persiste tras un relabel completo) +
`restorecon` sobre la ruta real (`/cdrs/renfygrid/...`, no el symlink `/opt/renfygrid/...`).

**Cerrado y verificado**: `renfygrid-partition-maintenance.service`+`.timer` activos en
`essmarplapp02`, corrida real confirmada (aseguró `raw_reading_y2026_m09/_m10/_m11`), próxima
corrida automática mañana 03:16. **F10 ya no tiene ningún pendiente real.**

### Pulido de consistencia entre módulos, Track B (2026-09-14)

**Motivo:** con el endurecimiento real cerrado, el usuario pidió una pasada de consistencia
entre las 4 pantallas nuevas de Track B (Balance de Red, Modelado Hidráulico, Gemelo Digital,
Mantenimiento) y entre los servicios backend nuevos vs. los de Track A.

**Revisión de frontend** (las 4 pantallas contra `Integrations.tsx`/`StagePage`/`EmptyState`
como referencia): sin hallazgos reales. Las 4 páginas ya siguen el mismo idioma visual completo
— mismas tarjetas de resumen, mismo patrón de formulario colapsable, mismo cuadro explicativo
`indigo-50` al pie, mismos estados de carga/vacío, mismo manejo de `ApiError`, ya integradas en
`AppShell`/`NAV_ITEMS` con ícono propio. No se tocó nada.

**Revisión de backend** (docstrings de módulo, nombres de excepciones, mapeo excepción→HTTP en
`portal-api/main.py`): los 4 servicios nuevos (`balance_service.py`, `model_service.py`,
`asset_service.py`, `order_service.py`) siguen el mismo patrón que los de Track A —
docstring de cabecera con la justificación de diseño, excepciones nombradas
`*Error(LookupError|ValueError|RuntimeError)`, `NotFound*` → 404, `Invalid*`/`Missing*` → 422.

**Un hallazgo real, corregido**: `order_service.InvalidStatusTransitionError` (transición de
estado inválida de una `maintenance_order`, ej. reenviar una orden que ya no está en
`generated`) mapeaba a `422` en los dos endpoints donde se usa
(`POST /maintenance-orders/{id}/send-to-bayforce`, `POST /maintenance-orders/bayforce-webhook`).
El caso análogo exacto en Control/SCR (`control_service.InvalidTransitionError`, transición de
estado inválida de un `control_order`) ya usaba `409` desde antes — mismo concepto semántico
(transición de máquina de estados inválida, no un cuerpo de request malformado) mapeado
distinto entre dos módulos. Corregido a `409` en Mantenimiento para seguir la convención ya
establecida por Control/SCR. `BayforceNotConfiguredError`/`BayforceIntegrationError` (errores
de configuración/integración real, no de transición de estado) se quedan en `422`, sin cambio.

E2E actualizado (`verify_maintenance_end_to_end.py`, pasos 5 y 7) y regresión completa de los
19 `verify_*_end_to_end.py` de `portal-api` en verde. `main.py` (mantenido como fuente, no
compilado con Nuitka) desplegado directo a `essmarplapp02`, `systemctl restart
renfygrid-portal-api` → activo, verificado en vivo desde internet (`401` en los endpoints
protegidos, no `500`, confirma que la app arrancó limpia con el cambio). El flujo `409` real
contra BayForce en vivo queda sin poder probarse en producción por la misma razón ya
documentada en B7 (`RENFYGRID_BAYFORCE_WEBHOOK_URL` no configurado ahí a propósito) — la
prueba real de punta a punta es el E2E local contra el sandbox real, no un mock.

### Pulido de usabilidad y navegación interna (2026-09-14)

**Motivo:** el usuario pidió explícitamente revisar la usabilidad de cada menú contra estándar
real de industria, sin conformarse con lo cosmético — "la navegación dentro de cada menú no se
ve intuitiva".

**Investigación real** (no gusto propio): Nielsen Norman Group, ["Anchors OK? Re-Assessing
In-Page Links"](https://www.nngroup.com/articles/in-page-links/) — una navegación
persistente/sticky es ~22% más rápida de recorrer que un scroll ciego, y una página larga sin
ella tiene 39% más abandono al 50% del scroll. El patrón real de "Settings view" empresarial
(Stripe, Salesforce Setup) organiza secciones heterogéneas con su propia navegación en vez de
apilarlas sin más.

**Hallazgo real**: revisando las 12 pantallas, 6 tenían 2+ secciones stackeadas verticalmente
sin ninguna forma de saltar entre ellas — la más severa, `Configuration.tsx` (5 secciones de
administración sin relación visual entre sí, la página más larga del portal).

**Corregido**: nuevo componente compartido `SectionNav` (`components/SectionNav.tsx`) — barra
de chips pegajosa justo debajo del header de `AppShell`, con scroll-spy real (resalta la
sección visible mientras se hace scroll, no solo al hacer click) y `scroll-mt-24` en cada
sección para que ni el header ni la propia barra tapen el título al saltar (el problema de
solape que NN/g documenta explícitamente). Aplicado a `Configuration.tsx` (5 secciones),
`Meters.tsx` (5), `NetworkBalance.tsx` (3), `Vee.tsx` (3, sobre el patrón V/E/E ya existente),
`DigitalTwin.tsx` (2), `Consumption.tsx` (2).

**Segundo hallazgo real, encontrado en la misma revisión**: `Overview.tsx` (Vista general, la
pantalla de entrada) solo tenía 4 tiles de KPI — únicamente Track A (HES, VEE, Consumo,
Control). Los 4 módulos de Track B (Balance de Red, Modelado Hidráulico, Gemelo Digital,
Mantenimiento) eran invisibles desde la entrada, sin ninguna señal de que existieran salvo el
propio sidebar. El usuario, viendo el resultado intermedio, pidió explícitamente ir más allá
de agregar tiles: **"eso luce como una plataforma escolar... asegúrate que sea un reflejo
general de TODA la plataforma con KPIs de todo. Mapas, si es posible, gráficos, etc."**

**Vista general reconstruida de punta a punta**, con datos reales ya expuestos por endpoints
existentes (nada inventado para "verse lleno"):
- **`dashboard_overview()` extendido** (`portal-api/dashboard.py`) con 3 conteos reales más,
  reusando servicios ya existentes en vez de duplicar SQL: `balance_summary()` → zonas sobre
  su tope de NRW; `list_assets()` → activos fuera de servicio; `list_orders(status='generated')`
  → órdenes de mantenimiento por enviar. Modelado Hidráulico deliberadamente NO tiene tile
  propio — no tiene una noción real de "excepción pendiente" (una simulación falla o no falla
  al pedirla, no queda cola por revisar); forzar un tile ahí violaría el patrón exception-first
  en vez de servirlo.
- **7 tiles de KPI** (antes 4) cubriendo los 7 módulos con noción real de excepción.
- **Mapa real de la red**: mismo `NetworkMap`/`nrwColorForMap` que usa Balance de Red, con las
  zonas geolocalizadas coloreadas por NRW.
- **2 gráficos reales**: tendencia VEE de 7 días (`TrendBars`, extraído de `Vee.tsx` a un
  componente compartido `components/TrendBars.tsx` para no duplicar lógica) y flota HES con
  menor % reportando (barras horizontales, mismo criterio visual que `Meters.tsx`) + 4
  estadísticos compactos (NRW% promedio, peor ILI, éxito de comando SCR, % listo para
  facturar).
- **Lanzador de los 11 módulos**: grid de tarjetas con ícono/nombre/descripción de una línea
  para cada pantalla del portal (mismos íconos que el sidebar de `AppShell`), para que la
  entrada sea un mapa real de toda la plataforma, no solo de los módulos con alertas.
- La propia Vista general ahora también usa `SectionNav` (4 secciones: Estado general, Mapa de
  la red, Tendencias, Todos los módulos) — aplica el mismo pulido de navegación a sí misma.

**Hallazgo real de infraestructura, encontrado al recompilar**: el build de Nuitka llevaba
desde el Sprint C11 (2026-09-11) fallando en silencio en `common/renmeter_common/__init__.py`
en CADA corrida — Nuitka rechaza compilar un `__init__.py` de paquete de forma standalone
("to compile a package, specify its directory but, not the '__init__.py'"), una limitación
real de la herramienta, no detectada antes porque el script nunca fallaba duro por un archivo
individual. Confirmado en producción: `__init__.py` seguía como fuente `.py` sin compilar
desde el primer despliegue manual (11-sep), violando la política de portafolio ("no fuentes
.py en servidores") sin que nadie lo notara. Corregido formalizando `__init__.py` en la lista
`SKIP` de `common` (109 bytes, un simple re-export sin lógica de negocio — la única excepción
real y documentada a la política, por una limitación genuina de Nuitka, no una decisión de
conveniencia) — `infra/build/build-renfygrid.sh` actualizado y sincronizado con la copia viva
en WSL. Build re-corrido: **0 fallidos** en los 10 servicios.

**Verificado y desplegado**: `tsc -b` y `vite build` limpios; regresión completa de los 19
`verify_*_end_to_end.py` de `portal-api` en verde (incluye `verify_login_and_dashboard_end_to_end.py`
extendido con aserciones reales sobre los 3 conteos nuevos). Backend: `dashboard.so`
recompilado (incremental) y desplegado a `essmarplapp02`, **smoke test real contra
producción** con el tenant demo (login real, JWT real) confirmando los 3 conteos nuevos en el
payload real. Frontend: build desplegado a `essmarplpxy03`, confirmado en vivo desde internet
(nuevas etiquetas de sección y del lanzador de módulos presentes en el bundle servido).

### Análisis real de alcance: Mantenimiento no es un CMMS todavía (2026-09-14)

**Motivo:** el usuario, viendo el panel de Mantenimiento en vivo, señaló directamente que "es un
dibujo y nada más" — sin parametrización de órdenes, planeación ni despacho — y pidió el mismo
rigor de investigación de industria ya aplicado en otros módulos (VEE, Consumo, HES) antes de
implementar nada.

**Investigación real, no cosmética**: se leyó completo `core/renflow/bayforce/main.py` (9400
líneas, otro producto del portafolio) para verificar el estado real de la integración —
resultado: **BayForce no tiene ningún endpoint de creación de orden externa genérico**. Todo lo
que entra a `field_orders` viene del workflow de cobro de RenFlow (`subscriber_id`/
`execution_id`, numeración `RF-...`), confirmado también por `BAYFORCE_USER_GUIDE.md`
("Workflow de cobro → genera FIELD_ORDER" es la única puerta de entrada). El contrato que
`send_to_bayforce()` asume no tiene nada real del otro lado, con o sin credenciales — la
descripción anterior de F45 como "bloqueado solo por credenciales" era inexacta, corregida en
la matriz funcional arriba.

Grounding de industria (Cityworks — referencia dominante en CMMS de acueducto/alcantarillado,
GIS-céntrico — y métricas estándar MTTR/MTBF/% cumplimiento PM): confirmado que Mantenimiento
carece de TODA la sustancia real de un CMMS — prioridad/SLA, códigos de falla, mantenimiento
preventivo programado (`preventive` era solo una etiqueta), planeación/asignación, cierre con
horas/materiales, KPIs.

**Discusión de arquitectura real con el usuario** (pregunta directa: ¿construir esto en
RenfyGrid viola una filosofía de microservicios de módulos encapsulados?) — respuesta: no, si se
separan correctamente dos capas. La parametrización del dominio (activos de red, zonas, NRW,
EPANET) es conocimiento propio real de RenfyGrid que BayForce nunca tendrá — construirla ahí no
es "clonar" nada. El motor de despacho/ruteo (cuadrillas, turnos, OR-Tools, ejecución móvil) sí
es tecnología genérica que BayForce ya resuelve bien — reconstruirla en RenfyGrid sí sería
duplicar ingeniería real innecesariamente.

**Decisión final** (detalle completo en `04-plan-sprints.md` §9 y
`contextos/renflow/docs/BAYFORCE_RENFYGRID_INTEGRATION_NOTE.md`, repo de contextos local):
RenfyGrid construye su propio CMMS de dominio (prioridad/SLA, códigos de falla, PM programado,
ciclo de vida completo, cierre, KPIs) con una capa de asignación PROPORCIONADA (cuadrilla/
técnico simple + calendario, no un motor de ruteo propio); BayForce queda como notificación de
salida opcional, nunca columna vertebral; convertir BayForce en un servicio de plataforma
compartido queda **explícitamente diferido, no autorizado** — decisión de negocio aparte que
toca otro producto en vivo.

**Pendiente de implementar** — alcance detallado ya en `04-plan-sprints.md` §9, siguiente ronda
de trabajo sobre Mantenimiento.

### CMMS real de Mantenimiento — Fase 1 construida y desplegada (2026-09-14)

**Motivo:** el usuario aprobó la fase 1 del alcance recién documentado ("Si, adelante") y pidió
seguir directo a la implementación real.

**Migración `0019_maintenance_cmms_core.sql`**: 4 tablas nuevas (patrón semilla+catálogo, RLS en
las 4) — `maintenance_sla_policy` (horas objetivo por tenant+prioridad), `maintenance_failure_code`,
`maintenance_crew`, `maintenance_pm_plan` (plan real por activo específico, nunca "por tipo de
activo" genérico); 9 columnas nuevas en `maintenance_order` (`priority`, `sla_due_at`,
`failure_code_id`, `scheduled_at`, `assigned_crew_id`, `labor_hours`, `materials_used`,
`root_cause`, `closed_at`).

**`maintenance_engine.py` (nuevo, lógica pura sin BD)**: `compute_sla_due_at` (nunca fabrica una
fecha límite sin una política real configurada), `is_overdue`, `compute_mttr_hours`,
`compute_backlog`, `compute_pm_compliance_pct` (solo cuenta órdenes que SÍ tenían un SLA real
configurado — nunca inventa un % de cumplimiento sobre nada), `pm_plan_is_due`/`advance_pm_plan`.
**16/16 pruebas puras nuevas en verde**.

**`order_service.py` reescrito**: ciclo de vida real y propio —
`generated -> scheduled -> assigned -> in_progress -> completed | cancelled` — con el ramal
`sent_to_bayforce` de B7 intacto como camino OPCIONAL en paralelo (BayForce sigue siendo
notificación de salida, nunca la columna vertebral, tal como se decidió). `priority` ahora
obligatoria al generar una orden (igual que `type`/`source`); `close_order()` exige horas de
mano de obra/materiales/causa raíz/código de falla reales para cerrar, solo válido desde
`in_progress`. Nueva fuente `pm_schedule`, exclusiva de `generate_due_pm_orders()` — nunca a
mano. 12 endpoints nuevos en `portal-api/main.py` (schedule/assign/start/close, KPIs, CRUD de
SLA/códigos de falla/cuadrillas/planes PM, generar vencidos), mapeo HTTP consistente con el
resto del proyecto (`NotFound*` → 404, `Invalid*` → 422, transición inválida → 409 — nueva
`InvalidCloseStatusError` separada de `InvalidStatusTransitionError` para que el endpoint no
tenga que adivinar cuál de las dos causó el error).

**E2E extendido** (`verify_maintenance_end_to_end.py`, 7 pasos nuevos): política de SLA real
(`high`→4h calcula `sla_due_at`, `low` sin política queda en `None`); catálogos; ciclo de vida
completo sin BayForce con cierre real (horas/materiales/causa/código de falla); cerrar antes de
`in_progress` → 409; asignar cuadrilla inexistente → 404; KPIs reflejan la orden completada
(MTTR) y las abiertas (backlog); plan PM ya vencido → `generate-due` genera una orden real
`pm_schedule` y avanza `next_due_at` al futuro, una segunda corrida inmediata no genera otra.
Regresión completa de los 19 `verify_*_end_to_end.py` en verde.

**Frontend**: `Configuration.tsx` gana 3 secciones nuevas (SLA de mantenimiento, códigos de
falla, cuadrillas) sobre el mismo patrón `SectionCard`. `Maintenance.tsx` reconstruida — tarjetas
de KPI reales (MTTR, backlog, % cumplimiento PM, vencidas de SLA), tabla de órdenes con badge de
prioridad/SLA/vencida y acciones contextuales según el estado real (programar → asignar → iniciar
→ cerrar con formulario real), sección nueva de planes de mantenimiento preventivo con botón
"Generar órdenes vencidas". `tsc -b`/`vite build` limpios.

**Desplegado y verificado en producción**: respaldo real (`pg_dump`) antes de la migración,
migración 0019 aplicada (peer auth como `postgres`, sin contraseña nueva) + `GRANT` explícito
verificado para `renfygrid_app` sobre las 4 tablas nuevas (nunca asumido); `maintenance_engine.so`
+ `order_service.so` recompilados (incremental, 0 fallidos) y desplegados; **smoke test real
contra producción** con el tenant demo (login real, JWT real): `GET /maintenance/kpis` responde
correcto, crear/listar/desactivar una cuadrilla real funciona de punta a punta. Frontend
desplegado y confirmado en vivo desde internet.

**Pendiente real, explícito, no bloqueante**: automatizar `generate_due_pm_orders()` con un
timer real (hoy es un botón manual en el Portal, mismo patrón que ya se resolvió para
`partition_maintenance.py` — se puede replicar el mismo timer systemd cuando haya planes PM
reales que lo necesiten). El motor de despacho/ruteo y la integración BayForce en vivo siguen
explícitamente fuera de alcance, tal como se decidió.

### Datos de demostración: segunda zona en Cali + CMMS con historial real (2026-09-14)

**Motivo:** el usuario pidió datos de muestra reales para que la funcionalidad se viera
completa, simulados sobre Cali y/o Bogotá — el tenant demo tenía Mantenimiento completamente
vacío (0 órdenes) tras cerrar la Fase 1 del CMMS, y toda la georreferenciación existente era
solo de Bogotá (Chapinero) pese a que ya había un modelo hidráulico demo de Cali sin zona ni
activos propios.

**`services/maintenance/seed_demo_cali_and_maintenance.py`** (nuevo, mismo patrón que
`seed_demo_assets.py`/`seed_demo_networks.py` — kept-as-source, todo por argumento DSN/tenant,
nunca fijo en código, deja los datos persistentes con etiqueta "ilustrativo"):

- **Segunda zona real en Cali** ("DMA Tres Cruces - San Fernando, ilustrativo") con las mismas
  coordenadas/`head_m` del modelo EPANET demo de Cali (para que "Generar modelo" también
  funcione ahí) — tanque+tubería+válvula conectados, y un balance real con NRW (17.1%) menor al
  de Bogotá (25%), para que el mapa muestre variedad real de colores, no un solo punto.
- **Un 4to activo real** (bomba de refuerzo en Bogotá, `out_of_service` a propósito) como
  disparador real de `asset_condition`.
- **Catálogos de Mantenimiento reales**: SLA por prioridad (72h/24h/8h/2h), 6 códigos de falla,
  3 cuadrillas.
- **6 órdenes reales en distintos estados** (usando los servicios reales para las validaciones,
  con timestamps ajustados después para dar antigüedad realista): 2 completadas con MTTR real
  (5.5h y 2h), 1 vencida de SLA real (emergencia sin atender hace 3 días), 1 en progreso, 1
  recién generada (para que el usuario pruebe el flujo completo en vivo desde cero).
- **2 planes de mantenimiento preventivo**: uno ya con una corrida completada (para que %
  cumplimiento PM tenga algo real que mostrar), otro TODAVÍA vencido a propósito, para que el
  usuario pueda darle clic a "Generar órdenes vencidas" en el Portal y ver una orden real
  aparecer en vivo.

**Corrido primero contra Postgres local** (validación completa, cero errores en la segunda
corrida — dos bugs reales encontrados y corregidos: `submit_balance` exige `date`, no texto; un
`UPDATE` con un placeholder de más), **luego contra producción real** (subido temporalmente a
`/opt/renfygrid/maintenance/` para que los imports relativos resolvieran contra los `.so` ya
desplegados, borrado inmediatamente después — política de portafolio, nunca fuente en el
servidor). **Verificado con un smoke test real contra producción** (login real del tenant demo):
`GET /maintenance/kpis` → 6 órdenes, MTTR 11.2h, backlog 3, 1 vencida, cumplimiento PM 100%;
`GET /dashboard/overview` → refleja el activo fuera de servicio y las 2 órdenes pendientes;
`GET /network-zones/geojson` → 2 zonas reales (Bogotá + Cali) en el mapa;
`GET /network-balances/summary` → NRW promedio 21%, ninguna zona excede su tope.

### HES de acueducto real y completo: 100 medidores, 6 meses, 4h de intervalo (2026-09-15)

**Motivo:** el usuario pidió enriquecer HES con datos suficientes para reflejar todo lo que
maneja un HES real: "al menos 100 medidores de acueducto (diferentes marcas) que entregan datos
cada 4 horas durante 6 meses. Al menos el 10% de los datos no llegaron o tienen valores
inconsistentes. El VEE procesa automáticamente el 90% de ese 10% y el resto pone un dato
sugerido pero requiere validación de usuario" — un escenario exacto, no solo "más datos".

**`services/hes-adapter-dlms/seed_demo_water_meters.py`** (nuevo, mismo patrón kept-as-source
que `seed_demo_data.py`): 100 medidores reales de 5 marcas de AMI de agua (Sensus, Badger Meter,
Neptune, Diehl Metering, Kamstrup — fabricantes reales, no inventados), canal propio
`volume_m3` (registro acumulado, mismo criterio que un registro DLMS de energía — nunca
resetea, el consumo real sale de la diferencia entre lecturas), 8 concentradores, ~1081
intervalos de 4h por medidor a lo largo de 6 meses (~108,100 intervalos totales).

**El 90%/9%/1% pedido, mapeado sobre las dos fallas reales que el motor VEE ya distingue** (no
una simulación aparte — el mismo split matemático que la arquitectura real):
- **9% del total (90% del 10% problemático) = intervalo NO LLEGA** — sin fila en `raw_reading`,
  hueco real. `vee_engine.detect_gaps` + `estimate_gap` (interpolación lineal, F16/F17) los
  rellena automáticamente — exactamente "el VEE procesa el 90% de ese 10% sin intervención".
- **1% del total (10% del 10% problemático) = intervalo LLEGA con valor inconsistente** — un
  valor de registro/comunicación absurdo (60-400x el valor real esperado), capturado por una
  regla `range` real (`vee_engine.validate_reading`) con un tope de sanidad configurado
  (`max=10000 m³`, nunca fijo en el motor — solo en los parámetros de esta regla demo). Queda
  `is_valid=false`, con un **valor sugerido calculado por la misma interpolación** puesto en
  `validation_notes` (ej. *"...-- valor sugerido por interpolación: 1185.50 m³ (pendiente de
  validación de un supervisor)"*) — el valor guardado sigue siendo el recibido tal cual, la
  corrección real la aplica un supervisor via el flujo de edición manual ya existente (F18).

**Escala real, sin simulación DLMS por lectura** (100 × 1081 vía el poller/simulador real
tardaría horas de I/O de socket por nada): se generó con las mismas funciones PURAS del motor
VEE real (`validate_reading`, `detect_gaps`, `estimate_gap`) e insertó en bloque. **Hallazgo real
en el camino**: `COPY FROM STDIN` de Postgres **no funciona contra una tabla con RLS activo**
para un rol no-superusuario ("FeatureNotSupported ... Use INSERT statements instead" — limitación
real de Postgres, no de este proyecto) — cambiado a `executemany` por lotes de 5000, ~2 minutos
para las ~206,000 filas totales (raw_reading + validated_reading + meter_event).

**Resultado real verificado** (`GET /vee/summary` contra producción): `exception_rate_pct: 1.1%`,
`fill_rate_pct: 9.0%` — calza con precisión con el 10%/90%/10% pedido. 6 excepciones antiguas
resueltas a mano de verdad (`manual_edit.edit_reading`, con 2 usuarios distintos, para que
"Edición manual" tenga historial real) dejando **1044 excepciones recientes genuinamente
pendientes** de validación — el escenario exacto pedido. Además, 1300 `meter_event` reales
(comunicación + 4 alarmas) sembrados solo en las últimas 48h (lo único que los paneles de 24h
de HES miran) — `comm_success_rate_24h: 91.8%`, no inventado ni en 0 ni en 100%.

**Hallazgo real de producto, no un bug de esta siembra**: con datos reales de 4 horas de
intervalo, `fleet_summary.reporting_pct` y el KPI "medidores caídos" de Vista general muestran
**0% reportando / 100% caídos** — porque `stale_after_seconds` tiene un **default fijo de 3600s
(1h) tanto en el backend (`observability.py`) como en el frontend (`api.ts`, nunca lo
sobreescribe)**, y ningún medidor de 4h en 4h puede estar "fresco" dentro de una ventana de 1h la
mayor parte del tiempo — la ventana de "caído" no fue pensada para una cadencia más lenta que
horaria (agua/gas vs. electricidad). **No es un problema de los datos de muestra: es un umbral
fijo real que no calza con una cadencia de reporte real más lenta** — mismo principio "cero
hardcode" que el resto del proyecto ya aplica en otros lados, aquí no se aplicó. **No corregido
en esta ronda** (fuera del alcance pedido -- "genera datos sample"), señalado al usuario para que
decida si se retoma.


## 2026-09-15 — Umbral de "caído" configurable, tipos de medidor y mapa por sector (registrado 2026-09-23)

Trabajo hecho y desplegado el 2026-09-15 que quedó sin comitear ni anotar aquí; se registra
al verificar que corre en producción (módulos `meter_geo` y `tenant_settings` compilados en
`/cdrs/renfygrid/portal-api/` con fecha 15-sep y migración 0020 aplicada en la BD `renfygrid`).

- **Cierra el hallazgo anterior**: `stale_after_seconds` deja de ser un default fijo de 3600 s;
  ahora es un ajuste por tenant (`tenant_settings.py`, editable en Configuración), leído por
  `observability.py`, `fleet_aggregation.py` y `dashboard.py`.
- **Migración 0020**: `meter_type` (`micro` = medidor de cliente, `macro` = macromedidor de
  sector) y geometría de zona.
- **`meter_geo.py`**: GeoJSON de medidores, resumen por sector, distribución de consumo y tasa de
  excepciones por marca; nuevas vistas en `Meters.tsx` y ajustes en Vista general.
- **`seed_demo_hydraulic_sectors.py`**: sectores hidráulicos ilustrativos (Cali) para el tenant demo.
- CI básico de Sprint 0 (`.github/workflows/tests.yml`) listo pero **sin subir a GitHub**: el token de este PC no tiene el permiso `workflow` (GitHub rechaza el push). Corre las 24 pruebas
  de `services/common` (verificadas en verde localmente el 2026-09-23).