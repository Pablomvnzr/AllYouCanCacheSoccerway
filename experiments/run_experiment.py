"""Ejecuta una configuración reproducible y exporta sus métricas en JSON."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "experiments" / "results"
METRICS_BASE_URL = "http://localhost:9000"


def request_json(path: str, method: str = "GET") -> dict:
    request = Request(f"{METRICS_BASE_URL}{path}", method=method)
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_service(base_url: str, timeout_seconds: int = 90):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=5) as response:
                health = json.loads(response.read().decode("utf-8"))
            if health.get("status") == "ok":
                return
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"{base_url} no respondió dentro del tiempo esperado")


def compose(command: list[str], environment: dict[str, str], check: bool = True):
    return subprocess.run(
        ["docker", "compose", *command],
        cwd=ROOT,
        env=environment,
        check=check,
    )


def build_environment(config: dict) -> dict[str, str]:
    traffic = config["traffic"]
    cache = config["cache"]
    environment = os.environ.copy()
    environment.update(
        {
            "CACHE_MAXMEMORY": str(cache["maxmemory"]),
            "CACHE_EVICTION_POLICY": str(cache["eviction_policy"]),
            "CACHE_TTL_SECONDS": str(cache["ttl_seconds"]),
            "TRAFFIC_DISTRIBUTION": str(traffic["distribution"]),
            "TRAFFIC_REQUEST_COUNT": str(traffic["request_count"]),
            "TRAFFIC_ARRIVAL_SECONDS": str(traffic["arrival_seconds"]),
            "TRAFFIC_ZIPF_ALPHA": str(traffic["zipf_alpha"]),
        }
    )
    fixed_payload = traffic.get("fixed_payload")
    if fixed_payload is not None:
        environment["TRAFFIC_FIXED_PAYLOAD"] = json.dumps(fixed_payload)
    benchmark = config.get("benchmark")
    if benchmark is not None:
        environment["TRAFFIC_BENCHMARK_KEY_SPACE"] = str(benchmark["key_space"])
        environment["TRAFFIC_BENCHMARK_VALUE_BYTES"] = str(benchmark["value_bytes"])
    return environment


def validate_config(config: dict):
    required = {
        "traffic": {"distribution", "request_count", "arrival_seconds", "zipf_alpha"},
        "cache": {"maxmemory", "eviction_policy", "ttl_seconds"},
    }
    for section, keys in required.items():
        missing = keys - set(config.get(section, {}))
        if missing:
            raise ValueError(f"Faltan claves en {section}: {', '.join(sorted(missing))}")
    if config["traffic"]["distribution"] not in {"uniforme", "zipf"}:
        raise ValueError("traffic.distribution debe ser 'uniforme' o 'zipf'")
    fixed_payload = config["traffic"].get("fixed_payload")
    if fixed_payload is not None:
        if not isinstance(fixed_payload, dict) or fixed_payload.get("tipo") not in {"Q1", "Q2", "Q3", "Q4", "Q5"}:
            raise ValueError("traffic.fixed_payload debe ser un payload válido de Q1 a Q5")
    benchmark = config.get("benchmark")
    if benchmark is not None:
        if not isinstance(benchmark, dict):
            raise ValueError("benchmark debe ser un objeto")
        for key in ("key_space", "value_bytes"):
            if not isinstance(benchmark.get(key), int) or benchmark[key] < 1:
                raise ValueError(f"benchmark.{key} debe ser un entero positivo")
    if config["cache"]["eviction_policy"] not in {"allkeys-lru", "allkeys-lfu"}:
        raise ValueError("Use allkeys-lru o allkeys-lfu como eviction_policy")


def run(config_path: Path, keep_running: bool):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    environment = build_environment(config)
    name = config.get("name", config_path.stem)

    try:
        # traffic-generator se ejecuta después con ``compose run`` y por eso
        # no se reconstruye automáticamente al levantar sólo los servicios base.
        compose(["build", "traffic-generator"], environment)
        compose(
            [
                "up", "--build", "--force-recreate", "-d",
                "redis", "scraper-service", "metrics-service", "cache-service",
            ],
            environment,
        )
        wait_for_service(METRICS_BASE_URL)
        wait_for_service("http://localhost:5001")
        request_json("/reset", method="POST")
        compose(["run", "--rm", "traffic-generator"], environment)

        result = {
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "configuration": config,
            "metrics": request_json("/metrics"),
            "events": request_json("/events?limit=1000")["events"],
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / f"{name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Resultado guardado en: {output_path.relative_to(ROOT)}")
    finally:
        if not keep_running:
            compose(["down"], environment, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Archivo JSON de configuración")
    parser.add_argument(
        "--keep-running",
        action="store_true",
        help="No detiene los contenedores al finalizar",
    )
    args = parser.parse_args()

    try:
        run(args.config, args.keep_running)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Experimento falló: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
