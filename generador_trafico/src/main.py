import time
import random
import numpy as np
import yaml
import requests
from distributions import get_distribucion_index
from query_builder import armar_payload, TIPOS_CONSULTA

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def iniciar_trafico():
    np.random.seed(42)
    random.seed(42)

    config = load_config()
    total = config["cantidad_solicitudes"]
    tasa = config["tasa_arribo_segundos"]
    dist = config["distribucion"]
    alpha = config["parametro_zipf"]

    URL_CACHE = "http://localhost:5000/api/consultas"

    print("=========================================")
    print(f"Iniciando Generador de Tráfico (Modular)")
    print(f"Distribución: {dist.upper()}")
    print(f"Total a generar: {total} solicitudes")
    print("=========================================\n")

    for i in range(total):
        idx = get_distribucion_index(dist, len(TIPOS_CONSULTA), alpha)
        payload = armar_payload(idx)

        print(f"[{i+1}/{total}] Enviando {payload['tipo']}: {payload}")

        try:
            response = requests.post(URL_CACHE, json=payload, timeout=2)
            print(f"  -> Éxito: Caché respondió con status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  -> Error: La caché no está disponible en {URL_CACHE}")

        time.sleep(tasa)

    print("\nTráfico finalizado con éxito.")

if __name__ == "__main__":
    iniciar_trafico()
