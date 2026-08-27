from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from atlas_api.config import Settings, get_settings
from atlas_api.domain.errors import (
    DomainError,
    IntegrityViolationError,
    ResourceNotFoundError,
)
from atlas_api.domain.models import IngestionJobState, RetryClass, UploadIntentStatus
from atlas_api.infrastructure.database import create_engine, create_session_factory
from atlas_api.infrastructure.models import UploadIntentModel
from atlas_api.infrastructure.object_store import LocalObjectStore
from atlas_api.infrastructure.repositories import SqlAlchemyIngestionJobStore


class RunOnceResponse(BaseModel):
    claimed: bool
    job_id: uuid.UUID | None = None
    state: IngestionJobState | None = None
    progress: int | None = None
    error_code: str | None = None


class ReconcileUploadsResponse(BaseModel):
    expired_intents: int
    orphan_objects_detected: int
    missing_objects_detected: int


async def _reconcile_uploads(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    object_store: LocalObjectStore,
    limit: int = 100,
) -> ReconcileUploadsResponse:
    expired_intents = 0
    orphan_objects_detected = 0
    missing_objects_detected = 0
    async with session_factory() as session, session.begin():
        intents = (
            await session.scalars(
                select(UploadIntentModel)
                .where(
                    UploadIntentModel.status.in_(
                        [
                            UploadIntentStatus.PENDING.value,
                            UploadIntentStatus.UPLOADED.value,
                        ]
                    ),
                    UploadIntentModel.expires_at < datetime.now(UTC),
                )
                .order_by(
                    UploadIntentModel.expires_at.asc(), UploadIntentModel.id.asc()
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        for intent in intents:
            intent.status = UploadIntentStatus.EXPIRED.value
            expired_intents += 1
            try:
                await object_store.head(intent.object_key)
            except DomainError:
                missing_objects_detected += 1
            else:
                orphan_objects_detected += 1
    return ReconcileUploadsResponse(
        expired_intents=expired_intents,
        orphan_objects_detected=orphan_objects_detected,
        missing_objects_detected=missing_objects_detected,
    )


async def _run_once(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    object_store: LocalObjectStore,
    worker_id: str,
) -> RunOnceResponse:
    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        claimed = await store.claim_next_job(worker_id)
        if claimed is None:
            return RunOnceResponse(claimed=False)

    if claimed.cancellation_requested:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            cancelled = await store.transition_job(
                claimed.id,
                worker_id,
                claimed.version,
                IngestionJobState.CANCELLED,
                progress=claimed.progress,
                reason="cancelled_before_processing",
                error_class=RetryClass.CANCELLED,
                error_code="cancelled",
                error_message="The job was cancelled before processing.",
            )
        return RunOnceResponse(
            claimed=True,
            job_id=cancelled.id,
            state=cancelled.state,
            progress=cancelled.progress,
        )

    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        verifying = await store.transition_job(
            claimed.id,
            worker_id,
            claimed.version,
            IngestionJobState.VERIFYING,
            progress=35,
            reason="verify_started",
        )
        version = await store.document_version_for_job(claimed.id)
        if version is None:
            raise ResourceNotFoundError()

    try:
        metadata = await object_store.head(version.object_key)
        if (
            metadata.byte_size != version.byte_size
            or metadata.digest_sha256 != version.digest_sha256
        ):
            raise IntegrityViolationError(
                "The stored object changed after finalization."
            )
    except DomainError as error:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            failed = await store.transition_job(
                claimed.id,
                worker_id,
                verifying.version,
                IngestionJobState.FAILED,
                progress=35,
                reason="integrity_failed",
                error_class=RetryClass.INTEGRITY,
                error_code=error.code,
                error_message=str(error),
            )
        return RunOnceResponse(
            claimed=True,
            job_id=failed.id,
            state=failed.state,
            progress=failed.progress,
            error_code=failed.error_code,
        )

    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        publishing = await store.transition_job(
            claimed.id,
            worker_id,
            verifying.version,
            IngestionJobState.PUBLISHING,
            progress=75,
            reason="publish_started",
        )

    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        completed = await store.publish_document_version(
            claimed.id, worker_id, publishing.version
        )
    return RunOnceResponse(
        claimed=True,
        job_id=completed.id,
        state=completed.state,
        progress=completed.progress,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = create_engine(resolved_settings)
    session_factory = create_session_factory(engine)
    object_store = LocalObjectStore(resolved_settings)
    worker_id = f"{socket.gethostname()}-{uuid.uuid4()}"

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.object_store = object_store
        app.state.worker_id = worker_id
        yield
        await engine.dispose()

    app = FastAPI(
        title="Atlas AI Worker",
        version="0.2.0",
        description="Durable ingestion worker for Atlas AI.",
        lifespan=lifespan,
    )

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "healthy", "service": "atlas-worker"}

    @app.get("/health/ready")
    async def readiness() -> dict[str, str]:
        return {"status": "ready", "service": "atlas-worker", "workload": "ingestion"}

    @app.post("/internal/ingestion/run-once", response_model=RunOnceResponse)
    async def run_once() -> RunOnceResponse:
        return await _run_once(
            session_factory=app.state.session_factory,
            object_store=app.state.object_store,
            worker_id=app.state.worker_id,
        )

    @app.post(
        "/internal/maintenance/reconcile-uploads",
        response_model=ReconcileUploadsResponse,
    )
    async def reconcile_uploads() -> ReconcileUploadsResponse:
        return await _reconcile_uploads(
            session_factory=app.state.session_factory,
            object_store=app.state.object_store,
        )

    return app


app = create_app()
