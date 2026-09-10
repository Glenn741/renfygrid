"""Servicio dummy del Sprint 0 -- prueba el criterio de aceptacion real:

    "Un servicio dummy desplegado como pod en k3s lee su config desde
    snapshot, no desde codigo" (docs/04-plan-sprints.md, Sprint 0).

Simula lo que hara cualquier servicio real (motor VEE, adaptador HES): un
Config Loader ya corrio refresh() y dejo un snapshot en disco -- este proceso
NUNCA toca la base de datos, solo hace load() + get(). Ningun umbral/regla
esta escrito en este archivo: viene todo del snapshot montado en
/config/snapshot.json (ver infra/k8s/services/dummy-config-reader/).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from renmeter_common.config_cache import ConfigCache, ConfigSnapshotError

SNAPSHOT_PATH = Path("/config/snapshot.json")


def main() -> None:
    cache = ConfigCache(fetch_fn=lambda: [], snapshot_path=SNAPSHOT_PATH)
    try:
        cache.load()
    except ConfigSnapshotError as exc:
        print(f"FALLO: no se pudo cargar el snapshot -- {exc}", flush=True)
        raise SystemExit(1)

    rules = cache.get_all()
    print(f"OK -- cargadas {len(rules)} reglas desde snapshot (sin tocar la BD)", flush=True)
    for rule in rules:
        print(f"  regla: {rule}", flush=True)

    # Se queda vivo para que el pod se vea "Running" y los logs sean inspeccionables.
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
