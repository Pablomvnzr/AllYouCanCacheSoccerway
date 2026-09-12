from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from statistics import mean
from threading import Lock


class MetricsStore:
    """Almacenamiento en memoria de eventos de una ejecución experimental."""

    def __init__(self):
        self._lock = Lock()
        self.reset()

    def reset(self):
        with self._lock:
            self._events: list[dict] = []
            self._started_at = datetime.now(timezone.utc)

    def add(self, event: dict):
        with self._lock:
            event["recorded_at"] = datetime.now(timezone.utc)
            self._events.append(event)

    def recent(self, limit: int) -> list[dict]:
        with self._lock:
            return [self._serializar(event) for event in self._events[-limit:]]

    def summary(self) -> dict:
        with self._lock:
            events = list(self._events)
            started_at = self._started_at

        total = len(events)
        hits = sum(event["cache_status"] == "hit" for event in events)
        misses = sum(event["cache_status"] == "miss" for event in events)
        successes = sum(event["success"] for event in events)
        errors = total - successes
        evictions = sum(event["evictions"] for event in events)
        elapsed_seconds = max(
            (datetime.now(timezone.utc) - started_at).total_seconds(), 0.001
        )

        latencies = [event["latency_ms"] for event in events]
        scraper_latencies = [
            event["scraper_latency_ms"]
            for event in events
            if event["scraper_latency_ms"] is not None
        ]
        hit_latencies = [
            event["latency_ms"] for event in events if event["cache_status"] == "hit"
        ]
        miss_latencies = [
            event["latency_ms"] for event in events if event["cache_status"] == "miss"
        ]

        cache_efficiency_ms = 0.0
        if total and hit_latencies and miss_latencies:
            cache_efficiency_ms = (
                hits * mean(hit_latencies) - misses * mean(miss_latencies)
            ) / total

        return {
            "total_requests": total,
            "successful_requests": successes,
            "hits": hits,
            "misses": misses,
            "errors": errors,
            "hit_rate": round(hits / total, 4) if total else 0.0,
            "miss_rate": round(misses / total, 4) if total else 0.0,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "throughput_rps": round(successes / elapsed_seconds, 4),
            "latency_ms": self._distribution(latencies),
            "scraper_latency_ms": self._distribution(scraper_latencies),
            "evictions": evictions,
            "eviction_rate_per_min": round(evictions / (elapsed_seconds / 60), 4),
            "cache_efficiency_ms": round(cache_efficiency_ms, 4),
            "elapsed_seconds": round(elapsed_seconds, 3),
        }

    @staticmethod
    def _distribution(values: list[float]) -> dict:
        if not values:
            return {"average": 0.0, "p50": 0.0, "p95": 0.0}
        ordered = sorted(values)
        return {
            "average": round(mean(ordered), 3),
            "p50": round(MetricsStore._percentile(ordered, 50), 3),
            "p95": round(MetricsStore._percentile(ordered, 95), 3),
        }

    @staticmethod
    def _percentile(ordered_values: list[float], percentile: int) -> float:
        index = max(0, ceil((percentile / 100) * len(ordered_values)) - 1)
        return ordered_values[index]

    @staticmethod
    def _serializar(event: dict) -> dict:
        result = dict(event)
        result["recorded_at"] = result["recorded_at"].isoformat()
        return result
