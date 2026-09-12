"""Siembra 3 activos reales (tanque + tuberia + valvula, conectados) en el
tenant de demostracion persistente, georreferenciados sobre las mismas
coordenadas del modelo hidraulico de demostracion de Chapinero (Bogota,
Sprint B3) y vinculados a la misma zona demo de Balance de Red (Sprint
B1) -- para que el panel de Gemelo Digital tenga algo real que mostrar,
coherente con el resto de los modulos de demostracion.

Mismo patron que `hes-adapter-dlms/seed_demo_data.py` y
`network-model/seed_demo_networks.py`: todo por argumento (DSN/tenant),
nunca fijo en codigo; idempotente en el sentido de que un modelo
reejecutado agrega activos nuevos, no falla (no hay una identidad natural
para deduplicar un activo fisico sin un codigo externo de SIG).

Uso:
    python seed_demo_assets.py "<DSN>" "<TENANT_ID>" "<ZONE_NAME>"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from asset_service import connect_assets, register_asset  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def run(dsn: str, tenant_id: str, zone_name: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM network_zone WHERE tenant_id = %s AND name = %s",
                        (tenant_id, zone_name),
                    )
                    row = cur.fetchone()
        if row is None:
            print(f"No existe la zona {zone_name!r} para este tenant -- registrala primero (Sprint B1)")
            return 1
        zone_id = str(row[0])
        print("zone_id", zone_id)

        tank = register_asset(
            conn, tenant_id, "tank", zone_id=zone_id,
            attributes={"notes": "Tanque elevado (ilustrativo, mismas coordenadas del modelo R1)", "capacity_m3": 500},
            geometry={"type": "Point", "coordinates": [-74.0464, 4.6572]},
        )
        print("tank", tank)

        pipe = register_asset(
            conn, tenant_id, "pipe", zone_id=zone_id,
            attributes={"notes": "Tuberia troncal (ilustrativo)", "material": "PVC", "diameter_mm": 250},
            geometry={"type": "Point", "coordinates": [-74.0530, 4.6540]},
        )
        print("pipe", pipe)

        valve = register_asset(
            conn, tenant_id, "valve", zone_id=zone_id,
            attributes={"notes": "Valvula de seccionamiento (ilustrativo)"},
            geometry={"type": "Point", "coordinates": [-74.0570, 4.6510]},
        )
        print("valve", valve)

        c1 = connect_assets(conn, tenant_id, tank["asset_id"], pipe["asset_id"], "flows_into")
        c2 = connect_assets(conn, tenant_id, pipe["asset_id"], valve["asset_id"], "flows_into")
        print("connections", c1, c2)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2], sys.argv[3]))
