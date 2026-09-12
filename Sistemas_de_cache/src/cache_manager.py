import redis
import json
import os

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)
ultimo_total_evictions = 0

def obtener_de_cache(llave):
    """Se busca una llave en Redis, si existe la llave se produche un cache hit."""
    resultado = redis_client.get(llave)

    if resultado:
        return json.loads(resultado)

    return None

def guardar_en_cache(llave, datos, ttl_segundos=30):
    """Guarda un diccionario en Redis indicando los segundos de vida que tenga (time to live)."""
    valor_json = json.dumps(datos)

    redis_client.setex(llave, ttl_segundos, valor_json)


def cache_disponible():
    """Comprueba la conexión a Redis para el health check del servicio."""
    return bool(redis_client.ping())


def evicciones_desde_ultima_consulta():
    """Devuelve las evictions nuevas de Redis desde la medición anterior."""
    global ultimo_total_evictions

    total_actual = int(redis_client.info("stats").get("evicted_keys", 0))
    nuevas_evictions = max(0, total_actual - ultimo_total_evictions)
    ultimo_total_evictions = total_actual
    return nuevas_evictions
