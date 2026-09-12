"""Verificacion end-to-end real de Track B, Sprint B5 (Gemelo Digital,
`docs/07-track-b-alcance-funcional.md` SS5) -- por HTTP real (FastAPI
TestClient), Postgres real.

Que prueba, en espanol llano:
  1. Registrar un activo real (una tuberia) -- tipo/estado validos.
  2. Un tipo de activo invalido -> 422, nunca se guarda "cualquier cosa".
  3. `GET /network-assets` lo lista; `GET /network-assets/{id}` trae el
     detalle CON conectividad (vacia todavia).
  4. Cambiar el estado de un activo sube `version` (mismo criterio de
     historial ligero que el resto del proyecto).
  5. Conectar dos activos reales -- `GET /network-assets/{id}` de
     cualquiera de los dos ya muestra la conexion.
  6. Conectar contra un activo que no existe -> 404.
  7. (Seguridad real, `asset_connectivity` no tiene RLS propio) Conectar
     un activo del tenant A con un activo de OTRO tenant -> 404 -- la
     verificacion explicita por `network_asset` (que si tiene RLS) es la
     UNICA proteccion real, se prueba que funciona de verdad.
  8. (Modulo de georreferenciacion) Dos activos CON geometria conectados
     entre si -> `GET /network-assets/geojson` trae 2 puntos + 1 linea;
     un activo SIN geometria no aparece.

Uso:
    python verify_digital_twin_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
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

JWT_SECRET = "e2e-b5-secret"
ORDER_SIGNING_SECRET = "e2e-b5-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Digital Twin Sprint B5",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Digital Twin B5 -- otro tenant",))
            (other_tenant_id,) = cur.fetchone()
            other_tenant_id = str(other_tenant_id)

        try:
            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "gemelo@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}
            other_token = create_token({"tenant_id": other_tenant_id, "role": "supervisor", "email": "otro@renfygrid.demo"}, JWT_SECRET)
            other_headers = {"Authorization": f"Bearer {other_token}"}

            # 1. Registrar un activo real.
            pipe_resp = client.post(
                "/network-assets", headers=headers,
                json={"type": "pipe", "attributes": {"material": "PVC", "diameter_mm": 150}},
            )
            print(f"POST /network-assets (pipe): {pipe_resp.status_code}, {pipe_resp.json()}")
            ok_create = pipe_resp.status_code == 201
            pipe_id = pipe_resp.json()["asset_id"]

            # 2. Tipo invalido -> 422.
            invalid_type_resp = client.post("/network-assets", headers=headers, json={"type": "dron"})
            print(f"POST /network-assets (tipo invalido): {invalid_type_resp.status_code}")
            ok_invalid_type = invalid_type_resp.status_code == 422

            # 3. Listar y detalle con conectividad vacia.
            assets = client.get("/network-assets", headers=headers).json()
            detail = client.get(f"/network-assets/{pipe_id}", headers=headers).json()
            print(f"GET /network-assets: {len(assets)} activo(s); detalle conectividad={detail['connectivity']}")
            ok_list_and_detail = len(assets) == 1 and detail["asset_id"] == pipe_id and detail["connectivity"] == []

            # 4. Cambiar estado sube version.
            status_resp = client.patch(f"/network-assets/{pipe_id}/status", headers=headers, json={"status": "maintenance"})
            print(f"PATCH status: {status_resp.status_code}, {status_resp.json()}")
            ok_status_update = status_resp.status_code == 200 and status_resp.json()["version"] == 2

            # 5. Conectar dos activos reales.
            valve_id = client.post("/network-assets", headers=headers, json={"type": "valve"}).json()["asset_id"]
            connect_resp = client.post(
                "/asset-connectivity", headers=headers,
                json={"source_asset_id": pipe_id, "target_asset_id": valve_id, "connection_type": "flows_into"},
            )
            print(f"POST /asset-connectivity: {connect_resp.status_code}")
            detail_after_connect = client.get(f"/network-assets/{valve_id}", headers=headers).json()
            print(f"GET /network-assets/{{valve}} conectividad: {detail_after_connect['connectivity']}")
            ok_connect = (
                connect_resp.status_code == 201
                and len(detail_after_connect["connectivity"]) == 1
                and detail_after_connect["connectivity"][0]["source_asset_id"] == pipe_id
            )

            # 6. Conectar contra un activo inexistente -> 404.
            missing_connect_resp = client.post(
                "/asset-connectivity", headers=headers,
                json={"source_asset_id": pipe_id, "target_asset_id": "00000000-0000-0000-0000-000000000000", "connection_type": "flows_into"},
            )
            print(f"POST /asset-connectivity (activo inexistente): {missing_connect_resp.status_code}")
            ok_missing_asset = missing_connect_resp.status_code == 404

            # 7. Seguridad real: activo de OTRO tenant -> 404 (asset_connectivity no tiene RLS propio).
            other_asset_id = client.post("/network-assets", headers=other_headers, json={"type": "tank"}).json()["asset_id"]
            cross_tenant_resp = client.post(
                "/asset-connectivity", headers=headers,
                json={"source_asset_id": pipe_id, "target_asset_id": other_asset_id, "connection_type": "flows_into"},
            )
            print(f"POST /asset-connectivity (activo de OTRO tenant): {cross_tenant_resp.status_code}")
            ok_cross_tenant_rejected = cross_tenant_resp.status_code == 404

            # 8. GeoJSON: solo activos CON geometria, mas la conexion entre ellos.
            geo_pipe_id = client.post(
                "/network-assets", headers=headers,
                json={"type": "pipe", "geometry": {"type": "Point", "coordinates": [-74.06, 4.65]}},
            ).json()["asset_id"]
            geo_valve_id = client.post(
                "/network-assets", headers=headers,
                json={"type": "valve", "geometry": {"type": "Point", "coordinates": [-74.061, 4.651]}},
            ).json()["asset_id"]
            client.post(
                "/asset-connectivity", headers=headers,
                json={"source_asset_id": geo_pipe_id, "target_asset_id": geo_valve_id, "connection_type": "flows_into"},
            )
            geojson = client.get("/network-assets/geojson", headers=headers).json()
            points = [f for f in geojson["features"] if f["geometry"]["type"] == "Point"]
            lines = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
            print(f"GET /network-assets/geojson: {len(points)} puntos, {len(lines)} lineas")
            # pipe/valve sin geometria (pasos 1 y 5) NO aparecen -- solo los 2 con geometria real.
            ok_geojson = len(points) == 2 and len(lines) == 1

            ok = (
                ok_create and ok_invalid_type and ok_list_and_detail and ok_status_update
                and ok_connect and ok_missing_asset and ok_cross_tenant_rejected and ok_geojson
            )
            print("SPRINT B5 DIGITAL TWIN E2E OK" if ok else "SPRINT B5 DIGITAL TWIN E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM asset_connectivity WHERE source_asset_id IN (SELECT id FROM network_asset WHERE tenant_id = %s) "
                            "OR target_asset_id IN (SELECT id FROM network_asset WHERE tenant_id = %s)",
                            (tenant_id, tenant_id),
                        )
                        cur.execute("DELETE FROM network_asset WHERE tenant_id = %s", (tenant_id,))
            with conn.transaction():
                with tenant_scope(conn, other_tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM network_asset WHERE tenant_id = %s", (other_tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
                cur.execute("DELETE FROM tenant WHERE id = %s", (other_tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
