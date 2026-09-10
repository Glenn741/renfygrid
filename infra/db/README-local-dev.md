# Base de datos local de desarrollo (esta máquina, sin Docker)

No hay Docker instalado en esta máquina (ver `docs/05-ejecucion.md`), así que en vez de
`docker-compose.yml` se usó el **binario portable de PostgreSQL** (EDB, sin instalador, sin
privilegios de administrador) para poder ejecutar y verificar de verdad la migración y el
aislamiento RLS, en lugar de dejarlos solo "escritos, sin correr".

Vive en `.devdb/` (raíz del repo, ignorado por git — son binarios + datos, no código).

## Arrancar / parar

```powershell
$pgHome = ".devdb\pgsql"
$pgData = ".devdb\pgdata"

# Arrancar (puerto 5455, no el 5432 default, para no chocar con otra instancia)
& "$pgHome\bin\pg_ctl.exe" -D $pgData -l ".devdb\pg.log" -o "-p 5455" start

# Parar
& "$pgHome\bin\pg_ctl.exe" -D $pgData stop -m fast
```

## Roles (ver el hallazgo real de RLS, `docs/05-ejecucion.md` bitácora 2026-09-10)

- `renfygrid` / `renfygrid_dev_only` — **superusuario** (rol de arranque de `initdb`). Se usó
  para crear el esquema y para tareas administrativas. **Nunca usarlo para conectar la
  aplicación** — los superusuarios de Postgres siempre se saltan RLS, sin importar las
  políticas.
- `renfygrid_app` / `renfygrid_app_dev_only` — rol de aplicación, sin privilegios de
  superusuario, es el que respeta RLS. **Es el rol que debe usar cualquier servicio real.**

## Verificar que RLS sigue funcionando

```powershell
python infra/db/verify_rls.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
```

## Cuándo esto deja de hacer falta

Cuando haya Docker/k3s reales disponibles (servidor o esta máquina), el flujo pasa a
`docker-compose.yml` (imagen oficial `timescale/timescaledb`, que sí trae la extensión
TimescaleDB — este binario portable de Windows no la tiene, por eso la migración se aplicó
aquí con `CREATE EXTENSION timescaledb` y `create_hypertable(...)` omitidos a propósito, ver
la bitácora). El esquema y las políticas RLS en sí ya están verificados igual — lo único que
falta correr contra el motor real es la parte de hypertables.
