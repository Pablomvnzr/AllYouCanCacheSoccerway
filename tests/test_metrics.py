import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'metrics-service/src'))
from metrics_store import MetricsStore


class MetricsTests(unittest.TestCase):
    def event(self, status, success=True, latency=2, source=None):
        return dict(query_type='Q5', cache_status=status, success=success,
                    latency_ms=latency, scraper_latency_ms=source, evictions=0)

    def test_formula_excludes_unclassified_errors(self):
        store = MetricsStore()
        store.add(self.event('hit'))
        store.add(self.event('miss', latency=100, source=80))
        store.add(self.event('error', success=False))
        m = store.summary()
        self.assertEqual(m['hit_rate'], .5)
        self.assertEqual(m['errors'], 1)
        self.assertEqual(m['cache_efficiency_ms'], -26)

    def test_bounded_storage_keeps_accumulated_counts(self):
        store = MetricsStore(max_events=2)
        for _ in range(5):
            store.add(self.event('hit'))
        self.assertEqual(store.summary()['total_requests'], 5)
        self.assertEqual(store.summary()['hits'], 5)
        self.assertTrue(store.page(0, 100)['truncated'])
        self.assertEqual(len(store.page(0, 100)['events']), 2)

    def test_efficiency_without_hits(self):
        store = MetricsStore()
        store.add(self.event('miss', latency=100, source=80))
        self.assertEqual(store.summary()['cache_efficiency_ms'], -80)
