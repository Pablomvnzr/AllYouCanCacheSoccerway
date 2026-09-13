import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scraper-service/src'))
from parsers import parse_proximos_partidos, filtrar_partidos_por_fecha


class ParserTests(unittest.TestCase):
    def test_next_match_includes_time_and_teams(self):
        html='''<section><h2>Próximos</h2><div class="headerLeague__wrapper"><span class="headerLeague__title-text">Liga de Primera</span></div><div id="g_1_test"><span class="wcl-dateContent_eEChT">13.09.2026 20:00</span><div class="event__homeParticipant"><span class="wcl-name_jjfMf">Colo Colo</span></div><div class="event__awayParticipant"><span class="wcl-name_jjfMf">U. Católica</span></div></div></section>'''
        match=parse_proximos_partidos(html)[0]
        self.assertEqual(match['hora'], '20:00')
        self.assertEqual(match['equipo_visitante'], 'U. Católica')

    def test_date_range_crosses_year(self):
        matches=[dict(fecha='28.12.2026'),dict(fecha='02.01.2027'),dict(fecha='02.01.2026')]
        self.assertEqual(len(filtrar_partidos_por_fecha(matches,'2026-12-25','2027-01-05')), 2)

    def test_invalid_calendar_date_rejected(self):
        with self.assertRaises(ValueError):
            filtrar_partidos_por_fecha([], '31.02.2026','01.03.2026')

    def test_yearless_source_not_relabelled_as_requested_year(self):
        matches=[dict(fecha='13.09. 20:00')]
        self.assertEqual(filtrar_partidos_por_fecha(matches,'2025-09-01','2025-09-30',reference_year=2026),[])
        self.assertEqual(len(filtrar_partidos_por_fecha(matches,'2026-09-01','2026-09-30',reference_year=2026)),1)
