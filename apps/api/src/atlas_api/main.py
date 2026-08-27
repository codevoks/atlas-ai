from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError

from atlas_api.api.routes import router
from atlas_api.application.services import DocumentService, WorkspaceService
from atlas_api.config import Settings, get_settings
from atlas_api.domain.errors import ConflictError, DomainError
from atlas_api.infrastructure.database import create_engine, create_session_factory
from atlas_api.infrastructure.object_store import LocalObjectStore
from atlas_api.infrastructure.repositories import IdentityRepository, SqlAlchemyTransactionFactory
from atlas_api.security.authentication import create_identity_verifier

logger = logging.getLogger("atlas_api")


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
                "details": details or {},
            }
        },
        headers={"X-Request-ID": request.state.request_id},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = create_engine(resolved_settings)
    session_factory = create_session_factory(engine)
    transaction_factory = SqlAlchemyTransactionFactory(session_factory)
    object_store = LocalObjectStore(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.object_store = object_store
        app.state.identity_verifier = create_identity_verifier(resolved_settings)
        app.state.identity_repository = IdentityRepository(session_factory)
        app.state.workspace_service = WorkspaceService(transaction_factory)
        app.state.document_service = DocumentService(
            transaction_factory, object_store, resolved_settings
        )
        yield
        await engine.dispose()

    app = FastAPI(
        title="Atlas AI API",
        version="0.1.0",
        description="Tenant-safe control and query plane for Atlas AI.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("X-Request-ID")
        try:
            request_id = str(uuid.UUID(incoming)) if incoming else str(uuid.uuid4())
        except ValueError:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
        return _error_response(
            request,
            status_code=error.status_code,
            code=error.code,
            message=str(error),
            details=error.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        safe_details: dict[str, object] = {
            "fields": [".".join(str(part) for part in item["loc"]) for item in error.errors()]
        }
        return _error_response(
            request,
            status_code=422,
            code="validation_error",
            message="The request is invalid.",
            details=safe_details,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, error: IntegrityError) -> JSONResponse:
        logger.warning(
            "database integrity conflict", extra={"request_id": request.state.request_id}
        )
        return _error_response(
            request,
            status_code=409,
            code=ConflictError.code,
            message=ConflictError.public_message,
        )

    @app.exception_handler(DBAPIError)
    async def database_error_handler(request: Request, error: DBAPIError) -> JSONResponse:
        logger.exception("database request failed", extra={"request_id": request.state.request_id})
        return _error_response(
            request,
            status_code=503,
            code="dependency_unavailable",
            message="A required dependency is temporarily unavailable.",
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, error: Exception) -> JSONResponse:
        logger.exception(
            "unhandled request failure", extra={"request_id": request.state.request_id}
        )
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred.",
        )

    app.include_router(router)
    return app


app = create_app()
