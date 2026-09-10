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

def _parse_seccion_partidos(soup: BeautifulSoup, titulo_seccion: str, solo_liga_primera: bool = True) -> list[dict]:
    """
    Función interna: busca la <section> cuyo <h2> coincide con titulo_seccion
    (ej. "Próximos" o "Últimos Resultados") y parsea sus partidos.
    Si solo_liga_primera=True, descarta partidos de otras competiciones
    (Copa Chile, amistosos, etc).
    """
    partidos = []

    secciones = soup.select("section")
    seccion_objetivo = None
    for sec in secciones:
        h2 = sec.select_one("h2")
        if h2 and titulo_seccion.lower() in h2.get_text(strip=True).lower():
            seccion_objetivo = sec
            break

    if seccion_objetivo is None:
        return partidos

    # Recorremos los hijos directos en orden para saber bajo qué competición
    # cae cada partido (los headers de liga aparecen intercalados con los partidos)
    competicion_actual = None

    for elemento in seccion_objetivo.find_all(recursive=True):
        # Detecta un header de competición
        if elemento.name == "div" and "headerLeague__wrapper" in elemento.get("class", []):
            titulo_liga = elemento.select_one(".headerLeague__title-text")
            if titulo_liga:
                competicion_actual = titulo_liga.get_text(strip=True)

        # Detecta una fila de partido
        if elemento.name == "div" and elemento.get("id", "").startswith("g_1_"):
            if solo_liga_primera and competicion_actual != "Liga de Primera":
                continue

            fecha_span = elemento.select_one("span.wcl-dateContent_eEChT")
            fecha = fecha_span.get_text(strip=True) if fecha_span else None

            local_span = elemento.select_one("div.event__homeParticipant span.wcl-name_jjfMf")
            visitante_span = elemento.select_one("div.event__awayParticipant span.wcl-name_jjfMf")
            equipo_local = local_span.get_text(strip=True) if local_span else None
            equipo_visitante = visitante_span.get_text(strip=True) if visitante_span else None

            score_local = elemento.select_one("span.event__score--home")
            score_visitante = elemento.select_one("span.event__score--away")
            marcador_local = score_local.get_text(strip=True) if score_local else None
            marcador_visitante = score_visitante.get_text(strip=True) if score_visitante else None

            link = elemento.select_one("a.eventRowLink")
            url_partido = link["href"] if link and link.get("href") else None

            partidos.append({
                "fecha": fecha,
                "competicion": competicion_actual,
                "equipo_local": equipo_local,
                "equipo_visitante": equipo_visitante,
                "goles_local": marcador_local if marcador_local != "-" else None,
                "goles_visitante": marcador_visitante if marcador_visitante != "-" else None,
                "url_partido": url_partido,
            })

    return partidos


def parse_proximos_partidos(html: str, solo_liga_primera: bool = True) -> list[dict]:
    """Consulta Q1: próximos partidos programados de un equipo."""
    soup = BeautifulSoup(html, "html.parser")
    return _parse_seccion_partidos(soup, "Próximos", solo_liga_primera)


def parse_ultimos_partidos(html: str, solo_liga_primera: bool = True) -> list[dict]:
    """Consulta Q2: últimos partidos disputados de un equipo."""
    soup = BeautifulSoup(html, "html.parser")
    return _parse_seccion_partidos(soup, "Últimos Resultados", solo_liga_primera)