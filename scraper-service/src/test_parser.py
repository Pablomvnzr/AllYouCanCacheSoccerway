from parsers import parse_tabla_posiciones, parse_proximos_partidos, parse_ultimos_partidos

with open("../scratch/pagina_renderizada.html", "r", encoding="utf-8") as f:
    html = f.read()

print("=== PRÓXIMOS PARTIDOS ===")
for p in parse_proximos_partidos(html):
    print(p)

print(f"\nTotal próximos: {len(parse_proximos_partidos(html))}")

print("\n=== ÚLTIMOS PARTIDOS ===")
for p in parse_ultimos_partidos(html):
    print(p)

print(f"\nTotal últimos: {len(parse_ultimos_partidos(html))}")
