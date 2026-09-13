# All You Can Cache - Plataforma de fútbol chileno

Primera integración de la tarea: el generador de tráfico envía consultas sintéticas a la caché; ante un *miss*, la caché consulta al scraper de Soccerway y guarda la respuesta en Redis con TTL.

Repositorio espejo personal de desarrollo: [AllYouCanCacheSoccerway en GitHub](https://github.com/Pablomvnzr/AllYouCanCacheSoccerway).

Repositorio de entrega: [GitLab UDP, rama TheRealMain](https://giteit.udp.cl/CIT2011/2026-2/seccion-2/grupo-4/-/tree/TheRealMain).

## Servicios

- `traffic-generator`: genera consultas Q1-Q5 con distribución uniforme o Zipf.
- `cache-service`: expone `POST /api/consultas`, construye claves canónicas y usa Redis.
- `scraper-service`: obtiene y estructura los datos de Soccerway.
- `metrics-service`: recibe eventos y calcula las métricas.
- `redis`: almacena temporalmente las respuestas del scraper.

## Ejecutar el sistema

Desde la raíz del repositorio:

```bash
docker compose up --build
```

Puertos disponibles en el host:

- Scraper: `http://localhost:8000/health`
- Caché: `http://localhost:5001/health`
- Métricas: `http://localhost:9000/health`

El generador ejecuta la cantidad de solicitudes configurada en `generador_trafico/config.yaml` y luego termina. Redis, la caché y el scraper siguen activos. Para detener todo:

```bash
docker compose down
```

## Contrato de consultas

La caché recibe un JSON con `tipo` y los parámetros de la consulta:

```json
{"tipo": "Q1", "slug": "colo-colo", "equipo_id": "th4HPIws"}
```

```json
{"tipo": "Q2", "slug": "u-de-chile", "equipo_id": "xW771C6U"}
```

```json
{"tipo": "Q3", "slug1": "colo-colo", "id1": "th4HPIws", "slug2": "u-de-chile", "id2": "xW771C6U"}
```

```json
{"tipo": "Q4", "fecha_inicio": "01.09", "fecha_fin": "30.09"}
```

```json
{"tipo": "Q5"}
```

Ejemplo manual:

```bash
curl -X POST http://localhost:5001/api/consultas \
  -H 'Content-Type: application/json' \
  -d '{"tipo":"Q5"}'
```

La primera solicitud devuelve `"status": "miss"`; una segunda solicitud idéntica dentro del TTL devuelve `"status": "hit"` y no vuelve a llamar al scraper.

## Métricas

La caché registra un evento por cada consulta, sin interrumpir el flujo si el servicio de métricas no está disponible. Al finalizar una corrida, consulta el resumen en:

```bash
curl http://localhost:9000/metrics
```

El resultado incluye hit/miss rate, throughput, latencia promedio/p50/p95, tiempo de scraping, errores, evictions y eficiencia de caché. Antes de cada experimento, reinicia la medición con:

```bash
curl -X POST http://localhost:9000/reset
```

## Experimentos

Cada archivo JSON de `experiments/configs/` define la distribución de tráfico, cantidad/tasa de solicitudes, tamaño de Redis, política de remoción y TTL. El runner reinicia los servicios, ejecuta el generador, exporta el resumen y eventos crudos en `experiments/results/`, y luego detiene Docker.

```bash
python3 experiments/run_experiment.py experiments/configs/uniform-2mb-lru.json
python3 experiments/run_experiment.py experiments/configs/zipf-2mb-lru.json
```

Las configuraciones incluidas permiten iniciar la comparación Uniforme vs Zipf, tamaños de 2/5/10 MB, LRU vs LFU y TTL de 3/60 segundos. Ajusta `request_count` antes de las corridas finales para obtener muestras suficientes.

### Tráfico continuo para generar presión de caché

Para una prueba manual de presión, el generador acepta `TRAFFIC_REQUEST_COUNT=0`: seguirá enviando solicitudes hasta que presiones `Ctrl+C`. Usa un TTL alto para evitar que las entradas expiren durante la prueba. Este modo es exploratorio; para las mediciones que irán al informe conserva corridas finitas y reproducibles.

En PowerShell:

```powershell
$env:CACHE_MAXMEMORY = "2mb"
$env:CACHE_EVICTION_POLICY = "allkeys-lru"
$env:CACHE_TTL_SECONDS = "3600"
$env:TRAFFIC_REQUEST_COUNT = "0"
$env:TRAFFIC_ARRIVAL_SECONDS = "0.05"
$env:TRAFFIC_DISTRIBUTION = "zipf"
$env:TRAFFIC_ZIPF_ALPHA = "1.5"
docker compose build traffic-generator cache-service metrics-service scraper-service
docker compose up -d redis scraper-service metrics-service cache-service
docker compose run --rm traffic-generator
```

En otra terminal puedes consultar las métricas mientras se ejecuta:

```powershell
Invoke-RestMethod http://localhost:9000/metrics
```

Detén el generador con `Ctrl+C` y baja los servicios al terminar con `docker compose down`.

Para comparar presión de memoria de manera reproducible, usa las configuraciones `pressure-zipf-<tamaño>-<política>.json` y `pressure-uniform-<tamaño>-<política>.json`, con tamaños de 2, 5 y 10 MB y políticas LRU/LFU. Cada una usa el mismo catálogo de 1.000 claves y valores de 64 KiB. Este modo no consulta Soccerway: mide exclusivamente la caché bajo presión; el tiempo de scraping y la eficiencia basada en el origen externo no son aplicables. Redis cuenta también estructuras internas dentro de maxmemory: 2 MB no equivalen a 2 MB de respuestas útiles.

### Matrices y evidencia reproducible en Windows

Desde esta carpeta, con Docker Desktop iniciado y Python disponible:

```powershell
python experiments/run_suite.py ttl
python experiments/run_suite.py pressure
python experiments/run_suite.py functional
python experiments/analyze_results.py
python experiments/verify_evidence.py
python experiments/build_report.py
Get-ChildItem experiments/results -Filter *.json | Sort-Object LastWriteTime -Descending
```

Ejecuta una matriz después de finalizar la anterior: comparten los mismos servicios. El runner guarda también las corridas fallidas y termina con error si hay solicitudes fallidas o pérdida de eventos. No cierres la terminal antes del mensaje final. Las matrices funcionales usan datos reales; su tamaño pequeño puede producir cero evictions, lo que es un resultado válido y debe explicarse.

El catálogo funcional predeterminado contiene 54 consultas completas y estables: 16 Q1, 16 Q2, una Q3, 20 Q4 y una Q5. Zipf finita asigna probabilidad proporcional a rango elevado a menos alpha; Uniforme asigna igual probabilidad. La semilla 42 y la permutación del catálogo se conservan al cambiar tamaño/política. El modo de llegada es cerrado: se espera la respuesta y luego el intervalo configurado; no representa una tasa abierta independiente de la latencia. Las ventanas de eventos y percentiles tienen un límite de 10.000; los contadores acumulados no se pierden.

Los JSON antiguos sin schema_version 2 corresponden a la implementación anterior y no deben mezclarse con las nuevas mediciones. El análisis selecciona la última corrida válida de cada configuración, separa datos reales/sintéticos y conserva el detalle por consulta.

Para ejecutar las 21 pruebas de regresión: `powershell -ExecutionPolicy Bypass -File tests/run_tests.ps1`. Compila `output/pdf/informe.tex` con una distribución LaTeX que incluya pgfplots, por ejemplo `tectonic --outdir output/pdf output/pdf/informe.tex`. El PDF sigue siendo de trabajo hasta añadir el enlace de video. Revisa `ENTREGA.md` para el cierre de los criterios y envío.

### Precarga en memoria

Tras crear el snapshot descrito abajo, puedes verificar integración y parada real con `python experiments/check_resilience.py` y `python experiments/check_continuous.py`. Ejecútalos uno después del otro, sin matrices activas. Levantan y detienen únicamente los servicios de prueba de este proyecto. Los errores se registran cuando Metrics está disponible; si cae Metrics, la consulta continúa pero la telemetría es best-effort y el runner detecta la pérdida.

La guía menciona precarga y también scraping ante misses. Se ofrecen ambos modos, sin mezclarlos en el análisis. `live` accede a Soccerway ante cada miss; `preloaded` carga un snapshot real en memoria al iniciar el scraper y nunca accede a la red durante las consultas. No usa una base de datos. El snapshot se obtiene antes de la medición:

```powershell
docker compose build scraper-service
docker compose run --rm --no-deps -e SCRAPER_MODE=live --volume "${PWD}:/repo" --entrypoint python scraper-service -m src.preload
docker compose run --rm --no-deps -e SCRAPER_MODE=preloaded --volume "${PWD}:/repo" --entrypoint python scraper-service /repo/experiments/verify_preloaded.py
$env:SCRAPER_MODE = 'preloaded'
docker compose up -d redis scraper-service metrics-service cache-service
```

La precarga predeterminada cubre el catálogo funcional y los H2H de las pruebas TTL; `--all-pairs` solicita los 120 pares, pero puede faltar una referencia en la vista de Soccerway y entonces se informa snapshot parcial. Una página fuera del snapshot devuelve 503, nunca consulta el sitio silenciosamente. El snapshot local se excluye de Git por tamaño y frescura; se reproduce con el comando anterior. Para volver al modo en vivo: `$env:SCRAPER_MODE = 'live'` y recrear los servicios. Un JSON de experimento puede indicar `"source_mode":"preloaded"`; sin él, el runner fuerza `live`. La latencia de origen en modo precargado es procesamiento del snapshot, no tiempo de scraping externo.

Ejemplo de consulta manual en PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:5001/api/consultas -ContentType 'application/json' -Body '{"tipo":"Q5"}'
Invoke-RestMethod http://localhost:9000/metrics
```

Para evaluar TTL de forma determinista, las configuraciones `ttl-*-3s.json` y `ttl-*-60s.json` repiten dos veces el mismo payload Q1-Q5. Las de 3 segundos esperan 4 segundos entre solicitudes, por lo que deben producir `miss -> miss` después de expirar; las de 60 segundos deben conservar la respuesta y producir `miss -> hit`. Ejecuta cada par y compara sus archivos JSON.
