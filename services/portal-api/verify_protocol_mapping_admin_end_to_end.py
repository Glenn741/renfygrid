"""Verificacion end-to-end real de Sprint C10 (`docs/06-benchmark-e2e-y-brechas.md`
E19): editor de mapeo OBIS en Configuracion -- por HTTP real (FastAPI
TestClient) contra los endpoints `/obis-mappings`, Postgres real, y el
mismo criterio de aceptacion que F06 (Sprint 2): "un operador cambia el
mapeo OBIS de una marca desde la UI (sin SQL) y el siguiente ciclo del
poller ya lo usa".

Que prueba, en espanol llano:
  1. `POST /obis-mappings` crea un mapeo real para BrandX/ModelX (sin tocar
     SQL a mano, sin passar por `INSERT INTO meter_protocol` directo).
  2. `GET /obis-mappings` (activos) lo devuelve; version=1.
  3. Un segundo `POST /obis-mappings` para la MISMA marca/modelo cierra el
     primero (`valid_to` deja de ser NULL) y sube a version=2 -- a lo sumo
     una fila activa por (brand, model), misma invariante que
     `control_approval_level`.
  4. El lado del poller (`obis_mapping.build_cache(...).refresh()` +
     `channels_for()`, SIN tocar `poller.py`) ve la version nueva despues
     de refrescar el snapshot -- el mismo criterio real que F06 verifico
     para el camino de SQL directo, ahora tambien para el camino de UI.

Uso:
    python verify_protocol_mapping_admin_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hes-adapter-dlms"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from obis_mapping import build_cache, channels_for  # noqa: E402
from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-c10-secret"
ORDER_SIGNING_SECRET = "e2e-c10-order-secret"


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main  # importado despues de fijar el entorno
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Protocol Mapping Sprint C10",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "ana@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            mapping_v1 = {"active_energy": {"obis_code": "1.0.1.8.0.255", "attribute_index": 2}}
            resp1 = client.post(
                "/obis-mappings",
                headers=headers,
                json={"brand": "BrandX", "model": "ModelX", "protocol": "DLMS_COSEM", "obis_mapping": mapping_v1},
            )
            print(f"POST /obis-mappings (v1): {resp1.status_code}, {resp1.json()}")

            active = client.get("/obis-mappings", headers=headers).json()
            print(f"GET /obis-mappings (activos, tras v1): {active}")
            ok_v1 = len(active) == 1 and active[0]["version"] == 1 and active[0]["valid_to"] is None

            mapping_v2 = {"active_energy": {"obis_code": "1.0.1.8.0.255", "attribute_index": 2},
                          "reactive_energy": {"obis_code": "1.0.1.3.8.0.255", "attribute_index": 2}}
            resp2 = client.post(
                "/obis-mappings",
                headers=headers,
                json={"brand": "BrandX", "model": "ModelX", "protocol": "DLMS_COSEM", "obis_mapping": mapping_v2},
            )
            print(f"POST /obis-mappings (v2): {resp2.status_code}, {resp2.json()}")

            active2 = client.get("/obis-mappings", headers=headers).json()
            all_versions = client.get("/obis-mappings?active_only=false", headers=headers).json()
            print(f"GET /obis-mappings (activos, tras v2): {active2}")
            print(f"GET /obis-mappings (todas las versiones): {[(r['version'], r['valid_to'] is None) for r in all_versions]}")
            ok_v2 = (
                len(active2) == 1 and active2[0]["version"] == 2
                and "reactive_energy" in active2[0]["obis_mapping"]
                and len(all_versions) == 2
                and any(r["version"] == 1 and r["valid_to"] is not None for r in all_versions)
            )

            # Lado del poller: el mismo snapshot cacheado que usa poller.py
            # de verdad, refrescado desde BD -- sin tocar poller.py.
            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "obis_mapping.json"
                cache = build_cache(snapshot_path, dsn, tenant_id)
                cache.refresh()
                cache.load()
                channels = channels_for(cache, "BrandX", "ModelX")
                print(f"obis_mapping.channels_for tras refresh: {channels}")
                ok_poller_side = "reactive_energy" in channels and "active_energy" in channels

            ok = ok_v1 and ok_v2 and ok_poller_side
            print("SPRINT C10 E2E OK" if ok else "SPRINT C10 E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter_protocol WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
