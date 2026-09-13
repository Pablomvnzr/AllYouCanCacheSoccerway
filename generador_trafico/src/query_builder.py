import random
from itertools import combinations

TIPOS_CONSULTA = ["Q1", "Q2", "Q3", "Q4", "Q5"]
EQUIPOS = [
    {"nombre": "Colo Colo", "slug": "colo-colo", "id": "th4HPIws"},
    {"nombre": "U. Católica", "slug": "u-catolica", "id": "Qe432hiO"},
    {"nombre": "U. De Chile", "slug": "u-de-chile", "id": "xW771C6U"},
    {"nombre": "Palestino", "slug": "palestino", "id": "U35cjf75"},
    {"nombre": "Everton", "slug": "everton", "id": "Kr3LOxgm"},
    {"nombre": "Limache", "slug": "limache", "id": "YPTUuyqJ"},
    {"nombre": "Ñublense", "slug": "nublense", "id": "vVvwgdNn"},
    {"nombre": "La Serena", "slug": "la-serena", "id": "d6kYgx8t"},
    {"nombre": "Dep. Concepción", "slug": "dep-concepcion", "id": "GKJrZE7I"},
    {"nombre": "Coquimbo", "slug": "coquimbo", "id": "hWejMZ6h"},
    {"nombre": "O'Higgins", "slug": "o-higgins", "id": "hYrshGxg"},
    {"nombre": "Audax Italiano", "slug": "a-italiano", "id": "rN3Jxc8g"},
    {"nombre": "Huachipato", "slug": "huachipato", "id": "SlhZpIaP"},
    {"nombre": "U. De Concepción", "slug": "u-de-concepcion", "id": "6BcMMext"},
    {"nombre": "Cobresal", "slug": "cobresal", "id": "YeUwzehC"},
    {"nombre": "U. La Calera", "slug": "u-la-calera", "id": "M34g8ulJ"},
]

# Un H2H necesita un partido de referencia. Este clásico tiene datos comprobados
# en Soccerway y permite que Q3 sea reproducible durante los experimentos.
H2H_PARES = [(EQUIPOS[0], EQUIPOS[1])]

def armar_payload(idx_consulta):
    """Construye el JSON de la consulta según el tipo asignado."""
    consulta = TIPOS_CONSULTA[idx_consulta]
    equipo1 = random.choice(EQUIPOS)
    
    payload = {"tipo": consulta}
    
    if consulta in ["Q1", "Q2"]:
        payload.update({"slug": equipo1["slug"], "equipo_id": equipo1["id"]})
    elif consulta == "Q3":
        equipo1, equipo2 = random.choice(H2H_PARES)
        payload.update({
            "slug1": equipo1["slug"], "id1": equipo1["id"],
            "slug2": equipo2["slug"], "id2": equipo2["id"],
        })
    elif consulta == "Q4":
        inicio = random.randint(1, 20)
        payload.update({
            "fecha_inicio": f"{inicio:02d}.09",
            "fecha_fin": f"{inicio + 7:02d}.09",
        })
        
    return payload


def build_catalog(types=None, all_pairs=False):
    """Catálogo estable de consultas completas para Uniforme y Zipf."""
    types = TIPOS_CONSULTA if types is None else types
    if not types or not set(types) <= set(TIPOS_CONSULTA):
        raise ValueError('Tipos de consulta inválidos')
    catalog = []
    for tipo in types:
        if tipo in ('Q1', 'Q2'):
            catalog.extend(dict(tipo=tipo, slug=t['slug'], equipo_id=t['id']) for t in EQUIPOS)
        elif tipo == 'Q3':
            pairs = combinations(EQUIPOS, 2) if all_pairs else H2H_PARES
            catalog.extend(dict(tipo=tipo, slug1=a['slug'], id1=a['id'], slug2=b['slug'], id2=b['id']) for a,b in pairs)
        elif tipo == 'Q4':
            catalog.extend(dict(tipo=tipo, fecha_inicio=f'{i:02d}.09', fecha_fin=f'{i+7:02d}.09') for i in range(1,21))
        else:
            catalog.append(dict(tipo=tipo))
    return catalog
