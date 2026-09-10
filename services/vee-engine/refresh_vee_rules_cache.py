"""Job corto de "Config Loader" para las reglas VEE (F19, Sprint 3) -- lee
`vee_rule` de la BD y escribe el snapshot que `run_vee_pass.py` lee en
caliente. Se corre por separado del pase de validacion.

Uso:
    python refresh_vee_rules_cache.py --dsn "postgresql://..." \
        --tenant-id <uuid> --snapshot-path .cache/vee_rule/<tenant>.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vee_rules_cache import build_cache


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
    print(f"OK: {count} regla(s) VEE activa(s) escritas en {args.snapshot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
