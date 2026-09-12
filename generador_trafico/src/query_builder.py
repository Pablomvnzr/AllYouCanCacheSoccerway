import random

TIPOS_CONSULTA = ["Q1", "Q2", "Q3", "Q4", "Q5"]
EQUIPOS = ["Colo Colo", "U de Chile", "U Catolica", "Cobreloa", "Union Espanola", "Audax Italiano", "Palestino", "Everton"]

def armar_payload(idx_consulta):
    """Construye el JSON de la consulta según el tipo asignado."""
    consulta = TIPOS_CONSULTA[idx_consulta]
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
        
    return payload
