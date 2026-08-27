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

from atlas_api.application.ports import ChunkDraftRecord
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
from atlas_worker.ingestion import (
    CHUNKER_NAME,
    CHUNKER_VERSION,
    PARSER_NAME,
    PARSER_VERSION,
    chunk_document,
    normalized_artifact_body,
    normalized_artifact_key,
    parse_document,
    total_token_count,
)


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
    settings: Settings,
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
        body = await object_store.get_bytes(version.object_key)
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
        parsing = await store.transition_job(
            claimed.id,
            worker_id,
            verifying.version,
            IngestionJobState.PARSING,
            progress=45,
            reason="parse_started",
        )

    try:
        parsed = parse_document(
            object_key=version.object_key,
            media_type=version.media_type,
            body=body,
            settings=settings,
        )
    except DomainError as error:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            failed = await store.transition_job(
                claimed.id,
                worker_id,
                parsing.version,
                IngestionJobState.FAILED,
                progress=45,
                reason="parse_failed",
                error_class=RetryClass.PERMANENT,
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
        normalizing = await store.transition_job(
            claimed.id,
            worker_id,
            parsing.version,
            IngestionJobState.NORMALIZING,
            progress=58,
            reason="normalize_started",
        )

    try:
        chunks = chunk_document(parsed, settings)
    except DomainError as error:
        async with session_factory() as session, session.begin():
            store = SqlAlchemyIngestionJobStore(session)
            failed = await store.transition_job(
                claimed.id,
                worker_id,
                normalizing.version,
                IngestionJobState.FAILED,
                progress=58,
                reason="chunking_failed",
                error_class=RetryClass.PERMANENT,
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
    artifact_key = normalized_artifact_key(version.workspace_id, version.id)
    artifact_metadata = await object_store.put_derived_bytes(
        object_key=artifact_key,
        body=normalized_artifact_body(parsed, chunks),
        media_type="application/json",
    )

    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        chunking = await store.transition_job(
            claimed.id,
            worker_id,
            normalizing.version,
            IngestionJobState.CHUNKING,
            progress=70,
            reason="chunking_completed",
        )

    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        publishing = await store.transition_job(
            claimed.id,
            worker_id,
            chunking.version,
            IngestionJobState.PUBLISHING,
            progress=85,
            reason="publish_started",
        )

    async with session_factory() as session, session.begin():
        store = SqlAlchemyIngestionJobStore(session)
        completed = await store.publish_document_version(
            claimed.id,
            worker_id,
            publishing.version,
            chunks=[
                ChunkDraftRecord(
                    ordinal=chunk.ordinal,
                    block_type=chunk.block_type,
                    heading=chunk.heading,
                    page_number=chunk.page_number,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    text=chunk.text,
                    safe_metadata=chunk.safe_metadata,
                )
                for chunk in chunks
            ],
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            chunker_name=CHUNKER_NAME,
            chunker_version=CHUNKER_VERSION,
            normalized_object_key=artifact_key,
            normalized_digest_sha256=artifact_metadata.digest_sha256,
            character_count=len(parsed.normalized_text),
            token_count=total_token_count(chunks),
            safe_metadata=parsed.metadata,
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
            settings=app.state.settings,
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
