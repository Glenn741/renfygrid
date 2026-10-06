"""Genera las ordenes de mantenimiento preventivo vencidas de TODAS las
organizaciones activas (Track D, D3.2). Lo corre el timer de systemd
`renfygrid-pm-generator.timer` una vez al dia; hasta ahora solo se generaban
cuando alguien pulsaba "Generar ordenes vencidas" en el Portal.

La condicion real sigue siendo la fecha de cada plan (`generate_due_pm_orders`):
este script no adivina nada, solo recorre las organizaciones. Usa la misma
conexion (rol de aplicacion, RLS) que el Portal/API, por `RENFYGRID_DSN`.

Uso (compilado con Nuitka, sin fuente en el servidor):
    python -c "import run_due_pm; run_due_pm.main()"
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from order_service import generate_due_pm_orders  # noqa: E402


def main() -> int:
    dsn = os.environ.get("RENFYGRID_DSN")
    if not dsn:
        print("Falta RENFYGRID_DSN", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc)
    total = 0
    failures = 0
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM tenant WHERE is_active ORDER BY name")
            tenants = cur.fetchall()
        for tenant_id, name in tenants:
            try:
                orders = generate_due_pm_orders(conn, str(tenant_id), now)
            except Exception as exc:  # una organizacion con problemas no frena a las demas
                failures += 1
                print(f"{name}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            total += len(orders)
            if orders:
                print(f"{name}: {len(orders)} orden(es) preventiva(s) generada(s)")
    print(f"{now.isoformat()} · {len(tenants)} organizaciones · {total} ordenes generadas · {failures} con error")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
