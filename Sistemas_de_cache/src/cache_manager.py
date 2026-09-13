import redis
import json
import os
from threading import Lock
from redis.retry import Retry
from redis.backoff import NoBackoff

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
    retry=Retry(NoBackoff(), 0),
)
ultimo_total_evictions = 0
ultimo_total_expired = 0
stats_lock = Lock()

def obtener_de_cache(llave):
    """Se busca una llave en Redis; si existe, se produce un cache hit."""
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


def estadisticas_redis():
    info = redis_client.info()
    return {key: info.get(key, 0) for key in ('evicted_keys', 'expired_keys', 'used_memory', 'used_memory_dataset', 'maxmemory', 'maxmemory_policy', 'db0')}


def remociones_desde_ultima_consulta():
    global ultimo_total_evictions, ultimo_total_expired
    try:
        with stats_lock:
            info = redis_client.info('stats')
            evicted = int(info.get('evicted_keys', 0))
            expired = int(info.get('expired_keys', 0))
            result = dict(evictions=max(0,evicted-ultimo_total_evictions), expired_keys=max(0,expired-ultimo_total_expired))
            ultimo_total_evictions, ultimo_total_expired = evicted, expired
            return result
    except redis.RedisError:
        # El fallo de Redis no debe impedir publicar el evento de error.
        return dict(evictions=0, expired_keys=0)
