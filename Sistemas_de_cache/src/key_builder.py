def generar_llave(payload):
    tipo = payload.get("tipo")
    llave = f"{tipo}"

    if tipo in ["Q1", "Q2"]:
        llave += f":{payload.get('slug')}:{payload.get('equipo_id')}"
    elif tipo == "Q3":
        equipos = sorted([
            f"{payload.get('slug1')}:{payload.get('id1')}",
            f"{payload.get('slug2')}:{payload.get('id2')}",
        ])
        llave += f":{equipos[0]}:{equipos[1]}"
    elif tipo == "Q4":
        llave += f":{payload.get('fecha_inicio')}:{payload.get('fecha_fin')}"

    if "benchmark_id" in payload:
        llave += f":benchmark:{payload['benchmark_id']}"

    return llave.replace(" ", "_")
