"""Verificacion end-to-end real de F10 (particionado nativo de `raw_reading`,
Sprint C11, migracion 0011) -- sin mocks, contra Postgres real.

Que prueba, en espanol llano:
  1. Dos tenants reales, cada uno con una fila real insertada en el mes
     actual, leidos con el rol de APLICACION (`renfygrid_app`, el mismo que
     usa el Portal/poller real -- nunca el admin, que se salta RLS siempre
     sin importar las politicas, bug ya documentado en este proyecto desde
     Sprint 0): confirma que RLS SIGUE aislando de verdad a traves de la
     tabla particionada (tenant B no ve la fila de tenant A).
  2. Cada fila real cae en la particion mensual que le corresponde
     (`tableoid::regclass`), no en la particion DEFAULT -- confirma que el
     particionado esta funcionando de verdad, no solo declarado.
  3. `partition_maintenance.ensure_partitions()` (rol ADMIN, DDL real):
     asegura la particion de un mes futuro que todavia no existia, y una
     fila insertada ahi (simulando una lectura de dentro de unos meses) cae
     en esa particion nueva, no en DEFAULT.

Uso:
    python verify_partitioning_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from renmeter_common.partition_maintenance import ensure_partitions  # noqa: E402

ADMIN_DSN = "postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid"


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn, psycopg.connect(ADMIN_DSN, autocommit=True) as admin_conn:
        with admin_conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Partitioning A Sprint C11",))
            (tenant_a,) = cur.fetchone()
            tenant_a = str(tenant_a)
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Partitioning B Sprint C11",))
            (tenant_b,) = cur.fetchone()
            tenant_b = str(tenant_b)

        try:
            meter_a = _register_meter(conn, tenant_a, "ACC-C11-PART-A")
            meter_b = _register_meter(conn, tenant_b, "ACC-C11-PART-B")

            now = datetime.now(timezone.utc)
            _insert_reading(conn, tenant_a, meter_a, now)
            _insert_reading(conn, tenant_b, meter_b, now)

            # 1. RLS a traves de la tabla particionada -- con el rol de
            #    APLICACION, nunca el admin (se saltaria RLS siempre).
            with conn.transaction():
                with tenant_scope(conn, tenant_a):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM raw_reading WHERE meter_id = %s", (meter_b,))
                        (visible_from_a,) = cur.fetchone()
            ok_rls = visible_from_a == 0
            print(f"Tenant A ve {visible_from_a} fila(s) del medidor de tenant B (esperado: 0)")

            # 2. La fila real cayo en la particion del mes, no en DEFAULT
            #    (tableoid es visible con el rol de aplicacion tambien).
            with conn.transaction():
                with tenant_scope(conn, tenant_a):
                    with conn.cursor() as cur:
                        cur.execute("SELECT tableoid::regclass::text FROM raw_reading WHERE meter_id = %s", (meter_a,))
                        (partition_name,) = cur.fetchone()
            expected_partition = f"raw_reading_y{now.year:04d}_m{now.month:02d}"
            ok_partition = partition_name == expected_partition
            print(f"Fila real cayo en la particion: {partition_name} (esperado: {expected_partition})")

            # 3. Mantenimiento (DDL real, rol admin): asegurar una particion
            #    futura y confirmar que una fila de esa fecha cae ahi.
            future = now + timedelta(days=200)  # unos 6-7 meses adelante
            months_ahead = max(1, (future.year - now.year) * 12 + (future.month - now.month))
            created = ensure_partitions(admin_conn, months_ahead=months_ahead, reference_date=now.date())
            expected_future_partition = f"raw_reading_y{future.year:04d}_m{future.month:02d}"
            ok_created = expected_future_partition in created
            print(f"Particiones aseguradas: {created}")

            _insert_reading(conn, tenant_a, meter_a, future)
            with conn.transaction():
                with tenant_scope(conn, tenant_a):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT tableoid::regclass::text FROM raw_reading WHERE meter_id = %s AND \"timestamp\" = %s",
                            (meter_a, future),
                        )
                        (future_partition,) = cur.fetchone()
            ok_future = future_partition == expected_future_partition
            print(f"Fila futura cayo en: {future_partition} (esperado: {expected_future_partition})")

            ok = ok_rls and ok_partition and ok_created and ok_future
            print("SPRINT C11 F10 E2E OK -- particionado real + RLS a traves de el + mantenimiento" if ok else "SPRINT C11 F10 E2E FALLA")
            return 0 if ok else 1
        finally:
            for tenant_id in (tenant_a, tenant_b):
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
                with admin_conn.cursor() as cur:
                    cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


def _register_meter(conn: psycopg.Connection, tenant_id: str, account_number: str) -> str:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                    "VALUES (%s, %s, %s, 'test-brand', 'DLMS_COSEM') RETURNING id",
                    (tenant_id, account_number, account_number),
                )
                (meter_id,) = cur.fetchone()
                return str(meter_id)


def _insert_reading(conn: psycopg.Connection, tenant_id: str, meter_id: str, timestamp: datetime) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO raw_reading (tenant_id, meter_id, channel, \"timestamp\", value) "
                    "VALUES (%s, %s, 'active_energy', %s, 100)",
                    (tenant_id, meter_id, timestamp),
                )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
