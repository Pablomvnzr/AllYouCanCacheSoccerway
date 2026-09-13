import os
import io
from contextlib import redirect_stdout
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'generador_trafico/src'))
import main as traffic


class TrafficTests(unittest.TestCase):
    def test_prints_each_query_and_actual_origin(self):
        responses = []
        for status, origin in [('miss', 'scraper'), ('hit', 'cache'), ('miss', 'benchmark')]:
            response = Mock()
            response.json.return_value = dict(status=status, origen=origin, datos={})
            responses.append(response)
        config = self.config(3)
        config['tasa_arribo_segundos'] = 0
        output = io.StringIO()
        with patch.object(traffic, 'load_config', return_value=config), patch.object(traffic.requests, 'post', side_effect=responses), patch.object(traffic.signal, 'signal'), patch.dict(os.environ, {'TRAFFIC_FIXED_PAYLOAD': '{"tipo":"Q5"}', 'TRAFFIC_RESULTS_PATH': ''}), redirect_stdout(output):
            self.assertEqual(traffic.iniciar_trafico(), 0)
        for number in (1, 2, 3):
            self.assertIn(f"[{number}/3] Enviando Q5: {{'tipo': 'Q5'}}", output.getvalue())
        for message in ('MISS: respuesta desde scraper', 'HIT: respuesta desde cache', 'MISS: respuesta desde benchmark'):
            self.assertIn(message, output.getvalue())

    def config(self, total):
        return dict(cantidad_solicitudes=total, tasa_arribo_segundos=1,
                    distribucion='uniforme', parametro_zipf=1.5)

    def test_final_request_does_not_wait(self):
        response=Mock()
        response.json.return_value=dict(status='miss', origen='scraper', datos=dict(tabla=[{}]))
        with patch.object(traffic,'load_config',return_value=self.config(1)), patch.object(traffic.requests,'post',return_value=response), patch.object(traffic.signal,'signal'), patch.object(traffic,'arrival_delay') as pause, patch.dict(os.environ,{'TRAFFIC_FIXED_PAYLOAD':'{"tipo":"Q5"}', 'TRAFFIC_RESULTS_PATH':''}):
            self.assertEqual(traffic.iniciar_trafico(),0)
            pause.assert_not_called()

    def test_continuous_stops_on_signal(self):
        handlers={}
        def register(kind, handler): handlers[kind]=handler
        def request(*args, **kwargs):
            handlers[traffic.signal.SIGTERM]()
            response=Mock()
            response.json.return_value=dict(status='hit',origen='cache',datos={})
            return response
        with patch.object(traffic,'load_config',return_value=self.config(0)), patch.object(traffic.requests,'post',side_effect=request) as post, patch.object(traffic.signal,'signal',side_effect=register), patch.dict(os.environ,{'TRAFFIC_RESULTS_PATH':''}):
            self.assertEqual(traffic.iniciar_trafico(),0)
            self.assertEqual(post.call_count,1)

    def test_invalid_source_returns_failure(self):
        response=Mock()
        response.json.return_value=dict(status='miss',origen='scraper',datos=dict(error='falló'))
        with patch.object(traffic,'load_config',return_value=self.config(1)), patch.object(traffic.requests,'post',return_value=response), patch.object(traffic.signal,'signal'), patch.dict(os.environ,{'TRAFFIC_RESULTS_PATH':''}):
            self.assertEqual(traffic.iniciar_trafico(),1)
