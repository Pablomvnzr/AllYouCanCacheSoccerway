def generar_llave(payload):
    tipo = payload.get("tipo")
    llave = f"{tipo}"

    if tipo in ["Q1", "Q2"]:
        llave += f":{payload.get('equipo')}"
    elif tipo == "Q3":
        equipos = sorted([payload.get('equipo1'), payload.get('equipo2')])
        llave += f":{equipos[0]}:{equipos[1]}"
    elif tipo == "Q4":
        llave += f":{payload.get('fecha')}"

    return llave.replace(" ", "_")
