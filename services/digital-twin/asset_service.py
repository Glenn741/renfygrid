"""Servicio de Gemelo Digital (Track B, Sprint B5, F42,
`docs/07-track-b-alcance-funcional.md` SS5) -- inventario de activos de
red (`network_asset`) y su conectividad (`asset_connectivity`). Esquema
ya existia desde `0001_init.sql` (Sprint 0) -- este sprint construye el
codigo encima, sin migracion.

Catastro operativo minimo, no un SIG completo (`07-track-b-alcance-funcional.md`
SS6) -- un cliente que ya tiene ArcGIS/QGIS sigue usandolo; esto es lo
suficiente para vincular Balance de Red (`zone_id`) y, mas adelante,
Mantenimiento (`maintenance_order.asset_id`, B7) con activos reales.

Hallazgo real de seguridad, documentado antes de escribir el codigo:
`asset_connectivity` NO tiene RLS propio ni `tenant_id` (el comentario de
`0001_init.sql` dice "inherits isolation from network_asset via join") --
toda lectura/escritura de conectividad DEBE verificar explicitamente que
ambos extremos pertenecen al tenant via `network_asset` (que si tiene
RLS), nunca confiar en un par de IDs sueltos del cliente."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402
from psycopg.types.json import Json  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402

ASSET_TYPES = {"pipe", "valve", "tank", "pump", "meter", "sensor"}
ASSET_STATUSES = {"operational", "out_of_service", "maintenance"}


class InvalidAssetTypeError(ValueError):
    """`type` fuera de los 6 tipos reales del catastro (`0001_init.sql`) --
    nunca se acepta un tipo libre que despues no se pueda filtrar/mostrar
    con sentido."""


class InvalidAssetStatusError(ValueError):
    """`status` fuera de los 3 estados reales del catastro."""


class AssetNotFoundError(LookupError):
    """No existe ese `network_asset` para este tenant."""


def register_asset(
    conn: psycopg.Connection,
    tenant_id: str,
    asset_type: str,
    zone_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    geometry: dict[str, Any] | None = None,
    status: str = "operational",
) -> dict[str, Any]:
    """Registra un activo real -- propio o cargado desde un SIG externo
    (`data_source` no existe como columna propia aca: un catastro externo
    trae su propio codigo, que va en `attributes` -- ej.
    `{"external_code": "VLV-04821"}`, nunca un campo especial inventado).
    `geometry`: un objeto GeoJSON (`{"type": "Point", "coordinates": [lon, lat]}`)
    si se conoce -- `None` si no, nunca una coordenada inventada."""
    if asset_type not in ASSET_TYPES:
        raise InvalidAssetTypeError(f"Tipo de activo invalido: {asset_type!r} (validos: {sorted(ASSET_TYPES)})")
    if status not in ASSET_STATUSES:
        raise InvalidAssetStatusError(f"Estado de activo invalido: {status!r} (validos: {sorted(ASSET_STATUSES)})")

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO network_asset (tenant_id, zone_id, type, attributes, geometry, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (tenant_id, zone_id, asset_type, Json(attributes or {}), Json(geometry) if geometry else None, status),
                )
                (asset_id,) = cur.fetchone()
    return {"asset_id": str(asset_id)}


def _asset_row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "asset_id": str(row[0]), "zone_id": str(row[1]) if row[1] else None, "type": row[2],
        "attributes": row[3], "geometry": row[4], "status": row[5],
        "version": row[6], "valid_from": row[7].isoformat(),
    }


def list_assets(
    conn: psycopg.Connection, tenant_id: str, zone_id: str | None = None, asset_type: str | None = None
) -> list[dict]:
    clauses = []
    params: list[Any] = [tenant_id]
    if zone_id:
        clauses.append("AND zone_id = %s")
        params.append(zone_id)
    if asset_type:
        clauses.append("AND type = %s")
        params.append(asset_type)
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, zone_id, type, attributes, geometry, status, version, valid_from "
                    f"FROM network_asset WHERE tenant_id = %s {' '.join(clauses)} ORDER BY valid_from DESC",
                    params,
                )
                rows = cur.fetchall()
    return [_asset_row_to_dict(row) for row in rows]


def _asset_belongs_to_tenant(conn: psycopg.Connection, tenant_id: str, asset_id: str) -> bool:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM network_asset WHERE id = %s AND tenant_id = %s", (asset_id, tenant_id))
                return cur.fetchone() is not None


def get_asset_detail(conn: psycopg.Connection, tenant_id: str, asset_id: str) -> dict[str, Any]:
    """El activo + su conectividad real (Sprint B5: "Un activo cargado via
    API queda visible con su conectividad")."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, zone_id, type, attributes, geometry, status, version, valid_from "
                    "FROM network_asset WHERE id = %s AND tenant_id = %s",
                    (asset_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise AssetNotFoundError(f"No existe el activo {asset_id} para este tenant")
    asset = _asset_row_to_dict(row)
    asset["connectivity"] = asset_connectivity(conn, tenant_id, asset_id)
    return asset


def update_asset_status(conn: psycopg.Connection, tenant_id: str, asset_id: str, status: str) -> dict[str, Any]:
    """Cambia el estado de un activo real -- sube `version`, nunca
    sobrescribe en silencio (mismo criterio de versionado por UPDATE que
    el resto de catalogos con historial ligero del proyecto)."""
    if status not in ASSET_STATUSES:
        raise InvalidAssetStatusError(f"Estado de activo invalido: {status!r} (validos: {sorted(ASSET_STATUSES)})")
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE network_asset SET status = %s, version = version + 1, valid_from = now() "
                    "WHERE id = %s AND tenant_id = %s RETURNING version",
                    (status, asset_id, tenant_id),
                )
                row = cur.fetchone()
    if row is None:
        raise AssetNotFoundError(f"No existe el activo {asset_id} para este tenant")
    return {"asset_id": asset_id, "status": status, "version": row[0]}


def connect_assets(
    conn: psycopg.Connection, tenant_id: str, source_asset_id: str, target_asset_id: str, connection_type: str
) -> dict[str, Any]:
    """Conecta dos activos reales -- verifica EXPLICITAMENTE que ambos
    pertenecen al tenant (via `network_asset`, que si tiene RLS) antes de
    escribir en `asset_connectivity` (que no tiene RLS propio -- ver
    docstring del modulo). `ON CONFLICT` actualiza el tipo de conexion en
    vez de duplicar la fila si ya existia ese par."""
    if not _asset_belongs_to_tenant(conn, tenant_id, source_asset_id):
        raise AssetNotFoundError(f"No existe el activo origen {source_asset_id} para este tenant")
    if not _asset_belongs_to_tenant(conn, tenant_id, target_asset_id):
        raise AssetNotFoundError(f"No existe el activo destino {target_asset_id} para este tenant")

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO asset_connectivity (source_asset_id, target_asset_id, connection_type) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (source_asset_id, target_asset_id) DO UPDATE SET connection_type = EXCLUDED.connection_type",
                (source_asset_id, target_asset_id, connection_type),
            )
    return {"source_asset_id": source_asset_id, "target_asset_id": target_asset_id, "connection_type": connection_type}


def asset_connectivity(conn: psycopg.Connection, tenant_id: str, asset_id: str) -> list[dict]:
    """Conectividad real de un activo (en cualquiera de los dos sentidos)
    -- el `JOIN` contra `network_asset` (con RLS activo via `tenant_scope`)
    es la UNICA forma en la que esta consulta queda aislada por tenant,
    dado que `asset_connectivity` no tiene su propio `tenant_id`."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ac.source_asset_id, ac.target_asset_id, ac.connection_type "
                    "FROM asset_connectivity ac "
                    "JOIN network_asset na_source ON na_source.id = ac.source_asset_id AND na_source.tenant_id = %s "
                    "JOIN network_asset na_target ON na_target.id = ac.target_asset_id AND na_target.tenant_id = %s "
                    "WHERE ac.source_asset_id = %s OR ac.target_asset_id = %s",
                    (tenant_id, tenant_id, asset_id, asset_id),
                )
                rows = cur.fetchall()
    return [
        {"source_asset_id": str(row[0]), "target_asset_id": str(row[1]), "connection_type": row[2]}
        for row in rows
    ]


def assets_geojson(conn: psycopg.Connection, tenant_id: str) -> dict:
    """GeoJSON real de los activos (modulo de georreferenciacion,
    `docs/07-track-b-alcance-funcional.md` SS7) -- solo activos CON
    `geometry` real cargada (nunca una coordenada inventada), mas las
    conexiones entre activos que AMBOS tengan geometria tipo `Point`
    (como `LineString`, igual que la topologia de un modelo hidraulico)."""
    assets = list_assets(conn, tenant_id)
    points_by_id = {}
    features: list[dict] = []

    for asset in assets:
        geom = asset["geometry"]
        if not geom or geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates")
        if not coords or len(coords) != 2:
            continue
        points_by_id[asset["asset_id"]] = coords
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coords},
            "properties": {
                "id": asset["asset_id"], "asset_type": asset["type"], "status": asset["status"],
                "zone_id": asset["zone_id"], "attributes": asset["attributes"],
            },
        })

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ac.source_asset_id, ac.target_asset_id, ac.connection_type "
                    "FROM asset_connectivity ac "
                    "JOIN network_asset na_source ON na_source.id = ac.source_asset_id AND na_source.tenant_id = %s "
                    "JOIN network_asset na_target ON na_target.id = ac.target_asset_id AND na_target.tenant_id = %s",
                    (tenant_id, tenant_id),
                )
                rows = cur.fetchall()

    for source_id, target_id, connection_type in rows:
        source_id, target_id = str(source_id), str(target_id)
        if source_id not in points_by_id or target_id not in points_by_id:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [points_by_id[source_id], points_by_id[target_id]]},
            "properties": {"source_asset_id": source_id, "target_asset_id": target_id, "connection_type": connection_type},
        })

    return {"type": "FeatureCollection", "features": features}


def zone_assets_and_connectivity(conn: psycopg.Connection, tenant_id: str, zone_id: str) -> tuple[list[dict], list[dict]]:
    """Activos de una zona + la conectividad restringida a AMBOS extremos
    dentro de esa misma zona (Sprint B6, `docs/07-track-b-alcance-funcional.md`
    SS5: "derivar network_model desde el Gemelo Digital"). Una conexion
    que sale de la zona (a un activo de otra zona o sin zona) se excluye
    sin avisar -- es un limite de alcance real, no un error: el modelo
    generado es el de ESA zona, no de toda la red del tenant."""
    assets = list_assets(conn, tenant_id, zone_id=zone_id)
    asset_ids = {a["asset_id"] for a in assets}
    if not asset_ids:
        return assets, []

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ac.source_asset_id, ac.target_asset_id, ac.connection_type "
                    "FROM asset_connectivity ac "
                    "JOIN network_asset na_source ON na_source.id = ac.source_asset_id AND na_source.tenant_id = %s "
                    "JOIN network_asset na_target ON na_target.id = ac.target_asset_id AND na_target.tenant_id = %s",
                    (tenant_id, tenant_id),
                )
                rows = cur.fetchall()

    connectivity = [
        {"source_asset_id": str(row[0]), "target_asset_id": str(row[1]), "connection_type": row[2]}
        for row in rows
        if str(row[0]) in asset_ids and str(row[1]) in asset_ids
    ]
    return assets, connectivity
