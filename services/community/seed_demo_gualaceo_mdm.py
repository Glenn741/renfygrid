"""Contexto de MDM, balance hidrico y gemelo digital para la junta demo de
Gualaceo (tenant `jaas001`, a pedido del usuario 2026-10-05). Complementa
`seed_demo_guias_tenant.py` (perfil `gualaceo`), que ya cargo los
componentes, revisiones, hallazgos y mantenimiento de las Guias 3 y 4.

Escenario (ILUSTRATIVO, no una junta real): la junta instalo micromedicion
con lectura diaria por radio en sus 96 conexiones y un macromedidor a la
entrada de cada sector. Dos sectores por gravedad:
  - Sector alto: alimentado desde el reservorio de 40 m3 (~2590 msnm).
    El agua no facturada SUBE de 24% a 33% en 6 meses (baja presion,
    conexiones por verificar -- la misma historia de las guias) y supera
    el tope configurado (25%) -> genera una orden de mantenimiento real
    por `balance_anomaly`.
  - Sector bajo: alimentado desde un tanque rompepresion (~2480 msnm),
    estable alrededor de 18%.

Que crea:
  MDM      2 concentradores, 96 micromedidores (Elster, Zenner, Sensus,
           Itron) + 2 macromedidores, 180 dias de lectura diaria, 6% de
           faltantes (estimados por VEE) y 1% inconsistentes (excepciones;
           las 3 mas antiguas corregidas a mano por la tesoreria), eventos
           de comunicacion de las ultimas 48 h y algunas alarmas. Umbral de
           "medidor caido" de 36 h (lectura diaria).
  Balance  2 zonas DMA y 6 balances mensuales top-down por zona
           (consumo facturado, consumo autorizado no facturado de la
           escuela y la casa comunal, perdidas aparentes estimadas).
  Gemelo   Cotas reales de la zona en cada componente, sectores ligados a
           sus zonas, tanque rompepresion, valvula de sectorizacion y
           tramos de PVC con su diametro -- cada sector puede generar su
           modelo EPANET desde el gemelo.
  Nivel    Instrumentacion: medicion avanzada, balance y red intermedios.

Los modelos EPANET se registran por la API (ver
`network-model/demo/gualaceo_rural_sectores.inp`), no aca: el
almacenamiento de modelos es del servicio.

Si el tenant ya tiene medidores, no hace nada.

Uso:
    python seed_demo_gualaceo_mdm.py "<DSN>" "<TENANT_ID>"
"""

from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
for sub in ("common", "hes-adapter-dlms", "vee-engine", "network-balance", "digital-twin", "maintenance", "portal-api"):
    sys.path.insert(0, str(ROOT / sub))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from asset_service import connect_assets, register_asset  # noqa: E402
from balance_service import register_zone, submit_balance  # noqa: E402
from manual_edit import edit_reading  # noqa: E402
from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from order_service import generate_order  # noqa: E402
from pack_service import get_instrumentation, set_instrumentation  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from tenant_settings import set_meter_stale_after_seconds  # noqa: E402
from vee_engine import detect_gaps, estimate_gap, validate_reading  # noqa: E402
from vee_rules_admin import create_vee_rule  # noqa: E402

CHANNEL = "volume_m3"
MACRO_CHANNEL = "volume_m3_bulk"
INTERVAL_SECONDS = 86400
DAYS = 180
READ_HOUR_UTC = 11  # 06:00 hora de Ecuador
STALE_AFTER_SECONDS = 36 * 3600
NRW_THRESHOLD_PCT = 25.0  # tope ilustrativo configurado para la demo, no una norma de ARCA

BRANDS = [("Elster", ["V200", "V100"]), ("Zenner", ["MNK-N", "ETK-EAX"]),
          ("Sensus", ["620", "iPERL"]), ("Itron", ["Unimag Cyble"])]

SECTORS = [
    {"key": "alto", "name": "Sector alto (Gualaceo, ilustrativo)", "n_meters": 52,
     "center": (-78.7640, -2.8822), "macro": (-78.7621, -2.8808), "nrw_from": 24.0, "nrw_to": 33.0,
     "apparent_pct": 3.0, "length_km": 2.1, "pressure": 38.0},
    {"key": "bajo", "name": "Sector bajo (Gualaceo, ilustrativo)", "n_meters": 44,
     "center": (-78.7680, -2.8862), "macro": (-78.7660, -2.8842), "nrw_from": 18.5, "nrw_to": 17.5,
     "apparent_pct": 1.5, "length_km": 1.8, "pressure": 33.0},
]

# Cotas aproximadas (msnm) de los componentes de agua de la semilla de las guias.
ELEVATIONS = {
    "Vertiente de la microcuenca alta": 2700, "Captación de la vertiente": 2695, "Desarenador": 2690,
    "Conducción principal (cruce de quebrada)": 2640, "Válvula de tramo de la conducción": 2620,
    "Sedimentador": 2600, "Filtro lento de arena": 2598, "Hipoclorador por goteo": 2595,
    "Reservorio de 40 m³ de la comunidad": 2590, "Bodega de la junta en la casa comunal": 2592,
    "Red sector alto": 2550, "Red sector bajo": 2440,
}

random.seed(20261005)


def _days() -> list[datetime]:
    today = datetime.now(timezone.utc).replace(hour=READ_HOUR_UTC, minute=0, second=0, microsecond=0)
    if today > datetime.now(timezone.utc):
        today -= timedelta(days=1)
    return [today - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]


def _season(ts: datetime) -> float:
    """Estiaje de la sierra azuaya (jul-sep): algo mas de consumo."""
    return 1.12 if ts.month in (7, 8, 9) else 1.0


def _bulk(conn, tenant_id, sql, rows, batch=5000) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                for i in range(0, len(rows), batch):
                    cur.executemany(sql, rows[i:i + batch])


def _exec(conn, tenant_id, sql, params) -> list[tuple]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall() if cur.description else []


def _readings(conn, tenant_id, meter_id, channel, true_values, days, missing_p, bad_p, rules, missing_rule_id,
              recent_cutoff, events, edit_candidates):
    """Arma raw + validated para un medidor con la misma semantica del
    pipeline real (validate_reading / detect_gaps / estimate_gap)."""
    raw, val = [], []
    stored: list[float | None] = []
    for v in true_values:
        r = random.random()
        if r < missing_p:
            stored.append(None)
        elif r < missing_p + bad_p:
            stored.append(round(v * random.uniform(60, 400), 3))
        else:
            stored.append(round(v, 3))
    for ts, s in zip(days, stored):
        if s is not None:
            raw.append((tenant_id, meter_id, ts, channel, s, "real"))
        if ts >= recent_cutoff:
            ok = s is not None
            events.append((tenant_id, meter_id, "communication_success" if ok else "communication_failure", ts,
                           "info" if ok else "warning",
                           {"operation": "poller_read", "duration_ms": random.randint(300, 2500) if ok else None,
                            "error": None if ok else "timeout: sin respuesta del medidor (radio)"}))
    present = [(ts, s) for ts, s in zip(days, stored) if s is not None]
    for idx, (ts, s) in enumerate(present):
        vr = validate_reading(s, channel, rules)
        notes = vr.notes
        if not vr.is_valid and 0 < idx < len(present) - 1:
            (pts, pv), (nts, nv) = present[idx - 1], present[idx + 1]
            suggested = pv + (nv - pv) * (ts - pts).total_seconds() / (nts - pts).total_seconds()
            notes = f"{notes} -- valor sugerido por interpolación: {suggested:.2f} m³ (pendiente de validación)"
            edit_candidates.append((meter_id, channel, ts, suggested))
        val.append((tenant_id, meter_id, ts, s, "real", channel, vr.is_valid, vr.vee_rule_id, notes,
                    ts + timedelta(minutes=random.randint(2, 20))))
    for gap in detect_gaps(present, INTERVAL_SECONDS, tolerance_seconds=3600):
        for p in estimate_gap(gap, INTERVAL_SECONDS, "linear_interpolation"):
            val.append((tenant_id, meter_id, p.timestamp, round(p.value, 3), "estimated", channel, True, missing_rule_id,
                        "Estimado automáticamente (interpolación lineal) por lectura diaria faltante",
                        p.timestamp + timedelta(minutes=random.randint(2, 20))))
    return raw, val


def main(dsn: str, tenant_id: str) -> None:
    days = _days()
    recent_cutoff = days[-1] - timedelta(hours=48)
    with psycopg.connect(dsn, autocommit=True) as conn:
        if _exec(conn, tenant_id, "SELECT count(*) FROM meter WHERE tenant_id = %s", (tenant_id,))[0][0] > 0:
            print("El tenant ya tiene medidores -- no se modifica.")
            return

        # ── Gemelo: cotas, zonas, rompepresion, sectorizacion ─────────────
        assets = {r[1]: (str(r[0]), r[2]) for r in _exec(
            conn, tenant_id, "SELECT id, attributes->>'name', type FROM network_asset WHERE tenant_id = %s", (tenant_id,))}
        needed = ["Reservorio de 40 m³ de la comunidad", "Red sector alto", "Red sector bajo"]
        missing = [n for n in needed if n not in assets]
        if missing:
            print(f"Faltan componentes de la semilla de las guías (perfil gualaceo): {missing}")
            sys.exit(1)
        for name, elev in ELEVATIONS.items():
            if name in assets:
                extra = {"elevation_m": elev}
                if name == "Reservorio de 40 m³ de la comunidad":
                    extra["head_m"] = elev + 3  # lamina de agua ~3 m sobre la base
                _exec(conn, tenant_id, "UPDATE network_asset SET attributes = attributes || %s::jsonb WHERE id = %s AND tenant_id = %s",
                      (Json(extra), assets[name][0], tenant_id))

        zones = {}
        for s in SECTORS:
            zones[s["key"]] = register_zone(
                conn, tenant_id, s["name"], "dma", data_source="renfygrid", network_length_km=s["length_km"],
                num_connections=s["n_meters"], avg_pressure_mca=s["pressure"], nrw_threshold_pct=NRW_THRESHOLD_PCT,
                avg_service_connection_length_km=0.012, centroid_lon=s["center"][0], centroid_lat=s["center"][1],
            )
        tank = assets["Reservorio de 40 m³ de la comunidad"][0]
        net_high = assets["Red sector alto"][0]
        net_low = assets["Red sector bajo"][0]

        def new_asset(asset_type, name, zone, coords=None, **attrs):
            return register_asset(conn, tenant_id, asset_type, zone_id=zones[zone],
                                  attributes={"name": name, "system": "Sistema comunitario de agua y saneamiento — zona rural de Gualaceo, Azuay (ilustrativo)", **attrs},
                                  geometry={"type": "Point", "coordinates": list(coords)} if coords else None)["asset_id"]

        valve_high = new_asset("valve", "Válvula de sectorización sector alto", "alto", (-78.7621, -2.8808), elevation_m=2585)
        pipe_high = new_asset("pipe", "Línea PVC 63 mm sector alto", "alto", diameter_mm=63, roughness=150, material="PVC")
        breaker = new_asset("tank", "Tanque rompepresión sector bajo", "bajo", (-78.7660, -2.8842), elevation_m=2480, head_m=2483)
        pipe_low = new_asset("pipe", "Línea PVC 50 mm sector bajo", "bajo", diameter_mm=50, roughness=150, material="PVC")
        _exec(conn, tenant_id, "UPDATE network_asset SET zone_id = %s WHERE id = ANY(%s::uuid[]) AND tenant_id = %s",
              (zones["alto"], [tank, net_high], tenant_id))
        _exec(conn, tenant_id, "UPDATE network_asset SET zone_id = %s WHERE id = %s AND tenant_id = %s",
              (zones["bajo"], net_low, tenant_id))
        # Las conexiones directas reservorio->red de la semilla de las guias se
        # reemplazan por el trazado con sectorizacion y rompepresion.
        conn.execute(
            "DELETE FROM asset_connectivity WHERE source_asset_id = %s AND target_asset_id = ANY(%s::uuid[])",
            (tank, [net_high, net_low]),
        )
        for a, b, kind in ((tank, valve_high, "flow"), (valve_high, pipe_high, "flow"), (pipe_high, net_high, "flow"),
                           (tank, breaker, "conveyance"), (breaker, pipe_low, "flow"), (pipe_low, net_low, "flow")):
            connect_assets(conn, tenant_id, a, b, kind)
        print("Gemelo: cotas, 2 zonas, rompepresión, sectorización y tramos PVC")

        # ── MDM: reglas, concentradores, medidores ────────────────────────
        rules = {}
        for channel, max_v in ((CHANNEL, 20_000.0), (MACRO_CHANNEL, 2_000_000.0)):
            rid = create_vee_rule(conn, tenant_id, "range", {"channel": channel, "min": 0, "max": max_v}, priority=100)
            mid = create_vee_rule(conn, tenant_id, "missing_interval",
                                  {"channel": channel, "expected_interval_seconds": INTERVAL_SECONDS,
                                   "tolerance_seconds": 3600, "estimation_method": "linear_interpolation"}, priority=100)
            rules[channel] = ([{"id": rid, "type": "range", "params": {"channel": channel, "min": 0, "max": max_v}, "priority": 100}], mid)
        set_meter_stale_after_seconds(conn, tenant_id, STALE_AFTER_SECONDS)

        gateways = {s["key"]: register_gateway(conn, tenant_id, f"Concentrador radio {s['name'].split(' (')[0].lower()}", "TCP",
                                               {"host": f"10.80.{i + 1}.1", "port": 4059, "client_address": 16})
                    for i, s in enumerate(SECTORS)}

        all_raw, all_val, events, edit_candidates = [], [], [], []
        sector_daily: dict[str, dict] = {}
        n = 0
        for s in SECTORS:
            billed = [0.0] * DAYS
            unbilled = [0.0] * DAYS
            for k in range(s["n_meters"]):
                n += 1
                brand, models = BRANDS[n % len(BRANDS)]
                kind = "residential"
                if s["key"] == "bajo" and k == 0:
                    kind, label = "productive", "Quesera (uso productivo)"
                elif s["key"] == "alto" and k == 0:
                    kind, label = "institutional", "Escuela de la comunidad"
                elif s["key"] == "bajo" and k == 1:
                    kind, label = "institutional", "Casa comunal"
                elif k in (2, 3):
                    kind, label = "commercial", "Tienda"
                else:
                    label = "Vivienda"
                daily = {"residential": random.uniform(0.35, 0.75), "commercial": random.uniform(0.8, 1.4),
                         "institutional": random.uniform(1.2, 2.0), "productive": random.uniform(2.5, 4.0)}[kind]
                geom = [s["center"][0] + random.uniform(-0.0022, 0.0022), s["center"][1] + random.uniform(-0.0018, 0.0018)]
                meter_id = register_meter(
                    conn, tenant_id, f"JA-{n:04d}", f"SN-{brand[:3].upper()}-{30000 + n}", brand, "DLMS_COSEM",
                    model=models[k % len(models)],
                    location={"city": "Gualaceo", "province": "Azuay", "use": label, "note": "conexión ilustrativa"},
                    meter_type="micro", zone_id=zones[s["key"]], geometry={"type": "Point", "coordinates": geom},
                )
                link_meter_to_gateway(conn, tenant_id, meter_id, gateways[s["key"]], server_address=k + 1)
                cumulative = random.uniform(80.0, 1400.0)
                true_values = []
                for i, ts in enumerate(days):
                    delta = daily * _season(ts) * random.uniform(0.75, 1.25)
                    cumulative += delta
                    true_values.append(cumulative)
                    (unbilled if kind == "institutional" else billed)[i] += delta
                raw, val = _readings(conn, tenant_id, meter_id, CHANNEL, true_values, days, 0.06, 0.01,
                                     rules[CHANNEL][0], rules[CHANNEL][1], recent_cutoff, events, edit_candidates)
                all_raw += raw
                all_val += val
            sector_daily[s["key"]] = {"billed": billed, "unbilled": unbilled}

        # ── Macromedidores: entrada = consumo facturado / (1 - NRW del dia) ──
        # NRW en sentido IWA: entrada menos consumo autorizado FACTURADO (el
        # autorizado no facturado de la escuela y la casa comunal es parte del
        # agua no facturada, igual que lo calcula network_balance_engine).
        for i, s in enumerate(SECTORS):
            d = sector_daily[s["key"]]
            nrw_by_day = [s["nrw_from"] + (s["nrw_to"] - s["nrw_from"]) * j / (DAYS - 1) + random.uniform(-0.6, 0.6)
                          for j in range(DAYS)]
            inflow = [d["billed"][j] / (1 - nrw_by_day[j] / 100.0) for j in range(DAYS)]
            d["inflow"] = inflow
            macro_id = register_meter(
                conn, tenant_id, f"JA-MACRO-{s['key'].upper()}", f"SN-MAC-{i + 1:03d}", "Sensus", "DLMS_COSEM",
                model="MeiStream (macromedición)", meter_type="macro", zone_id=zones[s["key"]],
                location={"city": "Gualaceo", "province": "Azuay", "note": f"Macromedidor de entrada — {s['name']}"},
                geometry={"type": "Point", "coordinates": list(s["macro"])},
            )
            link_meter_to_gateway(conn, tenant_id, macro_id, gateways[s["key"]], server_address=200)
            cumulative = random.uniform(3000.0, 9000.0)
            true_values = []
            for v in inflow:
                cumulative += v
                true_values.append(cumulative)
            raw, val = _readings(conn, tenant_id, macro_id, MACRO_CHANNEL, true_values, days, 0.005, 0.001,
                                 rules[MACRO_CHANNEL][0], rules[MACRO_CHANNEL][1], recent_cutoff, events, edit_candidates)
            all_raw += raw
            all_val += val

        _bulk(conn, tenant_id, "INSERT INTO raw_reading (tenant_id, meter_id, \"timestamp\", channel, value, source_quality) "
                               "VALUES (%s, %s, %s, %s, %s, %s)", all_raw)
        _bulk(conn, tenant_id, "INSERT INTO validated_reading (tenant_id, meter_id, \"timestamp\", value, source, channel, is_valid, "
                               "vee_rule_id, validation_notes, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", all_val)
        _bulk(conn, tenant_id, "INSERT INTO meter_event (tenant_id, meter_id, type, \"timestamp\", severity, detail) "
                               "VALUES (%s, %s, %s, %s, %s, %s)",
              [(t, m, e, ts, sev, Json(det)) for t, m, e, ts, sev, det in events])
        meter_ids = [r[0] for r in _exec(conn, tenant_id, "SELECT id FROM meter WHERE tenant_id = %s AND meter_type = 'micro'", (tenant_id,))]
        _bulk(conn, tenant_id, "INSERT INTO meter_event (tenant_id, meter_id, type, \"timestamp\", severity, detail) "
                               "VALUES (%s, %s, 'meter_alarm', %s, %s, %s)",
              [(tenant_id, m, days[-1] - timedelta(hours=random.randint(2, 40)), random.choice(["warning", "critical"]),
                Json({"event_code": code, "severity_code": 1, "description": desc}))
               for m, (code, desc) in zip(random.sample(meter_ids, 3),
                                          [(3, "Flujo inverso detectado"), (7, "Intento de manipulación (imán)"), (12, "Batería baja")])])
        print(f"MDM: {n} micro + 2 macro, {len(all_raw)} lecturas, {len(all_val)} validadas, {len(events)} eventos")

        edit_candidates.sort(key=lambda c: c[2])
        for meter_id, channel, ts, suggested in edit_candidates[:3]:
            edit_reading(conn, tenant_id, str(meter_id), channel, ts, round(suggested, 3), "usr001@renfygrid.com",
                         "Corregido tras verificar la lectura en campo con el operador")
        print(f"Excepciones: {len(edit_candidates)} (3 corregidas a mano, {max(0, len(edit_candidates) - 3)} pendientes)")

        # ── Balance mensual top-down por sector ───────────────────────────
        for s in SECTORS:
            d = sector_daily[s["key"]]
            for p in range(6):
                lo, hi = p * 30, (p + 1) * 30
                siv = sum(d["inflow"][lo:hi])
                b = submit_balance(
                    conn, tenant_id, zones[s["key"]], days[lo].date(), days[hi - 1].date(), "top_down",
                    system_input_volume=round(siv, 1),
                    billed_metered_consumption=round(sum(d["billed"][lo:hi]), 1),
                    unbilled_authorized_consumption=round(sum(d["unbilled"][lo:hi]), 1),
                    apparent_losses=round(siv * s["apparent_pct"] / 100.0, 1),
                )
            print(f"Balance {s['name']}: último mes NRW {b['nrw_pct']}% (excede tope {NRW_THRESHOLD_PCT}%: {b['exceeds_threshold']})")

        order = generate_order(conn, tenant_id, net_high, "corrective", "balance_anomaly", "high",
                               "El agua no facturada del sector alto supera el tope: buscar fugas y conexiones no autorizadas.")
        print(f"Orden por anomalía de balance: {order['order_id']}")

        set_instrumentation(conn, tenant_id, {**get_instrumentation(conn, tenant_id), "metering": "advanced",
                                              "water_balance": "intermediate", "network": "intermediate", "billing": "intermediate"})
        print("Listo.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
