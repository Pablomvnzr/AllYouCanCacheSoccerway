# All You Can Cache - Plataforma de fútbol chileno

Primera integración de la tarea: el generador de tráfico envía consultas sintéticas a la caché; ante un *miss*, la caché consulta al scraper de Soccerway y guarda la respuesta en Redis con TTL.

Repositorio espejo personal de desarrollo: [AllYouCanCacheSoccerway en GitHub](https://github.com/Pablomvnzr/AllYouCanCacheSoccerway).

## Servicios

- `traffic-generator`: genera consultas Q1-Q5 con distribución uniforme o Zipf.
- `cache-service`: expone `POST /api/consultas`, construye claves canónicas y usa Redis.
- `scraper-service`: obtiene y estructura los datos de Soccerway.
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
docker compose up -d redis scraper-service metrics-service cache-service
docker compose run --rm traffic-generator
```

En otra terminal puedes consultar las métricas mientras se ejecuta:

```powershell
Invoke-RestMethod http://localhost:9000/metrics
```

Detén el generador con `Ctrl+C` y baja los servicios al terminar con `docker compose down`.

Para comparar presión de memoria de manera reproducible, usa las configuraciones `pressure-zipf-<tamaño>-<política>.json` y `pressure-uniform-<tamaño>-<política>.json`, con tamaños de 2, 5 y 10 MB y políticas LRU/LFU. Cada una usa el mismo catálogo de claves y valores de 32 KiB; las 1.000 solicitudes pueden superar los 10 MB. Este modo mide la caché bajo presión de memoria y debe presentarse en el informe como complemento de las corridas funcionales contra Soccerway.

Para evaluar TTL de forma determinista, las configuraciones `ttl-*-3s.json` y `ttl-*-60s.json` repiten dos veces el mismo payload Q1-Q5. Las de 3 segundos esperan 4 segundos entre solicitudes, por lo que deben producir `miss -> miss` después de expirar; las de 60 segundos deben conservar la respuesta y producir `miss -> hit`. Ejecuta cada par y compara sus archivos JSON.
