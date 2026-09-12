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
