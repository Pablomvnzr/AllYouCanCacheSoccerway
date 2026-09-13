"""Genera fuente LaTeX con resultados medidos; no inventa corridas faltantes."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows = list(csv.DictReader((ROOT/'experiments/analysis/summary.csv').open(encoding='utf-8')))
    out = ROOT/'output/pdf'
    out.mkdir(parents=True, exist_ok=True)
    text = r'''\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish]{babel}
\usepackage[margin=2.2cm]{geometry}
\usepackage{amsmath,booktabs,longtable,hyperref,pgfplots}
\pgfplotsset{compat=1.18}
\hypersetup{colorlinks=true,urlcolor=blue}
\title{All You Can Cache: fútbol chileno\\Informe experimental de Sistemas Distribuidos}
\author{Ricardo Lepin \and Pablo Muñoz}
\date{12 de septiembre de 2026}
\begin{document}
\sloppy
\maketitle
\noindent\textbf{Estado: documento de trabajo.} Grupo 4, sección 2. El video está en preparación; incorporar su enlace y confirmar condiciones de entrega antes de enviar. Los resultados incluidos provienen de archivos JSON validados; una matriz incompleta no se presenta como terminada.
\section{Problema y arquitectura}
El sistema responde consultas de fútbol chileno con cache-aside: generador $\to$ servicio de caché $\to$ Redis; ante un miss consulta al scraper Soccerway y guarda un JSON con TTL. El cuarto servicio recoge métricas. Docker Compose separa dependencias y permite reproducir el despliegue. No hay una base de datos persistente: el término tiempo de origen corresponde aquí al scraping externo.

Para abordar la precarga indicada por la guía, se implementa también un modo preloaded: un snapshot real se obtiene antes de medir y se carga íntegramente en memoria al iniciar el scraper. Las consultas usan esas páginas sin llamadas externas; fuera del snapshot devuelven un error explícito. El alcance predeterminado cubre el catálogo funcional y los H2H de TTL, no todo el historial de Soccerway. No se mezcla su latencia de procesamiento en memoria con scraping en vivo. Python/FastAPI simplifican contratos HTTP y validación; Playwright permite obtener contenido dinámico; BeautifulSoup estructura el HTML; Redis ofrece TTL y políticas configurables sin reinventar almacenamiento.

Q1 entrega próximos partidos con fecha, hora, local y visita; Q2 resultados recientes; Q3 enfrentamientos entre dos equipos; Q4 partidos de un intervalo; Q5 tabla de posiciones. Las claves canónicas evitan que invertir los equipos en Q3 duplique respuestas. Se validan parámetros y estructura del origen; una respuesta de error no se guarda como dato válido. La extracción dinámica usa Playwright y BeautifulSoup, con límites de espera y cierre del navegador.

Redis admite allkeys-lru y allkeys-lfu, políticas aproximadas. LRU favorece recencia; LFU favorece frecuencia acumulada con envejecimiento. TTL reduce obsolescencia, pero un TTL demasiado corto añade misses incluso cuando hay capacidad. Un TTL largo mejora reutilización a costa de frescura, especialmente relevante para próximos partidos y tabla en días de juego.
\section{Metodología y métricas}
El catálogo funcional tiene 54 consultas estables: 16 Q1, 16 Q2, una Q3, 20 Q4 y una Q5. Se conservan semilla 42 y permutación al cambiar política o tamaño. Uniforme asigna probabilidad $1/N$; Zipf finita asigna $p_i=i^{-\alpha}/\sum_{j=1}^N j^{-\alpha}$. La selección afecta consultas completas, no parámetros aleatorios diferentes en cada repetición.

Las llegadas son de ciclo cerrado: se espera la respuesta y después el intervalo. Por tanto, el intervalo no es una tasa abierta independiente de la latencia. Cada corrida reinicia Redis y las métricas. La matriz real usa 40 consultas por configuración; es una muestra exploratoria, sin intervalos de confianza. Se recomienda repetir con distintas semillas antes de generalizar.

Las configuraciones funcionales admiten intervalos Uniformes entre cero y dos veces el promedio, o Zipf finita sobre 50 intervalos discretos normalizados al mismo promedio, con alpha 1.5. Esto permite llegadas dispersas o concentradas conservando la espera esperada. La matriz de presión mantiene intervalos constantes para aislar concentración de claves; no es un experimento de carga abierta concurrente.

La matriz sintética usa 1000 solicitudes, 1000 claves y valores de 64 KiB, TTL 3600 s, Zipf $\alpha=1.1$ o Uniforme. Omite deliberadamente Soccerway para aislar presión de capacidad. No se usa para estimar scraping ni eficiencia relativa al origen. Redis incluye memoria interna en maxmemory; datos útiles y capacidad configurada no son equivalentes.

Hit rate $=H/(H+M)$; errores se informan por separado. Throughput es el número de respuestas exitosas dividido por la duración del cliente. Latencia p50/p95 se mide desde el cliente e incluye red, serialización y envío de telemetría; la latencia interna se conserva separadamente. Tiempo de scraping se mide sólo en accesos reales al origen. Evictions/min se calcula con la diferencia del contador Redis y duración. Expired keys no se suman a evictions.

La eficiencia solicitada se implementa como $(\sum t_{hit}-\sum t_{origen,miss})/(H+M+E)$, equivalente a la fórmula con tiempos promedio por clase. Es un indicador definido por la guía, no ahorro de tiempo contrafactual: puede resultar negativo. Los contadores acumulados se conservan y los percentiles/eventos se limitan a las 10000 observaciones más recientes. El runner verifica concordancia cliente-servidor y código de salida; conserva evidencia fallida sin incluirla entre éxitos.
\section{Resultados medidos}
'''
    for group, title in [('ttl','TTL por consulta'),('pressure','Presión sintética: capacidad y política'),('functional','Consultas reales: Uniforme y Zipf'),('preloaded','Origen real precargado: procesamiento en memoria')]:
        selected=[r for r in rows if r['name'].startswith(group+'-')]
        text += '\\subsection{'+title+'}\n'
        text += f'Corridas válidas disponibles: {len(selected)}.\\par\n'
        text += r'{\small\begin{longtable}{lrrrrrr}\toprule Caso & Hits & Misses & Hit rate & p95 ms & Evict. & Exp.\\\midrule\endhead'+'\n'
        for r in selected:
            label=r['name'].replace(group+'-','').replace('uniform','U').replace('zipf','Z')
            text += f"{label} & {r['hits']} & {r['misses']} & {float(r['hit_rate']):.3f} & {float(r['p95_ms']):.1f} & {r['evictions']} & {r['expired_keys']} \\\\\n"
        text += r'\bottomrule\end{longtable}}'+'\n'
        if selected:
            text += r'{\small\begin{longtable}{lrrrrr}\toprule Caso & Resp./s & p50 ms & Origen ms & Efic. ms & Evict./min\\\midrule\endhead'+'\n'
            for r in selected:
                label=r['name'].replace(group+'-','').replace('uniform','U').replace('zipf','Z')
                source=f"{float(r['scraper_average_ms']):.1f}" if r['scraper_average_ms'] else 'N/A'
                efficiency=f"{float(r['efficiency_ms']):.1f}" if r['efficiency_ms'] else 'N/A'
                text += f"{label} & {float(r['throughput_rps']):.2f} & {float(r['p50_ms']):.1f} & {source} & {efficiency} & {float(r['evictions_per_min']):.1f} \\\\\n"
            text += r'\bottomrule\end{longtable}}'+'\n'
    pressure=[r for r in rows if r['name'].startswith('pressure-')]
    if pressure:
        text += r'\begin{figure}[ht]\centering\begin{tikzpicture}\begin{axis}[width=.9\textwidth,height=6cm,xlabel={Capacidad configurada (MB)},ylabel={Hit rate},xtick={2,5,10},ymin=0,ymax=1,legend pos=north west,grid=major]'+'\n'
        for dist in ('uniform','zipf'):
            for policy in ('lru','lfu'):
                points=[]
                for size in (2,5,10):
                    r=next((r for r in pressure if r['name']==f'pressure-{dist}-{size}mb-{policy}'),None)
                    if r: points.append(f"({size},{r['hit_rate']})")
                if points:
                    text += '\\addplot+[mark=*] coordinates {'+' '.join(points)+'};\\addlegendentry{'+dist+' '+policy+'}\n'
        text += r'\end{axis}\end{tikzpicture}\caption{Presión sintética: no incluye latencia de Soccerway.}\end{figure}'+'\n'
    functional=[r for r in rows if r['name'].startswith('functional-')]
    if functional:
        text += r'\begin{figure}[ht]\centering\begin{tikzpicture}\begin{axis}[width=.9\textwidth,height=6cm,xlabel={Capacidad configurada (MB)},ylabel={Latencia cliente (ms, escala log)},ymode=log,xtick={2,5,10},legend pos=south east,grid=major]'+'\n'
        for dist in ('uniform','zipf'):
            for percentile in ('p50','p95'):
                points=[]
                for size in (2,5,10):
                    r=next((r for r in functional if r['name']==f'functional-{dist}-{size}mb-lru'),None)
                    if r: points.append(f"({size},{r[percentile+'_ms']})")
                if points:
                    text += '\\addplot+[mark=*] coordinates {'+' '.join(points)+'};\\addlegendentry{'+dist+' '+percentile+'}\n'
        text += r'\end{axis}\end{tikzpicture}\caption{Consultas reales con LRU: mediana y cola de latencia.}\end{figure}'+'\n'
    text += '\\section{Comparaciones cuantitativas}\n'
    lookup = {r['name']: r for r in rows}
    for group in ('pressure', 'functional'):
        for dist in ('uniform', 'zipf'):
            a=lookup.get(f'{group}-{dist}-2mb-lru')
            b=lookup.get(f'{group}-{dist}-10mb-lru')
            if a and b:
                text += f"{group}, {dist}, LRU: al pasar de 2 a 10 MB, hit rate {float(a['hit_rate']):.3f} a {float(b['hit_rate']):.3f}; evictions {a['evictions']} a {b['evictions']}; p95 {float(a['p95_ms']):.1f} a {float(b['p95_ms']):.1f} ms.\\par\n"
        for policy in ('lru', 'lfu'):
            for size in (2,5,10):
                u=lookup.get(f'{group}-uniform-{size}mb-{policy}')
                z=lookup.get(f'{group}-zipf-{size}mb-{policy}')
                if u and z:
                    diff=100*(float(z['hit_rate'])-float(u['hit_rate']))
                    text += f"{group}, {size} MB, {policy.upper()}: Zipf cambia el hit rate en {diff:+.1f} puntos porcentuales frente a Uniforme; evictions {z['evictions']} frente a {u['evictions']}; throughput {float(z['throughput_rps']):.2f} frente a {float(u['throughput_rps']):.2f} respuestas/s.\\par\n"
    if functional:
        text += 'En las consultas reales, cuando los hits superan la mitad de las solicitudes, p50 puede pasar a reflejar el camino rápido de caché. Si más del 5\\% siguen siendo misses, p95 aún puede reflejar el origen lento: mejorar la mediana no garantiza eliminar la cola. Los intervalos entre consultas afectan throughput, pero no se incluyen dentro de la latencia individual de respuesta.\\par\n'
    resilience_path=ROOT/'experiments/analysis/resilience.json'
    if resilience_path.exists():
        resilience=json.loads(resilience_path.read_text(encoding='utf-8'))
        text += '\\section{Integración y fallos controlados}\n'
        text += 'Se probaron servicios Docker reales, usando el origen precargado para no depender de la red externa.\\par\n'
        text += r'\begin{center}\begin{tabular}{lrrr}\toprule Caso & HTTP esperado & HTTP observado & Segundos\\\midrule'+'\n'
        labels=dict(invalid_query='Consulta inválida',first_query='Primer acceso',repeated_query='Repetición',scraper_unavailable='Scraper detenido',redis_unavailable='Redis detenido',metrics_unavailable='Métricas detenidas')
        for name,status in resilience['expected_http_statuses'].items():
            text += labels[name]+' & '+str(status)+' & '+str(resilience['cases'][name]['http_status'])+f" & {resilience['cases'][name]['elapsed_seconds']:.2f} \\\\\n"
        text += r'\bottomrule\end{tabular}\end{center}'+'\n'
        text += ('Todas las comprobaciones pasaron.' if resilience['all_checks_passed'] else 'Hay comprobaciones fallidas: no presentar como validación completa.')+'\\par\n'
        text += 'Los errores de consulta inválida, scraper detenido y Redis detenido se registran cuando Metrics está disponible. Si Metrics está detenido, el hit sigue funcionando pero ese evento no puede persistirse: la telemetría es best-effort, sin cola durable. El runner detecta pérdida de eventos y no valida la corrida.\\par\n'
        text += 'El cliente Redis limita reintentos y tiempos de socket; si Redis ya falló, no se vuelve a consultarlo para registrar estadísticas del error. Los tiempos de socket no son una garantía universal de duración de DNS; se reportan los tiempos observados en este entorno.\\par\n'
    text += r'''\section{Preguntas y respuestas}
\paragraph{¿Cómo cambian hit rate y miss rate entre distribuciones?} Las comparaciones cuantitativas anteriores indican la diferencia medida; con cero errores, miss rate es uno menos hit rate. No debe confundirse porcentaje de hits sobre consultas válidas con porcentaje sobre todos los intentos cuando hay errores.
\paragraph{¿Qué distribución beneficia o estresa más la caché y por qué?} Bajo presión, Uniforme reparte accesos entre más claves y provoca más reemplazos; Zipf reutiliza las populares. La tabla permite comprobar si esta hipótesis se cumple en cada capacidad y política. Un efecto pequeño o nulo entre políticas cuando los datos caben no demuestra equivalencia bajo cualquier carga.
\paragraph{¿Qué implicaciones tiene para una plataforma deportiva real?} Eventos de alta audiencia concentran accesos a ciertos equipos y resultados. Reutilizar esos datos puede reducir llamadas al origen, pero exige TTL que limite obsolescencia. Los experimentos cerrados y sintéticos no prueban capacidad ante millones de usuarios: harían falta carga abierta concurrente, varias semillas y observación de saturación.
\paragraph{¿Qué sucede al aumentar memoria y cambiar política?} El gráfico de presión muestra las tres capacidades y ambas políticas. Si se conserva el conjunto popular, LFU puede superar LRU; con accesos uniformes el beneficio por frecuencia es menor. Se reportan los resultados observados, no una superioridad universal. El aumento de memoria sólo produce más hits si antes se perdían entradas útiles por capacidad.
\paragraph{¿Cómo afecta TTL a Q1--Q5?} La tabla TTL comprueba cada consulta individualmente. TTL 3 s vence antes de repetir a los 4 s; TTL 60 s conserva la respuesta. Frescura y rendimiento son objetivos distintos: estas pruebas verifican mecanismo, no si una respuesta quedó obsoleta en el sitio.
\section{Análisis crítico y limitaciones}
Las pruebas TTL con dos repeticiones aíslan expiración: un intervalo de 4 s supera TTL 3 s y produce miss seguido de miss; TTL 60 s conserva la respuesta y produce miss seguido de hit. Una segunda expiración al final de una corrida puede aparecer en el contador sin significar un tercer acceso. Los percentiles de dos solicitudes no son estimaciones robustas de rendimiento.

La concentración Zipf permite reutilizar un subconjunto popular; Uniforme dispersa accesos entre más claves y suele generar más misses bajo capacidad limitada. La dirección y magnitud deben leerse en las tablas, no suponerse como resultado universal. Aumentar memoria reduce reemplazos cuando el conjunto activo supera la capacidad; si las respuestas reales ya caben, ampliar de 2 a 10 MB puede no cambiar hit rate ni producir evictions. La comparación LRU/LFU se realiza con idéntico catálogo y semilla, pero el tiempo interno de Redis y sus algoritmos aproximados pueden introducir variación.

El catálogo no contiene el mismo número de claves de cada tipo: Uniforme significa uniforme entre consultas completas, no entre las cinco categorías. Zipf cambia también la mezcla de tipos y parámetros, cuyos tiempos de origen pueden ser diferentes; por eso las diferencias de throughput real no se atribuyen exclusivamente a hit rate. La matriz sintética controla tamaño de valor y elimina esa heterogeneidad, pero pierde realismo. Las curvas de presión incluyen calentamiento desde caché vacía y no sólo estado estacionario.

La latencia real también depende de Soccerway, Chromium y red; no es atribuible sólo a Redis. En ciclo cerrado, misses lentos reducen throughput. Q3 depende de hallar una referencia de partido; ausencia de referencia devuelve error explícito y no prueba que nunca hubo enfrentamientos. La extracción depende del diseño de la fuente y puede romperse si cambia. No se implementan colas ni dashboard avanzado, correspondientes a futuras entregas según la guía.

Como criterio de frescura, Q1 y Q5 merecen TTL más corto cuando hay partidos en curso o cambios de calendario; Q2 y Q3 contienen principalmente historia y admiten TTL mayor; Q4 depende de si el intervalo incluye fechas actuales. Son decisiones propuestas, no conclusiones de obsolescencia comprobada: las pruebas sólo verifican expiración y reutilización. La implementación permite variar TTL entre corridas, pero usa un TTL global, no cinco TTL simultáneos. Los valores 3 y 60 s son extremos experimentales, no una recomendación de producción.

Las fechas de la fuente sin año usan el año de obtención del snapshot o el actual en vivo; no se reasignan al año del intervalo solicitado. La vista actual no equivale a un archivo completo de temporadas históricas. Veintiuna pruebas automatizadas comprueban fórmulas, fechas, claves, distribución y fallos simulados; las 54 consultas sobre precarga se verifican con el acceso externo bloqueado.

@CONCLUSIONS@
\section{Reproducción y entrega}
Desde Windows con Python y Docker Desktop, ejecutar secuencialmente \texttt{python experiments/run\_suite.py ttl}, luego \texttt{pressure} y \texttt{functional}; ejecutar \texttt{python experiments/analyze\_results.py} y \texttt{python experiments/build\_report.py}. Las pruebas automatizadas están en \texttt{tests/run\_tests.ps1}. README documenta contratos, puertos, modo continuo y parada con Ctrl+C.

Repositorio de entrega: \url{https://giteit.udp.cl/CIT2011/2026-2/seccion-2/grupo-4/-/tree/TheRealMain}. Video: en preparación por los integrantes. Debe añadirse un enlace real de YouTube o Drive visible para el docente. Confirmar plazo y referencias inconsistentes de semestre con el docente; enviar PDF y enlace del repositorio por Canvas.

\section{Fuentes de evidencia}
Guía \textit{Tarea 1 Sistemas Distribuidos 2026 2} y \textit{Rúbrica T1 SD 2026 2}, suministradas por los integrantes. Datos reales: Soccerway, obtenidos en la fecha de las corridas, sin garantía de frescura posterior. Evidencia reproducible: \texttt{experiments/results/}, esquema 2; resumen \texttt{experiments/analysis/summary.csv}, verificación \texttt{validation.json}. Los archivos históricos de esquema anterior se excluyen. Cada JSON incluye configuración, semilla, revisión Git, marca de cambios locales, eventos, muestras funcionales y contadores Redis.
\end{document}
'''
    conclusions='\\section{Conclusiones}\n'
    u=lookup.get('functional-uniform-5mb-lru')
    z=lookup.get('functional-zipf-5mb-lru')
    if u and z:
        conclusions += f"Con datos reales y 5 MB LRU, hit rate fue {100*float(u['hit_rate']):.1f}\\% con Uniforme y {100*float(z['hit_rate']):.1f}\\% con Zipf. La diferencia describe esta muestra; no garantiza el mismo resultado con otros catálogos o semillas.\\par\n"
    for size in (2,5,10):
        lru=lookup.get(f'pressure-zipf-{size}mb-lru')
        lfu=lookup.get(f'pressure-zipf-{size}mb-lfu')
        if lru and lfu:
            delta=100*(float(lfu['hit_rate'])-float(lru['hit_rate']))
            conclusions += f"Presión Zipf {size} MB: LFU cambia hit rate en {delta:+.1f} puntos frente a LRU. La frecuencia ayuda a conservar claves populares bajo reemplazos; cuando aumenta la capacidad, ambas pueden retener más del conjunto activo.\\par\n"
    conclusions += 'Las corridas reales y las sintéticas responden preguntas diferentes: si los datos reales caben, más memoria no necesariamente mejora hits; bajo presión, capacidad y política sí influyen en permanencia. TTL se verificó individualmente para Q1--Q5 y debe elegirse también por frescura. Mejorar p50 no garantiza mejorar p95. Antes de extrapolar a alta audiencia se requieren más muestras, distintas semillas y carga concurrente abierta.\\par\n'
    text=text.replace('@CONCLUSIONS@',conclusions)
    (out/'informe.tex').write_text(text,encoding='utf-8')
    print(out/'informe.tex')


if __name__=='__main__':
    main()
