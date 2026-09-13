import sys
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Sistemas_de_cache/src'))
import main as cache
from fastapi import HTTPException
from key_builder import generar_llave


class CacheTests(unittest.TestCase):
    def test_invalid_query_is_400_not_redis_503(self):
        with patch.object(cache, 'registrar_metrica'), patch.object(cache, 'obtener_de_cache') as lookup:
            with self.assertRaises(HTTPException) as error:
                cache.manejar_consulta(dict(tipo='Q1'))
            self.assertEqual(error.exception.status_code, 400)
            lookup.assert_not_called()
            for tipo in (None, {}, []):
                with self.assertRaises(HTTPException) as error:
                    cache.manejar_consulta(dict(tipo=tipo))
                self.assertEqual(error.exception.status_code,400)
            lookup.assert_not_called()

    def test_source_error_never_cached_as_success(self):
        response=Mock()
        response.json.return_value=dict(error='No hay referencia H2H')
        query=dict(tipo='Q3',slug1='colo-colo',id1='a',slug2='u-catolica',id2='b')
        with patch.object(cache, 'registrar_metrica'), patch.object(cache, 'obtener_de_cache', return_value=None), patch.object(cache.requests,'get',return_value=response), patch.object(cache,'guardar_en_cache') as save:
            with self.assertRaises(HTTPException) as error:
                cache.manejar_consulta(query)
            self.assertEqual(error.exception.status_code, 502)
            save.assert_not_called()

    def test_h2h_key_order_independent(self):
        a=dict(tipo='Q3',slug1='a',id1='1',slug2='b',id2='2')
        b=dict(tipo='Q3',slug1='b',id1='2',slug2='a',id2='1')
        self.assertEqual(generar_llave(a), generar_llave(b))

    def test_redis_failure_reports_503_and_error_metric(self):
        with patch.object(cache,'obtener_de_cache',side_effect=RuntimeError('Redis detenido')), patch.object(cache,'registrar_metrica') as metric:
            with self.assertRaises(HTTPException) as error:
                cache.manejar_consulta(dict(tipo='Q5'))
            self.assertEqual(error.exception.status_code,503)
            self.assertFalse(metric.call_args.kwargs['exito'])
            self.assertFalse(metric.call_args.kwargs['redis_available'])

    def test_scraper_timeout_is_502_and_not_cached(self):
        with patch.object(cache,'obtener_de_cache',return_value=None), patch.object(cache.requests,'get',side_effect=cache.requests.Timeout('timeout')), patch.object(cache,'registrar_metrica'), patch.object(cache,'guardar_en_cache') as save:
            with self.assertRaises(HTTPException) as error:
                cache.manejar_consulta(dict(tipo='Q5'))
            self.assertEqual(error.exception.status_code,502)
            save.assert_not_called()

    def test_telemetry_failure_does_not_break_hit(self):
        with patch.object(cache,'obtener_de_cache',return_value=dict(tabla=[{}])), patch.object(cache,'remociones_desde_ultima_consulta',return_value=dict(evictions=0,expired_keys=0)), patch.object(cache.requests,'post',side_effect=cache.requests.ConnectionError('Metrics detenido')):
            self.assertEqual(cache.manejar_consulta(dict(tipo='Q5'))['status'],'hit')
