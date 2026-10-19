"""Alta de una organizacion desde la linea de comandos (Track E, E1, 0047).

Para lo que todavia no tiene quien lo cree desde el Portal: la primera
organizacion de tipo plataforma (desde ella se crean las demas) o una ONG
antes de un taller. Usa exactamente el mismo camino que el Portal
(`organization_service.create_organization`) y crea los usuarios extra con
las reglas de Configuracion -> Usuarios.

Uso:
    python bootstrap_organization.py --dsn "postgresql://..." --name apt --kind advisor \
        --display-name "APT" --admin admin --packs EC-ARCA,EC-MUNICIPIOS-AZULES \
        --timezone America/Guayaquil --ttl-hours 12 --currency USD --locale es-EC \
        --user asesor01:advisor --user asesor02:advisor

Las claves se piden por la consola (o variables RENFYGRID_PWD_<USUARIO>, en
mayusculas y con guion bajo en lugar de punto o guion); nunca van en la
linea de comandos ni en un archivo.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portal-api"))

import psycopg  # noqa: E402

from catalog_service import set_region  # noqa: E402
from organization_service import create_organization  # noqa: E402
from permissions import create_user  # noqa: E402


def _password(user: str) -> str:
    env = "RENFYGRID_PWD_" + re.sub(r"[^A-Z0-9]", "_", user.upper())
    if os.environ.get(env):
        return os.environ[env]
    return getpass.getpass(f"Clave para {user}: ")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--name", required=True, help="Código con el que se inicia sesión")
    parser.add_argument("--kind", required=True, choices=["provider", "group", "advisor", "platform"])
    parser.add_argument("--display-name")
    parser.add_argument("--admin", required=True, help="Usuario administrador")
    parser.add_argument("--packs", default="")
    parser.add_argument("--timezone")
    parser.add_argument("--ttl-hours", type=float, required=True)
    parser.add_argument("--currency")
    parser.add_argument("--locale")
    parser.add_argument("--user", action="append", default=[], help="usuario:rol (puede repetirse)")
    args = parser.parse_args()

    config = {"session_ttl_seconds": int(args.ttl_hours * 3600)}
    if args.timezone:
        config["timezone"] = args.timezone
    packs = [p.strip() for p in args.packs.split(",") if p.strip()]
    with psycopg.connect(args.dsn, autocommit=True) as conn:
        with conn.transaction():
            org = create_organization(conn, args.name, args.kind, args.admin, _password(args.admin), "cli:bootstrap",
                                      config=config, packs=packs, display_name=args.display_name)
            if args.currency and args.locale:
                set_region(conn, org["tenant_id"], args.currency, args.locale)
            for spec in args.user:
                user, _, role = spec.partition(":")
                create_user(conn, org["tenant_id"], user, _password(user), role or "operator")
                print(f"  usuario {user} ({role or 'operator'})")
    print(f"Organización {org['name']} ({org['kind']}) creada: {org['tenant_id']}; administrador {org['admin']['email']}")


if __name__ == "__main__":
    main()
