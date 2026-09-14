"""Verificacion end-to-end real de Track B, Sprint B6 (generar un modelo
EPANET desde el Gemelo Digital, `docs/07-track-b-alcance-funcional.md`
SS5) -- por HTTP real (FastAPI TestClient), Postgres real, WNTR real.

Que prueba, en espanol llano:
  1. Registrar una zona real, un activo `tank` (con `head_m`), un activo
     `pipe` (con diametro/rugosidad) y un activo `valve`, conectados
     tank->pipe->valve, todos con geometria real (coordenadas reales de
     Cali, Cerro de las Tres Cruces -> centro, mismas del modelo de
     demostracion de Sprint B3).
  2. `POST /network-zones/{id}/generate-model` genera un `.inp` real desde
     ese grafo y lo registra -- version 1, vinculado a la zona (`zone_id`).
  3. El modelo generado SE SIMULA de verdad (mismo endpoint que un modelo
     cargado a mano) -- la presion resultante es exactamente
     Head - Elevacion (sin demanda), confirmando que el .inp generado es
     hidraulicamente correcto, no solo "que carga".
  4. Generar un modelo desde una zona SIN ningun activo `tank` -> 422
     (nunca un modelo fabricado sin fuente real).

Uso:
    python verify_generate_model_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-model"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-b6-secret"
ORDER_SIGNING_SECRET = "e2e-b6-order-secret"


def run(dsn: str) -> int:
    storage_dir = tempfile.mkdtemp(prefix="renfygrid_e2e_b6_")
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET
    os.environ["RENFYGRID_NETWORK_MODEL_STORAGE_DIR"] = storage_dir

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Generate Model Sprint B6",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "gemelo@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Zona + grafo real: tank -> pipe -> valve.
            zone_id = client.post(
                "/network-zones", headers=headers,
                json={"name": "DMA generada desde gemelo", "type": "dma", "data_source": "external"},
            ).json()["zone_id"]

            tank_id = client.post(
                "/network-assets", headers=headers,
                json={
                    "type": "tank", "zone_id": zone_id,
                    "attributes": {"head_m": 50},
                    "geometry": {"type": "Point", "coordinates": [-76.5469, 3.4673]},
                },
            ).json()["asset_id"]
            pipe_id = client.post(
                "/network-assets", headers=headers,
                json={"type": "pipe", "zone_id": zone_id, "attributes": {"diameter_mm": 200, "roughness": 130}},
            ).json()["asset_id"]
            valve_id = client.post(
                "/network-assets", headers=headers,
                json={
                    "type": "valve", "zone_id": zone_id,
                    "attributes": {"elevation_m": 5},
                    "geometry": {"type": "Point", "coordinates": [-76.53, 3.45]},
                },
            ).json()["asset_id"]
            client.post("/asset-connectivity", headers=headers, json={"source_asset_id": tank_id, "target_asset_id": pipe_id, "connection_type": "flows_into"})
            client.post("/asset-connectivity", headers=headers, json={"source_asset_id": pipe_id, "target_asset_id": valve_id, "connection_type": "flows_into"})

            # 2. Generar el modelo desde el gemelo.
            gen_resp = client.post(f"/network-zones/{zone_id}/generate-model", headers=headers, json={"name": "Modelo generado E2E"})
            print(f"POST /network-zones/{{id}}/generate-model: {gen_resp.status_code}, {gen_resp.json()}")
            ok_generate = gen_resp.status_code == 201 and gen_resp.json()["version"] == 1
            model_id = gen_resp.json()["model_id"]

            # El modelo queda vinculado a la zona de origen (mismo mecanismo de B4).
            models = client.get("/network-models", headers=headers).json()
            ok_linked = any(m["model_id"] == model_id and m["zone_id"] == zone_id for m in models)

            # 3. Simular el modelo generado -- presion exacta Head - Elevacion (sin demanda).
            sim_resp = client.post(f"/network-models/{model_id}/simulate", headers=headers, json={"scenario": "desde-gemelo"})
            sim_body = sim_resp.json()
            print(f"POST simulate (modelo generado): {sim_resp.status_code}, num_nodes={sim_body.get('num_nodes')}")
            pressures = [v["avg_pressure"] for v in sim_body.get("nodes", {}).values()]
            ok_simulate = (
                sim_resp.status_code == 201
                and sim_body.get("num_nodes") == 2
                and sim_body.get("num_links") == 1
                and any(abs(p - 45.0) < 0.1 for p in pressures)  # 50 (head) - 5 (elevacion) en el nudo valvula
            )

            # 4. Zona sin ningun activo tank -> 422.
            empty_zone_id = client.post(
                "/network-zones", headers=headers,
                json={"name": "Zona sin activos", "type": "dma", "data_source": "external"},
            ).json()["zone_id"]
            client.post(
                "/network-assets", headers=headers,
                json={"type": "valve", "zone_id": empty_zone_id, "geometry": {"type": "Point", "coordinates": [0, 0]}},
            )
            no_source_resp = client.post(f"/network-zones/{empty_zone_id}/generate-model", headers=headers, json={"name": "Sin fuente"})
            print(f"POST generate-model (zona sin tank): {no_source_resp.status_code}")
            ok_no_source_rejected = no_source_resp.status_code == 422

            ok = ok_generate and ok_linked and ok_simulate and ok_no_source_rejected
            print("SPRINT B6 GENERATE MODEL E2E OK" if ok else "SPRINT B6 GENERATE MODEL E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM simulation_result WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_model WHERE tenant_id = %s", (tenant_id,))
                        cur.execute(
                            "DELETE FROM asset_connectivity WHERE source_asset_id IN (SELECT id FROM network_asset WHERE tenant_id = %s) "
                            "OR target_asset_id IN (SELECT id FROM network_asset WHERE tenant_id = %s)",
                            (tenant_id, tenant_id),
                        )
                        cur.execute("DELETE FROM network_asset WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_zone WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
            import shutil
            shutil.rmtree(storage_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
