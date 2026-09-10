"""Deja datos de DEMO reales y persistentes en Postgres (no los borra al
terminar, a diferencia de los verify_*.py) -- para que el usuario pueda
abrir DBeaver y ver algo concreto: un tenant, un gateway, un medidor y
varias lecturas reales en raw_reading, generadas por el pipeline real
(simulador + poller), no filas insertadas a mano.

Uso: python seed_demo_data.py "postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid"
(con el rol superusuario, para poder insertar el tenant sin pelear con RLS
-- el resto de las tablas si se llenan dentro de tenant_scope, como en
producción).
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from obis_mapping import build_cache  # noqa: E402
from poller import main as poller_main  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from simulator.dlms_simulator_server import serve_in_background  # noqa: E402

HOST = "127.0.0.1"
PORT = 22999
OBIS_CODE = "1.0.1.8.0.255"
SIMULATED_VALUE = 458213  # Wh, valor plausible de un medidor real
BRAND = "demo-brand"
MODEL = "demo-model-1"


def run(dsn: str) -> None:
    serve_in_background(HOST, PORT, OBIS_CODE, SIMULATED_VALUE)
    time.sleep(0.3)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant (name, plan) VALUES (%s, %s) RETURNING id",
                ("RenfyGrid Demo", "pilot"),
            )
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        gateway_id = register_gateway(
            conn, tenant_id, "Concentrador Demo (simulador)", "TCP",
            {"host": HOST, "port": PORT, "client_address": 16},
        )
        meter_id = register_meter(
            conn, tenant_id, "ACC-DEMO-001", "SER-DEMO-001", BRAND, "DLMS_COSEM", model=MODEL,
            location={"city": "Bogotá", "note": "medidor de demostración, no real"},
        )
        link_meter_to_gateway(conn, tenant_id, meter_id, gateway_id, server_address=1)

        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) "
                        "VALUES (%s, %s, %s, 'DLMS_COSEM', %s)",
                        (
                            tenant_id, BRAND, MODEL,
                            psycopg.types.json.Json(
                                {"active_energy": {"obis_code": OBIS_CODE, "attribute_index": 2}}
                            ),
                        ),
                    )

        with tempfile.TemporaryDirectory() as tmp_dir:
            snapshot_path = Path(tmp_dir) / "obis_mapping.json"
            build_cache(snapshot_path, dsn, tenant_id).refresh()
            poller_main(
                [
                    "--dsn", dsn,
                    "--tenant-id", tenant_id,
                    "--obis-mapping-snapshot", str(snapshot_path),
                    "--interval-seconds", "1",
                    "--iterations", "3",
                ]
            )

    print(f"\nListo. tenant_id de demo: {tenant_id}")
    print("Estas filas NO se borran solas -- son para que las veas en DBeaver.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
