from collections import Counter, deque
from datetime import datetime, timezone
from math import ceil
from statistics import mean
from threading import Lock


class MetricsStore:
    """Contadores acumulados y ventana acotada para ejecución continua."""
    def __init__(self, max_events=10000):
        self._lock = Lock()
        self.max_events = max_events
        self.reset()

    def reset(self):
        with self._lock:
            self._events = deque(maxlen=self.max_events)
            self._counts = Counter()
            self._hit_time = self._source_time = 0.0
            self._started_at = datetime.now(timezone.utc)

    def add(self, event):
        event = dict(event, recorded_at=datetime.now(timezone.utc))
        with self._lock:
            self._events.append(event)
            self._counts["total"] += 1
            self._counts[event["cache_status"]] += 1
            self._counts["success"] += int(event["success"])
            self._counts['benchmark'] += int(event.get('source_origin') == 'benchmark')
            self._counts["evictions"] += event.get("evictions", 0)
            self._counts["expired_keys"] += event.get("expired_keys", 0)
            if event["success"] and event["cache_status"] == "hit":
                self._hit_time += event["latency_ms"]
            if event["cache_status"] == "miss":
                self._source_time += event.get("scraper_latency_ms") or 0.0

    def recent(self, limit):
        with self._lock:
            return [self._serializar(e) for e in list(self._events)[-limit:]]

    def page(self, offset, limit):
        with self._lock:
            events = list(self._events)
            return dict(events=[self._serializar(e) for e in events[offset:offset+limit]],
                        retained=len(events), total=self._counts["total"],
                        truncated=self._counts["total"] > len(events))

    def summary(self):
        with self._lock:
            events, c = list(self._events), self._counts.copy()
            started = self._started_at
            efficiency = self._hit_time - self._source_time
        total, hits, misses = c["total"], c["hit"], c["miss"]
        elapsed = max((datetime.now(timezone.utc)-started).total_seconds(), .001)
        return dict(
            total_requests=total, successful_requests=c["success"], hits=hits, misses=misses,
            errors=total-c["success"], hit_rate=round(hits/(hits+misses), 4) if hits+misses else 0.0,
            miss_rate=round(misses/(hits+misses), 4) if hits+misses else 0.0,
            error_rate=round((total-c["success"])/total, 4) if total else 0.0,
            throughput_rps=round(c["success"]/elapsed, 4),
            latency_ms=self._distribution([e["latency_ms"] for e in events]),
            scraper_latency_ms=self._distribution([e["scraper_latency_ms"] for e in events if e.get("source_origin", "scraper") == "scraper" and e.get("scraper_latency_ms") is not None]),
            evictions=c["evictions"], expired_keys=c["expired_keys"],
            eviction_rate_per_min=round(c["evictions"]/(elapsed/60), 4),
            cache_efficiency_ms=None if c['benchmark'] else round(efficiency/total, 4) if total else 0.0,
            elapsed_seconds=round(elapsed, 3),
            latency_scope="server_internal_before_telemetry_and_serialization",
            percentile_window=len(events), events_truncated=total>len(events),
            by_query={q: dict(requests=len(group), hits=sum(e["cache_status"]=="hit" for e in group),
                              errors=sum(not e["success"] for e in group),
                              latency_ms=self._distribution([e["latency_ms"] for e in group]))
                      for q in sorted({e["query_type"] for e in events})
                      for group in [[e for e in events if e["query_type"]==q]]},
        )

    @staticmethod
    def _distribution(values):
        if not values:
            return dict(average=0.0, p50=0.0, p95=0.0)
        values = sorted(values)
        return dict(average=round(mean(values),3),
                    p50=round(values[max(0,ceil(.5*len(values))-1)],3),
                    p95=round(values[max(0,ceil(.95*len(values))-1)],3))

    @staticmethod
    def _serializar(event):
        return dict(event, recorded_at=event["recorded_at"].isoformat())
