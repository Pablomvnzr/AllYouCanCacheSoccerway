# All You Can Cache - Plataforma de fútbol chileno

Primera integración de la tarea: el generador de tráfico envía consultas sintéticas a la caché; ante un *miss*, la caché consulta al scraper de Soccerway y guarda la respuesta en Redis con TTL.

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

Las configuraciones incluidas permiten iniciar la comparación Uniforme vs Zipf, tamaños de 2/5/10 MB, LRU vs LFU y TTL de 15/60 segundos. Ajusta `request_count` antes de las corridas finales para obtener muestras suficientes.
