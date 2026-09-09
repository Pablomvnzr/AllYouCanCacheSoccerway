import numpy as np
import time
import random
import requests

np.random.seed(42)
random.seed(42)

CANTIDAD_SOLICITUDES = 20
TASA_ARRIBO_SEGUNDOS = 0.5
DISTRIBUCION = "zipf"
PARAMETRO_ZIPF = 1.5

TIPOS_CONSULTA = ["Q1", "Q2", "Q3", "Q4", "Q5"]
EQUIPOS = ["Colo Colo", "U de Chile", "U Catolica", "Cobreloa", "Union Espanola", "Audax Italiano", "Palestino", "Everton"]

def generar_consulta(tipo_distribucion):
    if tipo_distribucion == "uniforme":
        idx = np.random.randint(0, len(TIPOS_CONSULTA))
    elif tipo_distribucion == "zipf":
        idx = np.random.zipf(PARAMETRO_ZIPF) - 1
        idx = idx % len(TIPOS_CONSULTA)
    else:
        idx = 0
        
    consulta = TIPOS_CONSULTA[idx]
    
    equipo1 = random.choice(EQUIPOS)
    equipo2 = random.choice([e for e in EQUIPOS if e != equipo1])
    
    payload = {"tipo": consulta}
    
    if consulta in ["Q1", "Q2"]:
        payload["equipo"] = equipo1
    elif consulta == "Q3":
        payload["equipo1"] = equipo1
        payload["equipo2"] = equipo2
    elif consulta == "Q4":
        payload["fecha"] = f"2026-09-{random.randint(1, 30):02d}"
    elif consulta == "Q5":
        pass
        
    return payload

def iniciar_trafico():
    print("=========================================")
    print(f"Iniciando Generador de Tráfico")
    print(f"Distribución: {DISTRIBUCION.upper()}")
    print(f"Total a generar: {CANTIDAD_SOLICITUDES} solicitudes")
    print("=========================================\n")
    
    for i in range(CANTIDAD_SOLICITUDES):
        payload = generar_consulta(DISTRIBUCION)
        print(f"[{i+1}/{CANTIDAD_SOLICITUDES}] Enviando {payload['tipo']}: {payload}")
        time.sleep(TASA_ARRIBO_SEGUNDOS)
        
    print("\nTráfico finalizado con éxito.")

if __name__ == "__main__":
    iniciar_trafico()
