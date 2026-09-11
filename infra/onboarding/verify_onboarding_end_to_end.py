"""Verificacion end-to-end real de `onboard_tenant.py` -- corre el
manifiesto de ejemplo contra Postgres real y confirma que TODO quedo dado
de alta: tenant, medidor, gateway, mapeo OBIS, reglas VEE, regla de
anomalia de consumo, y niveles de aprobacion de control.

Uso:
    python verify_onboarding_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "common"))

import psycopg  # noqa: E402

from onboard_tenant import onboard_tenant  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def run(dsn: str) -> int:
    manifest = json.loads((Path(__file__).parent / "example_manifest.json").read_text(encoding="utf-8"))

    with psycopg.connect(dsn, autocommit=True) as conn:
        tenant_id = onboard_tenant(conn, manifest)
        print(f"Tenant dado de alta: {tenant_id}")

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM meter WHERE tenant_id = %s", (tenant_id,))
                        (meter_count,) = cur.fetchone()
                        cur.execute("SELECT count(*) FROM gateway WHERE tenant_id = %s", (tenant_id,))
                        (gateway_count,) = cur.fetchone()
                        cur.execute("SELECT count(*) FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
                        (protocol_count,) = cur.fetchone()
                        cur.execute("SELECT count(*) FROM vee_rule WHERE tenant_id = %s", (tenant_id,))
                        (vee_rule_count,) = cur.fetchone()
                        cur.execute("SELECT count(*) FROM consumption_anomaly_rule WHERE tenant_id = %s", (tenant_id,))
                        (anomaly_rule_count,) = cur.fetchone()
                        cur.execute("SELECT count(*) FROM control_approval_level WHERE tenant_id = %s", (tenant_id,))
                        (approval_level_count,) = cur.fetchone()
                        cur.execute("SELECT server_address FROM meter WHERE tenant_id = %s", (tenant_id,))
                        (server_address,) = cur.fetchone()

            print(f"medidores={meter_count} gateways={gateway_count} mapeos_obis={protocol_count} "
                  f"reglas_vee={vee_rule_count} reglas_anomalia={anomaly_rule_count} niveles_aprobacion={approval_level_count} "
                  f"server_address={server_address}")

            ok = (
                meter_count == 1 and gateway_count == 1 and protocol_count == 1
                and vee_rule_count == 2 and anomaly_rule_count == 1 and approval_level_count == 2
                and server_address == 1
            )
            print("ONBOARDING OK -- manifiesto completo dado de alta correctamente" if ok else "ONBOARDING FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM vee_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM consumption_anomaly_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM control_approval_level WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter_gateway WHERE meter_id IN (SELECT id FROM meter WHERE tenant_id = %s)", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM gateway WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
