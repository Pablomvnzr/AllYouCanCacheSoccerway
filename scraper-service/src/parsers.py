from bs4 import BeautifulSoup
import re


def parse_tabla_posiciones(html: str) -> list[dict]:
    """
    Parsea la tabla de posiciones (Consulta Q5) desde el HTML renderizado
    de Soccerway (cl.soccerway.com/chile/liga-de-primera).
    """
    soup = BeautifulSoup(html, "html.parser")
    filas = soup.select("div.ui-table__row")

    resultados = []

    for fila in filas:
        # Posición
        rank_div = fila.select_one("div.tableCellRank")
        posicion = rank_div.get_text(strip=True).rstrip(".") if rank_div else None

        # Equipo: nombre + slug/id extraídos del href
        equipo_a = fila.select_one("a.tableCellParticipant__name")
        nombre_equipo = equipo_a.get_text(strip=True) if equipo_a else None

        equipo_id = None
        slug_equipo = None
        if equipo_a and equipo_a.get("href"):
            # href tiene forma /equipo/{slug}/{ID}/
            match = re.match(r"/equipo/([^/]+)/([^/]+)/", equipo_a["href"])
            if match:
                slug_equipo = match.group(1)
                equipo_id = match.group(2)

        # Los 7 valores numéricos en orden: PJ, G, E, P, Goles, DG, Pts
        valores = fila.select("span.table__cell--value")
        if len(valores) < 7:
            continue  # fila incompleta o inesperada, la saltamos

        pj = valores[0].get_text(strip=True)
        ganados = valores[1].get_text(strip=True)
        empatados = valores[2].get_text(strip=True)
        perdidos = valores[3].get_text(strip=True)
        goles_texto = valores[4].get_text(strip=True)  # formato "47:21"
        diferencia_goles = valores[5].get_text(strip=True)
        puntos = valores[6].get_text(strip=True)

        goles_favor, goles_contra = None, None
        if ":" in goles_texto:
            gf, gc = goles_texto.split(":")
            goles_favor, goles_contra = gf.strip(), gc.strip()

        resultados.append({
            "posicion": int(posicion) if posicion else None,
            "equipo": nombre_equipo,
            "equipo_id": equipo_id,
            "equipo_slug": slug_equipo,
            "partidos_jugados": int(pj),
            "ganados": int(ganados),
            "empatados": int(empatados),
            "perdidos": int(perdidos),
            "goles_favor": int(goles_favor) if goles_favor else None,
            "goles_contra": int(goles_contra) if goles_contra else None,
            "diferencia_goles": int(diferencia_goles),
            "puntos": int(puntos),
        })

    return resultados
