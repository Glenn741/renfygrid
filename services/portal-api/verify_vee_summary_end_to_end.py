"""Verificacion end-to-end real del panel de VEE por etapa (Sprint C11-3,
sobre el feedback del usuario: "cada letra V.E.E. implica un nivel de
procesamiento y deberian haber estadisticas y KPIs en esos niveles" -- no
un resumen plano). F14-F19 estaban construidos desde Sprint 3-4/C11; el
gap era 100% de exposicion.

Que prueba, en espanol llano, con datos reales (2 excepciones, 1 estimada,
1 edicion real via `manual_edit.edit_reading` -- no un insert a mano que
se saltaria la auditoria):
  1. `GET /vee/summary` (validation/estimation/editing):
     - validation: `total_processed=2`, `invalid_total=2`,
       `exception_rate_pct=100.0`, `invalid_by_type` distingue range de
       channel_consistency, `active_rules_total=2`, `trend_7d` trae hoy.
     - estimation: `total_estimated=1`, `estimated_24h=1`,
       `fill_rate_pct≈33.3`, `by_method` = linear_interpolation, reglas=1.
     - editing: `total_edits=1`, `edits_24h=1`, `top_editors` trae al
       editor real (no un texto libre sin auditoria).
  2. `GET /vee/estimated-readings` y `GET /vee/edits`: cada uno trae la
     fila real esperada.
  3. `GET /vee/invalid-readings`: cada fila trae `rule_type` correcto.

Uso:
    python verify_vee_summary_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vee-engine"))
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
    from manual_edit import edit_reading
    from renmeter_common.auth import create_token

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E VEE Summary Sprint C11-3",))
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
                        edit_target_ts = now - timedelta(minutes=30)
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
                        # Lectura real, VALIDA, que se va a editar de verdad (no un
                        # insert directo con source='edited' -- eso se saltaria la
                        # auditoria en validated_reading_edit).
                        cur.execute(
                            "INSERT INTO validated_reading (tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                            "VALUES (%s, %s, 'active_energy', %s, 5000, 'real', true)",
                            (tenant_id, meter_id, edit_target_ts),
                        )

            edit_reading(
                conn, tenant_id, meter_id, "active_energy", edit_target_ts,
                new_value=5555.0, user_name="operador@renfygrid.demo", justification="corregido tras inspeccion",
            )

            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ana@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            summary = client.get("/vee/summary", headers=headers).json()
            print(f"GET /vee/summary: {summary}")
            v, e, ed = summary["validation"], summary["estimation"], summary["editing"]
            ok_validation = (
                v["total_processed"] == 2 and v["invalid_total"] == 2 and v["exception_rate_pct"] == 100.0
                and v["invalid_by_type"].get("range") == 1 and v["invalid_by_type"].get("channel_consistency") == 1
                and v["active_rules_total"] == 2 and len(v["trend_7d"]) >= 1
            )
            ok_estimation = (
                e["total_estimated"] == 1 and e["estimated_24h"] == 1
                and abs(e["fill_rate_pct"] - 33.3) < 0.5
                and e["by_method"].get("linear_interpolation") == 1 and e["active_rules_total"] == 1
            )
            ok_editing = (
                ed["total_edits"] == 1 and ed["edits_24h"] == 1
                and any(row["user_name"] == "operador@renfygrid.demo" for row in ed["top_editors"])
            )

            estimated = client.get("/vee/estimated-readings", headers=headers).json()
            print(f"GET /vee/estimated-readings: {estimated}")
            ok_estimated_list = len(estimated) == 1 and estimated[0]["estimation_method"] == "linear_interpolation"

            edits = client.get("/vee/edits", headers=headers).json()
            print(f"GET /vee/edits: {edits}")
            ok_edits_list = (
                len(edits) == 1 and edits[0]["previous_value"] == 5000.0 and edits[0]["new_value"] == 5555.0
                and edits[0]["justification"] == "corregido tras inspeccion"
            )

            invalid = client.get("/vee/invalid-readings", headers=headers).json()
            print(f"GET /vee/invalid-readings: {invalid}")
            by_channel = {row["channel"]: row["rule_type"] for row in invalid}
            ok_invalid = by_channel.get("active_energy") == "range" and by_channel.get("reactive_energy") == "channel_consistency"

            ok = ok_validation and ok_estimation and ok_editing and ok_estimated_list and ok_edits_list and ok_invalid
            print("SPRINT C11-3 VEE PANEL E2E OK" if ok else "SPRINT C11-3 VEE PANEL E2E FALLA")
            return 0 if ok else 1
        finally:
            with psycopg.connect("postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid", autocommit=True) as admin_conn:
                with tenant_scope(admin_conn, tenant_id):
                    with admin_conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading_edit WHERE tenant_id = %s", (tenant_id,))
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
