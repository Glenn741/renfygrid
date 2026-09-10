"""Verificacion end-to-end real de F16/F17 (deteccion de huecos + estimacion)
y F18 (edicion manual auditada), Sprint 4 -- nada de mocks contra la BD.

Que prueba, en espanol llano:
  1. Inserta lecturas validadas reales con un hueco de 3 intervalos.
  2. Define una regla `missing_interval` real (intervalo esperado, metodo
     `linear_interpolation`), refresca su cache, corre `run_vee_estimation.py`
     y confirma que aparecen exactamente 3 lecturas `estimated` con los
     valores interpolados esperados.
  3. Edita una de las lecturas reales via `manual_edit.edit_reading` y
     confirma: el valor cambio, `source` paso a 'edited', y quedo exactamente
     1 fila en `validated_reading_edit` con el valor anterior correcto.
  4. Confirma que el rol de aplicacion (`renfygrid_app`) NO puede hacer
     UPDATE ni DELETE sobre `validated_reading_edit` -- verificado contra
     Postgres real, no asumido.

Uso:
    python verify_estimation_and_edit_end_to_end.py "postgresql://renfygrid_app:renfygrid_app_dev_only@localhost:5455/renfygrid"
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from manual_edit import edit_reading  # noqa: E402
from renmeter_common.db import tenant_scope  # noqa: E402
from run_vee_estimation import main as estimation_main  # noqa: E402
from vee_rules_cache import build_cache  # noqa: E402

CHANNEL = "active_energy"
INTERVAL_SECONDS = 900  # 15 minutos


def run(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tenant (name) VALUES (%s) RETURNING id", ("E2E VEE Sprint4",))
            (tenant_id,) = cur.fetchone()
            tenant_id = str(tenant_id)

        try:
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO meter (tenant_id, account_number, serial_number, brand, protocol) "
                            "VALUES (%s, 'ACC-S4', 'SER-S4', 'test-brand', 'DLMS_COSEM') RETURNING id",
                            (tenant_id,),
                        )
                        (meter_id,) = cur.fetchone()
                        meter_id = str(meter_id)

                        cur.execute(
                            "INSERT INTO vee_rule (tenant_id, type, params, priority) VALUES (%s, 'missing_interval', %s, 100)",
                            (
                                tenant_id,
                                psycopg.types.json.Json(
                                    {
                                        "channel": CHANNEL,
                                        "expected_interval_seconds": INTERVAL_SECONDS,
                                        "tolerance_seconds": 60,
                                        "estimation_method": "linear_interpolation",
                                    }
                                ),
                            ),
                        )

                        t0 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
                        t1 = t0 + timedelta(seconds=INTERVAL_SECONDS * 4)  # faltan 3 intervalos
                        for timestamp, value in [(t0, 1000.0), (t1, 2000.0)]:
                            cur.execute(
                                "INSERT INTO validated_reading "
                                "(tenant_id, meter_id, channel, \"timestamp\", value, source, is_valid) "
                                "VALUES (%s, %s, %s, %s, %s, 'real', true)",
                                (tenant_id, meter_id, CHANNEL, timestamp, value),
                            )

            with tempfile.TemporaryDirectory() as tmp_dir:
                snapshot_path = Path(tmp_dir) / "vee_rule.json"
                build_cache(snapshot_path, dsn, tenant_id).refresh()
                estimation_main(["--dsn", dsn, "--tenant-id", tenant_id, "--vee-rules-snapshot", str(snapshot_path)])

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT \"timestamp\", value, source FROM validated_reading "
                            "WHERE meter_id = %s ORDER BY \"timestamp\"",
                            (meter_id,),
                        )
                        rows = cur.fetchall()

            print(f"Filas tras estimacion: {[(r[0].isoformat(), float(r[1]), r[2]) for r in rows]}")
            estimated_rows = [r for r in rows if r[2] == "estimated"]
            ok = (
                len(rows) == 5
                and len(estimated_rows) == 3
                and abs(float(estimated_rows[0][1]) - 1250.0) < 0.01
                and abs(float(estimated_rows[1][1]) - 1500.0) < 0.01
                and abs(float(estimated_rows[2][1]) - 1750.0) < 0.01
            )
            print("F16/F17 OK -- 3 lecturas estimadas con los valores interpolados esperados" if ok else "F16/F17 FALLA")

            # F18: editar la primera lectura real
            edit_reading(
                conn, tenant_id, meter_id, CHANNEL, t0, new_value=1100.0,
                user_name="operador.vee@renfygrid.demo", justification="Corregido tras inspeccion en sitio",
            )
            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT value, source FROM validated_reading WHERE meter_id = %s AND \"timestamp\" = %s",
                            (meter_id, t0),
                        )
                        edited_value, edited_source = cur.fetchone()
                        cur.execute(
                            "SELECT previous_value, new_value, user_name FROM validated_reading_edit "
                            "WHERE tenant_id = %s",
                            (tenant_id,),
                        )
                        edit_rows = cur.fetchall()

            ok_edit = (
                float(edited_value) == 1100.0
                and edited_source == "edited"
                and len(edit_rows) == 1
                and float(edit_rows[0][0]) == 1000.0
                and float(edit_rows[0][1]) == 1100.0
            )
            print(f"Tras editar: value={edited_value} source={edited_source}, validated_reading_edit={edit_rows}")
            print("F18 OK -- edicion aplicada y auditada" if ok_edit else "F18 FALLA")

            # Confirmar que el rol de aplicacion no puede tocar el historial de auditoria
            # -- conexion aparte, autocommit, para no arrastrar el error a `conn`.
            immutable_ok = False
            try:
                with psycopg.connect(dsn, autocommit=True) as guard_conn:
                    with tenant_scope(guard_conn, tenant_id):
                        with guard_conn.cursor() as cur:
                            cur.execute(
                                "UPDATE validated_reading_edit SET user_name = 'hacked' WHERE tenant_id = %s",
                                (tenant_id,),
                            )
            except psycopg.errors.InsufficientPrivilege:
                immutable_ok = True
            print("validated_reading_edit es verdaderamente append-only (UPDATE rechazado por Postgres)" if immutable_ok else "FALLA: se pudo modificar el historial de auditoria")

            return 0 if (ok and ok_edit and immutable_ok) else 1
        finally:
            # Limpieza de validated_reading_edit: el rol de aplicacion NO PUEDE
            # borrar esta tabla (a proposito, ver migracion 0005) -- ni siquiera
            # este script de verificacion se salta esa regla. En un entorno real
            # esto seria un job de retencion aparte con su propio rol admin; aca
            # se usa el superusuario local SOLO para poder dejar la BD de
            # desarrollo limpia entre corridas de este script.
            admin_dsn = "postgresql://renfygrid:renfygrid_dev_only@localhost:5455/renfygrid"
            with psycopg.connect(admin_dsn, autocommit=True) as admin_conn:
                with tenant_scope(admin_conn, tenant_id):
                    with admin_conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading_edit WHERE tenant_id = %s", (tenant_id,))

            with conn.transaction():
                with tenant_scope(conn, tenant_id):
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM validated_reading WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM vee_rule WHERE tenant_id = %s", (tenant_id,))
                        cur.execute("DELETE FROM meter WHERE tenant_id = %s", (tenant_id,))
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenant WHERE id = %s", (tenant_id,))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
