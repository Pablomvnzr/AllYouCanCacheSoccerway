"""Verifica SIGTERM real del generador continuo con un origen precargado."""
import json
import subprocess
import time
import uuid
from pathlib import Path
from run_experiment import build_environment, wait_for_service, request_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    env=build_environment(json.loads((ROOT/'experiments/configs/preloaded-5mb-lru.json').read_text()))
    env.update(TRAFFIC_REQUEST_COUNT='0',TRAFFIC_ARRIVAL_SECONDS='0.01',TRAFFIC_FIXED_PAYLOAD='{"tipo":"Q5"}',TRAFFIC_RESULTS_PATH='/results/continuous.json')
    directory=ROOT/'tmp/continuous'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    name='cache-traffic-check-'+uuid.uuid4().hex[:12]
    def compose(*args): subprocess.run(['docker','compose',*args],cwd=ROOT,env=env,check=True)
    try:
        compose('up','--force-recreate','-d','redis','scraper-service','metrics-service','cache-service')
        wait_for_service('http://localhost:5001')
        request_json('/reset',method='POST')
        compose('run','--rm','--detach','--name',name,'--volume',f'{directory}:/results','traffic-generator')
        deadline=time.monotonic()+30
        while request_json('/metrics')['total_requests'] < 10:
            if time.monotonic()>deadline: raise RuntimeError('El generador continuo no progresó')
            time.sleep(.1)
        subprocess.run(['docker','stop','--time','10',name],cwd=ROOT,check=True)
        client=json.loads((directory/'continuous.json').read_text(encoding='utf-8'))
        metrics=request_json('/metrics')
        passed=client['stopped_by_user'] and client['counters']['attempted']>=10 and client['counters']['errors']==0 and metrics['total_requests']==client['counters']['attempted']
        path=ROOT/'experiments/analysis/continuous_evidence.json'
        path.write_text(json.dumps(dict(all_checks_passed=passed,signal='SIGTERM',client=client,metrics=metrics),indent=2,ensure_ascii=False),encoding='utf-8')
        print(f'Parada real del tráfico continuo: {passed}; {path}',flush=True)
        if not passed: raise RuntimeError('No pasó la parada del modo continuo')
    finally:
        subprocess.run(['docker','stop','--time','10',name],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        subprocess.run(['docker','compose','down'],cwd=ROOT,env=env,check=False)


if __name__=='__main__': main()
