from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from atlas_api.main import create_app
from tests.support import make_settings, token_for


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(make_settings())
    async with app.router.lifespan_context(app):
        async with app.state.engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE idempotency_records, audit_events, memberships, "
                    "workspaces, users RESTART IDENTITY CASCADE"
                )
            )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http


@pytest.fixture
def alice_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('alice', 'alice@example.com', 'Alice')}"}


@pytest.fixture
def bob_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for('bob', 'bob@example.com', 'Bob')}"}
