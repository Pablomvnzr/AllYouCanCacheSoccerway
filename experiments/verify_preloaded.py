"""Comprueba las 54 consultas sobre el snapshot real sin llamadas externas."""
import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,'/repo/generador_trafico/src')
sys.path.insert(0,'/repo/scraper-service')
from query_builder import build_catalog
from src import main as scraper


async def check():
    rows=[]
    async with scraper.lifespan(scraper.app):
        with patch.object(scraper,'sync_playwright',side_effect=AssertionError('No debe consultar la red')):
            for q in build_catalog():
                kind=q['tipo']
                if kind=='Q1': result=scraper.proximos_partidos(q['slug'],q['equipo_id'])
                elif kind=='Q2': result=scraper.ultimos_partidos(q['slug'],q['equipo_id'])
                elif kind=='Q3': result=scraper.historial_enfrentamientos(q['slug1'],q['id1'],q['slug2'],q['id2'])
                elif kind=='Q4': result=scraper.partidos_por_fecha(q['fecha_inicio'],q['fecha_fin'])
                else: result=scraper.tabla_posiciones()
                field={'Q1':'proximos_partidos','Q2':'ultimos_partidos','Q3':'enfrentamientos','Q4':'partidos','Q5':'tabla'}[kind]
                rows.append(dict(query=q,rows=len(result[field]),success=isinstance(result[field],list)))
    output=Path('/repo/experiments/analysis/preloaded_evidence.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(dict(mode='preloaded',external_calls=0,queries=rows,all_successful=all(r['success'] for r in rows)),indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Verificadas {len(rows)} consultas; cero llamadas externas durante consultas.',flush=True)


if __name__=='__main__':
    asyncio.run(check())
