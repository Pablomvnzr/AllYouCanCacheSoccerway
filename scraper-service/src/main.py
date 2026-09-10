from fastapi import FastAPI
from playwright.sync_api import sync_playwright
from parsers import parse_tabla_posiciones, parse_proximos_partidos, parse_ultimos_partidos

app = FastAPI(title="Scraper Service")

URL_TABLA_POSICIONES = "https://cl.soccerway.com/chile/liga-de-primera/tabla-de-posiciones/"


def obtener_html_renderizado(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(2000)
        html = page.content()
        browser.close()
        return html


def url_equipo(slug: str, equipo_id: str) -> str:
    return f"https://cl.soccerway.com/equipo/{slug}/{equipo_id}/"


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
