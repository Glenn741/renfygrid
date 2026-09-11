"""Respaldo (F13, Sprint 9) -- wrapper sobre `pg_dump` en formato custom
(comprimido, restaurable con `pg_restore`) -- no reinventa un mecanismo de
backup propio, usa la herramienta nativa de Postgres (mismo principio que
Gurux/WNTR: no reimplementar lo que ya existe y esta probado).

Nada fijo: host/puerto/usuario/base/ruta de salida y hasta la ubicacion del
propio binario `pg_dump` llegan por argumento -- distinto entorno, distinta
instalacion de Postgres (portable en desarrollo, paquete del sistema en
produccion), sin que este script tenga que cambiar.

Uso:
    python backup.py --pg-bin-dir "C:\\...\\pgsql\\bin" --host localhost --port 5455 \
        --user renfygrid --password-env PGPASSWORD --dbname renfygrid \
        --output backups/renfygrid_2026-09-10.dump
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def backup(
    pg_bin_dir: Path, host: str, port: int, user: str, password: str, dbname: str, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    subprocess.run(
        [
            str(pg_bin_dir / "pg_dump.exe" if os.name == "nt" else pg_bin_dir / "pg_dump"),
            "-h", host, "-p", str(port), "-U", user, "-d", dbname,
            "-Fc",  # formato custom: comprimido, restaurable selectivamente con pg_restore
            "-f", str(output_path),
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
    parser.add_argument("--password-env", required=True, help="Nombre de la variable de entorno que trae la contraseña -- nunca la contraseña en un argumento")
    parser.add_argument("--dbname", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    password = os.environ.get(args.password_env)
    if not password:
        print(f"Falta la variable de entorno {args.password_env}", file=sys.stderr)
        return 2
    backup(args.pg_bin_dir, args.host, args.port, args.user, password, args.dbname, args.output)
    print(f"OK: respaldo escrito en {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
