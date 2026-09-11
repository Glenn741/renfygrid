"""Verificacion end-to-end real de F17 (Sprint C11): los dos metodos de
estimacion que quedaron pendientes desde Sprint 4 -- `customer_historical_average`
y `similar_customers_average` -- con datos reales insertados en Postgres,
por el mismo pipeline real (`run_vee_estimation.py`), sin mocks.

Que prueba, en espanol llano:
  1. **`customer_historical_average`** (canal `active_energy`, regla con
     `expected_interval_seconds=86400` -- un dia, para que "el mismo dia
     anterior" sea sencillo de construir): el propio medidor tiene lecturas
     reales a las 08:00 en 3 dias (dia0=100, dia1=120, dia3=140) con el
     dia2 08:00 faltante -- el pase de estimacion debe llenar ese hueco con
     el promedio de las OTRAS lecturas del MISMO medidor a esa hora
     ((100+120+140)/3 = 120), nunca interpolando entre los extremos del
     hueco (eso daria 130, no 120 -- confirma que de verdad usa el metodo
     pedido, no otro).
  2. **`similar_customers_average`** (canal `reactive_energy`): un segundo
     medidor del mismo tenant tiene una lectura real justo en el instante
     del hueco del primero (valor 500) -- el pase debe llenar el hueco del
     primer medidor con ese valor, usando la lectura de OTRO medidor, no
     historial propio (que aca ni siquiera se le da al primer medidor mas
     que los dos extremos del hueco).

Uso:
    python verify_estimation_methods_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from run_vee_estimation import main as estimation_main  # noqa: E402
from vee_rules_cache import build_cache  # noqa: E402

DAY = 86400
T0 = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E VEE Estimation Methods Sprint C11",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-C11-A', 'SER-C11-A', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_a,) = cur.fetchone()
                        meter_a = str(meter_a)
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-C11-B', 'SER-C11-B', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_b,) = cur.fetchone()
                        meter_b = str(meter_b)

                        # Regla 1: customer_historical_average sobre active_energy.
                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'missing_interval', %s, 100)",
                            (
                                tenant_id,
                                psycopg.types.json.Json(
                                    {
                                        "channel": "active_energy",
                                        "expected_interval_seconds": DAY,
                                        "tolerance_seconds": 60,
                                        "estimation_method": "customer_historical_average",
                                    }
                                ),
                            ),
                        )
                        # Regla 2: similar_customers_average sobre reactive_energy.
                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'missing_interval', %s, 100)",
                            (
                                tenant_id,
                                psycopg.types.json.Json(
                                    {
                                        "channel": "reactive_energy",
                                        "expected_interval_seconds": DAY,
                                        "tolerance_seconds": 60,
                                        "estimation_method": "similar_customers_average",
                                    }
                                ),
                            ),
                        )

                        # Meter A / active_energy: dia0, dia1, [dia2 falta], dia3 -- todas a las 08:00.
                        for offset_days, value in [(0, 100.0), (1, 120.0), (3, 140.0)]:
                            cur.execute(
                                "INSERT INTO validated_reading "
                                "(tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                                "VALUES (%s, %s, 'active_energy', %s, %s, 'real', true)",
                                (tenant_id, meter_a, T0 + timedelta(seconds=DAY * offset_days), value),
                            )

                        # Meter A / reactive_energy: solo los dos extremos del hueco (dia0, dia2) --
                        # a proposito sin historial propio a esa hora en ningun otro dia, para que
                        # la unica fuente posible del valor estimado sea meter_b.
                        for offset_days in (0, 2):
                            cur.execute(
                                "INSERT INTO validated_reading "
                                "(tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                                "VALUES (%s, %s, 'reactive_energy', %s, 10.0, 'real', true)",
                                (tenant_id, meter_a, T0 + timedelta(seconds=DAY * offset_days)),
                            )
                        # Meter B / reactive_energy: una lectura real justo en el instante del hueco (dia1).
                        cur.execute(
                            "INSERT INTO validated_reading "
                            "(tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                            "VALUES (%s, %s, 'reactive_energy', %s, 500.0, 'real', true)",
                            (tenant_id, meter_b, T0 + timedelta(seconds=DAY * 1)),
                        )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "vee_rule.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                estimation_main(["--dsn", dsn, "--tenant-id", tenant_id, "--vee-rules-snapshot", str(snapshot_path)])

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT \"timestamp\", value, source FROM validated_reading "
                            "WHERE meter_id = %s AND channel = 'active_energy' ORDER BY \"timestamp\"",
                            (meter_a,),
                        )
                        rows_a = cur.fetchall()
                        cur.execute(
                            "SELECT \"timestamp\", value, source FROM validated_reading "
                            "WHERE meter_id = %s AND channel = 'reactive_energy' ORDER BY \"timestamp\"",
                            (meter_a,),
                        )
                        rows_a_reactive = cur.fetchall()

            print(f"meter_a/active_energy tras estimacion: {[(r[0].isoformat(), float(r[1]), r[2]) for r in rows_a]}")
            estimated_a = [r for r in rows_a if r[2] == "estimated"]
            ok_historical = (
                len(estimated_a) == 1
                and abs(float(estimated_a[0][1]) - 120.0) < 0.01  # promedio (100+120+140)/3, NO interpolacion (130)
            )
            print("customer_historical_average OK -- hueco lleno con el promedio propio del medidor a esa hora" if ok_historical else "customer_historical_average FALLA")

            print(f"meter_a/reactive_energy tras estimacion: {[(r[0].isoformat(), float(r[1]), r[2]) for r in rows_a_reactive]}")
            estimated_a_reactive = [r for r in rows_a_reactive if r[2] == "estimated"]
            ok_similar = (
                len(estimated_a_reactive) == 1
                and abs(float(estimated_a_reactive[0][1]) - 500.0) < 0.01  # el valor de meter_b, no interpolacion (10)
            )
            print("similar_customers_average OK -- hueco lleno con la lectura de otro medidor" if ok_similar else "similar_customers_average FALLA")

            ok = ok_historical and ok_similar
            print("SPRINT C11 F17 E2E OK" if ok else "SPRINT C11 F17 E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM vee_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
