"""Job corto de "Config Loader" (docs/03-diseno.md SS2) para el mapeo OBIS
(F06, Sprint 2): lee `meter_protocol` de la BD y escribe el snapshot que
`poller.py` lee en caliente. Se corre por separado del poller -- a mano,
por cron, o disparado por una notificacion de cambio en BD -- nunca dentro
del ciclo de lectura (por eso el poller nunca toca `meter_protocol`
directamente).

Uso:
    python refresh_obis_mapping_cache.py --dsn "postgresql://..." \
        --tenant-id <uuid> --snapshot-path .cache/obis_mapping/<tenant>.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from obis_mapping import build_cache


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--snapshot-path", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cache = build_cache(Path(args.snapshot_path), args.dsn, args.tenant_id)
    count = cache.refresh()
    print(f"OK: {count} mapeo(s) OBIS activo(s) escritos en {args.snapshot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
