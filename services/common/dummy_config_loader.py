"""Config Loader del Sprint 0 (initContainer) -- hace refresh() UNA vez al
arrancar el pod y deja el snapshot listo para que el contenedor principal
(dummy_config_reader.py) lo lea. En un servicio real, `fetch_fn` seria una
consulta a `vee_rule`/`meter_protocol` -- aca son datos fijos de prueba
SOLO para este dummy de verificacion de infraestructura (no un servicio de
negocio real, ver docs/05-ejecucion.md F46).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from renmeter_common.config_cache import ConfigCache

SNAPSHOT_PATH = Path("/config/snapshot.json")


def fetch_fixture_rules() -> list[dict]:
    return [
        {"tenant_id": "sprint0-dummy", "type": "range", "params": {"min": 0, "max": 9999}},
    ]


def main() -> None:
    cache = ConfigCache(fetch_fn=fetch_fixture_rules, snapshot_path=SNAPSHOT_PATH)
    n = cache.refresh()
    print(f"Config Loader: {n} fila(s) escritas en {SNAPSHOT_PATH}", flush=True)


if __name__ == "__main__":
    main()
