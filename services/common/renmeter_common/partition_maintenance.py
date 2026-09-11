"""Mantenimiento de particiones de `raw_reading` (F10, Sprint C11) --
particionado declarativo nativo de Postgres por rango mensual de
`"timestamp"`, sustituto de la hypertable de TimescaleDB que nunca estuvo
disponible ni en desarrollo ni en produccion (ver migracion
`0011_raw_reading_partitioning.sql`).

Postgres, a diferencia de TimescaleDB, NO crea particiones nuevas solo:
hay una particion DEFAULT que atrapa cualquier fecha sin particion mensual
explicita (red de seguridad, nunca falla un INSERT), pero sin este job
corriendo periodicamente todo terminaria cayendo ahi -- perdiendo el
beneficio real de la poda de particiones. Mismo patron de job corto/aparte
que `refresh_obis_mapping_cache.py`: se corre por cron o al desplegar, nunca
dentro del hot path del poller.

Crear una particion es DDL (CREATE TABLE) -- necesita el rol ADMIN
(`renfygrid`, dueno del esquema), no `renfygrid_app` (que solo tiene
SELECT/INSERT/UPDATE/DELETE, ver `0002_app_role.sql`). El `--dsn` de este
job es siempre el admin, nunca el de la aplicacion.

Uso: NUNCA `python -m renmeter_common.partition_maintenance` contra el
`.so` compilado con Nuitka -- falla con "No code object available" (una
extension compilada no soporta el mecanismo `-m` de Python igual que un
`.py`). Usar el entry-point kept-as-source `run_partition_maintenance.py`
(mismo patron que `poller.py`/`main.py` de los otros servicios):
    python run_partition_maintenance.py --dsn "postgresql://renfygrid:...@host/renfygrid" --months-ahead 2
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import psycopg
from psycopg import sql


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def ensure_partitions(conn: psycopg.Connection, months_ahead: int = 2, reference_date: date | None = None) -> list[str]:
    """Crea (si falta) la particion del mes actual y las siguientes
    `months_ahead` -- idempotente (`IF NOT EXISTS`), se puede correr todos
    los dias sin problema. Devuelve los nombres de particion asegurados."""
    today = reference_date or date.today()
    created = []
    with conn.cursor() as cur:
        for offset in range(months_ahead + 1):
            month_start = _add_months(_month_start(today), offset)
            month_end = _add_months(month_start, 1)
            partition_name = f"raw_reading_y{month_start.year:04d}_m{month_start.month:02d}"
            # `PARTITION OF ... FOR VALUES FROM (...) TO (...)` es DDL -- Postgres
            # no acepta parametros bindeados ahi (solo literales), por eso se
            # compone con psycopg.sql en vez de %s -- las fechas son calculadas
            # por este mismo codigo, nunca vienen del usuario.
            cur.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {partition} PARTITION OF raw_reading "
                    "FOR VALUES FROM ({start}) TO ({end})"
                ).format(
                    partition=sql.Identifier(partition_name),
                    start=sql.Literal(month_start),
                    end=sql.Literal(month_end),
                )
            )
            created.append(partition_name)
    return created


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--months-ahead", type=int, default=2, help="cuantos meses futuros asegurar ademas del actual")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with psycopg.connect(args.dsn, autocommit=True) as conn:
        created = ensure_partitions(conn, args.months_ahead)
    print(f"OK: {len(created)} particion(es) de raw_reading aseguradas: {created}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
