"""Pase de validacion VEE (F14/F15, Sprint 3): toma las lecturas de
`raw_reading` que todavia no tienen fila en `validated_reading` para ese
mismo (medidor, canal, timestamp), les aplica las reglas activas cacheadas
(`vee_rules_cache.py`) y escribe el resultado -- `is_valid` + `vee_rule_id`
trazable (F19) si una regla de rango se aplico.

Se puede correr una vez (`--iterations 1`, ej. desde un cron) o en un
intervalo (mismo patron que `poller.py` de Sprint 1/2) -- pensado para
correr *despues* del poller en el pipeline real, nunca antes.

Uso:
    python run_vee_pass.py --dsn "postgresql://..." --tenant-id <uuid> \
        --vee-rules-snapshot .cache/vee_rule/<tenant>.json \
        --interval-seconds 30 --iterations 1
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402
from vee_engine import channel_consistency_rule_for, validate_reading  # noqa: E402
from vee_rules_cache import ConfigCache  # noqa: E402


def unvalidated_readings(conn: psycopg.Connection, tenant_id: str) -> list[dict]:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.meter_id, r.channel, r.\"timestamp\", r.value "
                    "FROM raw_reading r "
                    "WHERE r.tenant_id = %s AND NOT EXISTS ("
                    "    SELECT 1 FROM validated_reading v "
                    "    WHERE v.meter_id = r.meter_id AND v.channel = r.channel "
                    "    AND v.\"timestamp\" = r.\"timestamp\""
                    ")",
                    (tenant_id,),
                )
                return [
                    {"meter_id": str(row[0]), "channel": row[1], "timestamp": row[2], "value": row[3]}
                    for row in cur.fetchall()
                ]


def reference_channel_value(
    conn: psycopg.Connection, tenant_id: str, meter_id: str, channel: str, timestamp
) -> float | None:
    """Lectura CRUDA (no necesita estar validada todavia) del canal de
    referencia, mismo medidor, mismo instante -- fuente real para
    `channel_consistency` (F15, Sprint C11). None si ese canal no reporto en
    ese instante exacto (los canales no siempre se leen en el mismo ciclo)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM raw_reading "
                    "WHERE tenant_id = %s AND meter_id = %s AND channel = %s AND \"timestamp\" = %s",
                    (tenant_id, meter_id, channel, timestamp),
                )
                row = cur.fetchone()
                return float(row[0]) if row else None


def insert_validated_reading(
    conn: psycopg.Connection, tenant_id: str, reading: dict, result
) -> None:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO validated_reading "
                    "(tenant_id, meter_id, channel, \"timestamp\", value, source, "
                    " vee_rule_id, is_valid, validation_notes) "
                    "VALUES (%s, %s, %s, %s, %s, 'real', %s, %s, %s) "
                    "ON CONFLICT (meter_id, channel, \"timestamp\") DO NOTHING",
                    (
                        tenant_id,
                        reading["meter_id"],
                        reading["channel"],
                        reading["timestamp"],
                        reading["value"],
                        result.vee_rule_id,
                        result.is_valid,
                        result.notes,
                    ),
                )


def run_once(dsn: str, tenant_id: str, rules_cache: ConfigCache) -> None:
    rules_cache.load()  # hot-reload: un refresh corrido aparte ya se refleja aca
    rules = rules_cache.get_all()
    with psycopg.connect(dsn, autocommit=True) as conn:
        readings = unvalidated_readings(conn, tenant_id)
        print(f"Pase VEE: {len(readings)} lectura(s) sin validar")
        valid_count = 0
        invalid_count = 0
        for reading in readings:
            reference_value = None
            consistency_rule = channel_consistency_rule_for(rules, reading["channel"])
            if consistency_rule is not None:
                reference_value = reference_channel_value(
                    conn, tenant_id, reading["meter_id"], consistency_rule["params"]["reference_channel"], reading["timestamp"]
                )
            result = validate_reading(reading["value"], reading["channel"], rules, reference_value=reference_value)
            insert_validated_reading(conn, tenant_id, reading, result)
            if result.is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                print(f"  FUERA DE RANGO/INVALIDA meter_id={reading['meter_id']} channel={reading['channel']}: {result.notes}")
        print(f"  {valid_count} valida(s), {invalid_count} invalida(s)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--vee-rules-snapshot", required=True)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="0 = corre indefinidamente; >=1 = corre N ciclos y termina (default 1)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rules_cache = ConfigCache(
        fetch_fn=lambda: [],  # este proceso nunca llama a fetch_fn: solo hace load() del snapshot
        snapshot_path=Path(args.vee_rules_snapshot),
        source_name="vee_rule",
    )
    count = 0
    while True:
        run_once(args.dsn, args.tenant_id, rules_cache)
        count += 1
        if args.iterations and count >= args.iterations:
            return 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
