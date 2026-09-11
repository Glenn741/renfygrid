"""Panel real del motor VEE, por etapa (Sprint C11-3, sobre el feedback del
usuario: "cada letra V.E.E. implica un nivel de procesamiento y deberian
haber estadisticas y KPIs en esos niveles" -- la primera pasada de C11-2
agregó un resumen plano y una lista de estimadas, pero seguía sin separar
Validación / Estimación / Edición como 3 etapas con sus propios números,
que es como lo hacen los MDM de referencia.

Grounded en benchmark real (no memoria de entrenamiento):
  - Oracle Utilities MDM tiene un dashboard "VEE Exceptions" con paginas
    Overview/Exception Trend/Exception Analysis, conteo de los 5 tipos de
    excepcion mas frecuentes, y KPIs con bandas verde/amarillo/rojo
    configurables (docs.oracle.com/en/industries/energy-water/analytics).
  - Itron Enterprise Edition distingue explicitamente "validation sets"
    de "estimation sets" y una cola de trabajo de excepciones aparte
    (docs.itrontotal.com, IEEMDMHelp "VEE status codes").
  - Landis+Gyr Core MDMS: "exception management to process all validation
    and estimation exceptions not automatically handled by VEE rules"
    (landisgyr.com/product/core-mdms).
  - Tasa de excepciones como KPI: <2% excelente, 2-5% aceptable, >5%
    preocupante -- banda generica de calidad de datos, aplicada aca a
    falta de un benchmark propio del sector energia.

Por eso este modulo separa 3 resumenes -- uno por etapa -- en vez de un
solo dict plano, y agrega tasa de excepcion/estimacion como porcentaje
sobre el total procesado (no solo el conteo crudo)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from renmeter_common.db import tenant_scope  # noqa: E402


def _pct(numerator: int, denominator: int) -> float | None:
    """None (no 0.0) cuando no hay denominador -- una tasa de excepcion sin
    datos procesados todavia no es "0% de excepciones", es "sin datos"."""
    return round(100.0 * numerator / denominator, 1) if denominator else None


def validation_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Etapa Validacion (F14/F15): cuanto de lo procesado pasa vs. cuanto
    queda como excepcion, por tipo de regla, mas tendencia de 7 dias -- el
    mismo tipo de vista que Oracle llama "VEE Exceptions Overview/Trend"."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FILTER (WHERE source = 'real'), "
                    "       count(*) FILTER (WHERE source = 'real' AND is_valid = false) "
                    "FROM validated_reading WHERE tenant_id = %s",
                    (tenant_id,),
                )
                total_real, invalid_total = cur.fetchone()

                cur.execute(
                    "SELECT ru.type, count(*) FROM validated_reading vr "
                    "LEFT JOIN vee_rule ru ON ru.id = vr.vee_rule_id "
                    "WHERE vr.tenant_id = %s AND vr.source = 'real' AND vr.is_valid = false "
                    "GROUP BY ru.type",
                    (tenant_id,),
                )
                invalid_by_type = {(rule_type or "sin_regla_o_formato"): count for rule_type, count in cur.fetchall()}

                cur.execute(
                    "SELECT type, count(*) FROM vee_rule WHERE tenant_id = %s AND valid_to IS NULL "
                    "AND type IN ('range', 'channel_consistency') GROUP BY type",
                    (tenant_id,),
                )
                active_rules_by_type = dict(cur.fetchall())

                cur.execute(
                    "SELECT date_trunc('day', \"timestamp\")::date AS day, "
                    "       count(*) FILTER (WHERE source = 'real') AS total, "
                    "       count(*) FILTER (WHERE source = 'real' AND is_valid = false) AS invalid "
                    "FROM validated_reading WHERE tenant_id = %s AND \"timestamp\" > now() - interval '7 days' "
                    "GROUP BY 1 ORDER BY 1",
                    (tenant_id,),
                )
                trend_7d = [
                    {"date": day.isoformat(), "total": total, "invalid": invalid}
                    for day, total, invalid in cur.fetchall()
                ]

    return {
        "total_processed": total_real,
        "invalid_total": invalid_total,
        "exception_rate_pct": _pct(invalid_total, total_real),
        "invalid_by_type": invalid_by_type,
        "active_rules_by_type": active_rules_by_type,
        "active_rules_total": sum(active_rules_by_type.values()),
        "trend_7d": trend_7d,
    }


def estimation_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Etapa Estimacion (F16/F17): que porcentaje de la serie tuvo que
    rellenarse (no es lo mismo un tenant con 1% estimado que uno con 40%
    -- ese numero solo, sin el total de referencia, no dice nada), y con
    que metodo real (nunca inventado, ver InsufficientHistoryError en
    vee_engine.py)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FILTER (WHERE source = 'real'), "
                    "       count(*) FILTER (WHERE source = 'estimated'), "
                    "       count(*) FILTER (WHERE source = 'estimated' AND created_at > now() - interval '24 hours') "
                    "FROM validated_reading WHERE tenant_id = %s",
                    (tenant_id,),
                )
                total_real, total_estimated, estimated_24h = cur.fetchone()

                cur.execute(
                    "SELECT ru.params->>'estimation_method', count(*) FROM validated_reading vr "
                    "LEFT JOIN vee_rule ru ON ru.id = vr.vee_rule_id "
                    "WHERE vr.tenant_id = %s AND vr.source = 'estimated' "
                    "GROUP BY 1",
                    (tenant_id,),
                )
                by_method = {(method or "desconocido"): count for method, count in cur.fetchall()}

                cur.execute(
                    "SELECT count(*) FROM vee_rule WHERE tenant_id = %s AND valid_to IS NULL AND type = 'missing_interval'",
                    (tenant_id,),
                )
                (active_rules_total,) = cur.fetchone()

    return {
        "total_estimated": total_estimated,
        "estimated_24h": estimated_24h,
        "fill_rate_pct": _pct(total_estimated, total_real + total_estimated),
        "by_method": by_method,
        "active_rules_total": active_rules_total,
    }


def editing_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Etapa Edicion manual (F18): cuanto se corrige a mano y quien -- el
    volumen de ediciones manuales es en si mismo una senal (si sube mucho,
    algo rio arriba -- mapeo OBIS, reglas -- probablemente esta mal)."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*), count(*) FILTER (WHERE edited_at > now() - interval '24 hours') "
                    "FROM validated_reading_edit WHERE tenant_id = %s",
                    (tenant_id,),
                )
                total_edits, edits_24h = cur.fetchone()

                cur.execute(
                    "SELECT user_name, count(*) FROM validated_reading_edit WHERE tenant_id = %s "
                    "GROUP BY user_name ORDER BY count(*) DESC LIMIT 5",
                    (tenant_id,),
                )
                top_editors = [{"user_name": name, "count": count} for name, count in cur.fetchall()]

    return {
        "total_edits": total_edits,
        "edits_24h": edits_24h,
        "top_editors": top_editors,
    }


def list_estimated_readings(conn: psycopg.Connection, tenant_id: str, limit: int = 100) -> list[dict]:
    """Lecturas `source = 'estimated'` mas recientes, con el metodo real
    usado (de `vee_rule.params.estimation_method`, no adivinado)."""
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


def list_edits(conn: psycopg.Connection, tenant_id: str, limit: int = 100) -> list[dict]:
    """Historial real de ediciones manuales (F18) desde `validated_reading_edit`
    -- append-only (migracion 0005), la fuente de verdad de la auditoria,
    no una inferencia sobre `validated_reading.source`."""
    with conn.transaction():
        with tenant_scope(conn, tenant_id):
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT vr.meter_id, m.account_number, vr.channel, vr.\"timestamp\", "
                    "       e.previous_value, e.new_value, e.user_name, e.justification, e.edited_at "
                    "FROM validated_reading_edit e "
                    "JOIN validated_reading vr ON vr.id = e.validated_reading_id "
                    "JOIN meter m ON m.id = vr.meter_id "
                    "WHERE e.tenant_id = %s ORDER BY e.edited_at DESC LIMIT %s",
                    (tenant_id, limit),
                )
                return [
                    {
                        "meter_id": str(row[0]),
                        "account_number": row[1],
                        "channel": row[2],
                        "timestamp": row[3].isoformat(),
                        "previous_value": float(row[4]),
                        "new_value": float(row[5]),
                        "user_name": row[6],
                        "justification": row[7],
                        "edited_at": row[8].isoformat(),
                    }
                    for row in cur.fetchall()
                ]


def vee_summary(conn: psycopg.Connection, tenant_id: str) -> dict:
    """Compatibilidad con `GET /vee/summary` (Sprint C11-2): las 3 etapas
    juntas en un solo dict, para un solo request desde el Portal."""
    return {
        "validation": validation_summary(conn, tenant_id),
        "estimation": estimation_summary(conn, tenant_id),
        "editing": editing_summary(conn, tenant_id),
    }
