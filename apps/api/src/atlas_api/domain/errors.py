from __future__ import annotations

from typing import Any


class DomainError(Exception):
    code = "domain_error"
    status_code = 400
    public_message = "The request could not be completed."

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message or self.public_message)
        self.details = details or {}


class UnauthenticatedError(DomainError):
    code = "unauthenticated"
    status_code = 401
    public_message = "Authentication is required."


class ForbiddenError(DomainError):
    code = "forbidden"
    status_code = 403
    public_message = "You do not have permission to perform this action."


class ResourceNotFoundError(DomainError):
    code = "not_found"
    status_code = 404
    public_message = "The requested resource was not found."


class ConflictError(DomainError):
    code = "conflict"
    status_code = 409
    public_message = "The request conflicts with the current resource state."


class ValidationError(DomainError):
    code = "validation_error"
    status_code = 422
    public_message = "The request is invalid."


class DependencyUnavailableError(DomainError):
    code = "dependency_unavailable"
    status_code = 503
    public_message = "A required dependency is temporarily unavailable."


class ResourceExhaustedError(DomainError):
    code = "resource_exhausted"
    status_code = 429
    public_message = "A resource limit has been reached."


class IntegrityViolationError(DomainError):
    code = "integrity_violation"
    status_code = 422
    public_message = "The uploaded object failed integrity verification."
