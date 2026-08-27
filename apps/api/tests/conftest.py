from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from atlas_api.main import create_app
from tests.support import make_settings, token_for


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(make_settings())
    object_store_root = Path(make_settings().object_store_root)
    shutil.rmtree(object_store_root, ignore_errors=True)
    async with app.router.lifespan_context(app):
        async with app.state.engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE chunks, job_events, ingestion_jobs, document_versions, documents, "
                    "upload_intents, sources, idempotency_records, audit_events, "
                    "memberships, workspaces, users RESTART IDENTITY CASCADE"
                )
            )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http
    shutil.rmtree(object_store_root, ignore_errors=True)


@pytest.fixture
def alice_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('alice', 'alice@example.com', 'Alice')}"}


@pytest.fixture
def bob_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('bob', 'bob@example.com', 'Bob')}"}
