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

    print("=========================================")
    print(f"Iniciando Generador de Tráfico (Modular)")
    print(f"Distribución: {dist.upper()}")
    print(f"Total a generar: {total} solicitudes")
    print("=========================================\n")

    for i in range(total):
        if fixed_payload is not None:
            payload = dict(fixed_payload)
        else:
            idx = get_distribucion_index(dist, len(TIPOS_CONSULTA), alpha)
            payload = armar_payload(idx)

        print(f"[{i+1}/{total}] Enviando {payload['tipo']}: {payload}")

        try:
            response = requests.post(URL_CACHE, json=payload, timeout=60)
            response.raise_for_status()
            resultado = response.json()
            print(f"  -> {resultado['status'].upper()}: respuesta desde {resultado['origen']}")
        except requests.exceptions.RequestException as e:
            print(f"  -> Error: La caché no está disponible en {URL_CACHE}")

        time.sleep(tasa)

    print("\nTráfico finalizado con éxito.")

if __name__ == "__main__":
    iniciar_trafico()
