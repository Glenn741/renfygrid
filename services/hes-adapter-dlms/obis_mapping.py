"""Mapeo OBIS configurable por marca/modelo, cacheado (F06, Sprint 2).

Mismo patron "configuracion cacheada" que `renmeter_common.config_cache`
(docs/03-diseno.md SS2): `meter_protocol` (BD) es la fuente de verdad; un
snapshot en disco -- refrescado por `refresh_obis_mapping_cache.py`, un job
corto separado -- es lo unico que el poller lee en caliente. Cambiar el
mapeo de una marca/modelo en BD y correr el refresh no requiere tocar ni
desplegar `poller.py`.

Forma de `meter_protocol.obis_mapping` (jsonb): un objeto por canal, ej.
    {"active_energy": {"obis_code": "1.0.1.8.0.255", "attribute_index": 2},
     "reactive_energy": {"obis_code": "1.0.1.3.8.0.255", "attribute_index": 2}}
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.config_cache import ConfigCache  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def fetch_active_obis_mappings(conn: psycopg.Connection, tenant_id: str) -> list[dict[str, Any]]:
    """Solo el mapeo vigente por marca/modelo (`valid_to IS NULL`) -- ver el
    patron de configuracion versionada en 0001_init.sql."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT brand, model, protocol, obis_mapping FROM meter_protocol "
                    "WHERE tenant_id = %s AND valid_to IS NULL",
                    (tenant_id,),
                )
                return [
                    {"brand": row[0], "model": row[1], "protocol": row[2], "obis_mapping": row[3]}
                    for row in cur.fetchall()
                ]


def build_cache(snapshot_path: Path, dsn: str, tenant_id: str) -> ConfigCache:
    def fetch_fn() -> list[dict[str, Any]]:
        with psycopg.connect(dsn, autocommit=True) as conn:
            return fetch_active_obis_mappings(conn, tenant_id)

    return ConfigCache(fetch_fn=fetch_fn, snapshot_path=snapshot_path, source_name="obis_mapping")


def channels_for(cache: ConfigCache, brand: str, model: str) -> dict[str, dict]:
    """{channel: {obis_code, attribute_index}} para esa marca/modelo, o {} si
    no hay mapeo vigente -- el llamador (poller.py) decide que hacer con eso
    (no lee nada de un medidor sin mapeo, en vez de asumir un default)."""
    rows = cache.get(brand=brand, model=model)
    if not rows:
        return {}
    return rows[-1]["obis_mapping"]
