import os

import requests
from fastapi import FastAPI, HTTPException, Request

from key_builder import generar_llave
from cache_manager import cache_disponible, guardar_en_cache, obtener_de_cache

app = FastAPI(title="Sistema de Caché")

SCRAPER_URL = os.getenv("SCRAPER_URL", "http://localhost:8000").rstrip("/")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
SCRAPER_TIMEOUT_SECONDS = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "120"))


def url_scraper(payload: dict) -> str:
    """Traduce el contrato común Q1-Q5 a la ruta correspondiente del scraper."""
    tipo = payload.get("tipo")

    if tipo == "Q1":
        return f"{SCRAPER_URL}/consulta/proximos-partidos/{payload['slug']}/{payload['equipo_id']}"
    if tipo == "Q2":
        return f"{SCRAPER_URL}/consulta/ultimos-partidos/{payload['slug']}/{payload['equipo_id']}"
    if tipo == "Q3":
        return (
            f"{SCRAPER_URL}/consulta/enfrentamientos/"
            f"{payload['slug1']}/{payload['id1']}/{payload['slug2']}/{payload['id2']}"
        )
    if tipo == "Q4":
        return (
            f"{SCRAPER_URL}/consulta/partidos-fecha?"
            f"fecha_inicio={payload['fecha_inicio']}&fecha_fin={payload['fecha_fin']}"
        )
    if tipo == "Q5":
        return f"{SCRAPER_URL}/consulta/tabla-posiciones"

    raise ValueError("tipo de consulta no soportado; use Q1, Q2, Q3, Q4 o Q5")


def consultar_scraper(payload: dict) -> dict:
    try:
        respuesta = requests.get(url_scraper(payload), timeout=SCRAPER_TIMEOUT_SECONDS)
        respuesta.raise_for_status()
        return respuesta.json()
    except KeyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible consultar el scraper: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="El scraper respondió un JSON inválido",
        ) from error


@app.get("/health")
def health_check():
    try:
        cache_disponible()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Redis no está disponible") from error
    return {"status": "ok"}

@app.post("/api/consultas")
async def manejar_consulta(request: Request):
    payload = await request.json()

    llave = generar_llave(payload)

    try:
        respuesta_cache = obtener_de_cache(llave)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Redis no está disponible") from error

    if respuesta_cache is not None:

        print(f"[HIT] La llave '{llave}' ya estaba en la Caché.")

        return {"status": "hit", "origen": "cache", "datos": respuesta_cache}

    else:

        print(f"[MISS] La llave '{llave}' no existe. Consultando el Scraper...")
        datos = consultar_scraper(payload)

        try:
            guardar_en_cache(llave, datos, ttl_segundos=CACHE_TTL_SECONDS)
        except Exception as error:
            raise HTTPException(status_code=503, detail="No fue posible guardar en Redis") from error

        return {"status": "miss", "origen": "scraper", "datos": datos}
