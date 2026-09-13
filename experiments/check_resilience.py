"""Fallos controlados del stack de pruebas; siempre detiene sus servicios al finalizar."""
import json
import subprocess
from time import perf_counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from run_experiment import build_environment, wait_for_service

ROOT=Path(__file__).resolve().parents[1]


def query(payload):
    started=perf_counter()
    request=Request('http://localhost:5001/api/consultas',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(request,timeout=30) as response:
            return dict(http_status=response.status,body=json.loads(response.read()),elapsed_seconds=perf_counter()-started)
    except HTTPError as error:
        return dict(http_status=error.code,body=json.loads(error.read()),elapsed_seconds=perf_counter()-started)


def main():
    config=json.loads((ROOT/'experiments/configs/preloaded-5mb-lru.json').read_text())
    env=build_environment(config)
    def compose(*args):
        subprocess.run(['docker','compose',*args],cwd=ROOT,env=env,check=True)
    cases={}
    evidence={}
    try:
        compose('up','--force-recreate','-d','redis','scraper-service','metrics-service','cache-service')
        wait_for_service('http://localhost:5001')
        wait_for_service('http://localhost:9000')
        with urlopen(Request('http://localhost:9000/reset',method='POST'),timeout=10): pass
        cases['invalid_query']=query(dict(tipo='Q1'))
        cases['first_query']=query(dict(tipo='Q5'))
        cases['repeated_query']=query(dict(tipo='Q5'))
        compose('stop','scraper-service')
        cases['scraper_unavailable']=query(dict(tipo='Q1',slug='colo-colo',equipo_id='th4HPIws'))
        compose('start','scraper-service')
        compose('stop','redis')
        cases['redis_unavailable']=query(dict(tipo='Q5'))
        with urlopen('http://localhost:9000/events?limit=100',timeout=10) as response:
            evidence['events_before_metrics_restart']=json.loads(response.read())
        compose('start','redis')
        wait_for_service('http://localhost:5001')
        query(dict(tipo='Q5'))
        compose('stop','metrics-service')
        cases['metrics_unavailable']=query(dict(tipo='Q5'))
        expected={'invalid_query':400,'first_query':200,'repeated_query':200,'scraper_unavailable':502,'redis_unavailable':503,'metrics_unavailable':200}
        events=evidence['events_before_metrics_restart']['events']
        passed=all(cases[name]['http_status']==status for name,status in expected.items())
        passed=passed and cases['first_query']['body']['status']=='miss' and cases['repeated_query']['body']['status']=='hit'
        passed=passed and sum(not e['success'] for e in events)==3
        passed=passed and cases['metrics_unavailable']['body']['status']=='hit'
        passed=passed and cases['redis_unavailable']['elapsed_seconds'] < 10
        evidence.update(cases=cases,expected_http_statuses=expected,all_checks_passed=passed,
                        limitation='Cuando Metrics está indisponible, el hit funciona pero su telemetría no puede persistirse; no existe cola durable.')
        path=ROOT/'experiments/analysis/resilience.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
        print(f'Integración de errores: {passed}; {path}',flush=True)
        if not passed: raise RuntimeError('Falló una comprobación de resiliencia')
    finally:
        subprocess.run(['docker','compose','down'],cwd=ROOT,env=env,check=False)


if __name__=='__main__':
    main()
