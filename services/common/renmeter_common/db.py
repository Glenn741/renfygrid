"""Contexto de tenant para Row-Level Security (ver docs/02-arquitectura-general.md SS5
y docs/03-diseno.md). Cada request autenticado fija el tenant de la sesion antes de
correr cualquier query; las politicas RLS de infra/db/migrations filtran solas.

NO EJECUTADO TODAVIA contra una instancia real (ver docs/05-ejecucion.md, Sprint 0) --
no hay Postgres disponible en el entorno donde se escribio este modulo. Escrito
para ser correcto por diseno; falta la primera corrida real antes de darlo por
verificado.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg


@contextmanager
def tenant_scope(conn: psycopg.Connection, tenant_id: str) -> Iterator[None]:
    """Fija app.tenant_id SOLO para la transaccion actual (SET LOCAL, no SET).

    SET LOCAL se revierte solo al terminar la transaccion -- a diferencia de SET,
    no puede "quedarse pegado" en una conexion que vuelve a un pool y se reusa
    para otro tenant. Esa es la razon de fondo para no usar SET a secas aca: un
    connection pool que reusara una conexion con el tenant_id de sesion anterior
    todavia seteado seria exactamente el tipo de fuga entre tenants que RLS
    existe para evitar.

    Uso:
        with conn.transaction():
            with tenant_scope(conn, tenant_id):
                cur.execute("SELECT * FROM meter")  # ya viene filtrado por RLS
    """
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.tenant_id', %s, true)", (tenant_id,))
    try:
        yield
    finally:
        # No hace falta "desfijar" nada: SET LOCAL expira solo al cerrar/commitear
        # la transaccion. Este finally queda para dejar explicito el contrato,
        # no porque haga limpieza real.
        pass


def current_tenant_id(conn: psycopg.Connection) -> str | None:
    """Util para pruebas/diagnostico: que tenant ve la sesion actual ahora mismo."""
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('app.tenant_id', true)")
        (value,) = cur.fetchone()
        return value
