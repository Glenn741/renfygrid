"""Patron "configuracion cacheada" (ver docs/03-diseno.md SS2).

La base de datos es siempre la fuente de verdad. Los procesos de alto desempeno
(motor VEE, adaptadores HES) NUNCA consultan la base de datos por cada lectura ni
llevan un valor de negocio fijo en el codigo: leen un snapshot local (JSON),
escrito por un ConfigCache.refresh() que si conoce la base de datos.

Este modulo es deliberadamente independiente de Postgres (no importa psycopg2):
recibe una funcion `fetch_fn` que devuelve las filas vigentes desde donde sea
(Postgres real en produccion, datos de prueba en un test). Esto es lo que permite
probar el patron completo sin una base de datos corriendo -- ver
tests/test_config_cache.py.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


class ConfigSnapshotError(RuntimeError):
    """El snapshot local no existe, esta corrupto, o nunca se refresco."""


FetchFn = Callable[[], Iterable[dict[str, Any]]]


@dataclass
class ConfigCache:
    """Cachea en un archivo plano el resultado de `fetch_fn`, y lo sirve en memoria.

    Uso tipico (un adaptador HES o el motor VEE, al arrancar):

        cache = ConfigCache(fetch_fn=fetch_active_vee_rules, snapshot_path=path)
        cache.refresh()   # solo la primera vez, o disparado por notificacion de la BD
        cache.load()
        rules = cache.get(tenant_id="...", type="range")

    `refresh()` y `load()` estan separados a proposito: un proceso corto (el job
    "Config Loader" de docs/03-diseno.md) hace refresh(); cada worker/adaptador de
    larga duracion solo hace load() -- no necesita saber nada de la BD.
    """

    fetch_fn: FetchFn
    snapshot_path: Path
    source_name: str = "config"
    _data: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _loaded_at: float | None = field(default=None, repr=False)

    def refresh(self) -> int:
        """Llama a fetch_fn (la BD) y escribe el snapshot de forma atomica.

        Escribe a un archivo temporal en el mismo directorio y hace os.replace,
        para que un load() concurrente nunca vea un archivo a medio escribir.
        Devuelve la cantidad de filas escritas.
        """
        rows = list(self.fetch_fn())
        payload = {
            "source": self.source_name,
            "generated_at": time.time(),
            "row_count": len(rows),
            "rows": rows,
        }

        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            dir=self.snapshot_path.parent, prefix=".tmp-", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(payload, tmp_file, ensure_ascii=False, indent=2)
            os.replace(tmp_name, self.snapshot_path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise
        return len(rows)

    def load(self) -> None:
        """Carga el snapshot mas reciente del disco a memoria (hot reload)."""
        if not self.snapshot_path.exists():
            raise ConfigSnapshotError(
                f"No existe snapshot en {self.snapshot_path} -- "
                "corre refresh() al menos una vez antes de load()."
            )
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigSnapshotError(
                f"Snapshot corrupto en {self.snapshot_path}: {exc}"
            ) from exc

        self._data = payload["rows"]
        self._loaded_at = payload["generated_at"]

    @property
    def loaded_at(self) -> float | None:
        return self._loaded_at

    def get_all(self) -> list[dict[str, Any]]:
        return list(self._data)

    def get(self, **filters: Any) -> list[dict[str, Any]]:
        """Filtra las filas cacheadas por igualdad exacta de campos.

        Ej.: cache.get(tenant_id="t1", type="range") -> reglas VEE de tipo
        range para ese tenant. Sin filtros devuelve todo lo cacheado.
        """
        if not filters:
            return self.get_all()
        return [
            row
            for row in self._data
            if all(row.get(key) == value for key, value in filters.items())
        ]
