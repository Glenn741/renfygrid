"""Verificacion end-to-end real de F21/F22/F23/F24 (Sprint 5) -- nada de
mocks contra la BD.

Que prueba, en espanol llano:
  1. Registra un medidor con un canal marcado `"billable": true` en
     `meter_protocol.obis_mapping`, e inserta lecturas validadas reales:
     una lectura antes del periodo 1 (apertura), una al final del periodo 1
     / inicio del periodo 2, y una al final del periodo 2.
  2. Corre el pase de consumo para el periodo 1 -- sin consumo previo, no
     puede haber anomalia.
  3. Corre el pase de consumo para el periodo 2 con una regla de desviacion
     estricta (10%) y un consumo deliberadamente muy distinto al del
     periodo 1 -- confirma que sale `anomaly_status='under_review'` y que
     se genera la orden (`meter_event`) trazable a esa fila de consumo.
  4. Usa `get_consumption` (F24) para confirmar que devuelve ambos periodos.

Uso:
    python verify_consumption_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from consumption_rules_cache import build_cache  # noqa: E402
from get_consumption import get_consumption  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from run_consumption_pass import main as consumption_pass_main  # noqa: E402

CHANNEL = "active_energy"
BRAND = "test-brand-s5"
MODEL = "test-model-s5"


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Consumption Sprint5",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, model, protocol) "
                            "VALUES (%s, 'ACC-S5', 'SER-S5', %s, %s, 'DLMS_COSEM') RETURNING id",
                            (tenant_id, BRAND, MODEL),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                            "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                            (
                                tenant_id, BRAND, MODEL,
                                psycopg.types.json.Json(
                                    {CHANNEL: {"obis_code": "1.0.1.8.0.255", "attribute_index": 2, "billable": True}}
                                ),
                            ),
                        )

                        cur.execute(
                            "INSERT INTO consumption_anomaly_rule (tenant_id, condition, action) "
                            "VALUES (%s, %s, 'reread_order')",
                            (tenant_id, psycopg.types.json.Json({"max_deviation_pct": 10})),
                        )

                        # apertura periodo 1: 1 sept; cierre periodo 1 / apertura periodo 2: 1 oct;
                        # cierre periodo 2: 1 nov -- consumo periodo 1 = 500, periodo 2 = 5000 (10x, anomalo)
                        readings = [
                            (datetime(2026, 8, 31, 23, 0, tzinfo=timezone.utc), 1000.0),
                            (datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc), 1500.0),
                            (datetime(2026, 10, 31, 23, 0, tzinfo=timezone.utc), 6500.0),
                        ]
                        for timestamp, value in readings:
                            cur.execute(
                                "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                                "VALUES (%s, %s, %s, %s, %s, 'real', true)",
                                (tenant_id, meter_id, CHANNEL, timestamp, value),
                            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "consumption_anomaly_rule.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()

                consumption_pass_main([
                    "--dsn", dsn, "--tenant-id", tenant_id,
                    "--period-start", "2026-09-01", "--period-end", "2026-10-01",
                    "--consumption-rules-snapshot", str(snapshot_path),
                ])
                consumption_pass_main([
                    "--dsn", dsn, "--tenant-id", tenant_id,
                    "--period-start", "2026-10-01", "--period-end", "2026-11-01",
                    "--consumption-rules-snapshot", str(snapshot_path),
                ])

            rows = get_consumption(conn, tenant_id, meter_id=meter_id)
            print(f"Consumo devuelto por get_consumption: {rows}")

            ok_values = (
                len(rows) == 2
                and rows[0]["value"] == 500.0 and rows[0]["anomaly_status"] == "ok"
                and rows[1]["value"] == 5000.0 and rows[1]["anomaly_status"] == "under_review"
            )
            print("F21/F22/F24 OK -- consumo correcto en ambos periodos, segundo marcado anomalo" if ok_values else "F21/F22/F24 FALLA")

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT me.type, c.value FROM meter_event me "
                            "JOIN consumption c ON c.id = me.consumption_id "
                            "WHERE me.tenant_id = %s",
                            (tenant_id,),
                        )
                        event_rows = cur.fetchall()
            ok_order = len(event_rows) == 1 and event_rows[0][0] == "reread_order" and float(event_rows[0][1]) == 5000.0
            print(f"Orden generada (meter_event trazable a consumption): {event_rows}")
            print("F23 OK -- orden de relectura generada y trazable al consumo anomalo" if ok_order else "F23 FALLA")

            return 0 if (ok_values and ok_order) else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter_event WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM consumption WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM consumption_anomaly_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
