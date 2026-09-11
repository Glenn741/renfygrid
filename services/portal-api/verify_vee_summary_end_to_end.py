"""Verificacion end-to-end real del panel completo de VEE (Sprint C11-2):
el usuario reporto que "el panel de VEE se ve sin empezar" -- F14-F19
estaban construidos y verificados desde Sprint 3-4, pero la pantalla solo
mostraba la cola de excepciones, sin resumen ni lecturas estimadas visibles.

Que prueba, en espanol llano:
  1. `GET /vee/summary`: con 2 reglas activas distintas (range,
     channel_consistency) + 1 invalida por cada una + 1 estimada + 1
     editada reales insertadas -- confirma `invalid_pending=2`,
     `invalid_by_type` distingue range de channel_consistency,
     `estimated_24h=1`, `edited_24h=1`, `active_rules_total=2`.
  2. `GET /vee/estimated-readings`: la lectura estimada aparece con el
     `estimation_method` real de la regla que la genero.
  3. `GET /vee/invalid-readings`: cada fila trae `rule_type` -- distingue
     cual fue invalidada por rango y cual por coherencia entre canales.

Uso:
    python verify_vee_summary_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-vee-summary-secret"
ORDER_SIGNING_SECRET = "e2e-vee-summary-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient
    from renmeter_common.auth import create_token

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E VEE Summary Sprint C11-2",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-VEESUM', 'SER-VEESUM', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'range', %s, 100) RETURNING id",
                            (tenant_id, psycopg.types.json.Json({"channel": "active_energy", "min": 0, "max": 10000})),
                        )
                        (range_rule_id,) = cur.fetchone()

                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'channel_consistency', %s, 100) RETURNING id",
                            (
                                tenant_id,
                                psycopg.types.json.Json(
                                    {"channel": "reactive_energy", "reference_channel": "active_energy", "min_ratio": 0.0, "max_ratio": 1.0}
                                ),
                            ),
                        )
                        (consistency_rule_id,) = cur.fetchone()

                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'missing_interval', %s, 100) RETURNING id",
                            (
                                tenant_id,
                                psycopg.types.json.Json(
                                    {"channel": "active_energy", "expected_interval_seconds": 900, "estimation_method": "linear_interpolation"}
                                ),
                            ),
                        )
                        (interval_rule_id,) = cur.fetchone()

                        now = datetime.now(timezone.utc)
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, vee_rule_id, is_valid, validation_notes) "
                            "VALUES (%s, %s, 'active_energy', %s, 99999, 'real', %s, false, '99999 > max configurado (10000)')",
                            (tenant_id, meter_id, now, range_rule_id),
                        )
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, vee_rule_id, is_valid, validation_notes) "
                            "VALUES (%s, %s, 'reactive_energy', %s, 150, 'real', %s, false, 'reactive_energy/active_energy = 1.5 fuera de [0.0, 1.0]')",
                            (tenant_id, meter_id, now, consistency_rule_id),
                        )
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, vee_rule_id, is_valid) "
                            "VALUES (%s, %s, 'active_energy', %s, 1250, 'estimated', %s, true)",
                            (tenant_id, meter_id, now + timedelta(minutes=15), interval_rule_id),
                        )
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid, user_name, justification) "
                            "VALUES (%s, %s, 'active_energy', %s, 5555, 'edited', true, 'operador@renfygrid.demo', 'corregido tras inspeccion')",
                            (tenant_id, meter_id, now - timedelta(minutes=30)),
                        )

            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ana@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            summary = client.get("/vee/summary", headers=headers).json()
            print(f"GET /vee/summary: {summary}")
            ok_summary = (
                summary["invalid_pending"] == 2
                and summary["invalid_by_type"].get("range") == 1
                and summary["invalid_by_type"].get("channel_consistency") == 1
                and summary["estimated_24h"] == 1
                and summary["edited_24h"] == 1
                and summary["active_rules_total"] == 3
            )

            estimated = client.get("/vee/estimated-readings", headers=headers).json()
            print(f"GET /vee/estimated-readings: {estimated}")
            ok_estimated = len(estimated) == 1 and estimated[0]["estimation_method"] == "linear_interpolation"

            invalid = client.get("/vee/invalid-readings", headers=headers).json()
            print(f"GET /vee/invalid-readings: {invalid}")
            by_channel = {row["channel"]: row["rule_type"] for row in invalid}
            ok_invalid = by_channel.get("active_energy") == "range" and by_channel.get("reactive_energy") == "channel_consistency"

            ok = ok_summary and ok_estimated and ok_invalid
            print("SPRINT C11-2 VEE PANEL E2E OK" if ok else "SPRINT C11-2 VEE PANEL E2E FALLA")
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
