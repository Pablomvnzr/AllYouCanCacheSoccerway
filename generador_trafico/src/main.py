import time
import random
import os
import json
import numpy as np
import yaml
import requests
from distributions import get_distribucion_index
from query_builder import armar_payload, TIPOS_CONSULTA

def load_config():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Compose puede sobreescribir estos valores por corrida experimental sin
    # modificar el archivo base ni reconstruir la imagen.
    overrides = {
        "cantidad_solicitudes": ("TRAFFIC_REQUEST_COUNT", int),
        "tasa_arribo_segundos": ("TRAFFIC_ARRIVAL_SECONDS", float),
        "distribucion": ("TRAFFIC_DISTRIBUTION", str),
        "parametro_zipf": ("TRAFFIC_ZIPF_ALPHA", float),
        "benchmark_key_space": ("TRAFFIC_BENCHMARK_KEY_SPACE", int),
        "benchmark_value_bytes": ("TRAFFIC_BENCHMARK_VALUE_BYTES", int),
    }
    for campo, (variable, convertir) in overrides.items():
        if variable in os.environ:
            config[campo] = convertir(os.environ[variable])

    return config

def iniciar_trafico():
    np.random.seed(42)
    random.seed(42)

    config = load_config()
    total = config["cantidad_solicitudes"]
    tasa = config["tasa_arribo_segundos"]
    dist = config["distribucion"]
    alpha = config["parametro_zipf"]

    URL_CACHE = os.getenv("CACHE_URL", "http://localhost:5000/api/consultas")
    fixed_payload_raw = os.getenv("TRAFFIC_FIXED_PAYLOAD", "")
    fixed_payload = json.loads(fixed_payload_raw) if fixed_payload_raw else None
    benchmark_key_space = config.get("benchmark_key_space", 0)
    benchmark_value_bytes = config.get("benchmark_value_bytes", 0)
    benchmark_enabled = benchmark_key_space > 0 and benchmark_value_bytes > 0

    print("=========================================")
    print(f"Iniciando Generador de Tráfico (Modular)")
    print(f"Distribución: {dist.upper()}")
    if total < 0:
        raise ValueError("cantidad_solicitudes debe ser un entero positivo o 0 para tráfico continuo")

    detalle_total = "tráfico continuo (Ctrl+C para detener)" if total == 0 else f"{total} solicitudes"
    print(f"Total a generar: {detalle_total}")
    if benchmark_enabled:
        print(
            f"Modo de presión: {benchmark_key_space} claves por tipo, "
            f"valores de {benchmark_value_bytes} bytes"
        )
    print("=========================================\n")

    i = 0
    try:
        while total == 0 or i < total:
            i += 1
            if fixed_payload is not None:
                payload = dict(fixed_payload)
            else:
                idx = i % len(TIPOS_CONSULTA) if benchmark_enabled else get_distribucion_index(
                    dist, len(TIPOS_CONSULTA), alpha
                )
                payload = armar_payload(idx)
                if benchmark_enabled:
                    payload["benchmark_id"] = get_distribucion_index(
                        dist, benchmark_key_space, alpha
                    )
                    payload["benchmark_value_bytes"] = benchmark_value_bytes

            progreso = f"{i}/∞" if total == 0 else f"{i}/{total}"
            print(f"[{progreso}] Enviando {payload['tipo']}: {payload}")

            try:
                response = requests.post(URL_CACHE, json=payload, timeout=60)
                response.raise_for_status()
                resultado = response.json()
                print(f"  -> {resultado['status'].upper()}: respuesta desde {resultado['origen']}")
            except requests.exceptions.RequestException:
                print(f"  -> Error: La caché no está disponible en {URL_CACHE}")

            time.sleep(tasa)
    except KeyboardInterrupt:
        print("\nTráfico detenido por el usuario.")
        return

    print("\nTráfico finalizado con éxito.")

if __name__ == "__main__":
    iniciar_trafico()
