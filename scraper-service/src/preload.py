"""Obtiene un snapshot real antes del despliegue; no usa base de datos."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from itertools import combinations

from src.main import obtener_html_renderizado, url_equipo, url_h2h, extraer_mid, URL_TABLA_POSICIONES, URL_PARTIDOS, URL_RESULTADOS
from src.parsers import parse_ultimos_partidos, parse_proximos_partidos


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/repo/scraper-service/data/snapshot.json')
    parser.add_argument('--all-pairs',action='store_true')
    args=parser.parse_args()
    sys.path.insert(0,'/repo/generador_trafico/src')
    from query_builder import EQUIPOS
    pages={}
    for url in [url_equipo(t['slug'],t['id']) for t in EQUIPOS]+[URL_TABLA_POSICIONES,URL_PARTIDOS,URL_RESULTADOS]:
        print(f'Precargando {url}',flush=True)
        pages[url]=obtener_html_renderizado(url)
    pairs=list(combinations(EQUIPOS,2)) if args.all_pairs else [(EQUIPOS[0],EQUIPOS[1]),(EQUIPOS[0],EQUIPOS[2])]
    missing=[]
    for a,b in pairs:
        references=[]
        for team in (a,b):
            html=pages[url_equipo(team['slug'],team['id'])]
            references += parse_ultimos_partidos(html)+parse_proximos_partidos(html)
        mid=next((extraer_mid(p['url_partido']) for p in references if p.get('url_partido') and f"{a['slug']}-{a['id']}" in p['url_partido'] and f"{b['slug']}-{b['id']}" in p['url_partido']),None)
        if not mid:
            missing.append([a['slug'],b['slug']])
            continue
        url=url_h2h(a['slug'],a['id'],b['slug'],b['id'],mid)
        print(f'Precargando {url}',flush=True)
        pages[url]=obtener_html_renderizado(url)
    result=dict(schema_version=1,created_at=datetime.now(timezone.utc).isoformat(),pages=pages,
                scope='all_requested_pairs' if args.all_pairs else 'default_catalog_and_ttl',missing_h2h_references=missing)
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    if missing:
        raise SystemExit(f'Snapshot parcial: faltan referencias H2H {missing}')
    print(f'Snapshot completo para el catálogo solicitado: {len(pages)} páginas; {output}',flush=True)


if __name__=='__main__':
    main()
