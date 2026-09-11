"""Alta de un tenant piloto real (Sprint 10) desde un manifiesto JSON --
junta en un solo paso lo que hasta ahora requeria llamar por separado a
`meter_registry.py` (Sprint 1), insertar `meter_protocol` (Sprint 2),
`vee_rule` (Sprint 3), `consumption_anomaly_rule` (Sprint 5) y
`control_approval_level` (Sprint 6) a mano.

No inventa nada nuevo: es el mismo camino que ya usan los verify_*.py de
cada sprint, empaquetado para no tener que escribir SQL a mano cada vez que
haya que dar de alta un tenant real. Ver `example_manifest.json` para la
forma esperada.

Uso:
    python onboard_tenant.py --dsn "postgresql://..." --manifest manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "db"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "common"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "hes-adapter-dlms"))

import psycopg  # noqa: E402

from meter_registry import link_meter_to_gateway, register_gateway, register_meter  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402


def onboard_tenant(conn: psycopg.Connection, manifest: dict) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tenant (name, plan, config) VALUES (%s, %s, %s) RETURNING id",
            (
                manifest["tenant_name"],
                manifest.get("plan", "pilot"),
                psycopg.types.json.Json(manifest.get("tenant_config", {})),
            ),
        )
        (tenant_id,) = cur.fetchone()
        tenant_id = str(tenant_id)

    gateway_ids: dict[str, str] = {}
    for meter_spec in manifest.get("meters", []):
        gateway_spec = meter_spec["gateway"]
        gateway_key = gateway_spec["name"]
        if gateway_key not in gateway_ids:
            gateway_ids[gateway_key] = register_gateway(
                conn, tenant_id, gateway_spec["name"], gateway_spec["transport_protocol"], gateway_spec["connection"]
            )
        meter_id = register_meter(
            conn, tenant_id, meter_spec["account_number"], meter_spec["serial_number"],
            meter_spec["brand"], meter_spec["protocol"], model=meter_spec.get("model"),
            location=meter_spec.get("location"),
        )
        link_meter_to_gateway(conn, tenant_id, meter_id, gateway_ids[gateway_key], meter_spec["server_address"])

    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                for mapping in manifest.get("obis_mappings", []):
                    cur.execute(
                        "INSERT INTO meter_protocol (tenant_id, brand, model, protocol, obis_mapping) VALUES (%s, %s, %s, %s, %s)",
                        (tenant_id, mapping["brand"], mapping["model"], mapping["protocol"], psycopg.types.json.Json(mapping["obis_mapping"])),
                    )
                for rule in manifest.get("vee_rules", []):
                    cur.execute(
                        "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, %s, %s, %s)",
                        (tenant_id, rule["type"], psycopg.types.json.Json(rule["params"]), rule.get("priority", 100)),
                    )
                for rule in manifest.get("consumption_anomaly_rules", []):
                    cur.execute(
                        "INSERT INTO consumption_anomaly_rule (tenant_id, condition, action) VALUES (%s, %s, %s)",
                        (tenant_id, psycopg.types.json.Json(rule["condition"]), rule["action"]),
                    )
                for level in manifest.get("control_approval_levels", []):
                    cur.execute(
                        "INSERT INTO control_approval_level (tenant_id, order_type, requires_human_approval, min_required_role) "
                        "VALUES (%s, %s, %s, %s)",
                        (tenant_id, level["order_type"], level["requires_human_approval"], level["min_required_role"]),
                    )

    return tenant_id


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--manifest", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    with psycopg.connect(args.dsn, autocommit=True) as conn:
        tenant_id = onboard_tenant(conn, manifest)
    print(f"OK: tenant '{manifest['tenant_name']}' dado de alta -- id {tenant_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
