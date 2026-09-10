"""Verificacion end-to-end de Row-Level Security para RenfyGrid.

NO EJECUTADO TODAVIA -- requiere una instancia Postgres real con 0001_init.sql
ya aplicado (ver docker-compose.yml en la raiz del repo). Escrito ahora para
que correrlo sea el primer paso en cuanto haya una instancia disponible, en vez
de dejar la verificacion de RLS para mas adelante sin nada preparado.

Que prueba, en espanol llano:
  1. Crea dos tenants de prueba.
  2. Como tenant A, inserta un medidor.
  3. Como tenant B, intenta leer los medidores -- debe ver CERO filas.
  4. Como tenant A de nuevo, confirma que si ve su propio medidor.
  5. Limpia los datos de prueba.

Si el paso 3 devuelve algo distinto de cero filas, RLS no esta aislando
correctamente y el script termina con exit code 1 -- pensado para correr en
CI antes de cualquier despliegue, no solo a mano.

Uso:
    python infra/db/verify_rls.py "postgresql://renfygrid:renfygrid_dev_only@localhost:5432/renfygrid"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "common"))

import psycopg  # noqa: E402  (import despues del sys.path.insert a proposito)

from renmeter_common.db import tenant_scope  # noqa: E402


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant (name) VALUES (%s), (%s) "
                "RETURNING id, name",
                ("RLS test A", "RLS test B"),
            )
            rows = cur.fetchall()
            tenant_a_id, tenant_b_id = (str(r[0]) for r in rows)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_a_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-TEST-A', 'SER-A', 'test-brand', 'DLMS_COSEM')",
                            (tenant_a_id,),
                        )

            with conn.transaction():
                with tenant_scope(conn, tenant_b_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM meter")
                        (count_seen_by_b,) = cur.fetchone()

            with conn.transaction():
                with tenant_scope(conn, tenant_a_id):
                    with conn.cursor() as cur:
                        cur.execute("SELECT count(*) FROM meter")
                        (count_seen_by_a,) = cur.fetchone()

            print(f"Tenant B ve {count_seen_by_b} medidor(es) de tenant A (esperado: 0)")
            print(f"Tenant A ve {count_seen_by_a} medidor(es) propio(s) (esperado: 1)")

            ok = count_seen_by_b == 0 and count_seen_by_a == 1
            print("RLS OK -- aislamiento entre tenants confirmado" if ok else "RLS FALLA -- ver conteos arriba")
            return 0 if ok else 1
        finally:
            # La limpieza debe borrar DENTRO del contexto de cada tenant -- con
            # FORCE ROW LEVEL SECURITY activo (ver 0001_init.sql), un DELETE sin
            # tenant_scope fijado falla al evaluar la politica (app.tenant_id
            # vacio no castea a uuid). Es el comportamiento correcto: ni siquiera
            # la limpieza del script se salta el aislamiento.
            with conn.transaction():
                with tenant_scope(conn, tenant_a_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_a_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id IN (%s, %s)", (tenant_a_id, tenant_b_id))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
