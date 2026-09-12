"""Siembra los dos modelos EPANET de demostracion (Bogota/Chapinero,
Cali/Tres Cruces -- `demo/*.inp`) en el tenant de demostracion persistente
("RenfyGrid Demo") -- para que el panel de Modelado Hidraulico tenga algo
real que mostrar sin esperar a que el usuario cargue su propio modelo.

Mismo principio que `hes-adapter-dlms/seed_demo_data.py`: todo por
argumento (DSN, tenant, directorio de almacenamiento), nunca un valor fijo
en codigo; idempotente -- si el modelo ya existe (mismo nombre), esto crea
una nueva version, no falla.

Uso:
    python seed_demo_networks.py "<DSN>" "<TENANT_ID>" "<STORAGE_DIR>"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import psycopg  # noqa: E402

from model_service import register_model  # noqa: E402

DEMO_DIR = Path(__file__).resolve().parent / "demo"
MODELS = [
    ("DMA Chapinero (Bogota, ilustrativo)", DEMO_DIR / "bogota_chapinero_dma.inp"),
    ("DMA Tres Cruces - San Fernando (Cali, ilustrativo)", DEMO_DIR / "cali_tres_cruces_dma.inp"),
]


def run(dsn: str, tenant_id: str, storage_dir: str) -> int:
    with psycopg.connect(dsn, autocommit=True) as conn:
        for name, inp_path in MODELS:
            content = inp_path.read_text(encoding="utf-8")
            result = register_model(conn, tenant_id, name, content, storage_dir)
            print(f"OK: {name} -> model_id={result['model_id']} version={result['version']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(run(sys.argv[1], sys.argv[2], sys.argv[3]))
