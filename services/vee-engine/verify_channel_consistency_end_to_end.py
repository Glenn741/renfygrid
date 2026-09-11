"""Verificacion end-to-end real de F15 (coherencia entre canales, Sprint C11)
-- `docs/03-diseno.md` SS5 pedia "coherencia entre canales (activa/reactiva)",
diferido en Sprint 3 por falta de un medidor con mas de un canal mapeado.
Ya no: Sprint C10 dejo el editor de mapeo OBIS soportar varios canales por
marca/modelo.

Que prueba, en espanol llano:
  1. Un medidor real con 2 canales (`active_energy` de referencia,
     `reactive_energy` comparado), 3 instantes:
     - t0: activa=100, reactiva=60 (ratio 0.6, dentro de [0, 1.0]) -> valida.
     - t1: activa=100, reactiva=150 (ratio 1.5, fuera de [0, 1.0]) -> invalida,
       con `vee_rule_id` trazable a la regla de coherencia (no a una de rango).
     - t2: SOLO reactiva=60, sin lectura de activa en ese instante -> valida
       pero SIN evaluar la coherencia (no se adivina un ratio sin datos).
  2. Corre `run_vee_pass.py` una vez (el pipeline real, no una llamada
     directa a `validate_reading`) contra Postgres real.

Uso:
    python verify_channel_consistency_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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

REFERENCE_CHANNEL = "active_energy"
COMPARED_CHANNEL = "reactive_energy"
T0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Channel Consistency Sprint C11",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-C11-CONSIST', 'SER-C11-CONSIST', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'channel_consistency', %s, 100)",
                            (
                                tenant_id,
                                psycopg.types.json.Json(
                                    {
                                        "channel": COMPARED_CHANNEL,
                                        "reference_channel": REFERENCE_CHANNEL,
                                        "min_ratio": 0.0,
                                        "max_ratio": 1.0,
                                    }
                                ),
                            ),
                        )

                        rows = [
                            (REFERENCE_CHANNEL, T0, 100.0),
                            (COMPARED_CHANNEL, T0, 60.0),  # ratio 0.6 -> valida
                            (REFERENCE_CHANNEL, T0 + timedelta(minutes=15), 100.0),
                            (COMPARED_CHANNEL, T0 + timedelta(minutes=15), 150.0),  # ratio 1.5 -> invalida
                            (COMPARED_CHANNEL, T0 + timedelta(minutes=30), 60.0),  # sin activa en ese instante
                        ]
                        for channel, timestamp, value in rows:
                            cur.execute(
                                "INSERT INTO raw_reading (tenant_id, meter_id, channel, \"timestamp\", value) "
                                "VALUES (%s, %s, %s, %s, %s)",
                                (tenant_id, meter_id, channel, timestamp, value),
                            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "vee_rule.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                vee_pass_main(["--dsn", dsn, "--tenant-id", tenant_id, "--vee-rules-snapshot", str(snapshot_path), "--iterations", "1"])

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT \"timestamp\", is_valid, vee_rule_id, validation_notes FROM validated_reading "
                            "WHERE meter_id = %s AND channel = %s ORDER BY \"timestamp\"",
                            (meter_id, COMPARED_CHANNEL),
                        )
                        rows_out = cur.fetchall()

            print(f"reactive_energy tras el pase: {[(r[0].isoformat(), r[1], r[3]) for r in rows_out]}")
            ok = (
                len(rows_out) == 3
                and rows_out[0][1] is True and rows_out[0][2] is not None  # t0: valida, con regla trazable
                and rows_out[1][1] is False and rows_out[1][2] is not None  # t1: invalida, con regla trazable
                and "fuera de" in rows_out[1][3]
                and rows_out[2][1] is True and "no evaluada" in rows_out[2][3]  # t2: valida, sin evaluar
            )
            print("SPRINT C11 F15 E2E OK -- coherencia entre canales evaluada con datos reales" if ok else "SPRINT C11 F15 E2E FALLA")
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
