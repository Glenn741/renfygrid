"""Verificacion end-to-end real de F12 (retencion historica configurable
por tenant), Sprint 10 -- nada de mocks contra la BD.

Que prueba, en espanol llano:
  1. Tenant A configura `raw_reading_retention_days=30`. Tiene una lectura
     de hace 60 dias y una de hoy -- tras correr `run_retention`, la vieja
     desaparece y la de hoy sigue.
  2. Tenant B NO configura ninguna retencion. Tiene una lectura de hace
     3650 dias (10 años) -- tras correr `run_retention`, sigue intacta:
     sin configuracion explicita, nunca se borra nada (fail-safe).

Uso:
    python verify_retention_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from retention import run_retention  # noqa: E402


def run(dsn: str) -> int:
    now = datetime.now(timezone.utc)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant (name, config) VALUES (%s, %s) RETURNING id",
                ("E2E Retention A (configurado)", psycopg.types.json.Json({"raw_reading_retention_days": 30})),
            )
            (tenant_a_id,) = cur.fetchone()
            tenant_a_id = str(tenant_a_id)
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Retention B (sin configurar)",))
            (tenant_b_id,) = cur.fetchone()
            tenant_b_id = str(tenant_b_id)

        try:
            meter_ids = {}
            for tenant_id, label in ((tenant_a_id, "A"), (tenant_b_id, "B")):
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        with conn.cursor() as cur:
                            cur.execute(
                                "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                                "VALUES (%s, %s, %s, 'test-brand', 'DLMS_COSEM') RETURNING id",
                                (tenant_id, f"ACC-RET-{label}", f"SER-RET-{label}"),
                            )
                            meter_ids[tenant_id] = str(cur.fetchone()[0])

            with conn.transaction():
                with tenant_scope(conn, tenant_a_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', 1)",
                            (tenant_a_id, meter_ids[tenant_a_id], now - timedelta(days=60)),
                        )
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', 2)",
                            (tenant_a_id, meter_ids[tenant_a_id], now),
                        )
            with conn.transaction():
                with tenant_scope(conn, tenant_b_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', 3)",
                            (tenant_b_id, meter_ids[tenant_b_id], now - timedelta(days=3650)),
                        )

            results = run_retention(dsn)
            print(f"Resultado de run_retention: {results}")

            with conn.transaction():
                with tenant_scope(conn, tenant_a_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM raw_reading WHERE meter_id = %s", (meter_ids[tenant_a_id],))
                        (count_a,) = cur.fetchone()
            with conn.transaction():
                with tenant_scope(conn, tenant_b_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM raw_reading WHERE meter_id = %s", (meter_ids[tenant_b_id],))
                        (count_b,) = cur.fetchone()

            print(f"Tenant A (retencion 30d) tiene {count_a} lectura(s) (esperado: 1, solo la de hoy)")
            print(f"Tenant B (sin configurar) tiene {count_b} lectura(s) (esperado: 1, la de hace 10 años SIGUE)")

            ok = (
                tenant_a_id in results and results[tenant_a_id]["raw_reading"] == 1
                and count_a == 1 and count_b == 1
            )
            print("F12 OK -- retencion aplicada solo donde se configuro, fail-safe confirmado" if ok else "F12 FALLA")
            return 0 if ok else 1
        finally:
            for tenant_id in (tenant_a_id, tenant_b_id):
                with conn.transaction():
                    with tenant_scope(conn, tenant_id):
                        with conn.cursor() as cur:
                            cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                            cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
