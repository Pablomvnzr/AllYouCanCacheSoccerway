import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'generador_trafico/src'))
from distributions import probabilities, get_distribucion_index, arrival_delay
from query_builder import build_catalog


class DistributionTests(unittest.TestCase):
    def test_exact_finite_zipf(self):
        p = probabilities('zipf', 20, 1.5)
        self.assertAlmostEqual(float(p.sum()), 1)
        self.assertAlmostEqual(p[0] / p[1], 2 ** 1.5)
        self.assertTrue(np.all(np.diff(p) < 0))

    def test_same_seed_same_queries(self):
        a,b = np.random.default_rng(42), np.random.default_rng(42)
        self.assertEqual([get_distribucion_index('zipf', 54, 1.5, a) for _ in range(100)],
                         [get_distribucion_index('zipf', 54, 1.5, b) for _ in range(100)])

    def test_catalog_unique_and_types_configurable(self):
        catalog = build_catalog()
        self.assertEqual(len(catalog), 54)
        self.assertEqual(len({str(sorted(p.items())) for p in catalog}), 54)
        self.assertTrue(all(p['tipo']=='Q2' for p in build_catalog(['Q2'])))
        self.assertEqual(len(build_catalog(['Q3'], all_pairs=True)), 120)

    def test_arrival_delay_positive_and_uniform_mean(self):
        rng=np.random.default_rng(5)
        delays=[arrival_delay('uniforme', .2, rng) for _ in range(10000)]
        self.assertAlmostEqual(float(np.mean(delays)), .2, places=2)
        with self.assertRaises(ValueError):
            probabilities('zipf', 20, 1)
