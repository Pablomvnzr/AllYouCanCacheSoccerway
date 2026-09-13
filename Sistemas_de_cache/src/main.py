import os
import re
from datetime import datetime
from time import perf_counter

import requests
from fastapi import FastAPI, HTTPException

from cache_manager import (
    cache_disponible,
    guardar_en_cache,
    obtener_de_cache,
    estadisticas_redis,
    remociones_desde_ultima_consulta,
)
from key_builder import generar_llave

app = FastAPI(title="Sistema de Caché")

SCRAPER_URL = os.getenv("SCRAPER_URL", "http://localhost:8000").rstrip("/")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
SCRAPER_TIMEOUT_SECONDS = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "120"))
METRICS_URL = os.getenv("METRICS_URL", "http://localhost:9000/events").rstrip("/")


def registrar_metrica(
    *,
    tipo_consulta: str,
    estado_cache: str,
    exito: bool,
    latencia_ms: float,
    latencia_scraper_ms: float | None = None,
    error: str | None = None,
    source_origin: str = 'scraper',
    redis_available: bool = True,
):
    """Registra una métrica sin hacer fallar la consulta si Metrics cae."""
    try:
        evento = {
            "query_type": tipo_consulta,
            "cache_status": estado_cache,
            "success": exito,
            "latency_ms": round(latencia_ms, 3),
            "scraper_latency_ms": (
                round(latencia_scraper_ms, 3) if latencia_scraper_ms is not None else None
            ),
            "error": error,
            **(remociones_desde_ultima_consulta() if redis_available else dict(evictions=0, expired_keys=0)),
            "source_origin": source_origin,
        }
        respuesta = requests.post(METRICS_URL, json=evento, timeout=2)
        respuesta.raise_for_status()
    except Exception as metricas_error:
        print(f"[METRICS] No fue posible registrar el evento: {metricas_error}")


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
        data = respuesta.json()
        fields = {'Q1': 'proximos_partidos', 'Q2': 'ultimos_partidos', 'Q3': 'enfrentamientos', 'Q4': 'partidos', 'Q5': 'tabla'}
        field = fields[payload['tipo']]
        if not isinstance(data, dict) or 'error' in data or not isinstance(data.get(field), list):
            raise ValueError('Estructura inválida del scraper')
        if payload['tipo'] == 'Q5' and not data[field]:
            raise ValueError('Tabla vacía: no se pudo validar la fuente')
        return data
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


def respuesta_benchmark(payload: dict) -> dict:
    """Crea un valor determinista para las pruebas explícitas de presión."""
    size = int(payload["benchmark_value_bytes"])
    if size < 1 or size > 1_000_000:
        raise ValueError("benchmark_value_bytes debe estar entre 1 y 1000000")
    return {
        "benchmark": True,
        "benchmark_id": payload["benchmark_id"],
        "payload": "x" * size,
    }


@app.get("/health")
def health_check():
    try:
        cache_disponible()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Redis no está disponible") from error
    return {"status": "ok"}


def validar_consulta(payload):
    fields = {'Q1': ('slug','equipo_id'), 'Q2': ('slug','equipo_id'), 'Q3': ('slug1','id1','slug2','id2'), 'Q4': ('fecha_inicio','fecha_fin'), 'Q5': ()}
    if not isinstance(payload.get('tipo'), str) or payload['tipo'] not in fields:
        raise HTTPException(400, 'tipo debe ser Q1, Q2, Q3, Q4 o Q5')
    for field in fields[payload['tipo']]:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise HTTPException(400, f'Falta un valor válido para {field}')
        if field.startswith('fecha_'):
            valid = False
            for fmt in ('%d.%m', '%d.%m.%Y', '%Y-%m-%d'):
                try:
                    datetime.strptime(value, fmt)
                    valid = True
                    break
                except ValueError:
                    pass
            if not valid:
                raise HTTPException(400, f'Fecha inválida: {value}')
        elif not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise HTTPException(400, f'Identificador inválido: {field}')
    has_id, has_size = 'benchmark_id' in payload, 'benchmark_value_bytes' in payload
    if has_id != has_size:
        raise HTTPException(400, 'Benchmark incompleto')
    if has_id:
        if os.getenv('CACHE_ALLOW_BENCHMARK', '0') != '1':
            raise HTTPException(400, 'Benchmark deshabilitado en este servicio')
        if type(payload['benchmark_id']) is not int or payload['benchmark_id'] < 0 or type(payload['benchmark_value_bytes']) is not int or not 1 <= payload['benchmark_value_bytes'] <= 1000000:
            raise HTTPException(400, 'Parámetros benchmark inválidos')


@app.get('/redis/stats')
def redis_stats():
    return estadisticas_redis()


@app.post("/api/consultas")
def manejar_consulta(payload: dict):
    inicio = perf_counter()
    tipo_consulta = "desconocida"
    estado_cache = "error"
    latencia_scraper_ms = None

    try:
        validar_consulta(payload)
        tipo_consulta = payload.get("tipo", "desconocida")
        llave = generar_llave(payload)
        respuesta_cache = obtener_de_cache(llave)
    except HTTPException as error:
        registrar_metrica(tipo_consulta=str(payload.get('tipo') or 'invalid'), estado_cache='error', exito=False,
                         latencia_ms=(perf_counter()-inicio)*1000, error=str(error.detail), source_origin='error', redis_available=False)
        raise
    except Exception as error:
        registrar_metrica(
            tipo_consulta=tipo_consulta,
            estado_cache=estado_cache,
            exito=False,
            latencia_ms=(perf_counter() - inicio) * 1000,
            error=str(error),
            source_origin='error',
            redis_available=False,
        )
        raise HTTPException(status_code=503, detail="Redis no está disponible") from error

    if respuesta_cache is not None:
        estado_cache = "hit"
        print(f"[HIT] La llave '{llave}' ya estaba en la Caché.")
        registrar_metrica(
            tipo_consulta=tipo_consulta,
            estado_cache=estado_cache,
            exito=True,
            latencia_ms=(perf_counter() - inicio) * 1000,
            source_origin='cache',
        )
        return {"status": estado_cache, "origen": "cache", "datos": respuesta_cache}

    estado_cache = "miss"
    es_benchmark = "benchmark_id" in payload and "benchmark_value_bytes" in payload
    origen = "benchmark" if es_benchmark else "scraper"
    print(f"[MISS] La llave '{llave}' no existe. Consultando {origen}...")
    inicio_scraper = perf_counter()
    try:
        if es_benchmark:
            datos = respuesta_benchmark(payload)
        else:
            datos = consultar_scraper(payload)
        latencia_scraper_ms = None if es_benchmark else (perf_counter() - inicio_scraper) * 1000
        guardar_en_cache(llave, datos, ttl_segundos=CACHE_TTL_SECONDS)
    except HTTPException as error:
        registrar_metrica(
            tipo_consulta=tipo_consulta,
            estado_cache=estado_cache,
            exito=False,
            latencia_ms=(perf_counter() - inicio) * 1000,
            latencia_scraper_ms=latencia_scraper_ms,
            error=error.detail,
        )
        raise
    except Exception as error:
        registrar_metrica(
            tipo_consulta=tipo_consulta,
            estado_cache=estado_cache,
            exito=False,
            latencia_ms=(perf_counter() - inicio) * 1000,
            latencia_scraper_ms=latencia_scraper_ms,
            error=str(error),
            source_origin=origen,
            redis_available=False,
        )
        raise HTTPException(status_code=503, detail="No fue posible guardar en Redis") from error

    registrar_metrica(
        tipo_consulta=tipo_consulta,
        estado_cache=estado_cache,
        exito=True,
        latencia_ms=(perf_counter() - inicio) * 1000,
        latencia_scraper_ms=latencia_scraper_ms,
        source_origin=origen,
    )
    return {"status": estado_cache, "origen": origen, "datos": datos}
