"""Resume solamente evidencia nueva, válida y sin mezclar cargas reales/sintéticas."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-complete',action='store_true',help='Falla si falta cualquier caso de las tres matrices')
    args=parser.parse_args()
    latest = {}
    excluded = []
    stale = []
    for path in sorted((ROOT / 'experiments/results').glob('*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 2:
            continue
        if not data.get('validation', {}).get('all_requests_successful'):
            excluded.append(path.name)
            continue
        name = data['name']
        config_path=ROOT/'experiments/configs'/f'{name}.json'
        # Compara parámetros, no saltos de línea LF/CRLF de distintos sistemas.
        if config_path.exists() and json.loads(config_path.read_text(encoding='utf-8')) != data['configuration']:
            stale.append(path.name)
            continue
        if name not in latest or data['created_at'] > latest[name][1]['created_at']:
            latest[name] = (path, data)
    output = ROOT / 'experiments/analysis'
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    ttl = []
    pressure = []
    for name, (path, data) in sorted(latest.items()):
        m = data['metrics']
        rows.append(dict(name=name, workload=data['workload_kind'], requests=m['total_requests'],
                         hits=m['hits'], misses=m['misses'], errors=m['errors'], hit_rate=m['hit_rate'],
                         throughput_rps=m['throughput_rps'], p50_ms=m['latency_ms']['p50'],
                         p95_ms=m['latency_ms']['p95'], evictions=m['evictions'],
                         scraper_average_ms=(m.get('scraper_latency_ms') or {}).get('average') if data['workload_kind']!='synthetic_cache_pressure' else None,
                         efficiency_ms=m.get('cache_efficiency_ms') if data['workload_kind']!='synthetic_cache_pressure' else None,
                         evictions_per_min=m['eviction_rate_per_min'],
                         expired_keys=m['expired_keys'], source=path.name))
        if name.startswith('pressure-'):
            pressure.append(dict(name=name, passed=m['evictions'] > 0 and m['expired_keys'] == 0,
                                 evictions=m['evictions'], expired_keys=m['expired_keys']))
        if name.startswith('ttl-'):
            statuses = [e.get('cache_status', 'error') for e in data['client']['events']]
            expected = ['miss', 'miss'] if data['configuration']['cache']['ttl_seconds'] == 3 else ['miss', 'hit']
            ttl.append(dict(name=name, observed=statuses, expected=expected, passed=statuses == expected,
                            expired_keys=m['expired_keys']))
    if rows:
        with (output / 'summary.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    checks = dict(valid_configurations=len(rows), excluded_failed_runs=excluded, excluded_changed_configurations=stale, ttl=ttl, pressure=pressure,
                  expected_matrices=dict(ttl=10, pressure=12, functional=8),
                  observed_matrices={group: sum(r['name'].startswith(group+'-') for r in rows) for group in ('ttl','pressure','functional')})
    (output / 'validation.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    missing=any(checks['observed_matrices'][group] != expected for group,expected in checks['expected_matrices'].items())
    return int(any(not case['passed'] for case in ttl + pressure) or (args.require_complete and missing))


if __name__ == '__main__':
    raise SystemExit(main())
