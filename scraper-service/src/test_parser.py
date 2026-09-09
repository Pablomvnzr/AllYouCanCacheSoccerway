from parsers import parse_tabla_posiciones

with open("pagina_renderizada.html", "r", encoding="utf-8") as f:
    html = f.read()

tabla = parse_tabla_posiciones(html)

for equipo in tabla:
    print(equipo)

print(f"\nTotal equipos parseados: {len(tabla)}")
