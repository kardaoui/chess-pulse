from fastapi import FastAPI
from routers import stats, games, sync

app = FastAPI(
    title="ChessPulse Pipeline API",
    description="API REST exposant les données chess-pulse à chess-pulse-app",
    version="1.0.0"
)

app.include_router(stats.router, prefix="/stats", tags=["Stats"])
app.include_router(games.router, prefix="/games", tags=["Games"])
app.include_router(sync.router, prefix="/sync", tags=["Sync"])


@app.get("/health")
def health_check():
    """Vérifie que l'API est bien démarrée."""
    return {"status": "ok"}