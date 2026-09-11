"""Recuperacion (F13, Sprint 9) -- wrapper sobre `pg_restore` contra un
respaldo hecho con `backup.py` (formato custom). Restaura sobre una base ya
creada y vacia (`--dbname`) -- este script NO crea la base, para no darle a
un script de recuperacion el poder de crear infraestructura por su cuenta
sin que alguien lo haya decidido explicitamente.

Uso:
    python restore.py --pg-bin-dir "C:\\...\\pgsql\\bin" --host localhost --port 5455 \
        --user renfygrid --password-env PGPASSWORD --dbname renfygrid_restore_test \
        --input backups/renfygrid_2026-09-10.dump
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def restore(
    pg_bin_dir: Path, host: str, port: int, user: str, password: str, dbname: str, input_path: Path
) -> None:
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    subprocess.run(
        [
            str(pg_bin_dir / "pg_restore.exe" if os.name == "nt" else pg_bin_dir / "pg_restore"),
            "-h", host, "-p", str(port), "-U", user, "-d", dbname,
            "--no-owner",  # el rol del entorno de restauracion puede no ser el mismo que el del respaldo
            str(input_path),
        ],
        env=env,
        check=True,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin-dir", required=True, type=Path)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--dbname", required=True)
    parser.add_argument("--input", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    password = os.environ.get(args.password_env)
    if not password:
        print(f"Falta la variable de entorno {args.password_env}", file=sys.stderr)
        return 2
    restore(args.pg_bin_dir, args.host, args.port, args.user, password, args.dbname, args.input)
    print(f"OK: restaurado {args.input} en la base {args.dbname}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
