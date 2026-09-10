from fastapi import FastAPI, Request
from key_builder import generar_llave
from cache_manager import obtener_de_cache, guardar_en_cache

app = FastAPI(title="Sistema de Caché")

@app.post("/api/consultas")
async def manejar_consulta(request: Request):
    payload = await request.json()

    llave = generar_llave(payload)

    respuesta_cache = obtener_de_cache(llave)

    if respuesta_cache:

        print(f"[HIT] La llave '{llave}' ya estaba en la Caché.")

        return {"status": "hit", "origen": "cache", "datos": respuesta_cache}

    else:

        print(f"[MISS] La llave '{llave}' no existe. Se llamaría al Scraper...")

        datos_simulados = {"mensaje": f"Datos recién obtenidos desde la web para la llave {llave}"}


        guardar_en_cache(llave, datos_simulados, ttl_segundos=30)

        return {"status": "miss", "origen": "scraper", "datos": datos_simulados}
