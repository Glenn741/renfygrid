"""Pase de deteccion de intervalos faltantes + estimacion (F16/F17, Sprint 4):
por cada canal con una regla `missing_interval` configurada, mira las
lecturas ya validadas (reales o estimadas -- para no volver a estimar un
hueco que un pase anterior ya lleno), detecta huecos y los llena con el
metodo configurado en la regla.

Se corre *despues* de `run_vee_pass.py` (necesita lecturas ya validadas para
saber donde estan los huecos), nunca antes.

Uso:
    python run_vee_estimation.py --dsn "postgresql://..." --tenant-id <uuid> \
        --vee-rules-snapshot .cache/vee_rule/<tenant>.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from vee_engine import InsufficientHistoryError, detect_gaps, estimate_gap, missing_interval_rule_for  # noqa: E402
from vee_rules_cache import ConfigCache  # noqa: E402


def meters_and_channels(conn: psycopg.Connection, tenant_id: str) -> list[tuple[str, str]]:
    """Cada (meter_id, channel) que tiene al menos una lectura validada --
    no tiene sentido buscar huecos donde nunca hubo ninguna lectura."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT meter_id, channel FROM validated_reading WHERE tenant_id = %s",
                    (tenant_id,),
                )
                return [(str(row[0]), row[1]) for row in cur.fetchall()]


def ordered_readings(conn: psycopg.Connection, tenant_id: str, meter_id: str, channel: str) -> list[tuple]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT \"timestamp\", value FROM validated_reading "
                    "WHERE meter_id = %s AND channel = %s ORDER BY \"timestamp\"",
                    (meter_id, channel),
                )
                return [(row[0], float(row[1])) for row in cur.fetchall()]


def other_meters_readings(
    conn: psycopg.Connection, tenant_id: str, channel: str, exclude_meter_id: str, start, end
) -> list[tuple]:
    """Lecturas validadas de OTROS medidores (mismo canal, ventana del hueco)
    -- fuente real para `similar_customers_average` (F17, Sprint C11)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT \"timestamp\", value FROM validated_reading "
                    "WHERE tenant_id = %s AND channel = %s AND meter_id != %s "
                    "AND \"timestamp\" BETWEEN %s AND %s",
                    (tenant_id, channel, exclude_meter_id, start, end),
                )
                return [(row[0], float(row[1])) for row in cur.fetchall()]


def insert_estimated_reading(
    conn: psycopg.Connection, tenant_id: str, meter_id: str, channel: str, timestamp, value: float, vee_rule_id: str
) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO validated_reading "
                    "(tenant_id, meter_id, channel, \"timestamp\", value, source, vee_rule_id, is_valid) "
                    "VALUES (%s, %s, %s, %s, %s, 'estimated', %s, true) "
                    "ON CONFLICT (meter_id, channel, \"timestamp\") DO NOTHING",
                    (tenant_id, meter_id, channel, timestamp, value, vee_rule_id),
                )


def run_once(dsn: str, tenant_id: str, rules_cache: ConfigCache) -> None:
    rules_cache.load()
    rules = rules_cache.get_all()
    with psycopg.connect(dsn, autocommit=True) as conn:
        pairs = meters_and_channels(conn, tenant_id)
        print(f"Pase de estimacion: {len(pairs)} par(es) medidor/canal con lecturas")
        total_estimated = 0
        for meter_id, channel in pairs:
            rule = missing_interval_rule_for(rules, channel)
            if rule is None:
                continue
            readings = ordered_readings(conn, tenant_id, meter_id, channel)
            gaps = detect_gaps(
                readings,
                expected_interval_seconds=rule["params"]["expected_interval_seconds"],
                tolerance_seconds=rule["params"].get("tolerance_seconds", 0),
            )
            method = rule["params"].get("estimation_method", "linear_interpolation")
            for gap in gaps:
                # `historical_readings` solo se calcula para los metodos que
                # de verdad lo necesitan (F17, Sprint C11) -- linear_interpolation
                # no toca la BD de mas.
                historical_readings = None
                if method == "customer_historical_average":
                    historical_readings = readings
                elif method == "similar_customers_average":
                    historical_readings = other_meters_readings(
                        conn, tenant_id, channel, meter_id, gap.after_timestamp, gap.before_timestamp
                    )
                try:
                    points = estimate_gap(
                        gap,
                        expected_interval_seconds=rule["params"]["expected_interval_seconds"],
                        method=method,
                        historical_readings=historical_readings,
                    )
                except InsufficientHistoryError as exc:
                    # Sin historial real para promediar: se deja el hueco sin
                    # rellenar en este pase (se reintenta en el siguiente,
                    # cuando haya mas lecturas) en vez de adivinar un valor.
                    print(f"  meter_id={meter_id} channel={channel}: {exc}")
                    continue
                for point in points:
                    insert_estimated_reading(conn, tenant_id, meter_id, channel, point.timestamp, point.value, rule["id"])
                total_estimated += len(points)
                print(f"  meter_id={meter_id} channel={channel}: hueco de {gap.missing_count} lectura(s) estimado")
        print(f"  {total_estimated} lectura(s) estimada(s) en total")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--vee-rules-snapshot", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rules_cache = ConfigCache(
        fetch_fn=lambda: [],
        snapshot_path=Path(args.vee_rules_snapshot),
        source_name="vee_rule",
    )
    run_once(args.dsn, args.tenant_id, rules_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
