from fastapi import FastAPI

app = FastAPI(title="Scraper Service")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/consulta/proximos-partidos/{equipo}")
def proximos_partidos(equipo: str):
    # TODO: conectar con soccerway_scraper.py
    return {"equipo": equipo, "partidos": []}
