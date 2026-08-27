from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Atlas AI Worker",
    version="0.1.0",
    description="Health surface for the durable worker process.",
)


@app.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "healthy", "service": "atlas-worker"}


@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    return {"status": "ready", "service": "atlas-worker", "workload": "none-phase-1"}
