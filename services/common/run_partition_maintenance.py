"""Punto de entrada real para `renmeter_common.partition_maintenance` (F10,
Sprint C11) -- kept-as-source a proposito, mismo patron que `poller.py`/
`refresh_obis_mapping_cache.py`/`main.py` de los otros servicios: un
entry-point corto en texto plano que importa y llama al modulo COMPILADO,
nunca al reves.

Hallazgo real (Sprint C11-post): `python -m renmeter_common.partition_maintenance`
NO funciona contra el `.so` compilado con Nuitka -- "No code object
available for renmeter_common.partition_maintenance" -- el mecanismo `-m`
de Python espera poder ejecutar el modulo como script, algo que una
extension compilada no soporta igual que un `.py` normal. `import` +
llamar a `main()` directo SI funciona -- por eso este archivo existe, en
vez de intentar invocar el paquete compilado con `-m` desde cron.

Uso (el DSN es siempre el admin -- ver docstring de partition_maintenance.py):
    python run_partition_maintenance.py --dsn "postgresql://renfygrid:...@host/renfygrid" --months-ahead 2
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from renmeter_common.partition_maintenance import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
