import time
import random
import numpy as np
import yaml
import os
from distributions import get_distribucion_index
from query_builder import armar_payload, TIPOS_CONSULTA

def load_config():
    # Asume que main.py se ejecuta desde la carpeta generador_trafico/
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

    print("=========================================")
    print(f"Iniciando Generador de Tráfico (Modular)")
    print(f"Distribución: {dist.upper()}")
    print(f"Total a generar: {total} solicitudes")
    print("=========================================\n")

    for i in range(total):
        idx = get_distribucion_index(dist, len(TIPOS_CONSULTA), alpha)
        payload = armar_payload(idx)

        print(f"[{i+1}/{total}] Enviando {payload['tipo']}: {payload}")
        time.sleep(tasa)

    print("\nTráfico finalizado con éxito.")

if __name__ == "__main__":
    iniciar_trafico()
