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
| F08 | Reintentos / cola ante caída de concentrador | 2 | 🟡 (reintentos sí, cola persistente no — ver bitácora) |
| F09 | Auditoría de comunicación con dispositivos | 9 | 🟢 |

### Almacenamiento

| # | Función | Sprint | Estado |
|---|---|---|---|
| F10 | Ingesta de lecturas crudas (hypertable Timescale) | 1 | 🟡 |
| F11 | Metadatos de medidor/ubicación/catastro | 0-1 | 🟢 |
| F12 | Retención histórica configurable por tenant | 10 | 🟢 |
| F13 | Respaldo y recuperación | 9 | 🟢 |

### VEE (Validación · Estimación · Edición)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F14 | Validación de rangos (min/max configurable) | 3 | 🟢 |
| F15 | Validación de formato/coherencia/integridad | 3 | 🟡 (formato sí, coherencia entre canales diferida — ver bitácora) |
| F16 | Detección de intervalos faltantes | 4 | 🟢 |
| F17 | Estimación (método configurable por tenant) | 4 | 🟡 (solo `linear_interpolation` — ver bitácora) |
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

**Pendiente real para C6** (la pantalla): el endpoint ya existe y está probado, pero el Portal
Web todavía no tiene la pantalla "Integraciones (CIS)" — sigue siendo el mockup aprobado por el
usuario, no código React real todavía.

### Sprint C6 — Pantalla real Integraciones (CIS) (2026-09-11)

**Objetivo:** construir la pantalla sobre el endpoint de C5 (mockup ya aprobado por el usuario).
**Estado:** 🟢 cerrado y desplegado a producción.

| Fecha | Avance | Evidencia |
|---|---|---|
| 2026-09-11 | **`Integrations.tsx` construida**: 3 tarjetas resumen (total/automáticas/manuales), filtro por modo, tabla con hora/tipo/cuenta/origen/modo/estado (colores por origen y modo), nota con enlace real a Configuración → Niveles de aprobación de control | `services/portal-web/src/pages/Integrations.tsx` |
| 2026-09-11 | Ruta `/integrations` + link desde Vista general | `App.tsx`, `Overview.tsx` |
| 2026-09-11 | `npm run build` limpio, desplegado a producción — verificado en vivo: la ruta resuelve, y el bundle real contiene la pantalla y la llamada al endpoint | `curl https://renfygrid.rensoftlabs.com/integrations` → 200; bundle contiene "Integraciones (CIS)"/"service-orders" |

Commit `e20f04b`. Sigue **C7-C8** (HES/Ingesta: flota por marca + capa de agregación).
