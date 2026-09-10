# Ejecución — Matriz funcional y bitácora de sprints

**Última actualización:** 2026-09-10 (Sprint 3) · Documento vivo — se actualiza en cada avance real de
código, no por fecha. Complementa el Plan de sprints (`04-plan-sprints.md`).

---

## 1. Matriz funcional

34 funciones concretas derivadas del alcance (`01-planteamiento.md` §4) y del diseño
(`03-diseno.md`). Cada una mapeada al sprint donde se construye y a su estado real.

**Leyenda de estado:** ⚪ Planeado · 🟡 En progreso · 🟢 Hecho (con evidencia verificable)

### HES (Head End System)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F01 | Registro de medidores/concentradores | 0-1 | 🟢 |
| F02 | Adaptador de protocolo DLMS/COSEM (Gurux) | 1 | 🟢 |
| F03 | Lectura remota programada (polling) | 1 | 🟢 |
| F04 | Lectura remota bajo demanda | 8 | ⚪ |
| F05 | Recepción de eventos/alarmas del medidor | 1-2 | ⚪ (diferido a Sprint 2, ver bitácora) |
| F06 | Mapeo OBIS configurable por marca/modelo (cacheado) | 2 | 🟢 |
| F07 | Envío de comandos SCR al medidor | 7 | ⚪ |
| F08 | Reintentos / cola ante caída de concentrador | 2 | 🟡 (reintentos sí, cola persistente no — ver bitácora) |
| F09 | Auditoría de comunicación con dispositivos | 9 | ⚪ |

### Almacenamiento

| # | Función | Sprint | Estado |
|---|---|---|---|
| F10 | Ingesta de lecturas crudas (hypertable Timescale) | 1 | 🟡 |
| F11 | Metadatos de medidor/ubicación/catastro | 0-1 | 🟢 |
| F12 | Retención histórica configurable por tenant | 10 | ⚪ |
| F13 | Respaldo y recuperación | 9 | ⚪ |

### VEE (Validación · Estimación · Edición)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F14 | Validación de rangos (min/max configurable) | 3 | 🟢 |
| F15 | Validación de formato/coherencia/integridad | 3 | 🟡 (formato sí, coherencia entre canales diferida — ver bitácora) |
| F16 | Detección de intervalos faltantes | 4 | ⚪ |
| F17 | Estimación (método configurable por tenant) | 4 | ⚪ |
| F18 | Edición manual auditada | 4 | ⚪ |
| F19 | Versionado de reglas VEE (trazabilidad) | 0, 3-4 | 🟢 |
| F20 | Patrón de configuración cacheada (cero hardcode) | 0 | 🟢 |

### Gestión de Consumos

| # | Función | Sprint | Estado |
|---|---|---|---|
| F21 | Agregación de lecturas validadas en consumo | 5 | ⚪ |
| F22 | Reglas de crítica/desviación configurables | 5 | ⚪ |
| F23 | Órdenes de relectura/inspección | 5 | ⚪ |
| F24 | API de consulta de consumo por período | 5 | ⚪ |
| F25 | Preparación de datos para facturación (entrega a CIS) | 10 | ⚪ |

### Control (SCR)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F26 | Solicitud de orden de control | 6 | ⚪ |
| F27 | Flujo de aprobación configurable por tenant/tipo | 6 | ⚪ |
| F28 | Firma y validación de orden antes de ejecución | 6-7 | ⚪ |
| F29 | Ejecución vía adaptador HES | 7 | ⚪ |
| F30 | Confirmación de estado y auditoría inmutable | 7 | ⚪ |

### Transversal

| # | Función | Sprint | Estado |
|---|---|---|---|
| F31 | Multi-tenencia con Row-Level Security | 0 | 🟢 |
| F32 | Autenticación JWT y control de roles/permisos | 0 | 🟢 |
| F33 | Portal/API pública multi-tenant (RLS end-to-end) | 8 | ⚪ |
| F34 | Observabilidad (métricas de ingesta, alertas) | 9 | ⚪ |
| F46 | Clúster k3s bootstrapeado + primer servicio desplegado como pod | 0 | 🟢 |

### Balance de Red y Modelado de Red — Track B (agregado 2026-09-10)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F35 | `network_zone` jerárquica (DMA/circuito/distrito) | B1 | ⚪ |
| F36 | Endpoint de ingesta externa (venta modular sin HES propio) | B1 | ⚪ |
| F37 | Cálculo de balance Top-Down (IWA) | B2 | ⚪ |
| F38 | Cálculo de balance Bottom-Up (IWA) | B2 | ⚪ |
| F39 | Carga y versionado de modelo hidráulico (`.inp`) | B3 | ⚪ |
| F40 | Simulación vía WNTR | B3 | ⚪ |
| F41 | Calibración de modelo con datos de `network_balance` | B4 | ⚪ |
| F42 | `network_asset`/`asset_connectivity` (Gemelo Digital) + ingesta externa desde SIG | B5 | ⚪ |
| F43 | Derivar `network_model` desde el Gemelo Digital (export EPANET) | B6 | ⚪ |
| F44 | Generación de `maintenance_order` desde anomalías (condición/simulación/balance) | B7 | ⚪ |
| F45 | Integración con BayForce (envío de orden + webhook de cierre) | B7 | ⚪ |

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
entre tenants se confirma con `infra/db/verify_rls.py`, exit code 0. Pendiente real y
distinto: correr la migración contra la extensión **TimescaleDB** en sí (el `create_hypertable`
se omitió en esta verificación local por no estar disponible en el binario portable de
Windows — se confirma cuando haya Docker/k3s con la imagen oficial `timescale/timescaledb`,
que es la misma que ya usa `docker-compose.yml`).

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
