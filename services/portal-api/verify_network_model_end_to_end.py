"""Verificacion end-to-end real de Track B, Sprint B3 (Modelado Hidraulico,
`docs/07-track-b-alcance-funcional.md` SS5) -- por HTTP real (FastAPI
TestClient), Postgres real, WNTR real (motor EPANET 2.2, no un mock).

NOTA DE ENTORNO: requiere el paquete `wntr` instalado -- `wntr==1.2.0` es
la ultima version con wheel para Python 3.9 (ver
`services/network-model/requirements.txt`). En este portafolio, ese
paquete solo esta instalado en el venv de desarrollo dedicado
`~/renfygrid-network-model-dev` (WSL2) -- correr este script con ESE
interprete, no con el Python nativo de Windows del resto del repo.

Que prueba, en espanol llano:
  1. Registrar un modelo `.inp` real (deposito + 2 nudos + tanque, 3
     tuberias) -- version 1.
  2. Reenviar el MISMO nombre -> version 2 (versionado real, no
     sobrescritura); `GET /network-models` solo trae la ultima version.
  3. Simular el modelo real -> resultados reales de presion/caudal
     (mismos numeros que el unit test de `network_model_engine` ya
     verifico, ahora de punta a punta via HTTP+Postgres+WNTR).
  4. `GET /network-models/{id}/simulations` trae la corrida guardada.
  5. Registrar un `.inp` invalido -> 422, nunca se guarda un modelo roto.
  6. Simular un modelo que no existe -> 404.
  7. (Sprint B4, vinculo Modelo<->Balance) Un modelo vinculado a una zona
     CON balance real se calibra de verdad (`calibrate=true` usa
     `network_balance.real_losses` como insumo de calibracion, no un
     numero de ejemplo); un modelo sin vincular -> 422; un modelo
     vinculado a una zona SIN balance -> 422.

Uso:
    python verify_network_model_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "network-model"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-b3-secret"
ORDER_SIGNING_SECRET = "e2e-b3-order-secret"

FIXTURES = Path(__file__).resolve().parents[1] / "network-model" / "tests" / "fixtures"
VALID_INP = (FIXTURES / "valid_net.inp").read_text(encoding="utf-8")
INVALID_INP = (FIXTURES / "invalid_net.inp").read_text(encoding="utf-8")


def run(dsn: str) -> int:
    storage_dir = tempfile.mkdtemp(prefix="renfygrid_e2e_b3_")
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET
    os.environ["RENFYGRID_NETWORK_MODEL_STORAGE_DIR"] = storage_dir

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Network Model Sprint B3",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ing.red@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Registrar un modelo real -- version 1.
            create_resp = client.post(
                "/network-models", headers=headers,
                json={"name": "Red Centro", "inp_content": VALID_INP},
            )
            print(f"POST /network-models (v1): {create_resp.status_code}, {create_resp.json()}")
            ok_create = create_resp.status_code == 201 and create_resp.json()["version"] == 1
            model_id = create_resp.json()["model_id"]

            # 2. Reenviar el mismo nombre -> version 2, versionado real.
            resubmit_resp = client.post(
                "/network-models", headers=headers,
                json={"name": "Red Centro", "inp_content": VALID_INP},
            )
            print(f"POST /network-models (v2, mismo nombre): {resubmit_resp.status_code}, {resubmit_resp.json()}")
            ok_resubmit = resubmit_resp.status_code == 201 and resubmit_resp.json()["version"] == 2
            model_id_v2 = resubmit_resp.json()["model_id"]

            models = client.get("/network-models", headers=headers).json()
            print(f"GET /network-models (solo la ultima version): {models}")
            ok_latest_only = len(models) == 1 and models[0]["version"] == 2 and models[0]["model_id"] == model_id_v2

            # 3. Simular el modelo real (WNTR/EPANET) -- mismos numeros que el unit test.
            sim_resp = client.post(f"/network-models/{model_id_v2}/simulate", headers=headers, json={"scenario": "base"})
            print(f"POST /network-models/{{id}}/simulate: {sim_resp.status_code}, num_nodes={sim_resp.json().get('num_nodes')}")
            sim_body = sim_resp.json()
            ok_simulate = (
                sim_resp.status_code == 201
                and sim_body["num_nodes"] == 4
                and sim_body["num_links"] == 3
                and abs(sim_body["nodes"]["J1"]["min_pressure"] - 78.39) < 0.1
            )

            # 4. La corrida queda guardada.
            sims = client.get(f"/network-models/{model_id_v2}/simulations", headers=headers).json()
            print(f"GET /network-models/{{id}}/simulations: {len(sims)} corrida(s)")
            ok_sims_saved = len(sims) == 1 and sims[0]["scenario"] == "base"

            # 4b. (Modulo de georreferenciacion) GeoJSON real, enriquecido con la ultima simulacion.
            geojson = client.get(f"/network-models/{model_id_v2}/geojson", headers=headers).json()
            points = [f for f in geojson["features"] if f["geometry"]["type"] == "Point"]
            lines = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
            j1 = next((f for f in points if f["properties"]["id"] == "J1"), None)
            print(f"GET /network-models/{{id}}/geojson: {len(points)} puntos, {len(lines)} lineas")
            ok_geojson = (
                len(points) == 4 and len(lines) == 3
                and j1 is not None and "max_pressure" in j1["properties"]  # enriquecido con la corrida guardada
            )

            # 5. Un .inp invalido nunca se guarda.
            invalid_resp = client.post(
                "/network-models", headers=headers,
                json={"name": "Red Rota", "inp_content": INVALID_INP},
            )
            print(f"POST /network-models (inp invalido): {invalid_resp.status_code}")
            ok_invalid_rejected = invalid_resp.status_code == 422

            # 6. Simular un modelo inexistente -> 404.
            missing_resp = client.post(
                "/network-models/00000000-0000-0000-0000-000000000000/simulate", headers=headers, json={"scenario": "base"},
            )
            print(f"POST simulate a modelo inexistente: {missing_resp.status_code}")
            ok_missing_model = missing_resp.status_code == 404

            # 7. (B4) Vinculo Modelo<->Balance -- calibracion real con network_balance.real_losses.
            zone_id = client.post(
                "/network-zones", headers=headers,
                json={"name": "Zona para calibrar", "type": "dma", "data_source": "external"},
            ).json()["zone_id"]
            client.post(
                f"/network-zones/{zone_id}/balance", headers=headers,
                json={
                    "period_start": "2026-08-01", "period_end": "2026-08-02", "method": "top_down",
                    "system_input_volume": 10000, "billed_metered_consumption": 5000, "real_losses": 864,
                },
            )
            model_linked_id = client.post(
                "/network-models", headers=headers,
                json={"name": "Red Vinculada", "inp_content": VALID_INP, "zone_id": zone_id},
            ).json()["model_id"]

            calib_resp = client.post(
                f"/network-models/{model_linked_id}/simulate", headers=headers,
                json={"scenario": "calibrado", "calibrate": True},
            )
            calib_body = calib_resp.json()
            print(f"POST simulate (calibrate=true, con balance real): {calib_resp.status_code}, target_leak_lps={calib_body.get('target_leak_lps')}")
            ok_calibrated = (
                calib_resp.status_code == 201
                and calib_body.get("calibrated") is True
                and abs(calib_body.get("target_leak_lps", 0) - 10.0) < 0.1
                and "node_leak_lps" in calib_body
            )

            # Modelo sin vincular a ninguna zona -> 422 al pedir calibrar.
            unlinked_calib_resp = client.post(
                f"/network-models/{model_id_v2}/simulate", headers=headers,
                json={"scenario": "calibrado", "calibrate": True},
            )
            print(f"POST simulate (calibrate=true, modelo sin vincular): {unlinked_calib_resp.status_code}")
            ok_unlinked_rejected = unlinked_calib_resp.status_code == 422

            # Modelo vinculado a una zona SIN ningun balance -> 422 (nunca calibra con un numero de ejemplo).
            empty_zone_id = client.post(
                "/network-zones", headers=headers,
                json={"name": "Zona sin balance", "type": "dma", "data_source": "external"},
            ).json()["zone_id"]
            model_empty_zone_id = client.post(
                "/network-models", headers=headers,
                json={"name": "Red Vinculada Sin Balance", "inp_content": VALID_INP, "zone_id": empty_zone_id},
            ).json()["model_id"]
            no_balance_resp = client.post(
                f"/network-models/{model_empty_zone_id}/simulate", headers=headers,
                json={"scenario": "calibrado", "calibrate": True},
            )
            print(f"POST simulate (calibrate=true, zona sin balance): {no_balance_resp.status_code}")
            ok_no_balance_rejected = no_balance_resp.status_code == 422

            ok = (
                ok_create and ok_resubmit and ok_latest_only and ok_simulate
                and ok_sims_saved and ok_geojson and ok_invalid_rejected and ok_missing_model
                and ok_calibrated and ok_unlinked_rejected and ok_no_balance_rejected
            )
            print("SPRINT B3 NETWORK MODEL E2E OK" if ok else "SPRINT B3 NETWORK MODEL E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM simulation_result WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_model WHERE tenant_id = %s", (tenant_id,))  # antes de las zonas (FK zone_id)
                        cur.execute("DELETE FROM network_balance WHERE tenant_id = %s", (tenant_id,))
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
