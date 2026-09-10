# RenfyGrid

MDM/AMI para energía, agua y gas — portafolio [rensoftlabs.com](https://rensoftlabs.com).
Plan completo (planteamiento, arquitectura, diseño, sprints, benchmark de industria y
ejecución) en [`docs/`](docs/). Página del plan publicada en
[renfygrid.rensoftlabs.com](https://renfygrid.rensoftlabs.com).

## Estado

Sprint 0 en progreso — ver [`docs/05-ejecucion.md`](docs/05-ejecucion.md) para la matriz
funcional y la bitácora real (qué está probado vs. solo escrito).

## Estructura del repo

```
docs/                    Plan completo (las 4 fases + benchmark + ejecución)
site/                     Página estática del plan (desplegada en renfygrid.rensoftlabs.com)
services/
  common/                 Librería compartida entre microservicios
    renmeter_common/
      config_cache.py     Patrón "configuración cacheada" (cero hardcode) — probado, sin BD
      db.py               Contexto de tenant para RLS (SET LOCAL) — escrito, sin correr aún
    tests/                Pruebas reales, corren con `python -m unittest`
infra/
  db/
    migrations/0001_init.sql   Esquema inicial + RLS — escrito, sin correr aún
    verify_rls.py               Verificación de aislamiento entre tenants — escrito, sin correr aún
  k8s/
    README.md                   Plan de despliegue en k3s (servicios) — decisión tomada, sin ejecutar aún
docker-compose.yml        Solo Postgres+TimescaleDB y Redis (fuera del clúster k3s)
```

**Despliegue:** servicios de aplicación en **k3s** (Kubernetes liviano, desde el día 1 — ver
`docs/02-arquitectura-general.md` principio 4); Postgres/Redis fuera del clúster vía
`docker-compose.yml`. Ver `infra/k8s/README.md`.

## Cómo correr lo que ya está verificado (sin Docker ni Postgres)

```bash
cd services/common
python -m unittest tests.test_config_cache -v
```

## Cómo correr y verificar el esquema + RLS (ya verificado, sin Docker)

No hay Docker en esta máquina, así que se usó PostgreSQL portable (sin instalador, sin admin)
— ver `infra/db/README-local-dev.md` para arrancarlo/pararlo. Con la base arriba:

```powershell
pip install -r services/common/requirements.txt
psql -f infra/db/migrations/0001_init.sql   # esquema + RLS (FORCE incluido)
psql -f infra/db/migrations/0002_app_role.sql   # rol de aplicación, sin superusuario
python infra/db/verify_rls.py "postgresql://renfygrid_app:<password>@localhost:5455/renfygrid"
```

**Ya verificado** (2026-09-10, ver bitácora en `docs/05-ejecucion.md`): la primera corrida
encontró un bug real — RLS no aislaba nada porque el rol de conexión era superusuario. Corregido
(rol de aplicación + `FORCE ROW LEVEL SECURITY`), reverificado limpio desde cero.

**Pendiente real**: la extensión TimescaleDB en sí (el binario portable de Windows no la trae) —
se confirma cuando haya Docker/k3s con la imagen oficial que ya usa `docker-compose.yml`.
