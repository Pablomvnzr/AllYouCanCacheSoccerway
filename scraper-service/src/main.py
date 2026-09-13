from typing import Optional
import re
import os
import json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

from src.parsers import (
    parse_tabla_posiciones,
    parse_proximos_partidos,
    parse_ultimos_partidos,
    parse_h2h,
    parse_partidos_liga,
    filtrar_partidos_por_fecha,
)

PRELOADED_HTML = {}
SNAPSHOT_REFERENCE_YEAR = None


@asynccontextmanager
async def lifespan(app):
    global SNAPSHOT_REFERENCE_YEAR
    if os.getenv('SCRAPER_MODE', 'live') == 'preloaded':
        snapshot = json.loads(Path(os.getenv('SCRAPER_SNAPSHOT_PATH', '/data/snapshot.json')).read_text(encoding='utf-8'))
        if snapshot.get('schema_version') != 1 or not snapshot.get('pages'):
            raise RuntimeError('Snapshot ausente o inválido')
        PRELOADED_HTML.update(snapshot['pages'])
        SNAPSHOT_REFERENCE_YEAR = int(snapshot['created_at'][:4]) if snapshot.get('created_at') else None
    yield
    PRELOADED_HTML.clear()
    SNAPSHOT_REFERENCE_YEAR = None


app = FastAPI(title="Scraper Service", lifespan=lifespan)

URL_TABLA_POSICIONES = "https://cl.soccerway.com/chile/liga-de-primera/tabla-de-posiciones/"
URL_PARTIDOS = "https://cl.soccerway.com/chile/liga-de-primera/partidos/"
URL_RESULTADOS = "https://cl.soccerway.com/chile/liga-de-primera/resultados/"


def aceptar_cookies(page):
    """Intenta cerrar el banner de cookies probando varios selectores comunes."""
    selectores_posibles = [
        "button:has-text('Acepto')",
        "button:has-text('Aceptar todo')",
        "button:has-text('Aceptar')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "#onetrust-accept-btn-handler",
        "[id*='accept']",
        "[class*='accept']",
    ]
    for selector in selectores_posibles:
        try:
            locator = page.locator(selector).first
            if locator.is_visible():
                locator.click(timeout=2000)
                return True
        except Exception:
            continue
    return False


def obtener_html_renderizado(url: str) -> str:
    if os.getenv('SCRAPER_MODE', 'live') == 'preloaded':
        if url not in PRELOADED_HTML:
            raise HTTPException(503, 'La página requerida no pertenece al snapshot precargado; actualice la precarga')
        return PRELOADED_HTML[url]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
                if response is None or response.status >= 400:
                    raise HTTPException(502, f'Soccerway respondió HTTP {response.status if response else "desconocido"}')
                aceptar_cookies(page)
                page.wait_for_selector('div.ui-table__row, div[id^="g_1_"], a.h2h__row', timeout=20000)
                return page.content()
            finally:
                browser.close()
    except PlaywrightTimeout as error:
        raise HTTPException(504, 'Timeout esperando contenido de Soccerway') from error
    except PlaywrightError as error:
        raise HTTPException(502, 'No se pudo obtener contenido de Soccerway') from error


def url_equipo(slug: str, equipo_id: str) -> str:
    return f"https://cl.soccerway.com/equipo/{slug}/{equipo_id}/"


def url_h2h(slug1: str, id1: str, slug2: str, id2: str, mid: str) -> str:
    # ``general`` is the tab that contains the direct history rows parsed by
    # parse_h2h.  The parent ``/h2h/`` route can render a different view.
    return f"https://cl.soccerway.com/detalle-del-partido/{slug1}-{id1}/{slug2}-{id2}/h2h/general/?mid={mid}"


def extraer_mid(url: str) -> Optional[str]:
    match = re.search(r"mid=([A-Za-z0-9]+)", url)
    return match.group(1) if match else None


@app.get("/health")
def health_check():
    return {"status": "ok", "mode": os.getenv('SCRAPER_MODE', 'live'), "preloaded_pages": len(PRELOADED_HTML)}


@app.get("/consulta/tabla-posiciones")
def tabla_posiciones():
    html = obtener_html_renderizado(URL_TABLA_POSICIONES)
    tabla = parse_tabla_posiciones(html)
    if not tabla:
        raise HTTPException(502, 'Soccerway no devolvió una tabla interpretable')
    return {"liga": "Primera Division Chile", "tabla": tabla}


@app.get("/consulta/proximos-partidos/{slug}/{equipo_id}")
def proximos_partidos(slug: str, equipo_id: str):
    html = obtener_html_renderizado(url_equipo(slug, equipo_id))
    if not any('próximos' in h.get_text().lower() for h in BeautifulSoup(html, 'html.parser').select('h2')):
        raise HTTPException(502, 'No se encontró la sección de próximos partidos')
    partidos = parse_proximos_partidos(html)
    return {"equipo": slug, "proximos_partidos": partidos}


@app.get("/consulta/ultimos-partidos/{slug}/{equipo_id}")
def ultimos_partidos(slug: str, equipo_id: str):
    html = obtener_html_renderizado(url_equipo(slug, equipo_id))
    if not any('últimos resultados' in h.get_text().lower() for h in BeautifulSoup(html, 'html.parser').select('h2')):
        raise HTTPException(502, 'No se encontró la sección de resultados')
    partidos = parse_ultimos_partidos(html)
    return {"equipo": slug, "ultimos_partidos": partidos}


@app.get("/consulta/enfrentamientos/{slug1}/{id1}/{slug2}/{id2}")
def historial_enfrentamientos(slug1: str, id1: str, slug2: str, id2: str):
    # 1. Obtenemos un partido entre ambos equipos para usar su ``mid`` como
    # referencia. Usar simplemente el primer partido reciente de equipo 1
    # puede abrir el H2H contra un rival distinto y producir una lista vacía.
    html_equipo1 = obtener_html_renderizado(url_equipo(slug1, id1))
    ultimos = parse_ultimos_partidos(html_equipo1)
    ultimos += parse_proximos_partidos(html_equipo1)

    mid_referencia = None
    for partido in ultimos:
        url_partido = partido["url_partido"]
        if (
            url_partido
            and f"{slug1}-{id1}" in url_partido
            and f"{slug2}-{id2}" in url_partido
        ):
            mid_referencia = extraer_mid(url_partido)
            if mid_referencia:
                break

    if not mid_referencia:
        # Busca referencias también en el segundo equipo para cubrir su vista.
        html_equipo2 = obtener_html_renderizado(url_equipo(slug2, id2))
        for partido in parse_ultimos_partidos(html_equipo2) + parse_proximos_partidos(html_equipo2):
            link = partido.get('url_partido') or ''
            if f'{slug1}-{id1}' in link and f'{slug2}-{id2}' in link:
                mid_referencia = extraer_mid(link)
                if mid_referencia:
                    break
        if not mid_referencia:
            raise HTTPException(422, 'No hay referencia disponible para obtener este H2H en Soccerway')

    # 2. Construimos la URL de H2H y scrapeamos
    html_h2h = obtener_html_renderizado(url_h2h(slug1, id1, slug2, id2, mid_referencia))

    # Necesitamos los nombres "bonitos" de los equipos (ej. "Colo Colo") para filtrar
    tabla = parse_tabla_posiciones(obtener_html_renderizado(URL_TABLA_POSICIONES))
    nombre1 = next((e["equipo"] for e in tabla if e["equipo_slug"] == slug1), slug1)
    nombre2 = next((e["equipo"] for e in tabla if e["equipo_slug"] == slug2), slug2)

    enfrentamientos = parse_h2h(html_h2h, nombre1, nombre2)
    return {"equipo_1": nombre1, "equipo_2": nombre2, "enfrentamientos": enfrentamientos}


@app.get("/consulta/partidos-fecha")
def partidos_por_fecha(fecha_inicio: str, fecha_fin: str):
    """
    Consulta Q4: partidos de la liga en un rango de fechas.
    fecha_inicio y fecha_fin en formato DD.MM (ej: '05.09' y '14.09').
    """
    # La página principal sólo muestra una vista resumida. Para Q4 se usan las
    # páginas dedicadas de partidos programados y resultados finalizados.
    todos = []
    urls_vistas = set()
    for url in (URL_PARTIDOS, URL_RESULTADOS):
        for partido in parse_partidos_liga(obtener_html_renderizado(url)):
            llave = partido["url_partido"] or (
                partido["fecha"], partido["equipo_local"], partido["equipo_visitante"]
            )
            if llave not in urls_vistas:
                urls_vistas.add(llave)
                todos.append(partido)
    filtrados = filtrar_partidos_por_fecha(todos, fecha_inicio, fecha_fin, SNAPSHOT_REFERENCE_YEAR)
    return {"periodo": f"{fecha_inicio} a {fecha_fin}", "partidos": filtrados}
