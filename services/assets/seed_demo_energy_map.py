"""Datos del mapa tematico para la organizacion demo de energia (Track F,
Q2.5, 2026-10-21). docs/11-mapa-fronteras.md.

Completa `demoenergia` (sembrada por seed_demo_energy_tenant.py) con lo que el
mapa necesita para mostrarse completo. Todo es FICTICIO:

- tipo de cliente, mercado y estado comercial de cada frontera;
- ficha tecnica de los medidores principales (tecnologia y conexion) y medio
  de comunicacion de los modems;
- telemedida: cada medidor principal se registra en el HES (`meter`) con su
  misma serie, con su ultima lectura y algunas alarmas, y se fija la ventana
  de reporte si la organizacion no la tenia;
- unas 300 PQR con causales reales de la taxonomia de la Superservicios
  (paquete CO-SSPD, que se adopta), abiertas, respondidas, en recurso y cerradas.

No se vuelve a correr si la organizacion ya tiene PQR. Semilla aleatoria fija.

Uso:
    python seed_demo_energy_map.py "<dsn>"
"""

from __future__ import annotations

import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "community"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portal-api"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

import customer_request_service as crs  # noqa: E402
from pack_service import adopt_pack  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from tenant_settings import get_meter_stale_after_seconds, set_meter_stale_after_seconds  # noqa: E402

ORG = "demoenergia"
BY = "seed:demo-energia-mapa"
TODAY = date.today()
WINDOW_SECONDS = 6 * 3600   # cadencia de la telemedida de la demo: reporta cada hora

# Causales de energia mas frecuentes en una cartera no regulada (pesos ficticios).
CAUSES = [("101", 18), ("124", 14), ("118", 9), ("125", 7), ("109", 6), ("117", 5), ("116", 4), ("110", 4), ("120", 4),
          ("135", 3), ("200", 10), ("202", 6), ("204", 4), ("206", 4), ("208", 2)]


def seed(dsn: str) -> None:
    rng = random.Random(20261021)
    t0 = time.time()
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id::text FROM tenant WHERE name = %s", (ORG,))
            row = cur.fetchone()
        if row is None:
            sys.exit(f"No existe {ORG}: corra primero seed_demo_energy_tenant.py")
        tenant_id = row[0]
        with conn.transaction():
            adopt_pack(conn, tenant_id, "CO-SSPD")
            if get_meter_stale_after_seconds(conn, tenant_id) is None:
                set_meter_stale_after_seconds(conn, tenant_id, WINDOW_SECONDS)
            window = get_meter_stale_after_seconds(conn, tenant_id)
            cat = crs.catalog(conn, tenant_id)
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM customer_request")
                    if cur.fetchone()[0]:
                        sys.exit(f"{ORG} ya tiene PQR; no se vuelve a sembrar.")
                    cur.execute("SELECT id::text, code, point_class, customer_name FROM metering_point ORDER BY code")
                    points = cur.fetchall()
                    # Tipo de cliente, mercado y estado comercial.
                    for pid, code, klass, customer in points:
                        if customer.startswith("Alumbrado"):
                            cclass = "public_lighting"
                        elif klass in ("1", "2"):
                            cclass = "industrial"
                        else:
                            cclass = rng.choices(["industrial", "commercial", "official"], weights=[35, 55, 10])[0]
                        market = "non_regulated" if klass in ("1", "2", "3") or rng.random() < 0.35 else "regulated"
                        status = rng.choices(["current", "payment_agreement", "arrears", "disconnection", "suspended_debt", "retired"],
                                             weights=[86, 3, 6, 1.5, 2.5, 1])[0]
                        cur.execute("UPDATE metering_point SET customer_class = %s, market = %s, commercial_status = %s, "
                                    "niu = coalesce(niu, %s) WHERE id = %s", (cclass, market, status, f"NIU{code[-5:]}", pid))
                    # Ficha tecnica minima de medidores y modems instalados.
                    cur.execute("SELECT i.point_id::text, i.position_code, e.id::text, e.attributes, e.serial, e.brand, e.model, p.code, "
                                "p.point_class FROM equipment_installation i JOIN equipment e ON e.id = i.equipment_id "
                                "JOIN metering_point p ON p.id = i.point_id "
                                "WHERE i.removed_on IS NULL AND i.position_code IN ('main_active', 'backup', 'modem_main')")
                    installed = cur.fetchall()
                    for pid, position, eid, attrs, serial, brand, model, pcode, klass in installed:
                        fields = dict((attrs or {}).get("fields") or {})
                        if position in ("main_active", "backup"):
                            fields.setdefault("c3_9", {"value": "estatico" if rng.random() < 0.94 else "hibrido"})
                            fields.setdefault("c3_10", {"value": {"1": "indirecta", "2": "indirecta", "3": "semidirecta"}.get(klass, "directa")})
                        else:
                            fields.setdefault("c11_9", {"value": rng.choices(["4g", "3g", "gprs", "fibra_optica"], weights=[55, 20, 15, 10])[0]})
                            fields.setdefault("c11_8", {"value": rng.choice(["claro", "movistar", "tigo"])})
                        cur.execute("UPDATE equipment SET attributes = %s WHERE id = %s", (Json({"fields": fields}), eid))
                    # Telemedida: el medidor principal en el HES, con su ultima lectura.
                    now = datetime.now(timezone.utc)
                    linked = 0
                    for pid, position, eid, attrs, serial, brand, model, pcode, klass in installed:
                        if position != "main_active" or (klass in ("4", "5") and rng.random() < 0.45):
                            continue   # parte de los tipos 4 y 5 no tiene telemedida
                        cur.execute("INSERT INTO meter (tenant_id, account_number, serial_number, brand, model, protocol, status) "
                                    "VALUES (%s, %s, %s, %s, %s, 'DLMS_COSEM', 'active') "
                                    "ON CONFLICT (tenant_id, account_number) DO NOTHING RETURNING id",
                                    (tenant_id, pcode, serial, brand, model))
                        mrow = cur.fetchone()
                        if mrow is None:
                            continue
                        linked += 1
                        silent = rng.random() < 0.06
                        last = now - (timedelta(hours=rng.uniform(7, 96)) if silent else timedelta(minutes=rng.uniform(5, 55)))
                        cur.execute("INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value) VALUES (%s, %s, %s, 'active_energy', %s)",
                                    (tenant_id, mrow[0], last, round(rng.uniform(1000, 900000), 2)))
                        if rng.random() < 0.035:
                            cur.execute("INSERT INTO meter_event (tenant_id, meter_id, type, \"timestamp\", severity) VALUES (%s, %s, %s, %s, %s)",
                                        (tenant_id, mrow[0], rng.choice(["tamper_cover_open", "voltage_sag", "reverse_energy", "power_failure"]),
                                         now - timedelta(minutes=rng.uniform(10, window / 60 - 10)), rng.choice(["critical", "warning"])))
                    # PQR con causales de la Superservicios.
                    allowed = {c["code"] for c in cat["causes"]}
                    causes = [(c, w) for c, w in CAUSES if c in allowed]
                    chosen = rng.sample(points, 260)
                    n = 0
                    for pid, code, klass, customer in chosen:
                        for _ in range(1 if rng.random() < 0.85 else 2):
                            n += 1
                            cause = rng.choices([c for c, _ in causes], weights=[w for _, w in causes])[0]
                            filed = TODAY - timedelta(days=rng.randint(1, 240))
                            age = (TODAY - filed).days
                            status = "open" if age < 15 else rng.choices(["answered", "closed", "appealed", "open"], weights=[25, 55, 8, 12])[0]
                            response = None if status == "open" else rng.choice(["1", "2", "3"])
                            responded = None if status == "open" else filed + timedelta(days=min(age, rng.randint(3, 15)))
                            rtype = "2" if cause.startswith("2") else ("5" if status == "appealed" else "1")
                            crs._create(cur, tenant_id, cat, {
                                "account": f"NIU{code[-5:]}", "filing_number": f"RAD-DEMO-{filed.year}-{n:05d}", "filed_on": filed,
                                "request_type": rtype, "cause_code": cause, "status": status, "response_code": response,
                                "responded_on": responded}, BY, "import")
    print(f"{ORG}: tipo de cliente y estado comercial en {len(points)} fronteras, {linked} medidores con telemedida, "
          f"{n} PQR, en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    seed(sys.argv[1])
