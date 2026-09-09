from fastapi import FastAPI
from playwright.sync_api import sync_playwright
from parsers import parse_tabla_posiciones

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


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/consulta/tabla-posiciones")
def tabla_posiciones():
    html = obtener_html_renderizado(URL_TABLA_POSICIONES)
    tabla = parse_tabla_posiciones(html)
    return {"liga": "Primera Division Chile", "tabla": tabla}
