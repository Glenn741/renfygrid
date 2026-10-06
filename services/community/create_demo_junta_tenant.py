"""Crea una junta de DEMOSTRACION nueva (tenant + usuario) y le carga el caso
completo de las Guias 3 y 4 con el perfil indicado (ver
`seed_demo_guias_tenant.PROFILES`). Pensado para separar la demo de juntas
de la demo urbana de MDM (Bogota/Cali), a pedido del usuario 2026-10-05.

Si ya existe un tenant con ese nombre, no hace nada.

Uso:
    python create_demo_junta_tenant.py "<DSN>" "<nombre del tenant>" "<usuario>" "<clave>" [perfil]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from pack_service import adopt_pack, set_instrumentation  # noqa: E402
from renmeter_common.user_service import create_app_user  # noqa: E402
from seed_demo_guias_tenant import PROFILES  # noqa: E402
from seed_demo_guias_tenant import main as seed_guias  # noqa: E402


DEMO_PACKS = ("EC-ARCA", "EC-MUNICIPIOS-AZULES")


def main(dsn: str, tenant_name: str, username: str, password: str, profile: str = "gualaceo") -> None:
    if profile not in PROFILES:
        print(f"Perfil desconocido: {profile!r} (validos: {sorted(PROFILES)})")
        sys.exit(2)
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenant WHERE lower(name) = lower(%s)", (tenant_name,))
            row = cur.fetchone()
            if row:
                print(f"Ya existe el tenant {tenant_name!r}: {row[0]} -- no se modifica.")
                return
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", (tenant_name,))
            tenant_id = str(cur.fetchone()[0])
        # Pais y programa se eligen al crear la organizacion (0046): la junta
        # demo es de Ecuador y del programa Municipios Azules.
        for pack_id in DEMO_PACKS:
            adopt_pack(conn, tenant_id, pack_id)
        create_app_user(conn, tenant_id, username, password, "supervisor")
        set_instrumentation(conn, tenant_id, {
            "metering": "basic", "water_balance": "basic", "quality": "basic",
            "maintenance": "basic", "network": "basic", "billing": "basic",
        })
    seed_guias(dsn, tenant_id, profile)
    print(f"Tenant {tenant_name!r} creado: {tenant_id} -- usuario {username!r}")


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6):
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:])
