import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

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
