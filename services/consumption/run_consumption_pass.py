"""Pase de Gestion de Consumos (F21/F22/F23, Sprint 5): por cada medidor con
un canal facturable configurado (`meter_protocol.obis_mapping`, un canal
marcado `"billable": true` -- mismo mapeo de Sprint 2, sin tabla nueva),
agrega las lecturas validadas de un periodo en un consumo (cierre menos
apertura, ver `consumption_engine.py`), lo compara contra el periodo
anterior del mismo medidor, y si se desvia mas de lo configurado
(`consumption_anomaly_rule`) genera la orden correspondiente
(`meter_event`, F23 -- se reusa esa tabla en vez de crear una nueva).

Uso:
    python run_consumption_pass.py --dsn "postgresql://..." --tenant-id <uuid> \
        --period-start 2026-09-01 --period-end 2026-10-01 \
        --consumption-rules-snapshot .cache/consumption_anomaly_rule/<tenant>.json
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.range import Range  # noqa: E402

from consumption_engine import compute_consumption, detect_deviation  # noqa: E402
from consumption_rules_cache import ConfigCache  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def billable_meters(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    """Cada medidor activo con un canal marcado `"billable": true` en el
    mapeo OBIS vigente de su marca/modelo."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT m.id, mp.obis_mapping FROM meter m "
                    "JOIN meter_protocol mp ON mp.tenant_id = m.tenant_id "
                    "  AND mp.brand = m.brand AND mp.model = m.model AND mp.valid_to IS NULL "
                    "WHERE m.tenant_id = %s AND m.status = 'active'",
                    (tenant_id,),
                )
                result = []
                for meter_id, obis_mapping in cur.fetchall():
                    billable_channel = next(
                        (channel for channel, mapping in obis_mapping.items() if mapping.get("billable")),
                        None,
                    )
                    if billable_channel:
                        result.append({"meter_id": str(meter_id), "channel": billable_channel})
                return result


def boundary_value(conn: psycopg.Connection, tenant_id: str, meter_id: str, channel: str, before) -> float | None:
    """El valor de la ultima lectura validada valida ANTES de `before` --
    None si no hay ninguna (ver IncompleteBillingDataError en el llamador)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM validated_reading "
                    "WHERE meter_id = %s AND channel = %s AND is_valid AND \"timestamp\" < %s "
                    "ORDER BY \"timestamp\" DESC LIMIT 1",
                    (meter_id, channel, before),
                )
                row = cur.fetchone()
                return float(row[0]) if row else None


def previous_consumption(conn: psycopg.Connection, tenant_id: str, meter_id: str, period: Range) -> float | None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM consumption WHERE meter_id = %s AND period << %s "
                    "ORDER BY period DESC LIMIT 1",
                    (meter_id, period),
                )
                row = cur.fetchone()
                return float(row[0]) if row else None


def insert_consumption_and_maybe_order(
    conn: psycopg.Connection, tenant_id: str, meter_id: str, period: Range, value: float, deviation
) -> None:
    anomaly_status = "under_review" if deviation.is_anomalous else "ok"
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO consumption (tenant_id, meter_id, period, value, anomaly_status) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, meter_id, period, value, anomaly_status),
                )
                (consumption_id,) = cur.fetchone()
                if deviation.is_anomalous:
                    cur.execute(
                        "INSERT INTO meter_event (tenant_id, meter_id, type, severity, consumption_id) "
                        "VALUES (%s, %s, %s, 'warning', %s)",
                        (tenant_id, meter_id, deviation.action, consumption_id),
                    )


def run_once(dsn: str, tenant_id: str, period_start: date, period_end: date, rules_cache: ConfigCache) -> None:
    rules_cache.load()
    rules = rules_cache.get_all()
    period = Range(period_start, period_end, bounds="[)")
    with psycopg.connect(dsn, autocommit=True) as conn:
        meters = billable_meters(conn, tenant_id)
        print(f"Pase de consumo {period}: {len(meters)} medidor(es) facturable(s)")
        for meter in meters:
            opening = boundary_value(conn, tenant_id, meter["meter_id"], meter["channel"], period_start)
            closing = boundary_value(conn, tenant_id, meter["meter_id"], meter["channel"], period_end)
            if opening is None or closing is None:
                print(f"  SIN DATOS SUFICIENTES meter_id={meter['meter_id']}: falta lectura de apertura o cierre")
                continue
            value = compute_consumption(opening, closing)
            previous = previous_consumption(conn, tenant_id, meter["meter_id"], period)
            deviation = detect_deviation(value, previous, rules)
            insert_consumption_and_maybe_order(conn, tenant_id, meter["meter_id"], period, value, deviation)
            flag = f" -- ANOMALO ({deviation.action}, {deviation.deviation_pct:.1f}%)" if deviation.is_anomalous else ""
            print(f"  meter_id={meter['meter_id']}: consumo={value}{flag}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--period-start", required=True, type=date.fromisoformat)
    parser.add_argument("--period-end", required=True, type=date.fromisoformat)
    parser.add_argument("--consumption-rules-snapshot", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rules_cache = ConfigCache(
        fetch_fn=lambda: [],
        snapshot_path=Path(args.consumption_rules_snapshot),
        source_name="consumption_anomaly_rule",
    )
    run_once(args.dsn, args.tenant_id, args.period_start, args.period_end, rules_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
