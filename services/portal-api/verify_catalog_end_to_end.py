"""Verificacion end-to-end real de la base generica (migracion 0045) --
HTTP real (FastAPI TestClient), JWT real, Postgres real con el rol de
aplicacion (RLS activo), sin mocks.

Que prueba, en espanol llano:
  1. Catalogo de la interfaz: etiquetas de codigos del nucleo, terminologia y
     formatos que traen los paquetes adoptados; sin moneda ni region hasta
     que la organizacion las defina.
  2. Sin los paquetes de un pais/programa, los terminos son neutros y no hay
     formatos de programa: nada del pais vive en el codigo.
  3. Moneda y region: validadas contra el catalogo; solo quien administra la
     configuracion las cambia; los textos que arma el servidor usan los
     separadores de la region.
  4. Terminologia propia de la organizacion, que vuelve a la del paquete.
  5. Aislamiento.
Al final borra SOLO las organizaciones de prueba y lo que crearon.

Uso:
    python verify_catalog_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from e2e_packs import adopt_program_packs  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402

JWT_SECRET = "e2e-cat-secret"
ORDER_SIGNING_SECRET = "e2e-cat-order-secret"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  OK  {message}")


def run(dsn: str) -> None:
    os.environ["RENFYGRID_DSN"] = dsn
    os.environ["RENFYGRID_JWT_SECRET"] = JWT_SECRET
    os.environ["RENFYGRID_ORDER_SIGNING_SECRET"] = ORDER_SIGNING_SECRET

    import main  # despues de fijar el entorno
    from fastapi.testclient import TestClient

    client = TestClient(main.app)
    now = datetime.now(timezone.utc)

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E catalogo') RETURNING id")
            tenant_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO tenant (name) VALUES ('E2E catalogo otra') RETURNING id")
            other_id = str(cur.fetchone()[0])
        try:
            adopt_program_packs(conn, tenant_id, other_id)
            create_app_user(conn, tenant_id, "admin@cat.test", "clave-admin-1", "supervisor")
            create_app_user(conn, tenant_id, "operador@cat.test", "clave-oper-1", "operator")
            create_app_user(conn, other_id, "admin@otra-cat.test", "clave-admin-2", "supervisor")

            def login(tid, email, pwd):
                return {"Authorization": f"Bearer {client.post('/auth/login', json={'tenant_id': tid, 'email': email, 'password': pwd}).json()['access_token']}"}

            h = login(tenant_id, "admin@cat.test", "clave-admin-1")
            op = login(tenant_id, "operador@cat.test", "clave-oper-1")
            other = login(other_id, "admin@otra-cat.test", "clave-admin-2")
            client.put("/settings/timezone", headers=h, json={"timezone": "America/Guayaquil"})

            print("1. Catálogo de la interfaz")
            c = client.get("/catalog/ui", headers=op).json()
            check(c["currency"] is None and c["locale"] is None, "sin moneda ni región hasta definirlas")
            check(set(c["labels"]["priority"]) == {"high", "medium", "low"} and c["labels"]["priority"]["high"]["tone"] == "danger"
                  and "emergency" in c["labels"]["maintenance.priority"], "etiquetas del núcleo con su tono (prioridad de órdenes aparte)")
            check(len(c["labels"]) >= 30 and any(x["code"] == "USD" for x in c["currencies"]) and any(x["code"] == "es-CO" for x in c["locales"]),
                  "30 dominios de etiquetas, monedas y regiones del catálogo")
            check(c["terms"]["provider"]["label"] == "junta" and c["terms"]["regulator"]["label"] == "ARCA"
                  and c["terms"]["board"]["label"] == "directiva", "los paquetes adoptados nombran prestador y ente rector")
            check(c["forms"]["improvement_inputs"]["code"] == "7G.2", "formato del programa adoptado")

            print("2. Sin paquetes de país ni de programa")
            for p in ("EC-MUNICIPIOS-AZULES", "EC-ARCA"):
                assert client.delete(f"/packs/{p}/adopt", headers=h).status_code == 200
            c = client.get("/catalog/ui", headers=op).json()
            check(c["terms"]["provider"]["label"] == "organización" and c["terms"]["regulator"]["label"] == "ente rector"
                  and c["terms"]["local_government"]["label"] == "gobierno local", "términos neutros del núcleo")
            check(c["forms"] == {}, "sin formatos de programa")
            for p in ("EC-ARCA", "EC-MUNICIPIOS-AZULES"):
                assert client.post(f"/packs/{p}/adopt", headers=h).status_code in (200, 201)

            print("3. Moneda y región")
            check(client.put("/settings/region", headers=op, json={"currency": "USD", "locale": "es-EC"}).status_code == 403,
                  "el operador no cambia la configuración")
            check(client.put("/settings/region", headers=h, json={"currency": "XXX", "locale": "es-EC"}).status_code == 422, "moneda inventada -> 422")
            check(client.put("/settings/region", headers=h, json={"currency": "USD", "locale": "xx-YY"}).status_code == 422, "región inventada -> 422")
            r = client.put("/settings/region", headers=h, json={"currency": "usd", "locale": "es-EC"})
            check(r.status_code == 200 and r.json()["currency"]["code"] == "USD" and r.json()["currency"]["decimals"] == 2
                  and r.json()["locale"]["decimal_sep"] == ",", "USD con 2 decimales, coma decimal (es-EC)")
            far = client.post("/sampling-points", headers=h, json={"kind_code": "network_far", "name": "Extremo"}).json()["point_id"]
            for i, v in enumerate((0.15, 0.18)):
                client.post("/field-readings", headers=op, json={"parameter_code": "free_chlorine", "value": v, "sampling_point_id": far,
                                                                  "measured_at": (now - timedelta(hours=3 - i)).isoformat()})
            ev = next(x for x in client.get("/improvement/inputs", headers=h).json()["candidates"] if x["source_kind"] == "reading")["evidence"]
            check("0,15; 0,18" in ev, f"el servidor escribe los números con la región: {ev!r}")
            client.put("/settings/region", headers=h, json={"currency": "USD", "locale": "en-US"})
            ev = next(x for x in client.get("/improvement/inputs", headers=h).json()["candidates"] if x["source_kind"] == "reading")["evidence"]
            check("0.15; 0.18" in ev, "y cambia al cambiar la región")

            print("4. Terminología propia")
            check(client.put("/settings/terms", headers=h, json={"changes": {"inventado": {"label": "x", "plural": "y"}}}).status_code == 422,
                  "término desconocido -> 422")
            check(client.put("/settings/terms", headers=h, json={"changes": {"provider": {"label": "ASADA", "plural": " "}}}).status_code == 422,
                  "sin plural -> 422")
            check(client.put("/settings/terms", headers=op, json={"changes": {"provider": {"label": "x", "plural": "y"}}}).status_code == 403,
                  "el operador no cambia la terminología")
            r = client.put("/settings/terms", headers=h, json={"changes": {"provider": {"label": "ASADA", "plural": "ASADAS"}}})
            check(r.status_code == 200 and r.json()["provider"] == {"label": "ASADA", "plural": "ASADAS", "source": "organization"},
                  "la organización se llama a sí misma ASADA")
            check(client.get("/catalog/ui", headers=other).json()["terms"]["provider"]["label"] == "junta", "otra organización no cambia")
            r = client.put("/settings/terms", headers=h, json={"changes": {"provider": None}})
            check(r.json()["provider"]["label"] == "junta", "vuelve al término del paquete")

            print("5. Aislamiento")
            oc = client.get("/catalog/ui", headers=other).json()
            check(oc["currency"] is None and oc["locale"] is None, "la región de una organización no es la de otra")
        finally:
            for tid in (tenant_id, other_id):
                with conn.transaction():
                    with tenant_scope(conn, tid):
                        conn.execute("UPDATE field_reading SET finding_id = NULL WHERE tenant_id = %s", (tid,))
                        for table in ("tenant_term", "field_reading", "finding", "sampling_point", "tenant_pack", "app_user"):
                            conn.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tid,))
                conn.execute("DELETE FROM tenant WHERE id = %s", (tid,))
            print("Limpieza: organizaciones de prueba y sus datos borrados")
    print("BASE GENERICA E2E OK")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    run(sys.argv[1])
