"""Comprobaciones estructurales de datos reales y cobertura de la tarea."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    samples={}
    for path in sorted((ROOT/'experiments/results').glob('*.json')):
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version')==2 and data.get('workload_kind')=='live_soccerway' and data.get('validation',{}).get('all_requests_successful'):
            samples.update(data['client'].get('response_samples',{}))
    fields={'Q1':'proximos_partidos','Q2':'ultimos_partidos','Q3':'enfrentamientos','Q4':'partidos','Q5':'tabla'}
    checks={}
    for query,field in fields.items():
        sample=samples.get(query,{})
        values=sample.get('data',{}).get(field)
        checks[query]=dict(present=isinstance(values,list), rows=len(values) if isinstance(values,list) else 0)
        if query=='Q1' and values:
            checks[query]['all_rows_have_time']=all('hora' in row for row in values)
    result=dict(functional_checks=checks, note='La estructura válida no sustituye contrastar exactitud y frescura con Soccerway.')
    output=ROOT/'experiments/analysis/functional_evidence.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return int(not all(case['present'] for case in checks.values()) or not checks['Q1'].get('all_rows_have_time',False) or checks['Q5']['rows']==0)


if __name__=='__main__':
    raise SystemExit(main())
