from typing import Optional
import re

from fastapi import FastAPI
from playwright.sync_api import sync_playwright

from parsers import (
    parse_tabla_posiciones,
    parse_proximos_partidos,
    parse_ultimos_partidos,
    parse_h2h,
)

app = FastAPI(title="Scraper Service")

URL_TABLA_POSICIONES = "https://cl.soccerway.com/chile/liga-de-primera/tabla-de-posiciones/"


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
            page.click(selector, timeout=2000)
            return True
        except Exception:
            continue
    return False


def obtener_html_renderizado(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)
        aceptar_cookies(page)
        page.wait_for_timeout(1500)
        html = page.content()
        browser.close()
        return html


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
    return {"status": "ok"}


@app.get("/consulta/tabla-posiciones")
def tabla_posiciones():
    html = obtener_html_renderizado(URL_TABLA_POSICIONES)
    tabla = parse_tabla_posiciones(html)
    return {"liga": "Primera Division Chile", "tabla": tabla}


@app.get("/consulta/proximos-partidos/{slug}/{equipo_id}")
def proximos_partidos(slug: str, equipo_id: str):
    html = obtener_html_renderizado(url_equipo(slug, equipo_id))
    partidos = parse_proximos_partidos(html)
    return {"equipo": slug, "proximos_partidos": partidos}


@app.get("/consulta/ultimos-partidos/{slug}/{equipo_id}")
def ultimos_partidos(slug: str, equipo_id: str):
    html = obtener_html_renderizado(url_equipo(slug, equipo_id))
    partidos = parse_ultimos_partidos(html)
    return {"equipo": slug, "ultimos_partidos": partidos}


@app.get("/consulta/enfrentamientos/{slug1}/{id1}/{slug2}/{id2}")
def historial_enfrentamientos(slug1: str, id1: str, slug2: str, id2: str):
    # 1. Obtenemos un partido entre ambos equipos para usar su ``mid`` como
    # referencia. Usar simplemente el primer partido reciente de equipo 1
    # puede abrir el H2H contra un rival distinto y producir una lista vacía.
    html_equipo1 = obtener_html_renderizado(url_equipo(slug1, id1))
    ultimos = parse_ultimos_partidos(html_equipo1)

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
        return {
            "error": (
                "No se encontro un partido reciente entre ambos equipos "
                "para construir la consulta H2H"
            )
        }

    # 2. Construimos la URL de H2H y scrapeamos
    html_h2h = obtener_html_renderizado(url_h2h(slug1, id1, slug2, id2, mid_referencia))

    # Necesitamos los nombres "bonitos" de los equipos (ej. "Colo Colo") para filtrar
    tabla = parse_tabla_posiciones(obtener_html_renderizado(URL_TABLA_POSICIONES))
    nombre1 = next((e["equipo"] for e in tabla if e["equipo_slug"] == slug1), slug1)
    nombre2 = next((e["equipo"] for e in tabla if e["equipo_slug"] == slug2), slug2)

    enfrentamientos = parse_h2h(html_h2h, nombre1, nombre2)
    return {"equipo_1": nombre1, "equipo_2": nombre2, "enfrentamientos": enfrentamientos}
