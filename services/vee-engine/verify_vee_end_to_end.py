"""Verificacion end-to-end real del motor VEE (F14/F15/F19, Sprint 3) --
mismo espiritu que los verify_*.py de hes-adapter-dlms: nada de mocks para
la parte que toca BD real.

Crea un tenant+medidor de prueba, inserta 3 lecturas crudas a mano (una
dentro de rango, una por encima del maximo, una por debajo del minimo),
define una regla de rango real en `vee_rule`, refresca su cache, corre
`run_vee_pass.py` una vez, y confirma que `validated_reading` quedo con
exactamente 1 valida y 2 invalidas, cada una con `vee_rule_id` trazable.

Uso:
    python verify_vee_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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
from run_vee_pass import main as vee_pass_main  # noqa: E402
from vee_rules_cache import build_cache  # noqa: E402

CHANNEL = "active_energy"


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E VEE test",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-VEE', 'SER-VEE', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) "
                            "VALUES (%s, 'range', %s, 100)",
                            (tenant_id, psycopg.types.json.Json({"channel": CHANNEL, "min": 0, "max": 10000})),
                        )

                        now = datetime.now(timezone.utc)
                        readings = [
                            (now, 5000),               # dentro de rango
                            (now + timedelta(seconds=1), 99999),   # por encima del max
                            (now + timedelta(seconds=2), -50),     # por debajo del min
                        ]
                        for timestamp, value in readings:
                            cur.execute(
                                "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) "
                                "VALUES (%s, %s, %s, %s, %s)",
                                (tenant_id, meter_id, timestamp, CHANNEL, value),
                            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "vee_rule.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                vee_pass_main(
                    [
                        "--dsn", dsn,
                        "--tenant-id", tenant_id,
                        "--vee-rules-snapshot", str(snapshot_path),
                        "--iterations", "1",
                    ]
                )

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT is_valid, vee_rule_id IS NOT NULL, value FROM validated_reading "
                            "WHERE meter_id = %s ORDER BY \"timestamp\"",
                            (meter_id,),
                        )
                        rows = cur.fetchall()

            print(f"Filas en validated_reading: {rows}")
            valid_flags = [row[0] for row in rows]
            all_traced = all(row[1] for row in rows)
            ok = (
                len(rows) == 3
                and valid_flags == [True, False, False]
                and all_traced
            )
            print("E2E VEE OK -- 1 valida + 2 invalidas, todas con regla trazable" if ok else "E2E VEE FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM raw_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM vee_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
