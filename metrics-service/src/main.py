from typing import Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from metrics_store import MetricsStore

app = FastAPI(title="Metrics Service")
store = MetricsStore()


class MetricEvent(BaseModel):
    query_type: str
    cache_status: Literal["hit", "miss", "error"]
    success: bool
    latency_ms: float = Field(ge=0)
    scraper_latency_ms: float | None = Field(default=None, ge=0)
    error: str | None = None
    evictions: int = Field(default=0, ge=0)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/events", status_code=202)
def register_event(event: MetricEvent):
    store.add(event.model_dump())
    return {"status": "accepted"}


@app.get("/metrics")
def get_metrics():
    return store.summary()


@app.get("/events")
def get_events(limit: int = Query(default=100, ge=1, le=1000)):
    return {"events": store.recent(limit)}


@app.post("/reset")
def reset_metrics():
    store.reset()
    return {"status": "reset"}
