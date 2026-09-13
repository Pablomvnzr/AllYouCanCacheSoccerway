"""Carga reproducible de consultas completas y latencia de extremo a extremo."""
import json
import os
import signal
import time
from collections import deque
from pathlib import Path

import numpy as np
import requests
import yaml
from distributions import get_distribucion_index, arrival_delay
from query_builder import build_catalog


def load_config():
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    overrides = {
        "cantidad_solicitudes": ("TRAFFIC_REQUEST_COUNT", int),
        "tasa_arribo_segundos": ("TRAFFIC_ARRIVAL_SECONDS", float),
        "distribucion": ("TRAFFIC_DISTRIBUTION", str),
        "parametro_zipf": ("TRAFFIC_ZIPF_ALPHA", float),
        "seed": ("TRAFFIC_SEED", int),
        "arrival_distribution": ("TRAFFIC_ARRIVAL_DISTRIBUTION", str),
        "benchmark_key_space": ("TRAFFIC_BENCHMARK_KEY_SPACE", int),
        "benchmark_value_bytes": ("TRAFFIC_BENCHMARK_VALUE_BYTES", int),
    }
    for field, (variable, cast) in overrides.items():
        if os.getenv(variable):
            config[field] = cast(os.environ[variable])
    return config


def iniciar_trafico():
    c = load_config()
    total, delay = c["cantidad_solicitudes"], c["tasa_arribo_segundos"]
    seed = c.get("seed", 42)
    if total < 0 or delay < 0:
        raise ValueError("Solicitudes o espera negativas")
    fixed = json.loads(os.getenv("TRAFFIC_FIXED_PAYLOAD") or "null")
    types = json.loads(os.getenv("TRAFFIC_QUERY_TYPES") or "null")
    catalog = build_catalog(types, os.getenv("TRAFFIC_ALL_PAIRS") == "1")
    key_space, size = c.get("benchmark_key_space", 0), c.get("benchmark_value_bytes", 0)
    if bool(key_space) != bool(size) or not 0 <= size <= 1_000_000 or key_space < 0:
        raise ValueError("Configuración benchmark inválida")
    benchmark = key_space > 0 and size > 0
    if benchmark:
        catalog = [dict(catalog[i % len(catalog)], benchmark_id=i, benchmark_value_bytes=size) for i in range(key_space)]
    # La permutación mantiene un catálogo idéntico entre distribuciones/políticas.
    np.random.default_rng(seed + 2).shuffle(catalog)
    rng, arrivals = np.random.default_rng(seed), np.random.default_rng(seed + 1)
    records, samples = deque(maxlen=10000), {}
    counters = dict(attempted=0, successful=0, errors=0)
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    print(f"Tráfico {c['distribucion']}; catálogo {len(catalog)}; seed {seed}; llegada closed-loop", flush=True)
    started = time.perf_counter()
    while not stopped and (total == 0 or counters["attempted"] < total):
        payload = dict(fixed) if fixed else dict(catalog[get_distribucion_index(c["distribucion"], len(catalog), c["parametro_zipf"], rng)])
        event = dict(payload=payload, success=False)
        print(f"[{counters['attempted'] + 1}/{total or 'continuo'}] Enviando {payload['tipo']}: {payload}", flush=True)
        start = time.perf_counter()
        try:
            response = requests.post(os.getenv("CACHE_URL", "http://localhost:5000/api/consultas"), json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            if result.get("status") not in ("hit", "miss") or not isinstance(result.get("datos"), dict) or result["datos"].get("error"):
                raise ValueError("Respuesta inválida")
            event.update(success=True, cache_status=result["status"], origin=result["origen"])
            print(f" -> {result['status'].upper()}: respuesta desde {result['origen']}", flush=True)
            # Evidencia funcional acotada: primera respuesta válida de cada tipo.
            samples.setdefault(payload["tipo"], dict(query=payload, data=result["datos"]))
        except (requests.RequestException, ValueError, KeyError) as error:
            event["error"] = str(error)
            print(f" -> ERROR: {error}", flush=True)
        event["latency_ms"] = (time.perf_counter() - start) * 1000
        counters["attempted"] += 1
        counters["successful" if event["success"] else "errors"] += 1
        records.append(event)
        if total and counters["attempted"] == total:
            break
        pause = arrival_delay(c.get("arrival_distribution", "constant"), delay, arrivals, c["parametro_zipf"])
        deadline = time.perf_counter() + pause
        while not stopped and time.perf_counter() < deadline:
            time.sleep(max(0, min(0.1, deadline - time.perf_counter())))
    result = dict(configuration=c, counters=counters, stopped_by_user=stopped,
                  elapsed_seconds=time.perf_counter() - started, arrival_mode="closed-loop",
                  events=list(records), events_truncated=counters["attempted"] > len(records),
                  response_samples=samples)
    if os.getenv("TRAFFIC_RESULTS_PATH"):
        path = Path(os.environ["TRAFFIC_RESULTS_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Tráfico detenido por el usuario." if stopped else "Tráfico finalizado con errores." if counters["errors"] else "Tráfico finalizado con éxito.", flush=True)
    return 1 if counters["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(iniciar_trafico())
