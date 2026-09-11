"""Verificacion end-to-end real de Track B, Sprint B1 (Balance de Red,
`docs/07-track-b-alcance-funcional.md`) -- por HTTP real (FastAPI
TestClient), Postgres real, sin ningun medidor RenfyGrid de por medio
(venta modular, `01-planteamiento.md` SS3).

Que prueba, en espanol llano:
  1. Una zona SIN insumos de infraestructura (Lm/Nc/P) recibe un balance
     real via API -- NRW se calcula, ILI queda en `None` (nunca inventado
     sin insumos).
  2. Una zona CON insumos reales recibe un balance real -- NRW e ILI se
     calculan correcto (mismos numeros que el motor puro ya verifico por
     unit test, ahora de punta a punta via HTTP+Postgres).
  3. Reenviar un balance para la MISMA zona/periodo sube de version (2) --
     `GET /network-balances` devuelve solo la version mas reciente, el
     historial queda en BD pero no duplica la vista.
  4. Enviar un balance a una zona que no existe -> 404, no un 500 ni un
     "exito" fabricado.

Uso:
    python verify_network_balance_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-b1-secret"
ORDER_SIGNING_SECRET = "e2e-b1-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Network Balance Sprint B1",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ing.red@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Zona sin insumos de infraestructura.
            zone_no_infra = client.post(
                "/network-zones", headers=headers,
                json={"name": "DMA sin infra", "type": "dma", "data_source": "external"},
            ).json()["zone_id"]

            balance_no_infra = client.post(
                f"/network-zones/{zone_no_infra}/balance", headers=headers,
                json={
                    "period_start": "2026-08-01", "period_end": "2026-09-01", "method": "top_down",
                    "system_input_volume": 10000, "billed_metered_consumption": 8000,
                    "apparent_losses": 300, "real_losses": 700,
                },
            )
            print(f"POST balance (sin infra): {balance_no_infra.status_code}, {balance_no_infra.json()}")
            ok_no_infra = (
                balance_no_infra.status_code == 201
                and balance_no_infra.json()["nrw"] == 2000.0
                and balance_no_infra.json()["ili"] is None
            )

            # 2. Zona con insumos reales -- mismos numeros ya verificados por unit test.
            zone_with_infra = client.post(
                "/network-zones", headers=headers,
                json={
                    "name": "DMA con infra", "type": "dma", "data_source": "external",
                    "network_length_km": 100, "num_connections": 5000, "avg_pressure_mca": 40,
                },
            ).json()["zone_id"]

            balance_with_infra = client.post(
                f"/network-zones/{zone_with_infra}/balance", headers=headers,
                json={
                    "period_start": "2026-08-01", "period_end": "2026-08-31", "method": "top_down",
                    "system_input_volume": 10000, "billed_metered_consumption": 3000,
                    "real_losses": 6960,  # 30 dias * 232000 L/dia (UARL de esta zona) / 1000 = 6960 m3 -> ILI = 1.0
                },
            )
            print(f"POST balance (con infra): {balance_with_infra.status_code}, {balance_with_infra.json()}")
            ok_with_infra = (
                balance_with_infra.status_code == 201
                and balance_with_infra.json()["nrw"] == 7000.0
                and abs(balance_with_infra.json()["ili"] - 1.0) < 0.01
            )

            # 3. Reenviar el mismo periodo -> version 2, la lista solo trae la ultima.
            resubmit = client.post(
                f"/network-zones/{zone_with_infra}/balance", headers=headers,
                json={
                    "period_start": "2026-08-01", "period_end": "2026-08-31", "method": "bottom_up",
                    "system_input_volume": 10500, "billed_metered_consumption": 3200, "real_losses": 6900,
                },
            ).json()
            print(f"Reenvio del mismo periodo: {resubmit}")
            ok_version = resubmit["version"] == 2

            balances = client.get(f"/network-balances?zone_id={zone_with_infra}", headers=headers).json()
            print(f"GET /network-balances (solo la ultima version): {balances}")
            ok_latest_only = len(balances) == 1 and balances[0]["version"] == 2 and balances[0]["method"] == "bottom_up"

            # 4. Zona inexistente -> 404.
            missing_zone_resp = client.post(
                "/network-zones/00000000-0000-0000-0000-000000000000/balance", headers=headers,
                json={"period_start": "2026-08-01", "period_end": "2026-09-01", "method": "top_down", "system_input_volume": 100},
            )
            print(f"POST balance a zona inexistente: {missing_zone_resp.status_code}")
            ok_missing_zone = missing_zone_resp.status_code == 404

            zones = client.get("/network-zones", headers=headers).json()
            print(f"GET /network-zones: {[z['name'] for z in zones]}")
            ok_zones_list = len(zones) == 2

            ok = ok_no_infra and ok_with_infra and ok_version and ok_latest_only and ok_missing_zone and ok_zones_list
            print("SPRINT B1 NETWORK BALANCE E2E OK" if ok else "SPRINT B1 NETWORK BALANCE E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM network_balance WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_zone WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
