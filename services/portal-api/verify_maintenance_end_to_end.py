"""Verificacion end-to-end real de Track B, Sprint B7 (Gestion de
Mantenimiento + integracion BayForce, `docs/07-track-b-alcance-funcional.md`
SS5) -- por HTTP real (FastAPI TestClient), Postgres real, y un servidor
HTTP LOCAL REAL (stdlib `http.server`, en un hilo) haciendo de sandbox de
BayForce -- nada mockeado, una llamada HTTP real de punta a punta.

NOTA: la integracion viva contra el BayForce real (`core/renflow/bayforce`)
necesita su URL/credenciales de sandbox reales, que esta sesion no tiene
-- este E2E prueba el CONTRATO real que RenfyGrid expone/consume (mismo
JSON, mismo flujo de estados), listo para apuntar a BayForce en cuanto
haya una URL real configurada (`RENFYGRID_BAYFORCE_WEBHOOK_URL`).

Que prueba, en espanol llano:
  1. Generar una orden `asset_condition` sobre un activo REALMENTE
     `out_of_service` -- éxito.
  2. La misma fuente sobre un activo `operational` -> 422 (la anomalia
     real no se cumple, nunca se genera la orden de todas formas).
  3. Generar una orden `balance_anomaly` sobre un activo vinculado a una
     zona CON `exceeds_threshold=True` -- éxito; sobre una zona SIN
     balance que exceda -> 422.
  4. Enviar la orden a BayForce (HTTP real contra el sandbox local) --
     quedan `sent_to_bayforce` con un `bayforce_order_ref` real devuelto
     por el sandbox.
  5. Reenviar la misma orden -> 422 (no esta en `generated`).
  6. El webhook de cierre (llamado como lo haria BayForce) avanza el
     estado real -- `sent_to_bayforce -> in_progress -> completed`.
  7. Una transicion invalida (`completed -> in_progress`) -> 422.
  8. `bayforce_order_ref` que no existe -> 404.
  9. Enviar a BayForce SIN `RENFYGRID_BAYFORCE_WEBHOOK_URL` configurado ->
     `BayforceNotConfiguredError` real (probado contra el servicio
     directo, no vía HTTP -- el webhook configurado es de instancia).

Uso:
    python verify_maintenance_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "digital-twin"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maintenance"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.auth import create_token  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

JWT_SECRET = "e2e-b7-secret"
ORDER_SIGNING_SECRET = "e2e-b7-order-secret"

_BAYFORCE_REF_COUNTER = [0]


class _FakeBayforceSandbox(BaseHTTPRequestHandler):
    """Sandbox real de BayForce para esta prueba -- recibe la orden por
    HTTP de verdad, devuelve un `bayforce_order_ref` real (no fijo)."""

    def do_POST(self):  # noqa: N802 -- nombre exigido por BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _BAYFORCE_REF_COUNTER[0] += 1
        ref = f"BF-{_BAYFORCE_REF_COUNTER[0]:06d}"
        print(f"  [sandbox BayForce] recibida orden {body.get('renfygrid_order_id')} -> {ref}")
        response = json.dumps({"bayforce_order_ref": ref}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args):  # silencia el log por defecto de http.server
        pass


def run(dsn: str) -> int:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    sandbox = HTTPServer(("127.0.0.1", 0), _FakeBayforceSandbox)
    sandbox_port = sandbox.server_port
    sandbox_thread = threading.Thread(target=sandbox.serve_forever, daemon=True)
    sandbox_thread.start()
    webhook_url = f"http://127.0.0.1:{sandbox_port}/orders"
    os.environ["RENFYGRID_BAYFORCE_WEBHOOK_URL"] = webhook_url
    print(f"Sandbox BayForce real levantado en {webhook_url}")

    import main
    from fastapi.testclient import TestClient

    client = TestClient(main.app)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E Maintenance Sprint B7",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            token = create_token({"tenant_id": tenant_id, "role": "supervisor", "email": "mantenimiento@renfygrid.demo"}, JWT_SECRET)
            headers = {"Authorization": f"Bearer {token}"}

            # 1. asset_condition sobre un activo REALMENTE out_of_service.
            broken_asset_id = client.post("/network-assets", headers=headers, json={"type": "pump", "status": "out_of_service"}).json()["asset_id"]
            order_resp = client.post(
                "/maintenance-orders", headers=headers,
                json={"asset_id": broken_asset_id, "type": "corrective", "source": "asset_condition", "reason": "Bomba fuera de servicio"},
            )
            print(f"POST /maintenance-orders (asset_condition, activo roto): {order_resp.status_code}, {order_resp.json()}")
            ok_create = order_resp.status_code == 201 and order_resp.json()["status"] == "generated"
            order_id = order_resp.json()["order_id"]

            # 2. asset_condition sobre un activo operativo -> 422.
            healthy_asset_id = client.post("/network-assets", headers=headers, json={"type": "pump"}).json()["asset_id"]
            rejected_resp = client.post(
                "/maintenance-orders", headers=headers,
                json={"asset_id": healthy_asset_id, "type": "corrective", "source": "asset_condition"},
            )
            print(f"POST /maintenance-orders (asset_condition, activo operativo): {rejected_resp.status_code}")
            ok_condition_rejected = rejected_resp.status_code == 422

            # 3. balance_anomaly: zona CON exceso -> ok; zona SIN exceso -> 422.
            zone_bad_id = client.post("/network-zones", headers=headers, json={"name": "Zona con exceso", "type": "dma", "data_source": "external", "nrw_threshold_pct": 30.0}).json()["zone_id"]
            client.post(
                f"/network-zones/{zone_bad_id}/balance", headers=headers,
                json={"period_start": "2026-08-01", "period_end": "2026-09-01", "method": "top_down", "system_input_volume": 10000, "billed_metered_consumption": 6000, "real_losses": 4000},
            )
            asset_in_bad_zone = client.post("/network-assets", headers=headers, json={"type": "valve", "zone_id": zone_bad_id}).json()["asset_id"]
            balance_order_resp = client.post(
                "/maintenance-orders", headers=headers,
                json={"asset_id": asset_in_bad_zone, "type": "inspection", "source": "balance_anomaly", "reason": "NRW sobre el tope regulatorio"},
            )
            print(f"POST /maintenance-orders (balance_anomaly, zona con exceso): {balance_order_resp.status_code}")
            ok_balance_anomaly = balance_order_resp.status_code == 201

            zone_ok_id = client.post("/network-zones", headers=headers, json={"name": "Zona sin exceso", "type": "dma", "data_source": "external"}).json()["zone_id"]
            asset_in_ok_zone = client.post("/network-assets", headers=headers, json={"type": "valve", "zone_id": zone_ok_id}).json()["asset_id"]
            balance_rejected_resp = client.post(
                "/maintenance-orders", headers=headers,
                json={"asset_id": asset_in_ok_zone, "type": "inspection", "source": "balance_anomaly"},
            )
            print(f"POST /maintenance-orders (balance_anomaly, zona sin balance): {balance_rejected_resp.status_code}")
            ok_balance_rejected = balance_rejected_resp.status_code == 422

            # 4. Enviar a BayForce (HTTP real contra el sandbox).
            send_resp = client.post(f"/maintenance-orders/{order_id}/send-to-bayforce", headers=headers)
            print(f"POST send-to-bayforce: {send_resp.status_code}, {send_resp.json()}")
            bayforce_ref = send_resp.json().get("bayforce_order_ref")
            ok_send = send_resp.status_code == 200 and send_resp.json()["status"] == "sent_to_bayforce" and bool(bayforce_ref)

            # 5. Reenviar la misma orden -> 422 (no esta en 'generated').
            resend_resp = client.post(f"/maintenance-orders/{order_id}/send-to-bayforce", headers=headers)
            print(f"POST send-to-bayforce (reenvio): {resend_resp.status_code}")
            ok_resend_rejected = resend_resp.status_code == 422

            # 6. Webhook de cierre real: sent_to_bayforce -> in_progress -> completed.
            wh1 = client.post("/maintenance-orders/bayforce-webhook", headers=headers, json={"bayforce_order_ref": bayforce_ref, "status": "in_progress"})
            wh2 = client.post("/maintenance-orders/bayforce-webhook", headers=headers, json={"bayforce_order_ref": bayforce_ref, "status": "completed"})
            print(f"webhook in_progress: {wh1.status_code}, webhook completed: {wh2.status_code}, {wh2.json()}")
            ok_webhook_flow = wh1.status_code == 200 and wh2.status_code == 200 and wh2.json()["status"] == "completed"

            # 7. Transicion invalida (completed -> in_progress) -> 422.
            wh_invalid = client.post("/maintenance-orders/bayforce-webhook", headers=headers, json={"bayforce_order_ref": bayforce_ref, "status": "in_progress"})
            print(f"webhook transicion invalida: {wh_invalid.status_code}")
            ok_invalid_transition = wh_invalid.status_code == 422

            # 8. bayforce_order_ref inexistente -> 404.
            wh_missing = client.post("/maintenance-orders/bayforce-webhook", headers=headers, json={"bayforce_order_ref": "BF-NO-EXISTE", "status": "completed"})
            print(f"webhook ref inexistente: {wh_missing.status_code}")
            ok_missing_ref = wh_missing.status_code == 404

            # 9. Sin webhook configurado -> BayforceNotConfiguredError real (directo al servicio).
            from order_service import BayforceNotConfiguredError, send_to_bayforce as send_to_bayforce_direct
            order2_id = client.post(
                "/maintenance-orders", headers=headers,
                json={"asset_id": broken_asset_id, "type": "corrective", "source": "manual", "reason": "prueba sin webhook"},
            ).json()["order_id"]
            ok_not_configured = False
            try:
                send_to_bayforce_direct(conn, tenant_id, order2_id, None)
            except BayforceNotConfiguredError:
                ok_not_configured = True
            print(f"send_to_bayforce sin webhook configurado -> BayforceNotConfiguredError: {ok_not_configured}")

            ok = (
                ok_create and ok_condition_rejected and ok_balance_anomaly and ok_balance_rejected
                and ok_send and ok_resend_rejected and ok_webhook_flow and ok_invalid_transition
                and ok_missing_ref and ok_not_configured
            )
            print("SPRINT B7 MAINTENANCE E2E OK" if ok else "SPRINT B7 MAINTENANCE E2E FALLA")
            return 0 if ok else 1
        finally:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM maintenance_order WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_balance WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_asset WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM network_zone WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
            sandbox.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
