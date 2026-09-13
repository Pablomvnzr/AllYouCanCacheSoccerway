import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scraper-service'))
from src import main as scraper


class PreloadTests(unittest.TestCase):
    def test_load_once_and_never_fetch_during_queries(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'snapshot.json'
            path.write_text(json.dumps(dict(schema_version=1,pages={'https://example.test':'<html>snapshot</html>'})),encoding='utf-8')
            async def check():
                async with scraper.lifespan(scraper.app):
                    self.assertEqual(scraper.obtener_html_renderizado('https://example.test'),'<html>snapshot</html>')
                    with self.assertRaises(scraper.HTTPException) as error:
                        scraper.obtener_html_renderizado('https://missing.test')
                    self.assertEqual(error.exception.status_code,503)
            with patch.dict(os.environ,{'SCRAPER_MODE':'preloaded','SCRAPER_SNAPSHOT_PATH':str(path)}), patch.object(scraper,'sync_playwright') as network:
                asyncio.run(check())
                network.assert_not_called()
            self.assertEqual(scraper.PRELOADED_HTML,{})
