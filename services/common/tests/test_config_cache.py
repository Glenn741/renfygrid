"""Prueba el patron de configuracion cacheada (docs/03-diseno.md SS2) de punta a punta,
SIN Postgres: `fetch_fn` es una funcion de prueba, no una consulta real. Lo que se
verifica es el contrato -- refresh() escribe snapshot, load() lo lee, y un cambio
en la fuente se refleja tras un nuevo refresh()+load() (hot reload) -- que es
exactamente lo que hara el patron real contra la base de datos en produccion.

Correr con:  python -m unittest tests.test_config_cache -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from renmeter_common.config_cache import ConfigCache, ConfigSnapshotError


class FakeVeeRuleSource:
    """Sustituye a una consulta Postgres real (SELECT * FROM vee_rule WHERE is_active).

    Mutable a proposito: el test cambia .rows entre llamadas para simular que la
    BD cambio, sin tocar nada del ConfigCache ni del snapshot en disco a mano.
    """

    def __init__(self, rows):
        self.rows = rows
        self.call_count = 0

    def __call__(self):
        self.call_count += 1
        return self.rows


class ConfigCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.snapshot_path = Path(self.tmpdir.name) / "vee_rule.snapshot.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_load_without_prior_refresh_fails_with_clear_message(self):
        cache = ConfigCache(fetch_fn=lambda: [], snapshot_path=self.snapshot_path)
        with self.assertRaises(ConfigSnapshotError):
            cache.load()

    def test_refresh_then_load_exposes_source_rows(self):
        source = FakeVeeRuleSource(
            rows=[
                {"tenant_id": "t1", "type": "range", "params": {"min": 0, "max": 9999}},
                {"tenant_id": "t1", "type": "deviation", "params": {"max_pct": 2}},
                {"tenant_id": "t2", "type": "range", "params": {"min": 0, "max": 500}},
            ]
        )
        cache = ConfigCache(fetch_fn=source, snapshot_path=self.snapshot_path)

        n = cache.refresh()
        self.assertEqual(n, 3)
        self.assertTrue(self.snapshot_path.exists())

        cache.load()
        self.assertEqual(len(cache.get_all()), 3)

        # get() filtra igual que lo haria el motor VEE al pedir las reglas de UN tenant
        rules_t1 = cache.get(tenant_id="t1")
        self.assertEqual(len(rules_t1), 2)
        range_rule_t1 = cache.get(tenant_id="t1", type="range")
        self.assertEqual(range_rule_t1[0]["params"]["max"], 9999)

    def test_hot_path_never_calls_fetch_fn_again(self):
        """El motor VEE en produccion NO debe volver a tocar la BD por cada lectura.

        load() se puede llamar muchas veces (recarga en caliente) sin que eso
        dispare una nueva consulta a la fuente -- solo refresh() la toca.
        """
        source = FakeVeeRuleSource(rows=[{"tenant_id": "t1", "type": "range"}])
        cache = ConfigCache(fetch_fn=source, snapshot_path=self.snapshot_path)

        cache.refresh()
        self.assertEqual(source.call_count, 1)

        for _ in range(50):
            cache.load()
        self.assertEqual(source.call_count, 1, "load() no debe volver a llamar fetch_fn")

    def test_source_change_reflected_after_new_refresh_hot_reload(self):
        source = FakeVeeRuleSource(
            rows=[{"tenant_id": "t1", "type": "range", "params": {"max": 100}}]
        )
        cache = ConfigCache(fetch_fn=source, snapshot_path=self.snapshot_path)
        cache.refresh()
        cache.load()
        self.assertEqual(cache.get(tenant_id="t1")[0]["params"]["max"], 100)

        # Simula que alguien cambio la regla en la BD (como pediria el usuario:
        # "cambiar un umbral sin desplegar codigo") y llega la notificacion de refresco.
        source.rows = [{"tenant_id": "t1", "type": "range", "params": {"max": 250}}]
        cache.refresh()
        cache.load()

        self.assertEqual(cache.get(tenant_id="t1")[0]["params"]["max"], 250)
        self.assertEqual(source.call_count, 2)

    def test_corrupt_snapshot_raises_explicit_error_not_silent(self):
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_path.write_text("{ esto no es json valido", encoding="utf-8")
        cache = ConfigCache(fetch_fn=lambda: [], snapshot_path=self.snapshot_path)
        with self.assertRaises(ConfigSnapshotError):
            cache.load()


if __name__ == "__main__":
    unittest.main()
