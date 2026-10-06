"""Apoyo para las pruebas end-to-end (2026-10-06, migracion 0046).

Desde la 0046 una organizacion nueva nace solo con el nucleo: el pais y el
programa se eligen al crearla. Las pruebas que ejercitan el contenido del
programa Municipios Azules (Ecuador) lo adoptan explicitamente aqui, igual que
lo haria una organizacion real al darse de alta.
"""

from __future__ import annotations

import psycopg

from renmeter_common.db import tenant_scope

PROGRAM_PACKS = ("EC-ARCA", "EC-MUNICIPIOS-AZULES")


def adopt_program_packs(conn: psycopg.Connection, *tenant_ids: str, packs: tuple[str, ...] = PROGRAM_PACKS) -> None:
    for tid in tenant_ids:
        with conn.transaction():
            with tenant_scope(conn, tid):
                for pack in packs:
                    conn.execute("INSERT INTO tenant_pack (tenant_id, pack_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (tid, pack))
