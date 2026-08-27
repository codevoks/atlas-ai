from __future__ import annotations

from fastapi.testclient import TestClient

from atlas_worker.main import app


def test_worker_health_endpoints() -> None:
    client = TestClient(app)

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "healthy", "service": "atlas-worker"}
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "service": "atlas-worker",
        "workload": "ingestion",
    }
