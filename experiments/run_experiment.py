"""Ejecuta una configuración reproducible y exporta sus métricas en JSON."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import hashlib
import uuid
from math import ceil
from statistics import mean
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
            "TRAFFIC_FIXED_PAYLOAD": '',
            "TRAFFIC_BENCHMARK_KEY_SPACE": '0',
            "TRAFFIC_BENCHMARK_VALUE_BYTES": '0',
            "CACHE_ALLOW_BENCHMARK": '0',
            "SCRAPER_MODE": config.get('source_mode', 'live'),
            "TRAFFIC_SEED": str(traffic.get('seed', 42)),
            "TRAFFIC_QUERY_TYPES": json.dumps(traffic.get('query_types')) if traffic.get('query_types') else '',
            "TRAFFIC_ALL_PAIRS": str(int(traffic.get('all_pairs', False))),
            "TRAFFIC_ARRIVAL_DISTRIBUTION": traffic.get('arrival_distribution', 'constant'),
            "TRAFFIC_RESULTS_PATH": '/results/client-events.json',
        }
    )
    fixed_payload = traffic.get("fixed_payload")
    if fixed_payload is not None:
        environment["TRAFFIC_FIXED_PAYLOAD"] = json.dumps(fixed_payload)
    benchmark = config.get("benchmark")
    if benchmark is not None:
        environment['CACHE_ALLOW_BENCHMARK'] = '1'
        environment["TRAFFIC_BENCHMARK_KEY_SPACE"] = str(benchmark["key_space"])
        environment["TRAFFIC_BENCHMARK_VALUE_BYTES"] = str(benchmark["value_bytes"])
    return environment


def validate_config(config: dict):
    if config.get('source_mode', 'live') not in ('live','preloaded'):
        raise ValueError('source_mode debe ser live o preloaded')
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
    traffic = config['traffic']
    if type(traffic['request_count']) is not int or traffic['request_count'] < 1:
        raise ValueError('El runner exige corridas finitas; use Compose para modo continuo')
    if traffic['arrival_seconds'] < 0 or traffic['zipf_alpha'] <= 1 or config['cache']['ttl_seconds'] < 1:
        raise ValueError('Espera/alpha/TTL inválidos')
    if traffic.get('arrival_distribution', 'constant') not in ('constant', 'uniforme', 'zipf'):
        raise ValueError('Distribución de llegada inválida')
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


def run(config_path: Path, keep_running: bool, no_build: bool = False):
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes.decode('utf-8'))
    validate_config(config)
    environment = build_environment(config)
    name = config.get("name", config_path.stem)
    client_dir = ROOT / 'tmp' / 'traffic' / uuid.uuid4().hex
    client_dir.mkdir(parents=True, exist_ok=True)

    try:
        # traffic-generator se ejecuta después con ``compose run`` y por eso
        # no se reconstruye automáticamente al levantar sólo los servicios base.
        if not no_build:
            compose(["build", "traffic-generator"], environment)
        compose(
            [
                "up", *([] if no_build else ['--build']), "--force-recreate", "-d",
                "redis", "scraper-service", "metrics-service", "cache-service",
            ],
            environment,
        )
        wait_for_service(METRICS_BASE_URL)
        wait_for_service("http://localhost:5001")
        request_json("/reset", method="POST")
        def redis_stats():
            with urlopen('http://localhost:5001/redis/stats', timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        baseline = redis_stats()
        traffic_process = compose(['run', '--rm', '--volume', f'{client_dir}:/results', 'traffic-generator'], environment, check=False)
        client = json.loads((client_dir / 'client-events.json').read_text(encoding='utf-8'))
        metrics = request_json('/metrics')
        final_stats = redis_stats()
        elapsed = max(client['elapsed_seconds'], .001)
        values = sorted(e['latency_ms'] for e in client['events'])
        metrics['server_latency_ms'] = metrics['latency_ms']
        metrics['latency_ms'] = dict(average=round(mean(values),3), p50=round(values[max(0,ceil(.5*len(values))-1)],3), p95=round(values[max(0,ceil(.95*len(values))-1)],3)) if values else dict(average=0,p50=0,p95=0)
        metrics['latency_scope'] = 'client_end_to_end'
        metrics['scraper_latency_scope'] = 'in_memory_snapshot_processing' if config.get('source_mode')=='preloaded' else 'external_soccerway_fetch_and_parse'
        metrics['server_throughput_rps'] = metrics['throughput_rps']
        metrics['throughput_rps'] = client['counters']['successful'] / elapsed
        for output, raw in [('evictions','evicted_keys'), ('expired_keys','expired_keys')]:
            metrics[output] = max(0, int(final_stats[raw]) - int(baseline[raw]))
        metrics['eviction_rate_per_min'] = metrics['evictions'] * 60 / elapsed
        metrics['elapsed_seconds'] = elapsed
        if config.get('benchmark'):
            metrics['scraper_latency_scope'] = 'not_applicable'
            metrics['scraper_latency_ms'] = None
            metrics['cache_efficiency_ms'] = None
            metrics['source_metrics_applicable'] = False
        else:
            metrics['source_metrics_applicable'] = True
        exported = []
        offset = 0
        while True:
            page = request_json(f'/events?limit=1000&offset={offset}')
            exported.extend(page['events'])
            offset += len(page['events'])
            if not page['events'] or offset >= page['retained']:
                break
        revision = subprocess.run(['git','rev-parse','HEAD'], cwd=ROOT, capture_output=True, text=True)
        dirty = subprocess.run(['git','diff','--quiet'], cwd=ROOT, capture_output=True).returncode != 0
        running_ids = subprocess.run(['docker','compose','ps','-q'],cwd=ROOT,env=environment,capture_output=True,text=True,check=True).stdout.split()
        runtime_images = {}
        if running_ids:
            inspected=json.loads(subprocess.run(['docker','inspect',*running_ids],cwd=ROOT,capture_output=True,text=True,check=True).stdout)
            runtime_images={item['Config']['Image']:item['Image'] for item in inspected}
        complete = client['counters']['attempted'] == config['traffic']['request_count'] and not client['stopped_by_user']
        counts_match = metrics['total_requests'] == client['counters']['attempted']
        all_successful = complete and counts_match and traffic_process.returncode == 0 and client['counters']['errors'] == 0 and metrics['errors'] == 0
        validation = dict(traffic_exit_code=traffic_process.returncode,
                          expected_requests=config['traffic']['request_count'],
                          client_attempts=client['counters']['attempted'],
                          server_events=metrics['total_requests'],
                          complete=complete, counts_match=counts_match,
                          all_requests_successful=all_successful)

        result = {
            'schema_version': 2,
            'workload_kind': 'synthetic_cache_pressure' if config.get('benchmark') else 'preloaded_soccerway' if config.get('source_mode') == 'preloaded' else 'live_soccerway',
            'code_revision': revision.stdout.strip(),
            'code_dirty': dirty,
            'runtime_images': runtime_images,
            'config_sha256': hashlib.sha256(config_bytes).hexdigest(),
            'config_canonical_sha256': hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest(),
            'workspace_source_sha256': {str(p.relative_to(ROOT)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest()
                              for folder in ('generador_trafico/src','Sistemas_de_cache/src','scraper-service/src','metrics-service/src')
                              for p in sorted((ROOT/folder).glob('*.py'))},
            'client': client,
            'redis': dict(baseline=baseline, final=final_stats),
            'validation': validation,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "configuration": config,
            "metrics": metrics,
            "events": exported,
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / f"{name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Resultado guardado en: {output_path.relative_to(ROOT)}")
        if not result['validation']['all_requests_successful']:
            raise RuntimeError('Corrida guardada con errores o pérdida de métricas; revise validation')
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
    parser.add_argument('--no-build', action='store_true', help='Reutiliza imágenes ya reconstruidas')
    args = parser.parse_args()

    try:
        run(args.config, args.keep_running, args.no_build)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Experimento falló: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
