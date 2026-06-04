"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import briefs, signals, snapshots

app = FastAPI(
    title="AdSignal API",
    description="Competitive ad intelligence: Spark + Iceberg + MongoDB + LLM",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(briefs.router, tags=["Intelligence"])
app.include_router(signals.router, tags=["Signals"])
app.include_router(snapshots.router, tags=["Time Travel"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "adsignal-api"}
