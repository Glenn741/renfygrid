"""Panel real del motor VEE (Sprint C11-2, sobre el gap encontrado tras C11):
F14-F19 estan construidos y verificados de punta a punta desde Sprint 3-4
(validacion, deteccion de huecos, estimacion, edicion, coherencia entre
canales) pero la pantalla de Validacion (Vee.tsx) solo mostraba la cola de
excepciones invalidas -- ni un resumen (cuantas reglas activas, cuanto se
estimo, cuanto se edito), ni las lecturas ESTIMADAS (F16/F17: el trabajo
mas visible del motor, y el que menos se veia).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def vee_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT "
                    "  count(*) FILTER (WHERE is_valid = false) AS invalid_pending, "
                    "  count(*) FILTER (WHERE source = 'estimated' AND created_at > now() - interval '24 hours') AS estimated_24h, "
                    "  count(*) FILTER (WHERE source = 'edited' AND created_at > now() - interval '24 hours') AS edited_24h "
                    "FROM validated_reading WHERE tenant_id = %s",
                    (tenant_id,),
                )
                invalid_pending, estimated_24h, edited_24h = cur.fetchone()

                cur.execute(
                    "SELECT ru.type, count(*) FROM validated_reading vr "
                    "LEFT JOIN vee_rule ru ON ru.id = vr.vee_rule_id "
                    "WHERE vr.tenant_id = %s AND vr.is_valid = false "
                    "GROUP BY ru.type",
                    (tenant_id,),
                )
                invalid_by_type = {(rule_type or "sin_regla_o_formato"): count for rule_type, count in cur.fetchall()}

                cur.execute(
                    "SELECT type, count(*) FROM vee_rule WHERE tenant_id = %s AND valid_to IS NULL GROUP BY type",
                    (tenant_id,),
                )
                active_rules_by_type = dict(cur.fetchall())

    return {
        "invalid_pending": invalid_pending,
        "invalid_by_type": invalid_by_type,
        "estimated_24h": estimated_24h,
        "edited_24h": edited_24h,
        "active_rules_by_type": active_rules_by_type,
        "active_rules_total": sum(active_rules_by_type.values()),
    }


def list_estimated_readings(conn: psycopg.Connection, tenant_id: str, limit: int = 100) -> list[dict]:
    """Lecturas `source = 'estimated'` mas recientes, con el metodo real
    usado (de `vee_rule.params.estimation_method`, no adivinado) -- F16/F17
    hecho visible, no solo verificado por script."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT vr.meter_id, m.account_number, vr.channel, vr.\"timestamp\", vr.value, "
                    "       vr.created_at, ru.params->>'estimation_method' "
                    "FROM validated_reading vr JOIN meter m ON m.id = vr.meter_id "
                    "LEFT JOIN vee_rule ru ON ru.id = vr.vee_rule_id "
                    "WHERE vr.tenant_id = %s AND vr.source = 'estimated' "
                    "ORDER BY vr.created_at DESC LIMIT %s",
                    (tenant_id, limit),
                )
                return [
                    {
                        "meter_id": str(row[0]),
                        "account_number": row[1],
                        "channel": row[2],
                        "timestamp": row[3].isoformat(),
                        "value": float(row[4]),
                        "created_at": row[5].isoformat(),
                        "estimation_method": row[6],
                    }
                    for row in cur.fetchall()
                ]
