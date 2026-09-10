# Ejecución — Matriz funcional y bitácora de sprints

**Última actualización:** 2026-09-10 · Documento vivo — se actualiza en cada avance real de
código, no por fecha. Complementa el Plan de sprints (`04-plan-sprints.md`).

---

## 1. Matriz funcional

34 funciones concretas derivadas del alcance (`01-planteamiento.md` §4) y del diseño
(`03-diseno.md`). Cada una mapeada al sprint donde se construye y a su estado real.

**Leyenda de estado:** ⚪ Planeado · 🟡 En progreso · 🟢 Hecho (con evidencia verificable)

### HES (Head End System)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F01 | Registro de medidores/concentradores | 0-1 | ⚪ |
| F02 | Adaptador de protocolo DLMS/COSEM (Gurux) | 1 | 🟡 |
| F03 | Lectura remota programada (polling) | 1 | 🟡 |
| F04 | Lectura remota bajo demanda | 8 | ⚪ |
| F05 | Recepción de eventos/alarmas del medidor | 1-2 | ⚪ |
| F06 | Mapeo OBIS configurable por marca/modelo (cacheado) | 2 | ⚪ |
| F07 | Envío de comandos SCR al medidor | 7 | ⚪ |
| F08 | Reintentos / cola ante caída de concentrador | 2 | ⚪ |
| F09 | Auditoría de comunicación con dispositivos | 9 | ⚪ |

### Almacenamiento

| # | Función | Sprint | Estado |
|---|---|---|---|
| F10 | Ingesta de lecturas crudas (hypertable Timescale) | 1 | 🟡 |
| F11 | Metadatos de medidor/ubicación/catastro | 0-1 | ⚪ |
| F12 | Retención histórica configurable por tenant | 10 | ⚪ |
| F13 | Respaldo y recuperación | 9 | ⚪ |

### VEE (Validación · Estimación · Edición)

| # | Función | Sprint | Estado |
|---|---|---|---|
| F14 | Validación de rangos (min/max configurable) | 3 | ⚪ |
| F15 | Validación de formato/coherencia/integridad | 3 | ⚪ |
| F16 | Detección de intervalos faltantes | 4 | ⚪ |
| F17 | Estimación (método configurable por tenant) | 4 | ⚪ |
| F18 | Edición manual auditada | 4 | ⚪ |
| F19 | Versionado de reglas VEE (trazabilidad) | 0, 3-4 | 🟡 |
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
**Estado:** 🟡 En progreso, iniciado 2026-09-10.

| Fecha | Avance | Función(es) | Evidencia |
|---|---|---|---|
| 2026-09-10 | **Verificación de librería**: `gurux-dlms`, `gurux-net` y `gurux-common` sí existen como paquetes Python reales en PyPI (investigación previa solo había encontrado bindings C#/Java/Delphi) — `gurux-dlms` 1.0.203, incluye `GXDLMSClient`/`GXDLMSServer`. Instalados sin problema (`pip install`) | F02 | `services/hes-adapter-dlms/requirements.txt` |
| 2026-09-10 | **Gap identificado y decisión de alcance explícita**: Gurux no publica un simulador/servidor DLMS de referencia en Python (solo ejemplos de cliente); su simulador oficial (`Gurux.DLMS.Simulator.Net`) requiere .NET SDK, no instalado en este entorno; tampoco hay hardware real disponible. Decisión: construir el adaptador cliente real (adaptado fielmente de `GXDLMSReader.py`, el ejemplo de referencia oficial de Gurux) y probar con pruebas unitarias sobre un cliente/medio simulados (`unittest.mock`) la lógica de orquestación (reintentos, secuencia de asociación) — no el protocolo DLMS en sí, que ya lo garantiza Gurux. **Queda pendiente, documentado como gap abierto**: verificación end-to-end contra un medidor o simulador real | F02 | Docstring de `dlms_session.py` (sección "ESTADO REAL") |
| 2026-09-10 | **Adaptador construido**: `dlms_session.py` (`DlmsSession` — asociación SNRM/UA+AARQ/AARE, lectura de atributo con reintentos y reensamblado de tramas, desconexión), `meter_reader.py` (`read_register`/`NormalizedReading` — normaliza una lectura COSEM a fila `raw_reading`), `reading_store.py` (`insert_raw_reading`, usa `tenant_scope`), `main.py` (CLI real, sin valores fijos — host/puerto/tenant/medidor/OBIS todo por argumento) | F02, F03, F10 | `services/hes-adapter-dlms/*.py` |
| 2026-09-10 | Bug corregido: nombre de clase equivocado (`GXReceiveParameters`, que no existe) — corregido a `ReceiveParameters` tras inspeccionar el paquete `gurux_common` instalado | F02 | `dlms_session.py` import corregido |
| 2026-09-10 | **10/10 pruebas unitarias pasando** — 7 sobre `dlms_session` (orquestación: sin datos, camino feliz sin ronda de recepción, una ronda completa, agotamiento de reintentos lanza `TimeoutError_`, se salta asociación de aplicación con `Authentication.NONE`, se salta SNRM cuando el cliente no lo requiere, lectura de atributo actualiza el valor) + 3 sobre `meter_reader` (normalización a fila, índice de atributo 2 por defecto, índice de atributo configurable) | F02, F03, F10 | `python -m unittest discover -s tests -v` → **Ran 10 tests in 0.867s / OK** |

**F02/F03/F10 en 🟡, no 🟢**: el código del adaptador es real (mismo protocolo SNRM/AARQ/framing
que el cliente de referencia oficial de Gurux, no una reimplementación propia) y está probado
a nivel de orquestación con dobles de prueba, pero la Definición de Hecho de estas funciones
(`04-plan-sprints.md`) exige conectar contra un medidor/simulador real — eso sigue sin
verificarse en este entorno (sin hardware, sin .NET para el simulador oficial de Gurux). Cerrar
este gap requiere una decisión del usuario: conseguir acceso a un medidor/simulador real, o
invertir tiempo en construir un simulador DLMS/COSEM propio en Python (no trivial — no hay
ninguno de referencia).

*(Esta tabla se sigue completando a medida que avanza el Sprint 1 real.)*
