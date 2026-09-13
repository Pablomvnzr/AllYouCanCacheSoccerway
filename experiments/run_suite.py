"""Ejecuta una matriz secuencial y deja evidencia de éxitos y fallos."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('group', choices=['ttl', 'pressure', 'functional', 'all'])
    parser.add_argument('--no-build', action='store_true')
    parser.add_argument('--config',action='append',help='Limita la matriz a un nombre de configuración; puede repetirse')
    args = parser.parse_args()
    prefixes = {'ttl': ['ttl-'], 'pressure': ['pressure-'], 'functional': ['functional-'], 'all': ['ttl-', 'pressure-', 'functional-']}[args.group]
    configs = sorted(p for p in (ROOT/'experiments/configs').glob('*.json') if any(p.name.startswith(prefix) for prefix in prefixes))
    if args.config:
        requested=set(args.config)
        configs=[p for p in configs if p.name in requested or p.stem in requested]
        matched={p.name for p in configs}|{p.stem for p in configs}
        if not requested <= matched:
            raise SystemExit(f'Configuraciones inexistentes en esta matriz: {requested-matched}')
    if not configs:
        raise SystemExit('No hay configuraciones para esta matriz')
    if not args.no_build:
        subprocess.run(['docker','compose','build','traffic-generator','cache-service','metrics-service','scraper-service'], cwd=ROOT, check=True)
    summary=[]
    for config in configs:
        print(f'Iniciando {config.name}', flush=True)
        before=set((ROOT/'experiments/results').glob('*.json'))
        process=subprocess.run([sys.executable, str(ROOT/'experiments/run_experiment.py'), str(config),'--no-build'], cwd=ROOT)
        outputs=sorted(set((ROOT/'experiments/results').glob('*.json'))-before)
        summary.append(dict(config=config.name, exit_code=process.returncode,
                            results=[str(p.relative_to(ROOT)).replace('\\','/') for p in outputs]))
    path=ROOT/'experiments/results'/f"suite-{args.group}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(dict(created_at=datetime.now(timezone.utc).isoformat(),runs=summary), indent=2),encoding='utf-8')
    print(f'Matriz guardada en {path}')
    return int(any(s['exit_code'] for s in summary))


if __name__=='__main__':
    raise SystemExit(main())
