"""Verificacion end-to-end real de F13 (respaldo y recuperacion), Sprint 9
-- corre `pg_dump`/`pg_restore` de verdad, no simula el comando.

Por seguridad, restaura a una base TEMPORAL separada
(`renfygrid_restore_test_e2e`), nunca sobre la base de desarrollo en uso
(que tiene datos de demo reales para que el usuario los vea en DBeaver) --
un restore real de disaster-recovery tambien se prueba primero contra una
instancia separada, no directo sobre produccion.

Que prueba, en espanol llano:
  1. Inserta un tenant marcador en la base real.
  2. Corre `backup.py` -- respaldo real de toda la base.
  3. Crea una base temporal vacia y corre `restore.py` sobre ella.
  4. Confirma que el tenant marcador esta en la base restaurada, con el
     mismo nombre -- el respaldo capturo el dato real, y el restore lo trajo
     de vuelta en un lugar limpio.
  5. Limpia: borra el tenant marcador de la base real, la base temporal, y
     el archivo de respaldo.

Uso:
    python verify_backup_restore_end_to_end.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backup import backup  # noqa: E402
from restore import restore  # noqa: E402

PG_BIN_DIR = Path(__file__).resolve().parents[2] / ".devdb" / "pgsql" / "bin"
HOST = "localhost"
PORT = 5455
ADMIN_USER = "renfygrid"
ADMIN_PASSWORD = "renfygrid_dev_only"
DBNAME = "renfygrid"
TEMP_DBNAME = "renfygrid_restore_test_e2e"
MARKER_TENANT_NAME = "E2E Backup Restore Sprint9"


def run() -> int:
    admin_dsn = f"postgresql://{ADMIN_USER}:{ADMIN_PASSWORD}@{HOST}:{PORT}/{DBNAME}"

    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", (MARKER_TENANT_NAME,))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dump_path = Path(tmp_dir) / "renfygrid.dump"
            backup(PG_BIN_DIR, HOST, PORT, ADMIN_USER, ADMIN_PASSWORD, DBNAME, dump_path)
            print(f"Respaldo real generado: {dump_path} ({dump_path.stat().st_size} bytes)")

            postgres_dsn = f"postgresql://{ADMIN_USER}:{ADMIN_PASSWORD}@{HOST}:{PORT}/postgres"
            with psycopg.connect(postgres_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute(f'DROP DATABASE IF EXISTS "{TEMP_DBNAME}"')
                    cur.execute(f'CREATE DATABASE "{TEMP_DBNAME}"')

            restore(PG_BIN_DIR, HOST, PORT, ADMIN_USER, ADMIN_PASSWORD, TEMP_DBNAME, dump_path)
            print(f"Restauracion real corrida sobre base temporal: {TEMP_DBNAME}")

            temp_dsn = f"postgresql://{ADMIN_USER}:{ADMIN_PASSWORD}@{HOST}:{PORT}/{TEMP_DBNAME}"
            with psycopg.connect(temp_dsn, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM tenant WHERE id = %s", (tenant_id,))
                    row = cur.fetchone()

            ok = row is not None and row[0] == MARKER_TENANT_NAME
            print(f"Tenant marcador en la base restaurada: {row} (esperado: ('{MARKER_TENANT_NAME}',))")
            print("F13 OK -- respaldo y recuperacion reales confirmados" if ok else "F13 FALLA")
            return 0 if ok else 1
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))
        postgres_dsn = f"postgresql://{ADMIN_USER}:{ADMIN_PASSWORD}@{HOST}:{PORT}/postgres"
        with psycopg.connect(postgres_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(f'DROP DATABASE IF EXISTS "{TEMP_DBNAME}"')


if __name__ == "__main__":
    sys.exit(run())
