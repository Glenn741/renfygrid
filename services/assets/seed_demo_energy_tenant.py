"""Organizacion de demostracion de energia (Track F, Q2, 2026-10-20).

Pedido del usuario: ver como luce el workspace de una comercializadora de
energia que controla unos 2.000 medidores de clientes no regulados
(industriales, comerciales, alumbrado publico) con su hoja de vida,
calibraciones y mantenimientos. docs/10-caso-energia-fronteras.md.

Crea la organizacion `demoenergia` (sector energia, paquete CO-CREG-038) y le
carga 2.000 fronteras FICTICIAS con sus equipos y su bitacora, por las mismas
funciones del servicio que usa el Portal (mismas validaciones):

- tipos de punto 1 a 5 con una distribucion de cartera no regulada;
- medidor principal siempre; respaldo en tipos 1 y 2; CT y modem en 1 a 3;
  PT en 1 y 2;
- calibraciones repartidas para que haya equipos al dia, por vencer,
  vencidos, sin registro y uno con el sello de la tapa retirado;
- algunos cambios de medidor (novedad para XM, unas reportadas y otras no)
  y visitas de verificacion.

Los nombres de clientes y los codigos de frontera son inventados
(FRT-DEMO-00001...). La semilla aleatoria es fija: dos corridas dan lo mismo.

Uso (las claves salen de RENFYGRID_PWD_<USUARIO> o se piden por consola):
    python seed_demo_energy_tenant.py "<dsn>"
"""

from __future__ import annotations

import getpass
import os
import random
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "community"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portal-api"))

import psycopg  # noqa: E402

import metering_asset_service as svc  # noqa: E402
from organization_service import create_organization  # noqa: E402
from permissions import create_user  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402

ORG = "demoenergia"
DISPLAY = "Comercializadora Demo (energía)"
POINTS = 2000
BY = "seed:demo-energia"
TODAY = date.today()

# (tipo, proporcion, rango de consumo MWh-mes, rango de kVA)
CLASS_MIX = [("1", 0.005, (15000, 22000), (30000, 45000)), ("2", 0.08, (500, 4000), (1000, 8000)),
             ("3", 0.35, (50, 480), (112.5, 1000)), ("4", 0.45, (5, 48), (15, 112.5)), ("5", 0.115, (0.5, 4.8), (3, 10))]
CITIES = [("Barranquilla", "Atlántico", 10.9685, -74.7813), ("Cartagena", "Bolívar", 10.3910, -75.4794),
          ("Santa Marta", "Magdalena", 11.2408, -74.1990), ("Valledupar", "Cesar", 10.4631, -73.2532),
          ("Montería", "Córdoba", 8.7479, -75.8814), ("Sincelejo", "Sucre", 9.3047, -75.3978),
          ("Riohacha", "La Guajira", 11.5444, -72.9072), ("Bogotá", "Cundinamarca", 4.7110, -74.0721),
          ("Medellín", "Antioquia", 6.2442, -75.5812), ("Cali", "Valle del Cauca", 3.4516, -76.5320),
          ("Bucaramanga", "Santander", 7.1193, -73.1227), ("Soledad", "Atlántico", 10.9184, -74.7646)]
WEIGHTS = [26, 14, 8, 6, 5, 4, 3, 12, 9, 6, 4, 3]
PREFIX = ["Industrias", "Comercializadora", "Distribuidora", "Frigorífico", "Textiles", "Plásticos", "Alimentos", "Logística",
          "Hotel", "Clínica", "Centro Comercial", "Colegio", "Supermercado", "Cementos", "Agroindustrial", "Laboratorios"]
CORE = ["del Caribe", "Andina", "Costa Norte", "La Ribera", "El Prado", "Sol Naciente", "Montealegre", "Los Almendros",
        "Puerto Nuevo", "Santa Lucía", "Alto Magdalena", "La Esperanza", "Bahía", "San Andrés", "Las Palmas", "Mirador"]
SUFFIX = ["S.A.S.", "S.A.", "Ltda.", "y Cía.", "S.A.S. E.S.P."]
METERS = [("Elster", "A1800"), ("Itron", "SL7000"), ("Landis+Gyr", "E650"), ("Schneider", "ION8650"), ("ZIV", "5CTD"), ("Kaifa", "MA309")]
CTS = [("Arteche", "CXE"), ("ABB", "TPU"), ("Schneider", "ARJP3")]
PTS = [("Arteche", "UDP"), ("ABB", "TJP")]
MODEMS = [("Teltonika", "TRB140"), ("Sierra Wireless", "RV50"), ("Robustel", "R2000")]
LABS = ["Laboratorio de Metrología Eléctrica Demo", "Laboratorio Acreditado Norte (demo)", "Centro de Calibración Andino (demo)"]


def _password(user: str) -> str:
    env = "RENFYGRID_PWD_" + re.sub(r"[^A-Z0-9]", "_", user.upper())
    return os.environ.get(env) or getpass.getpass(f"Clave para {user}: ")


def _calibration_date(rng: random.Random, every_months: int) -> date | None:
    """Ultima calibracion: 2 % sin registro, 7 % vencida, 6 % por vencer
    (dentro de 90 dias), el resto al dia."""
    roll = rng.random()
    if roll < 0.02:
        return None
    period = every_months * 30.44
    if roll < 0.09:
        age = period + rng.uniform(15, 400)
    elif roll < 0.15:
        age = period - rng.uniform(5, 85)
    else:
        age = rng.uniform(30, period - 120)
    return TODAY - timedelta(days=int(age))


def _fields(**kw: object) -> dict:
    return {"fields": {k: {"value": v} for k, v in kw.items()}}


def seed(dsn: str) -> None:
    rng = random.Random(20261020)
    t0 = time.time()
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenant WHERE name = %s", (ORG,))
            row = cur.fetchone()
        if row:
            sys.exit(f"La organización {ORG} ya existe ({row[0]}); no se vuelve a sembrar.")
        with conn.transaction():
            org = create_organization(conn, ORG, "provider", "admin", _password("admin"), BY,
                                      config={"session_ttl_seconds": 12 * 3600, "timezone": "America/Bogota",
                                              "currency": "COP", "locale": "es-CO"},
                                      packs=["CO-CREG-038"], display_name=DISPLAY, sectors=["electricity"])
            tenant_id = org["tenant_id"]
            for user, role in (("tecnico01", "operator"), ("gerencia", "board")):
                create_user(conn, tenant_id, user, _password(user), role)
            svc.set_due_soon_days(conn, tenant_id, 90)
            ctx = svc._context(conn, tenant_id)
            freq = ctx["frequencies"]
            pack = ctx["pack_id"]
            with tenant_scope(conn, tenant_id):
                with conn.cursor() as cur:
                    serial = 0

                    def equipment(klass: str, models: list[tuple[str, str]], year: int) -> str:
                        nonlocal serial
                        serial += 1
                        brand, model = rng.choice(models)
                        return svc._create_equipment(cur, tenant_id, ctx, {
                            "class_code": klass, "serial": f"{klass[:1].upper()}{year % 100:02d}{serial:06d}", "brand": brand,
                            "model": model, "manufacturer": brand, "year": year, "ownership": rng.choice(["rf", "rf", "user"])}, BY)

                    def calibrate(eq_id: str, klass: str, point_class: str, installed: date) -> None:
                        activity = "calibration" if klass == "meter" else "routine_test"
                        every = freq[(pack, point_class, klass, activity)]["every_months"] if klass in ("meter", "ct", "pt") else None
                        if klass in ("ct", "pt"):
                            # CT/PT: calibracion inicial antes de la puesta en servicio (art. 11).
                            day = installed - timedelta(days=rng.randint(10, 60))
                        else:
                            day = _calibration_date(rng, every) if every else None
                            if day and day < installed:
                                day = installed - timedelta(days=rng.randint(5, 40))
                        if not day:
                            return
                        svc._record(cur, tenant_id, ctx, type_code="calibration", occurred_on=day, recorded_by=BY, point_id=None,
                                    equipment_id=eq_id, data=_fields(certificate_number=f"CC-{day.year}-{rng.randint(10000, 99999)}",
                                                                     laboratory=rng.choice(LABS), accredited=True,
                                                                     issued_on=day.isoformat(), error_pct=round(rng.uniform(-0.18, 0.18), 3),
                                                                     result="pass"),
                                    notes=None, source="import", external_ref=None)

                    classes = rng.choices([c[0] for c in CLASS_MIX], weights=[c[1] for c in CLASS_MIX], k=POINTS)
                    points = []
                    for n, klass in enumerate(sorted(classes), start=1):
                        _, _, (cmin, cmax), (kmin, kmax) = next(c for c in CLASS_MIX if c[0] == klass)
                        city, region, lat, lon = rng.choices(CITIES, weights=WEIGHTS, k=1)[0]
                        lighting = klass in ("4", "5") and rng.random() < 0.12
                        customer = (f"Alumbrado Público de {city} (demo)" if lighting else
                                    f"{rng.choice(PREFIX)} {rng.choice(CORE)} {rng.choice(SUFFIX)}")
                        registered = TODAY - timedelta(days=rng.randint(200, 3650))
                        pid = svc._create_point(cur, tenant_id, ctx, {
                            "code": f"FRT-DEMO-{n:05d}", "name": f"{'Circuito' if lighting else 'Sede'} {rng.choice(CORE)} {n}",
                            "customer_name": customer, "address": f"Calle {rng.randint(1, 120)} # {rng.randint(1, 99)}-{rng.randint(1, 99)}",
                            "city": city, "region": region, "lat": round(lat + rng.uniform(-0.06, 0.06), 6),
                            "lon": round(lon + rng.uniform(-0.06, 0.06), 6), "point_class": klass,
                            "voltage_kv": {"1": 115, "2": 34.5, "3": 13.2}.get(klass, 0.208),
                            "capacity_kva": round(rng.uniform(kmin, kmax), 1), "consumption_mwh_month": round(rng.uniform(cmin, cmax), 2),
                            "registered_on": registered.isoformat(), "verified_on": (registered + timedelta(days=rng.randint(5, 60))).isoformat(),
                            "status": "active" if rng.random() > 0.01 else "suspended"}, BY)
                        installed = registered - timedelta(days=rng.randint(1, 20))
                        year = installed.year - rng.randint(0, 2)
                        layout = [("main_active", "meter", METERS)]
                        if klass in ("1", "2"):
                            layout += [("backup", "meter", METERS)] + [(f"pt_{i}", "pt", PTS) for i in (1, 2, 3)]
                        if klass in ("1", "2", "3"):
                            layout += [(f"ct_{i}", "ct", CTS) for i in (1, 2, 3)] + [("modem_main", "modem", MODEMS)]
                        for position, eq_class, models in layout:
                            eq = equipment(eq_class, models, year)
                            svc._install(cur, tenant_id, ctx, eq, pid, position, installed, BY, None, "import", None)
                            calibrate(eq, eq_class, klass, installed)
                        points.append((pid, klass))
                        if n % 250 == 0:
                            print(f"  {n} fronteras ({time.time() - t0:.0f} s)")

                    # Visitas de verificacion en los tipos 1 y 2 (bitacora de la frontera).
                    for pid, klass in points:
                        if klass in ("1", "2") and rng.random() < 0.6:
                            day = TODAY - timedelta(days=rng.randint(20, 330))
                            svc._record(cur, tenant_id, ctx, type_code="verification_visit", occurred_on=day, recorded_by=BY,
                                        point_id=pid, equipment_id=None, data=_fields(result="ok", report_number=f"AV-{rng.randint(1000, 9999)}"),
                                        notes=None, source="import", external_ref=None)
                    # Cambios de medidor recientes: novedad para XM (las de mas de 20 dias, reportadas).
                    replaced = rng.sample([p for p in points if p[1] in ("3", "4")], 40)
                    for pid, klass in replaced:
                        cur.execute("SELECT equipment_id::text FROM equipment_installation WHERE point_id = %s "
                                    "AND position_code = 'main_active' AND removed_on IS NULL", (pid,))
                        old = cur.fetchone()[0]
                        day = TODAY - timedelta(days=rng.randint(1, 120))
                        svc._record(cur, tenant_id, ctx, type_code="seal_removed", occurred_on=day, recorded_by=BY, point_id=None,
                                    equipment_id=old, data=_fields(serial=f"SL{rng.randint(100000, 999999)}", location="Tapa principal",
                                                                   main_cover=True),
                                    notes="Retiro para cambio de medidor", source="field", external_ref=f"BF-DEMO-{rng.randint(1000, 9999)}")
                        cur.execute("UPDATE equipment_installation SET removed_on = %s, removed_by = %s, removal_reason = %s "
                                    "WHERE equipment_id = %s AND removed_on IS NULL", (day, BY, "Falla de registrador", old))
                        cur.execute("UPDATE equipment SET status = 'lab' WHERE id = %s", (old,))
                        svc._insert_event(cur, tenant_id, ctx, type_code="removed", point_id=pid, equipment_id=old, occurred_on=day,
                                          data=_fields(new_status="lab"), notes="Falla de registrador", source="field",
                                          external_ref=None, recorded_by=BY)
                        new = equipment("meter", METERS, day.year)
                        calibrate_day = day - timedelta(days=rng.randint(3, 20))
                        svc._record(cur, tenant_id, ctx, type_code="calibration", occurred_on=calibrate_day, recorded_by=BY, point_id=None,
                                    equipment_id=new, data=_fields(certificate_number=f"CC-{calibrate_day.year}-{rng.randint(10000, 99999)}",
                                                                   laboratory=rng.choice(LABS), accredited=True,
                                                                   issued_on=calibrate_day.isoformat(), result="pass"),
                                    notes=None, source="import", external_ref=None)
                        svc._install(cur, tenant_id, ctx, new, pid, "main_active", day, BY, "Cambio por falla", "field",
                                     f"BF-DEMO-{rng.randint(1000, 9999)}")
                        if (TODAY - day).days > 20:
                            cur.execute("UPDATE metering_event SET xm_status = 'reported', xm_reported_on = %s, xm_reported_by = %s "
                                        "WHERE point_id = %s AND type_code = 'meter_change_main' AND xm_status = 'pending'",
                                        (day + timedelta(days=rng.randint(2, 10)), BY, pid))
                    # Un medidor con el sello de la tapa retirado sin recalibrar (debe salir "vencida").
                    pid, _ = next(p for p in points if p[1] == "2")
                    cur.execute("SELECT equipment_id::text FROM equipment_installation WHERE point_id = %s AND position_code = 'main_active' "
                                "AND removed_on IS NULL", (pid,))
                    svc._record(cur, tenant_id, ctx, type_code="seal_removed", occurred_on=TODAY - timedelta(days=12), recorded_by=BY,
                                point_id=None, equipment_id=cur.fetchone()[0],
                                data=_fields(serial="SL000001", location="Tapa principal", main_cover=True),
                                notes="Sello roto encontrado en visita", source="field", external_ref="BF-DEMO-0001")
                    cur.execute("SELECT count(*) FROM equipment")
                    total_equipment = cur.fetchone()[0]
    print(f"Organización {ORG} creada ({tenant_id}): {POINTS} fronteras, {total_equipment} equipos, en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    seed(sys.argv[1])
