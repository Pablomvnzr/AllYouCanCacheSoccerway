# Evidencia y cierre de la entrega

## Orden de prioridad

1. Correctitud: Q1–Q5 reales, errores HTTP explícitos, resultados inválidos no cacheados, fechas y hora de partidos.
2. Métricas: hit/(hit+miss), latencia del cliente, throughput exitoso, tiempos reales de origen, evictions y expiraciones diferenciados.
3. Experimentos: diez TTL (cada Q1–Q5), doce de presión (Uniforme/Zipf × 2/5/10 MB × LRU/LFU), ocho funcionales reales.
4. Análisis crítico e informe LaTeX PDF con tablas/gráficos basados en JSON válidos.
5. Video y envío en Canvas: requieren intervención de los integrantes.

## Correspondencia con criterios

| Criterio | Evidencia verificable | Límite o paso pendiente |
|---|---|---|
| Cuatro componentes desacoplados y Redis en Docker | docker-compose.yml y health de caché/scraper/métricas | Docker Desktop debe estar iniciado |
| Consultas Q1–Q5 sobre datos reales | JSON ttl-q1 a ttl-q5 y functional_evidence.json | La fuente cambia; Q3 puede carecer de referencia |
| Uniforme y Zipf configurables y reproducibles | distributions.py, catálogo estable, seed 42, configuraciones | Llegadas de ciclo cerrado, no carga abierta |
| Caché 2/5/10 MB y dos políticas | doce configuraciones pressure, LRU/LFU | Memoria Redis incluye sobrecarga interna |
| Métricas completas y resultados experimentales | JSON esquema 2, summary.csv, tablas del informe | Métricas de origen no aplican a datos sintéticos |
| Impacto del TTL en cada consulta | diez corridas ttl, secuencias comprobadas por validation.json | Dos solicitudes aíslan expiración, no percentiles robustos |
| Comparación Uniforme/Zipf y concentración de accesos | tabla y gráfico de hit rate; evictions y latencia | Separar resultados reales y sintéticos |
| Instrucciones de despliegue y reproducción | README y tests/run_tests.ps1 | Confirmar ambiente del evaluador |
| Informe LaTeX con análisis crítico | output/pdf/informe.tex y PDF compilado; Ricardo Lepin y Pablo Muñoz | Completar enlace real del video |
| Video de aproximadamente diez minutos | Guion incluido abajo | Grabar, publicar y verificar permisos |
| GitLab UDP y entrega Canvas | Enlace TheRealMain incluido en README/informe | Publicar cambios finales y enviar en Canvas |

Las 21 pruebas automatizadas cubren fórmulas, almacenamiento acotado, Zipf finita, semilla, catálogo, fechas/hora, clave H2H, validación, fallos simulados, parada del tráfico y precarga sin llamadas externas. No sustituyen una prueba de carga concurrente ni una revisión manual de exactitud de Soccerway.

## Interpretación que debe quedar en el informe

No se necesita llenar artificialmente la memoria para calcular hit rate. Para observar reemplazos sí debe haber presión de capacidad, con TTL suficientemente alto para no confundir expiración con eviction. La matriz sintética aísla capacidad/política, pero no permite concluir sobre la latencia real de Soccerway. La matriz funcional sí mide el origen real; cero evictions es legítimo si el conjunto de respuestas cabe en Redis. Un hit rate mayor con Zipf se relaciona con concentración de accesos, no con que cada respuesta sea más pequeña.

Cada experimento usa una caché vacía y semilla fija. Redis LRU/LFU son políticas aproximadas, no implementaciones exactas de libro. Hay que distinguir calentamiento, tamaño de datos útiles y memoria interna. Los percentiles de dos consultas TTL muestran el contraste miss/hit, pero no estiman de forma robusta una distribución de latencias.

## Guion de video (aproximadamente diez minutos)

- 0:00–1:00: integrantes, problema, repositorio UDP y arquitectura de cuatro servicios más Redis.
- 1:00–3:00: levantar Docker; mostrar Q1 con fecha/hora/local/visita, Q2 resultados, Q3 enfrentamientos, Q4 intervalo y Q5 tabla. Mostrar primer miss y segundo hit.
- 3:00–4:30: configuración Uniforme/Zipf, catálogo estable, semilla, límites de tamaño, LRU/LFU y TTL.
- 4:30–6:30: mostrar JSON reales y sintéticos por separado, tablas y gráficos del informe, comparar concentración y capacidad.
- 6:30–8:00: TTL por Q1–Q5, expiraciones frente a reemplazos; explicar latencia del cliente y tiempo de origen.
- 8:00–9:00: pruebas automatizadas y manejo de consultas inválidas/fallos.
- 9:00–10:00: limitaciones, conclusiones justificadas y cómo reproducir.

## Pasos humanos pendientes

Grabar el video; subirlo a YouTube o Drive con permiso de visualización para el docente; añadir su enlace real al informe; verificar integrantes (máximo dos), plazo/sección y requisitos de Canvas; entregar el PDF y enlace al GitLab UDP. No sustituir el enlace por un archivo de video descargable. No afirmar que estos pasos se realizaron sin comprobarlos.

La guía contiene referencias de semestre y fecha que conviene confirmar con el docente. Esta implementación ofrece cache-aside en vivo y un modo de precarga en memoria para el catálogo declarado, sin una base de datos persistente. La evidencia preloaded_evidence.json comprueba las 54 consultas sin llamadas externas durante su procesamiento.
