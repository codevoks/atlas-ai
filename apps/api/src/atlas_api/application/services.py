from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from atlas_api.application.embeddings import (
    DeterministicLocalEmbeddingProvider,
    EmbeddingBatchPlanner,
    EmbeddingRequest,
)
from atlas_api.application.evaluations import (
    METRIC_VERSIONS,
    DeterministicEvaluationRunner,
    aggregate_results,
    current_code_revision,
)
from atlas_api.application.generation import (
    CitationValidator,
    ContextBuilder,
    DeterministicLocalGenerator,
    DeterministicReranker,
)
from atlas_api.application.ports import (
    AnswerRunRecord,
    ChunkEmbeddingWriteRecord,
    ChunkRecord,
    DocumentRecord,
    DocumentVersionRecord,
    EmbeddingBackfillResult,
    EvaluationBaselineRecord,
    EvaluationCaseDraft,
    EvaluationDatasetRecord,
    EvaluationDatasetVersionRecord,
    EvaluationResultRecord,
    EvaluationRunRecord,
    IngestionJobRecord,
    MemberRecord,
    ResearchBudget,
    ResearchRunRecord,
    SearchCandidate,
    SearchFilter,
    SecurityEventRecord,
    SecurityPostureRecord,
    SourceRecord,
    TransactionFactory,
    UploadIntentRecord,
    WorkspaceRecord,
)
from atlas_api.application.research import (
    RESEARCH_CONFIG_VERSION,
    RESEARCH_GRAPH_VERSION,
    RESEARCH_PROMPT_VERSION,
    DeterministicResearchGraph,
    default_research_budget,
)
from atlas_api.application.retrieval_planning import (
    BASELINE_RETRIEVAL_CONFIG,
    DeterministicQueryTransformer,
    QueryVariant,
    retrieval_config,
)
from atlas_api.config import Settings
from atlas_api.domain.errors import (
    ForbiddenError,
    IntegrityViolationError,
    ResourceExhaustedError,
    ResourceNotFoundError,
    ValidationError,
)
from atlas_api.domain.models import (
    Actor,
    AnswerRunStatus,
    EvaluationResultStatus,
    EvaluationRunStatus,
    Permission,
    ResearchRunStatus,
    Role,
    SecurityEventOutcome,
    SecurityEventSeverity,
)
from atlas_api.domain.policy import can_manage_role, require_permission
from atlas_api.infrastructure.object_store import LocalObjectStore
from atlas_api.security.guardrails import (
    DEFAULT_POLICY_CONFIG_VERSION,
    GUARDRAIL_VERSION,
    GuardrailAction,
    GuardrailDecision,
    GuardrailFinding,
    InputValidator,
    OutputValidator,
    Redactor,
    findings_to_safe_metadata,
)

ALLOWED_UPLOAD_MEDIA_TYPES = frozenset(
    {"text/plain", "text/markdown", "application/pdf", "application/octet-stream"}
)


class WorkspaceService:
    def __init__(self, transaction_factory: TransactionFactory) -> None:
        self._transactions = transaction_factory

    async def list_workspaces(self, actor: Actor) -> list[WorkspaceRecord]:
        async with self._transactions() as tx:
            return await tx.workspaces.list_workspaces(actor.user_id)

    async def get_workspace(self, actor: Actor, workspace_id: uuid.UUID) -> WorkspaceRecord:
        async with self._transactions() as tx:
            record = await tx.workspaces.get_workspace(workspace_id, actor.user_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def create_workspace(
        self, actor: Actor, name: str, idempotency_key: str, request_id: str
    ) -> tuple[WorkspaceRecord, bool]:
        async with self._transactions() as tx:
            return await tx.workspaces.create_workspace(actor, name, idempotency_key, request_id)

    async def rename_workspace(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        name: str,
        expected_version: int,
        request_id: str,
    ) -> WorkspaceRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.WORKSPACE_UPDATE)
            return await tx.workspaces.rename_workspace(
                workspace_id, name, expected_version, actor, membership.role, request_id
            )

    async def list_members(self, actor: Actor, workspace_id: uuid.UUID) -> list[MemberRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.MEMBER_LIST)
            return await tx.workspaces.list_members(workspace_id)

    async def add_member(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        email: str,
        role: Role,
        request_id: str,
    ) -> MemberRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.MEMBER_ADD)
            if not can_manage_role(membership.role, Role.VIEWER, role):
                raise ForbiddenError()
            return await tx.workspaces.add_member(workspace_id, email, role, actor, request_id)

    async def update_member_role(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: Role,
        expected_version: int,
        request_id: str,
    ) -> MemberRecord:
        async with self._transactions() as tx:
            actor_membership = await tx.workspaces.membership_context(
                workspace_id, actor.user_id, lock=True
            )
            target_membership = await tx.workspaces.membership_context(
                workspace_id, user_id, lock=True
            )
            if actor_membership is None or target_membership is None:
                raise ResourceNotFoundError()
            require_permission(actor_membership, Permission.MEMBER_UPDATE)
            if not can_manage_role(actor_membership.role, target_membership.role, role):
                raise ForbiddenError()
            return await tx.workspaces.update_member_role(
                workspace_id, user_id, role, expected_version, actor, request_id
            )

    async def remove_member(
        self, actor: Actor, workspace_id: uuid.UUID, user_id: uuid.UUID, request_id: str
    ) -> None:
        async with self._transactions() as tx:
            actor_membership = await tx.workspaces.membership_context(
                workspace_id, actor.user_id, lock=True
            )
            target_membership = await tx.workspaces.membership_context(
                workspace_id, user_id, lock=True
            )
            if actor_membership is None or target_membership is None:
                raise ResourceNotFoundError()
            require_permission(actor_membership, Permission.MEMBER_REMOVE)
            if not can_manage_role(actor_membership.role, target_membership.role, None):
                raise ForbiddenError()
            await tx.workspaces.remove_member(workspace_id, user_id, actor, request_id)


class SecurityService:
    def __init__(self, transaction_factory: TransactionFactory, settings: Settings) -> None:
        self._transactions = transaction_factory
        self._settings = settings
        self._input_validator = InputValidator()
        self._output_validator = OutputValidator()
        self._redactor = Redactor()

    async def list_security_events(
        self, actor: Actor, workspace_id: uuid.UUID, *, limit: int = 25
    ) -> list[SecurityEventRecord]:
        if not 1 <= limit <= 100:
            raise ValidationError("Security event limit is outside the supported bounds.")
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.SECURITY_READ)
            return await tx.security.list_security_events(workspace_id, limit=limit)

    async def posture(self, actor: Actor, workspace_id: uuid.UUID) -> SecurityPostureRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.SECURITY_READ)
        return SecurityPostureRecord(
            policy_config_version=DEFAULT_POLICY_CONFIG_VERSION,
            guardrail_version=GUARDRAIL_VERSION,
            zero_cost=True,
            paid_services_enabled=False,
            fail_closed_controls=[
                "authentication",
                "authorization",
                "tenant_scope",
                "egress_policy",
                "secret_output",
                "quota_reservation",
                "citation_validation",
                "research_approval",
            ],
            deterministic_controls=[
                "schema_validation",
                "rbac_policy",
                "input_scanner",
                "output_scanner",
                "redactor",
                "fixed_window_quota",
                "allowlisted_retrieval_config",
                "allowlisted_research_tools",
            ],
            residual_risks=[
                {
                    "risk": "Pattern-based scanners can miss novel prompt-injection wording.",
                    "severity": "medium",
                    "mitigation": (
                        "Keep deterministic deny rules at authority boundaries and expand "
                        "adversarial corpus."
                    ),
                    "owner": "security",
                },
                {
                    "risk": (
                        "Local deterministic suite does not replace external penetration testing."
                    ),
                    "severity": "medium",
                    "mitigation": (
                        "Schedule external red-team/compliance work before enterprise launch."
                    ),
                    "owner": "security",
                },
            ],
        )

    async def enforce_text_input(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        text: str,
        boundary: str,
        request_id: str,
        block_on_secret: bool = True,
    ) -> GuardrailDecision:
        decision = self._input_validator.scan_text(
            text, boundary=boundary, block_on_secret=block_on_secret
        )
        if decision.detected:
            await self.record_decision(
                actor=actor,
                workspace_id=workspace_id,
                decision=decision,
                event_type=f"{boundary}.input_guardrail",
                request_id=request_id,
                target_type=None,
                target_id=None,
            )
        if decision.blocked:
            raise ValidationError(
                "The request was blocked by security policy.",
                details=findings_to_safe_metadata(decision.findings),
            )
        return decision

    async def enforce_output(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        text: str,
        boundary: str,
        request_id: str,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
    ) -> GuardrailDecision:
        decision = self._output_validator.scan_output(text, boundary=boundary)
        if decision.detected:
            await self.record_decision(
                actor=actor,
                workspace_id=workspace_id,
                decision=decision,
                event_type=f"{boundary}.output_guardrail",
                request_id=request_id,
                target_type=target_type,
                target_id=target_id,
            )
        if decision.blocked:
            raise ValidationError(
                "The generated output was blocked by security policy.",
                details=findings_to_safe_metadata(decision.findings),
            )
        return decision

    async def enforce_quota(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        operation: str,
        request_id: str,
    ) -> None:
        window_seconds = self._settings.security_rate_window_seconds
        limit = self._quota_limit(operation)
        now = datetime.now(UTC)
        epoch = int(now.timestamp())
        window_epoch = epoch - (epoch % window_seconds)
        window_start = datetime.fromtimestamp(window_epoch, UTC)
        quota_metadata: dict[str, object] | None = None
        async with self._transactions() as tx:
            decision = await tx.security.increment_quota_counter(
                workspace_id=workspace_id,
                actor_user_id=actor.user_id,
                operation=operation,
                window_start=window_start,
                window_seconds=window_seconds,
                limit=limit,
            )
            if not decision.allowed:
                quota_metadata = {
                    "operation": operation,
                    "limit": decision.limit,
                    "window_seconds": decision.window_seconds,
                    "retry_after_seconds": decision.retry_after_seconds,
                }
        if quota_metadata is not None:
            async with self._transactions() as tx:
                await tx.security.record_security_event(
                    workspace_id=workspace_id,
                    actor_user_id=actor.user_id,
                    event_type=f"{operation}.quota_exceeded",
                    severity=SecurityEventSeverity.MEDIUM,
                    outcome=SecurityEventOutcome.BLOCKED,
                    request_id=request_id,
                    target_type=None,
                    target_id=None,
                    control_version=GUARDRAIL_VERSION,
                    safe_metadata=quota_metadata,
                )
            raise ResourceExhaustedError(
                "The request was throttled by security policy.",
                details={
                    "code": "quota_exceeded",
                    "operation": operation,
                    "retry_after_seconds": quota_metadata["retry_after_seconds"],
                },
            )

    async def record_decision(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        decision: GuardrailDecision,
        event_type: str,
        request_id: str,
        target_type: str | None,
        target_id: uuid.UUID | None,
    ) -> None:
        severity = _max_severity(decision.findings)
        outcome = (
            SecurityEventOutcome.BLOCKED
            if decision.action is GuardrailAction.BLOCK
            else SecurityEventOutcome.DETECTED
        )
        async with self._transactions() as tx:
            await tx.security.record_security_event(
                workspace_id=workspace_id,
                actor_user_id=actor.user_id,
                event_type=event_type,
                severity=severity,
                outcome=outcome,
                request_id=request_id,
                target_type=target_type,
                target_id=target_id,
                control_version=GUARDRAIL_VERSION,
                safe_metadata=findings_to_safe_metadata(decision.findings),
            )

    def redacted_text(self, value: str) -> str:
        return self._redactor.redact_text(value)

    def _quota_limit(self, operation: str) -> int:
        if operation == "search":
            return self._settings.security_search_requests_per_window
        if operation == "answer":
            return self._settings.security_answer_requests_per_window
        if operation == "research":
            return self._settings.security_research_requests_per_window
        return self._settings.security_search_requests_per_window


_SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def _max_severity(findings: Sequence[GuardrailFinding]) -> SecurityEventSeverity:
    value = "info"
    for finding in findings:
        severity = getattr(finding, "severity", "info")
        if _SEVERITY_ORDER.get(str(severity), 0) > _SEVERITY_ORDER[value]:
            value = str(severity)
    return SecurityEventSeverity(value)


class DocumentService:
    def __init__(
        self,
        transaction_factory: TransactionFactory,
        object_store: LocalObjectStore,
        settings: Settings,
    ) -> None:
        self._transactions = transaction_factory
        self._object_store = object_store
        self._settings = settings
        self._security = SecurityService(transaction_factory, settings)

    async def create_source(
        self, actor: Actor, workspace_id: uuid.UUID, name: str, request_id: str
    ) -> SourceRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.SOURCE_CREATE)
            return await tx.documents.create_source(
                actor, workspace_id, self._clean_name(name), request_id
            )

    async def list_sources(self, actor: Actor, workspace_id: uuid.UUID) -> list[SourceRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.SOURCE_READ)
            return await tx.documents.list_sources(workspace_id)

    async def create_upload_intent(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        original_filename: str,
        media_type: str,
        byte_size: int,
        digest_sha256: str,
        base_url: str,
        request_id: str,
    ) -> UploadIntentRecord:
        filename = self._clean_filename(original_filename)
        clean_media_type = media_type.strip().lower()
        clean_digest = digest_sha256.strip().lower()
        if clean_media_type not in ALLOWED_UPLOAD_MEDIA_TYPES:
            raise ValidationError("The upload media type is not supported.")
        if byte_size <= 0:
            raise ValidationError("Upload byte size must be positive.")
        if byte_size > self._settings.max_upload_bytes:
            raise ResourceExhaustedError("The upload exceeds the workspace upload limit.")
        if len(clean_digest) != 64 or any(char not in "0123456789abcdef" for char in clean_digest):
            raise ValidationError("digest_sha256 must be a lowercase hexadecimal SHA-256 digest.")

        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_CREATE)
            decision = self._security._input_validator.scan_text(
                f"{filename} {clean_media_type}",
                boundary="upload_intent",
                block_on_secret=False,
            )
            if decision.detected:
                await tx.security.record_security_event(
                    workspace_id=workspace_id,
                    actor_user_id=actor.user_id,
                    event_type="upload_intent.input_guardrail",
                    severity=_max_severity(decision.findings),
                    outcome=(
                        SecurityEventOutcome.BLOCKED
                        if decision.blocked
                        else SecurityEventOutcome.DETECTED
                    ),
                    request_id=request_id,
                    target_type=None,
                    target_id=None,
                    control_version=GUARDRAIL_VERSION,
                    safe_metadata=findings_to_safe_metadata(decision.findings),
                )
            if decision.blocked:
                raise ValidationError(
                    "The request was blocked by security policy.",
                    details=findings_to_safe_metadata(decision.findings),
                )
            intent_id = uuid.uuid4()
            expires_at = datetime.now(UTC) + timedelta(
                seconds=self._settings.upload_intent_ttl_seconds
            )
            object_key = self._object_store.object_key(workspace_id, intent_id, filename)
            record = await tx.documents.create_upload_intent(
                actor,
                workspace_id,
                filename,
                clean_media_type,
                byte_size,
                clean_digest,
                object_key,
                expires_at,
                request_id,
            )
        upload_url = self._object_store.signed_upload_url(
            base_url=base_url,
            upload_intent_id=record.id,
            object_key=record.object_key,
            expires_at=record.expires_at,
        )
        return UploadIntentRecord(
            id=record.id,
            workspace_id=record.workspace_id,
            created_by_user_id=record.created_by_user_id,
            object_key=record.object_key,
            original_filename=record.original_filename,
            media_type=record.media_type,
            byte_size=record.byte_size,
            digest_sha256=record.digest_sha256,
            status=record.status,
            expires_at=record.expires_at,
            upload_url=upload_url,
        )

    async def receive_upload_content(
        self,
        *,
        upload_intent_id: uuid.UUID,
        token: str,
        body: bytes,
        media_type: str,
    ) -> UploadIntentRecord:
        async with self._transactions() as tx:
            intent = await tx.documents.get_upload_intent(upload_intent_id)
            if intent is None:
                raise ResourceNotFoundError()
            now = datetime.now(UTC)
            if intent.expires_at < now:
                raise ValidationError("The upload intent has expired.")
            if intent.byte_size != len(body):
                raise IntegrityViolationError(
                    "The uploaded object byte size does not match the intent."
                )
            if intent.media_type != media_type.strip().lower():
                raise ValidationError("The upload media type does not match the intent.")
            if intent.media_type.startswith("text/"):
                text_sample = body[: min(len(body), 4096)].decode("utf-8", errors="ignore")
                decision = self._security._input_validator.scan_text(
                    text_sample, boundary="upload_content", block_on_secret=True
                )
                if decision.detected:
                    await tx.security.record_security_event(
                        workspace_id=intent.workspace_id,
                        actor_user_id=intent.created_by_user_id,
                        event_type="upload_content.input_guardrail",
                        severity=_max_severity(decision.findings),
                        outcome=(
                            SecurityEventOutcome.BLOCKED
                            if decision.blocked
                            else SecurityEventOutcome.DETECTED
                        ),
                        request_id="signed-upload",
                        target_type="upload_intent",
                        target_id=intent.id,
                        control_version=GUARDRAIL_VERSION,
                        safe_metadata=findings_to_safe_metadata(decision.findings),
                    )
                if decision.blocked:
                    raise ValidationError(
                        "The upload was blocked by security policy.",
                        details=findings_to_safe_metadata(decision.findings),
                    )
            self._object_store.verify_upload_token(
                upload_intent_id=intent.id,
                object_key=intent.object_key,
                token=token,
                now=now,
            )
            metadata = await self._object_store.put_bytes(
                object_key=intent.object_key,
                body=body,
                media_type=intent.media_type,
                expected_digest=intent.digest_sha256,
            )
            if metadata.byte_size != intent.byte_size:
                raise IntegrityViolationError(
                    "The uploaded object byte size does not match the intent."
                )
            await tx.documents.mark_upload_received(
                intent.id, metadata.byte_size, metadata.digest_sha256
            )
            updated = await tx.documents.get_upload_intent(upload_intent_id)
            if updated is None:
                raise ResourceNotFoundError()
            return updated

    async def finalize_upload(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        upload_intent_id: uuid.UUID,
        title: str,
        idempotency_key: str,
        request_id: str,
    ) -> tuple[DocumentRecord, DocumentVersionRecord, IngestionJobRecord, bool]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_CREATE)
            intent = await tx.documents.get_upload_intent(upload_intent_id)
            if intent is None or intent.workspace_id != workspace_id:
                raise ResourceNotFoundError()
            metadata = await self._object_store.head(intent.object_key)
            if (
                metadata.byte_size != intent.byte_size
                or metadata.digest_sha256 != intent.digest_sha256
            ):
                raise IntegrityViolationError(
                    "The stored object does not match the finalized intent."
                )
            return await tx.documents.finalize_upload(
                actor,
                workspace_id,
                source_id,
                upload_intent_id,
                self._clean_title(title),
                idempotency_key,
                request_id,
            )

    async def list_documents(self, actor: Actor, workspace_id: uuid.UUID) -> list[DocumentRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_documents(actor, workspace_id)

    async def get_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> DocumentRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            record = await tx.documents.get_document(actor, workspace_id, document_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def list_versions(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_versions(actor, workspace_id, document_id)

    async def list_chunks(
        self,
        actor: Actor,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> list[ChunkRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_chunks(actor, workspace_id, document_id, version_id)

    async def delete_document(
        self, actor: Actor, workspace_id: uuid.UUID, document_id: uuid.UUID, request_id: str
    ) -> None:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_DELETE)
            await tx.documents.delete_document(actor, workspace_id, document_id, request_id)

    async def get_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID
    ) -> IngestionJobRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_READ)
            record = await tx.documents.get_job(actor, workspace_id, job_id)
            if record is None:
                raise ResourceNotFoundError()
            return record

    async def cancel_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_MANAGE)
            return await tx.documents.cancel_job(actor, workspace_id, job_id, request_id)

    async def retry_job(
        self, actor: Actor, workspace_id: uuid.UUID, job_id: uuid.UUID, request_id: str
    ) -> IngestionJobRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_MANAGE)
            return await tx.documents.retry_job(actor, workspace_id, job_id, request_id)

    @staticmethod
    def _clean_name(value: str) -> str:
        normalized = " ".join(value.split())
        if not 2 <= len(normalized) <= 160:
            raise ValidationError("The source name must contain between 2 and 160 characters.")
        return normalized

    @staticmethod
    def _clean_title(value: str) -> str:
        normalized = " ".join(value.split())
        if not 1 <= len(normalized) <= 255:
            raise ValidationError("The document title must contain between 1 and 255 characters.")
        return normalized

    @staticmethod
    def _clean_filename(value: str) -> str:
        filename = Path(value).name.strip()
        if not filename or filename in {".", ".."}:
            raise ValidationError("The upload filename is invalid.")
        if len(filename) > 255:
            raise ValidationError("The upload filename is too long.")
        return filename


class SemanticSearchService:
    def __init__(
        self,
        transaction_factory: TransactionFactory,
        settings: Settings,
    ) -> None:
        self._transactions = transaction_factory
        self._settings = settings
        self._provider = DeterministicLocalEmbeddingProvider(settings)
        self._transformer = DeterministicQueryTransformer()
        self._security = SecurityService(transaction_factory, settings)

    async def search(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        top_k: int | None,
        filters: SearchFilter,
        mode: Literal["semantic", "lexical", "hybrid"] = "semantic",
        retrieval_config_version: str | None = None,
    ) -> tuple[list[SearchCandidate], dict[str, object]]:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValidationError("Search query must not be empty.")
        if len(clean_query) > self._settings.embedding_max_text_chars:
            raise ValidationError("Search query exceeds the configured length limit.")
        limit = top_k or self._settings.semantic_search_default_top_k
        if not 1 <= limit <= self._settings.semantic_search_max_top_k:
            raise ValidationError("top_k is outside the configured search bounds.")
        if mode not in {"semantic", "lexical", "hybrid"}:
            raise ValidationError("Search mode is not supported.")
        plan = self._transformer.plan(
            query=clean_query,
            retrieval_config_version=(
                retrieval_config_version or self._settings.retrieval_config_version
            ),
        )

        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
        await self._security.enforce_text_input(
            actor=actor,
            workspace_id=workspace_id,
            text=clean_query,
            boundary="search",
            request_id="service-search",
            block_on_secret=True,
        )
        await self._security.enforce_quota(
            actor=actor, workspace_id=workspace_id, operation="search", request_id="service-search"
        )

        batch = None
        query_vectors: dict[int, list[float]] = {}
        if mode in {"semantic", "hybrid"}:
            batch = await self._provider.embed(
                [
                    EmbeddingRequest(item_id=uuid.uuid4(), text=variant.text)
                    for variant in plan.variants
                ]
            )
            query_vectors = {
                variant.rank: item.vector
                for variant, item in zip(plan.variants, batch.items, strict=True)
            }
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            candidate_limit = min(
                self._settings.semantic_search_max_top_k,
                limit * self._settings.hybrid_search_candidate_multiplier,
                plan.config.max_candidates_per_branch,
            )
            semantic_candidates: list[SearchCandidate] = []
            lexical_candidates: list[SearchCandidate] = []
            semantic_by_variant: list[tuple[QueryVariant, list[SearchCandidate]]] = []
            lexical_by_variant: list[tuple[QueryVariant, list[SearchCandidate]]] = []
            embedding_set = None
            if batch is not None:
                embedding_set = await tx.documents.active_embedding_set(
                    workspace_id,
                    provider=batch.provider,
                    model=batch.model,
                    model_version=batch.model_version,
                    dimension=batch.dimension,
                    normalized=batch.normalized,
                    config={
                        "zero_cost": True,
                        "storage": "postgres_jsonb_exact_cosine",
                        "external_provider": False,
                    },
                )
                for variant in plan.variants:
                    variant_candidates = await tx.documents.semantic_search(
                        actor=actor,
                        workspace_id=workspace_id,
                        embedding_set_id=embedding_set.id,
                        query_vector=query_vectors[variant.rank],
                        top_k=candidate_limit if mode == "hybrid" else limit,
                        filters=filters,
                    )
                    variant_candidates = [
                        self._with_query_provenance(candidate, variant, plan.config.version)
                        for candidate in variant_candidates
                    ]
                    semantic_by_variant.append((variant, variant_candidates))
                    semantic_candidates.extend(variant_candidates)
            if mode in {"lexical", "hybrid"}:
                for variant in plan.variants:
                    variant_candidates = await tx.documents.lexical_search(
                        actor=actor,
                        workspace_id=workspace_id,
                        query=variant.text,
                        top_k=candidate_limit if mode == "hybrid" else limit,
                        filters=filters,
                        language=self._settings.lexical_search_language,
                    )
                    variant_candidates = [
                        self._with_query_provenance(candidate, variant, plan.config.version)
                        for candidate in variant_candidates
                    ]
                    lexical_by_variant.append((variant, variant_candidates))
                    lexical_candidates.extend(variant_candidates)
        if mode == "semantic":
            candidates = self._aggregate_variant_candidates(
                semantic_by_variant,
                limit=limit,
                stage="semantic",
                diversity_enabled=plan.config.diversity_enabled,
            )
        elif mode == "lexical":
            candidates = self._aggregate_variant_candidates(
                lexical_by_variant,
                limit=limit,
                stage="lexical",
                diversity_enabled=plan.config.diversity_enabled,
            )
        elif plan.config.version == BASELINE_RETRIEVAL_CONFIG:
            candidates = self._fuse_rrf(semantic_candidates, lexical_candidates, limit=limit)
        else:
            candidates = self._fuse_planned_rrf(
                [*semantic_by_variant, *lexical_by_variant],
                limit=limit,
                diversity_enabled=plan.config.diversity_enabled,
            )
        debug = {
            "mode": mode,
            "retrieval_config_version": plan.config.version,
            "retrieval_plan": {
                "original_query": plan.original_query,
                "variants": [
                    {"rank": item.rank, "text": item.text, "transform": item.transform}
                    for item in plan.variants
                ],
                "branch_budget": plan.branch_budget,
                "warnings": plan.warnings,
                "transformation_policy": plan.config.transformation_policy,
                "diversity_enabled": plan.config.diversity_enabled,
            },
            "lexical_language": self._settings.lexical_search_language,
            "rrf_k": self._settings.hybrid_search_rrf_k,
            "candidate_limit": candidate_limit if mode == "hybrid" else limit,
            "branch_counts": {
                "semantic": len(semantic_candidates),
                "lexical": len(lexical_candidates),
                "final": len(candidates),
            },
            "branch_status": {
                "semantic": "not_requested" if mode == "lexical" else "ok",
                "lexical": "not_requested" if mode == "semantic" else "ok",
            },
            "embedding_provider": batch.provider if batch is not None else None,
            "embedding_model": batch.model if batch is not None else None,
            "embedding_model_version": batch.model_version if batch is not None else None,
            "embedding_dimension": batch.dimension if batch is not None else None,
            "embedding_normalized": batch.normalized if batch is not None else None,
            "embedding_set_id": str(embedding_set.id) if embedding_set is not None else None,
            "vector_store": "postgres_jsonb_exact_cosine",
            "lexical_store": "postgres_full_text_search",
            "query_persisted": False,
            "paid_services": False,
        }
        return candidates, debug

    @staticmethod
    def _with_query_provenance(
        candidate: SearchCandidate, variant: QueryVariant, retrieval_config_version: str
    ) -> SearchCandidate:
        return replace(
            candidate,
            retrieval_provenance={
                "retrieval_config_version": retrieval_config_version,
                "query_variant_rank": variant.rank,
                "query_variant": variant.text,
                "query_transform": variant.transform,
                "matched_query_variants": [variant.text],
            },
        )

    def _aggregate_variant_candidates(
        self,
        variant_candidates: list[tuple[QueryVariant, list[SearchCandidate]]],
        *,
        limit: int,
        stage: Literal["semantic", "lexical"],
        diversity_enabled: bool,
    ) -> list[SearchCandidate]:
        by_identity: dict[tuple[uuid.UUID, uuid.UUID], SearchCandidate] = {}
        best_score: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        matched_variants: dict[tuple[uuid.UUID, uuid.UUID], list[str]] = {}
        for variant, candidates in variant_candidates:
            for candidate in candidates:
                identity = (candidate.chunk_id, candidate.document_version_id)
                matched_variants.setdefault(identity, []).append(variant.text)
                if identity not in by_identity or candidate.score > best_score[identity]:
                    by_identity[identity] = candidate
                    best_score[identity] = candidate.score
        ordered = sorted(
            by_identity,
            key=lambda identity: (-best_score[identity], by_identity[identity].chunk_id.hex),
        )
        if diversity_enabled:
            ordered = self._diversify_identities(ordered, by_identity)
        return [
            replace(
                by_identity[identity],
                retrieval_stage=stage,
                retrieval_provenance={
                    **(by_identity[identity].retrieval_provenance or {}),
                    "matched_query_variants": sorted(set(matched_variants[identity])),
                    "aggregator": "best_score_with_optional_diversity",
                },
            )
            for identity in ordered[:limit]
        ]

    def _fuse_planned_rrf(
        self,
        variant_candidates: list[tuple[QueryVariant, list[SearchCandidate]]],
        *,
        limit: int,
        diversity_enabled: bool,
    ) -> list[SearchCandidate]:
        by_identity: dict[tuple[uuid.UUID, uuid.UUID], SearchCandidate] = {}
        scores: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        semantic_scores: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        lexical_scores: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        semantic_ranks: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        lexical_ranks: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        matched_variants: dict[tuple[uuid.UUID, uuid.UUID], list[str]] = {}
        rrf_k = float(self._settings.hybrid_search_rrf_k)

        for variant, candidates in variant_candidates:
            for rank, candidate in enumerate(candidates, start=1):
                identity = (candidate.chunk_id, candidate.document_version_id)
                by_identity.setdefault(identity, candidate)
                scores[identity] = scores.get(identity, 0.0) + (1.0 / (rrf_k + rank))
                matched_variants.setdefault(identity, []).append(variant.text)
                if candidate.retrieval_stage == "semantic":
                    semantic_scores[identity] = max(
                        semantic_scores.get(identity, candidate.semantic_score or candidate.score),
                        candidate.semantic_score or candidate.score,
                    )
                    semantic_ranks[identity] = min(semantic_ranks.get(identity, rank), rank)
                if candidate.retrieval_stage == "lexical":
                    lexical_scores[identity] = max(
                        lexical_scores.get(identity, candidate.lexical_score or candidate.score),
                        candidate.lexical_score or candidate.score,
                    )
                    lexical_ranks[identity] = min(lexical_ranks.get(identity, rank), rank)

        ordered = sorted(
            by_identity,
            key=lambda identity: (-scores[identity], by_identity[identity].chunk_id.hex),
        )
        if diversity_enabled:
            ordered = self._diversify_identities(ordered, by_identity)
        return [
            replace(
                by_identity[identity],
                retrieval_stage="hybrid",
                score=round(scores[identity], 10),
                distance=round(1.0 - scores[identity], 10),
                semantic_score=semantic_scores.get(identity),
                lexical_score=lexical_scores.get(identity),
                rrf_score=round(scores[identity], 10),
                semantic_rank=semantic_ranks.get(identity),
                lexical_rank=lexical_ranks.get(identity),
                retrieval_provenance={
                    **(by_identity[identity].retrieval_provenance or {}),
                    "matched_query_variants": sorted(set(matched_variants[identity])),
                    "aggregator": "planned_rrf_with_optional_diversity",
                },
            )
            for identity in ordered[:limit]
        ]

    @staticmethod
    def _diversify_identities(
        ordered: list[tuple[uuid.UUID, uuid.UUID]],
        candidates: dict[tuple[uuid.UUID, uuid.UUID], SearchCandidate],
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        selected: list[tuple[uuid.UUID, uuid.UUID]] = []
        deferred: list[tuple[uuid.UUID, uuid.UUID]] = []
        seen_documents: set[uuid.UUID] = set()
        for identity in ordered:
            document_id = candidates[identity].document_id
            if document_id in seen_documents:
                deferred.append(identity)
                continue
            selected.append(identity)
            seen_documents.add(document_id)
        return [*selected, *deferred]

    def _fuse_rrf(
        self,
        semantic_candidates: list[SearchCandidate],
        lexical_candidates: list[SearchCandidate],
        *,
        limit: int,
    ) -> list[SearchCandidate]:
        by_identity: dict[tuple[uuid.UUID, uuid.UUID], SearchCandidate] = {}
        scores: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        semantic_scores: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        lexical_scores: dict[tuple[uuid.UUID, uuid.UUID], float] = {}
        semantic_ranks: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        lexical_ranks: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
        rrf_k = float(self._settings.hybrid_search_rrf_k)

        for rank, candidate in enumerate(semantic_candidates, start=1):
            identity = (candidate.chunk_id, candidate.document_version_id)
            by_identity.setdefault(identity, candidate)
            scores[identity] = scores.get(identity, 0.0) + (1.0 / (rrf_k + rank))
            semantic_scores[identity] = candidate.semantic_score or candidate.score
            semantic_ranks[identity] = rank
        for rank, candidate in enumerate(lexical_candidates, start=1):
            identity = (candidate.chunk_id, candidate.document_version_id)
            by_identity.setdefault(identity, candidate)
            scores[identity] = scores.get(identity, 0.0) + (1.0 / (rrf_k + rank))
            lexical_scores[identity] = candidate.lexical_score or candidate.score
            lexical_ranks[identity] = rank

        ranked = sorted(
            by_identity,
            key=lambda identity: (-scores[identity], by_identity[identity].chunk_id.hex),
        )[:limit]
        return [
            replace(
                by_identity[identity],
                retrieval_stage="hybrid",
                score=round(scores[identity], 10),
                distance=round(1.0 - scores[identity], 10),
                semantic_score=semantic_scores.get(identity),
                lexical_score=lexical_scores.get(identity),
                rrf_score=round(scores[identity], 10),
                semantic_rank=semantic_ranks.get(identity),
                lexical_rank=lexical_ranks.get(identity),
            )
            for identity in ranked
        ]

    async def backfill_missing_embeddings(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        limit: int,
    ) -> EmbeddingBackfillResult:
        if not 1 <= limit <= self._settings.max_chunks_per_document:
            raise ValidationError("Backfill limit is outside the configured bounds.")

        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.INGESTION_JOB_MANAGE)
            embedding_set = await tx.documents.active_embedding_set(
                workspace_id,
                provider=self._provider.provider,
                model=self._provider.model,
                model_version=self._provider.model_version,
                dimension=self._provider.dimension,
                normalized=self._provider.normalized,
                config={
                    "zero_cost": True,
                    "storage": "postgres_jsonb_exact_cosine",
                    "external_provider": False,
                },
            )
            coverage_before = await tx.documents.embedding_coverage(workspace_id, embedding_set.id)
            missing = await tx.documents.list_missing_embedding_chunks(
                workspace_id, embedding_set.id, limit=limit
            )

        planner = EmbeddingBatchPlanner(
            max_items=self._settings.embedding_batch_size,
            max_text_chars=self._settings.embedding_max_text_chars,
        )
        requests = [EmbeddingRequest(item_id=item.chunk_id, text=item.text) for item in missing]
        vectors_by_chunk: dict[uuid.UUID, tuple[list[float], int]] = {}
        for batch_requests in planner.batches(requests):
            batch = await self._provider.embed(batch_requests)
            for item in batch.items:
                vectors_by_chunk[item.item_id] = (item.vector, item.token_count)

        async with self._transactions() as tx:
            embedded_count = await tx.documents.write_chunk_embeddings(
                workspace_id,
                embedding_set.id,
                [
                    ChunkEmbeddingWriteRecord(
                        chunk_id=item.chunk_id,
                        document_version_id=item.document_version_id,
                        vector=vectors_by_chunk[item.chunk_id][0],
                        token_count=vectors_by_chunk[item.chunk_id][1],
                    )
                    for item in missing
                ],
            )
            coverage_after = await tx.documents.embedding_coverage(workspace_id, embedding_set.id)

        return EmbeddingBackfillResult(
            embedding_set_id=embedding_set.id,
            missing_before=max(
                coverage_before.total_ready_chunks - coverage_before.embedded_ready_chunks, 0
            ),
            embedded_count=embedded_count,
            missing_after=max(
                coverage_after.total_ready_chunks - coverage_after.embedded_ready_chunks, 0
            ),
        )


class AnswerService:
    def __init__(self, transaction_factory: TransactionFactory, settings: Settings) -> None:
        self._transactions = transaction_factory
        self._settings = settings
        self._search = SemanticSearchService(transaction_factory, settings)
        self._reranker = DeterministicReranker()
        self._context_builder = ContextBuilder(settings)
        self._generator = DeterministicLocalGenerator(settings)
        self._citation_validator = CitationValidator()
        self._security = SecurityService(transaction_factory, settings)

    async def answer(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        top_k: int | None,
        filters: SearchFilter,
        retrieval_mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
        retrieval_config_version: str | None = None,
    ) -> AnswerRunRecord:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValidationError("Answer query must not be empty.")
        if len(clean_query) > self._settings.embedding_max_text_chars:
            raise ValidationError("Answer query exceeds the configured length limit.")
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
        await self._security.enforce_text_input(
            actor=actor,
            workspace_id=workspace_id,
            text=clean_query,
            boundary="answer",
            request_id="service-answer",
            block_on_secret=True,
        )
        await self._security.enforce_quota(
            actor=actor, workspace_id=workspace_id, operation="answer", request_id="service-answer"
        )
        candidates, retrieval_debug = await self._search.search(
            actor=actor,
            workspace_id=workspace_id,
            query=clean_query,
            top_k=top_k,
            filters=filters,
            mode=retrieval_mode,
            retrieval_config_version=retrieval_config_version,
        )
        reranked = self._reranker.rerank(candidates)
        context = self._context_builder.build(reranked)
        generated = self._generator.generate(query=clean_query, context=context)
        await self._security.enforce_output(
            actor=actor,
            workspace_id=workspace_id,
            text=generated.text,
            boundary="answer",
            request_id="service-answer",
        )
        self._citation_validator.validate(
            answer_text=generated.text,
            evidence=context.evidence,
            citations=generated.citations,
        )
        status = AnswerRunStatus.SUCCEEDED if generated.citations else AnswerRunStatus.REFUSED
        grounding_status = "citation_verified" if generated.citations else "no_evidence"
        warnings = sorted(set([*context.warnings, *generated.warnings]))

        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.create_answer_run(
                actor=actor,
                workspace_id=workspace_id,
                query=clean_query,
                status=status,
                answer_text=generated.text,
                retrieval_mode=retrieval_mode,
                retrieval_config_version=str(retrieval_debug["retrieval_config_version"]),
                generation_provider=self._generator.provider,
                generation_model=self._generator.model,
                generation_model_version=self._generator.model_version,
                prompt_version=self._generator.prompt_version,
                grounding_status=grounding_status,
                warnings=warnings,
                input_tokens=context.input_tokens,
                output_tokens=generated.output_tokens,
                total_cost_usd=0.0,
                latency_ms=generated.latency_ms,
                evidence=context.evidence,
                citations=generated.citations,
            )

    async def get_answer_run(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        answer_run_id: uuid.UUID,
    ) -> AnswerRunRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            record = await tx.documents.get_answer_run(
                workspace_id=workspace_id,
                answer_run_id=answer_run_id,
            )
            if record is None:
                raise ResourceNotFoundError()
            return record


class EvaluationService:
    def __init__(self, transaction_factory: TransactionFactory, settings: Settings) -> None:
        self._transactions = transaction_factory
        self._settings = settings
        self._search = SemanticSearchService(transaction_factory, settings)
        self._answer = AnswerService(transaction_factory, settings)
        self._runner = DeterministicEvaluationRunner(self._search, self._answer)

    async def create_dataset(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        name: str,
        description: str | None,
    ) -> EvaluationDatasetRecord:
        clean_name = self._clean_name(name)
        clean_description = self._clean_optional_text(description, limit=1_000)
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_CREATE)
            return await tx.documents.create_evaluation_dataset(
                actor=actor,
                workspace_id=workspace_id,
                name=clean_name,
                description=clean_description,
            )

    async def list_datasets(
        self, *, actor: Actor, workspace_id: uuid.UUID
    ) -> list[EvaluationDatasetRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_evaluation_datasets(workspace_id)

    async def create_dataset_version(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        dataset_id: uuid.UUID,
        description: str | None,
        cases: list[EvaluationCaseDraft],
    ) -> EvaluationDatasetVersionRecord:
        clean_description = self._clean_optional_text(description, limit=1_000)
        if not (1 <= len(cases) <= 50):
            raise ValidationError(
                "Evaluation dataset versions must contain between 1 and 50 cases."
            )
        clean_cases = [self._clean_case(case) for case in cases]
        labeled_chunk_ids = sorted(
            {chunk_id for case in clean_cases for chunk_id in case.relevant_chunk_ids}
        )
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_CREATE)
            dataset = await tx.documents.get_evaluation_dataset(workspace_id, dataset_id)
            if dataset is None:
                raise ResourceNotFoundError()
            valid_chunk_ids = await tx.documents.validate_ready_chunk_ids(
                workspace_id, labeled_chunk_ids
            )
            missing = set(labeled_chunk_ids) - valid_chunk_ids
            if missing:
                raise ValidationError(
                    "Evaluation cases reference unavailable or unauthorized chunks."
                )
            return await tx.documents.create_evaluation_dataset_version(
                actor=actor,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                description=clean_description,
                config={
                    "schema_version": "phase7-evaluation-dataset-v1",
                    "content_redacted": False,
                    "expected_answers_hidden_from_system_under_test": True,
                    "max_cases": 50,
                },
                content_digest=self._dataset_digest(clean_cases),
                cases=clean_cases,
            )

    async def get_dataset_version(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
    ) -> EvaluationDatasetVersionRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            version = await tx.documents.get_evaluation_dataset_version(
                workspace_id, dataset_version_id
            )
            if version is None:
                raise ResourceNotFoundError()
            return version

    async def run_evaluation(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        run_name: str,
        retrieval_config_version: str | None = None,
    ) -> EvaluationRunRecord:
        clean_name = self._clean_name(run_name)
        clean_retrieval_config_version = retrieval_config_version or BASELINE_RETRIEVAL_CONFIG
        started = datetime.now(UTC)
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            version = await tx.documents.get_evaluation_dataset_version(
                workspace_id, dataset_version_id
            )
            if version is None:
                raise ResourceNotFoundError()
            run = await tx.documents.create_evaluation_run(
                actor=actor,
                workspace_id=workspace_id,
                dataset_version_id=dataset_version_id,
                run_name=clean_name,
                evaluation_config={
                    "runner": "deterministic-local",
                    "runner_version": "phase8-evaluation-runner-v1",
                    "retrieval_config_version": clean_retrieval_config_version,
                    "paid_services": False,
                    "large_local_model_required": False,
                },
                metric_versions=METRIC_VERSIONS,
                code_revision=current_code_revision(),
            )
        result_drafts: list[EvaluationResultRecord] = []
        for case in version.cases:
            executed = await self._runner.run_case(
                actor=actor,
                workspace_id=workspace_id,
                case=case,
                retrieval_config_version=clean_retrieval_config_version,
            )
            result_drafts.append(
                EvaluationResultRecord(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    evaluation_run_id=run.id,
                    evaluation_case_id=case.id,
                    status=executed.status,
                    metrics=executed.metrics,
                    retrieved_chunk_ids=executed.retrieved_chunk_ids,
                    answer_run_id=executed.answer_run_id,
                    error_code=executed.error_code,
                    error_message=executed.error_message,
                    latency_ms=executed.latency_ms,
                    total_cost_usd=executed.total_cost_usd,
                    created_at=datetime.now(UTC),
                )
            )
        aggregate, slices, failures = aggregate_results(version.cases, result_drafts)
        succeeded = sum(
            1 for result in result_drafts if result.status == EvaluationResultStatus.SUCCEEDED
        )
        status = (
            EvaluationRunStatus.SUCCEEDED
            if succeeded == len(result_drafts)
            else EvaluationRunStatus.PARTIAL
            if succeeded
            else EvaluationRunStatus.FAILED
        )
        latency_ms = max(int((datetime.now(UTC) - started).total_seconds() * 1000), 0)
        total_cost = sum(result.total_cost_usd for result in result_drafts)
        async with self._transactions() as tx:
            return await tx.documents.complete_evaluation_run(
                workspace_id=workspace_id,
                evaluation_run_id=run.id,
                status=status,
                aggregate_metrics=aggregate,
                slice_metrics=slices,
                failure_summary=failures,
                total_cost_usd=total_cost,
                latency_ms=latency_ms,
                results=result_drafts,
            )

    async def list_runs(
        self, *, actor: Actor, workspace_id: uuid.UUID, limit: int
    ) -> list[EvaluationRunRecord]:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            return await tx.documents.list_evaluation_runs(workspace_id, limit=limit)

    async def get_run(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        evaluation_run_id: uuid.UUID,
    ) -> EvaluationRunRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            run = await tx.documents.get_evaluation_run(workspace_id, evaluation_run_id)
            if run is None:
                raise ResourceNotFoundError()
            return run

    async def approve_baseline(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        evaluation_run_id: uuid.UUID,
        notes: str | None,
    ) -> EvaluationBaselineRecord:
        clean_notes = self._clean_optional_text(notes, limit=1_000)
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.WORKSPACE_UPDATE)
            return await tx.documents.approve_evaluation_baseline(
                actor=actor,
                workspace_id=workspace_id,
                evaluation_run_id=evaluation_run_id,
                notes=clean_notes,
            )

    @staticmethod
    def _clean_name(value: str) -> str:
        clean = " ".join(value.split())
        if len(clean) < 2:
            raise ValidationError("Name must contain at least two visible characters.")
        return clean[:160]

    @staticmethod
    def _clean_optional_text(value: str | None, *, limit: int) -> str | None:
        if value is None:
            return None
        clean = " ".join(value.split())
        return clean[:limit] if clean else None

    def _clean_case(self, case: EvaluationCaseDraft) -> EvaluationCaseDraft:
        query = " ".join(case.query.split())
        if not query:
            raise ValidationError("Evaluation case query must not be empty.")
        if len(query) > self._settings.embedding_max_text_chars:
            raise ValidationError("Evaluation case query exceeds the configured length limit.")
        if not (1 <= case.top_k <= 20):
            raise ValidationError("Evaluation case top_k must be between 1 and 20.")
        if not case.relevant_chunk_ids:
            raise ValidationError("Evaluation case must include relevant chunk labels.")
        retrieval_config(case.retrieval_config_version)
        return EvaluationCaseDraft(
            query=query,
            retrieval_mode=case.retrieval_mode,
            retrieval_config_version=case.retrieval_config_version,
            top_k=case.top_k,
            relevant_chunk_ids=list(dict.fromkeys(case.relevant_chunk_ids)),
            expected_answer_substrings=[
                item.strip()[:500] for item in case.expected_answer_substrings if item.strip()
            ][:10],
            expected_citation_quotes=[
                item.strip()[:500] for item in case.expected_citation_quotes if item.strip()
            ][:10],
            slices=[item.strip()[:80] for item in case.slices if item.strip()][:10] or ["default"],
            metadata=case.metadata,
        )

    @staticmethod
    def _dataset_digest(cases: list[EvaluationCaseDraft]) -> str:
        payload = [
            {
                "query": case.query,
                "retrieval_mode": case.retrieval_mode,
                "retrieval_config_version": case.retrieval_config_version,
                "top_k": case.top_k,
                "relevant_chunk_ids": sorted(str(item) for item in case.relevant_chunk_ids),
                "expected_answer_substrings": case.expected_answer_substrings,
                "expected_citation_quotes": case.expected_citation_quotes,
                "slices": sorted(case.slices),
                "metadata": case.metadata,
            }
            for case in cases
        ]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class ResearchService:
    def __init__(self, transaction_factory: TransactionFactory, settings: Settings) -> None:
        self._transactions = transaction_factory
        self._settings = settings
        self._search = SemanticSearchService(transaction_factory, settings)
        self._graph = DeterministicResearchGraph()
        self._security = SecurityService(transaction_factory, settings)

    async def create_research_run(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        purpose: str,
        question: str,
        idempotency_key: str,
    ) -> tuple[ResearchRunRecord, bool]:
        clean_purpose = " ".join(purpose.split())[:160]
        clean_question = " ".join(question.split())
        if len(idempotency_key) < 8 or len(idempotency_key) > 128:
            raise ValidationError("Idempotency-Key must contain between 8 and 128 characters.")
        if len(clean_purpose) < 2:
            raise ValidationError("Research purpose must contain at least two visible characters.")
        if not clean_question:
            raise ValidationError("Research question must not be empty.")
        if len(clean_question) > self._settings.embedding_max_text_chars:
            raise ValidationError("Research question exceeds the configured length limit.")
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_MANAGE)
        await self._security.enforce_text_input(
            actor=actor,
            workspace_id=workspace_id,
            text=f"{clean_purpose} {clean_question}",
            boundary="research",
            request_id="service-research",
            block_on_secret=True,
        )
        await self._security.enforce_quota(
            actor=actor,
            workspace_id=workspace_id,
            operation="research",
            request_id="service-research",
        )
        self._graph.validate_question(clean_question)
        budget = default_research_budget()
        budget_body = self._budget_dict(budget)
        request_hash = hashlib.sha256(
            json.dumps(
                {
                    "purpose": clean_purpose,
                    "question": clean_question,
                    "budget": budget_body,
                    "config_version": RESEARCH_CONFIG_VERSION,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_MANAGE)
            run, replayed = await tx.research.create_research_run(
                actor=actor,
                workspace_id=workspace_id,
                purpose=clean_purpose,
                question=clean_question,
                graph_version=RESEARCH_GRAPH_VERSION,
                config_version=RESEARCH_CONFIG_VERSION,
                model_versions={
                    "planner": "deterministic-local@2026-08-28",
                    "tools": "deterministic-local@2026-08-28",
                    "synthesis": RESEARCH_PROMPT_VERSION,
                },
                input_hash=hashlib.sha256(clean_question.encode("utf-8")).hexdigest(),
                budget=budget_body,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        if replayed or run.status is not ResearchRunStatus.PENDING:
            return run, replayed
        return (
            await self.resume_research_run(actor=actor, workspace_id=workspace_id, run_id=run.id),
            False,
        )

    async def list_research_runs(
        self, *, actor: Actor, workspace_id: uuid.UUID, limit: int
    ) -> list[ResearchRunRecord]:
        if not 1 <= limit <= 25:
            raise ValidationError("Research run limit must be between 1 and 25.")
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_READ)
            return await tx.research.list_research_runs(workspace_id, limit=limit)

    async def get_research_run(
        self, *, actor: Actor, workspace_id: uuid.UUID, run_id: uuid.UUID
    ) -> ResearchRunRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_READ)
            run = await tx.research.get_research_run(workspace_id, run_id)
            if run is None:
                raise ResourceNotFoundError()
            return run

    async def resume_research_run(
        self, *, actor: Actor, workspace_id: uuid.UUID, run_id: uuid.UUID
    ) -> ResearchRunRecord:
        run = await self.get_research_run(actor=actor, workspace_id=workspace_id, run_id=run_id)
        if run.status in {
            ResearchRunStatus.SUCCEEDED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.CANCELLED,
            ResearchRunStatus.BUDGET_EXHAUSTED,
            ResearchRunStatus.TIMED_OUT,
        }:
            return run
        if run.status is ResearchRunStatus.WAITING_APPROVAL:
            return run

        budget = self._budget_from_record(run.budget)

        async def retrieve(query: str) -> list[SearchCandidate]:
            candidates, _debug = await self._search.search(
                actor=actor,
                workspace_id=workspace_id,
                query=query,
                top_k=3,
                filters=SearchFilter(),
                mode="hybrid",
                retrieval_config_version="phase8-multi-query-expansion-v1",
            )
            return candidates

        graph_output = await self._graph.run_until_approval(
            question=run.question,
            budget=budget,
            retrieval=retrieve,
        )
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_MANAGE)
            updated = await tx.research.append_research_progress(
                workspace_id=workspace_id,
                research_run_id=run.id,
                expected_version=run.version,
                status=ResearchRunStatus.RUNNING,
                usage=graph_output.usage,
                report_text=None,
                evidence=graph_output.evidence,
                warnings=graph_output.warnings,
                terminal_reason=None,
                steps=graph_output.steps,
                tool_invocations=graph_output.tool_invocations,
                checkpoint=graph_output.state,
            )
            return await tx.research.request_approval(
                actor=actor,
                workspace_id=workspace_id,
                research_run_id=updated.id,
                expected_run_version=updated.version,
                approval_type="synthesize_cited_report",
                reason=str(graph_output.approval_payload["reason"]),
                approval_payload=graph_output.approval_payload,
            )

    async def cancel_research_run(
        self, *, actor: Actor, workspace_id: uuid.UUID, run_id: uuid.UUID, expected_version: int
    ) -> ResearchRunRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_MANAGE)
            return await tx.research.cancel_research_run(
                workspace_id=workspace_id,
                research_run_id=run_id,
                expected_version=expected_version,
            )

    async def decide_approval(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        approval_id: uuid.UUID,
        expected_version: int,
        approved: bool,
    ) -> ResearchRunRecord:
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_MANAGE)
            decided = await tx.research.decide_approval(
                actor=actor,
                workspace_id=workspace_id,
                research_run_id=run_id,
                approval_id=approval_id,
                expected_version=expected_version,
                approved=approved,
            )
        if not approved:
            return decided
        latest_checkpoint = decided.checkpoints[-1] if decided.checkpoints else None
        if latest_checkpoint is None:
            raise ValidationError("Research run has no resumable checkpoint.")
        output = self._graph.synthesize_after_approval(
            question=decided.question,
            checkpoint_state=latest_checkpoint.state,
            existing_usage=decided.usage,
            budget=self._budget_from_record(decided.budget),
        )
        await self._security.enforce_output(
            actor=actor,
            workspace_id=workspace_id,
            text=output.report_text,
            boundary="research",
            request_id="service-research",
            target_type="research_run",
            target_id=decided.id,
        )
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.RESEARCH_RUN_MANAGE)
            return await tx.research.append_research_progress(
                workspace_id=workspace_id,
                research_run_id=decided.id,
                expected_version=decided.version,
                status=ResearchRunStatus.SUCCEEDED,
                usage=output.usage,
                report_text=output.report_text,
                evidence=decided.evidence,
                warnings=sorted(set([*decided.warnings, *output.warnings])),
                terminal_reason="completed_after_human_approval",
                steps=output.steps,
                tool_invocations=[],
                checkpoint={
                    **latest_checkpoint.state,
                    "next_node": None,
                    "report_hash": hashlib.sha256(output.report_text.encode("utf-8")).hexdigest(),
                },
            )

    @staticmethod
    def _budget_dict(budget: ResearchBudget) -> dict[str, object]:
        return {
            "max_steps": budget.max_steps,
            "max_tool_calls": budget.max_tool_calls,
            "max_input_tokens": budget.max_input_tokens,
            "max_output_tokens": budget.max_output_tokens,
            "max_cost_usd": budget.max_cost_usd,
            "max_wall_time_ms": budget.max_wall_time_ms,
        }

    @staticmethod
    def _budget_from_record(record: dict[str, object]) -> ResearchBudget:
        return ResearchBudget(
            max_steps=_int_json(record, "max_steps"),
            max_tool_calls=_int_json(record, "max_tool_calls"),
            max_input_tokens=_int_json(record, "max_input_tokens"),
            max_output_tokens=_int_json(record, "max_output_tokens"),
            max_cost_usd=_float_json(record, "max_cost_usd"),
            max_wall_time_ms=_int_json(record, "max_wall_time_ms"),
        )


def _int_json(record: dict[str, object], key: str) -> int:
    value = record[key]
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise ValidationError(f"Invalid integer value for {key}.")


def _float_json(record: dict[str, object], key: str) -> float:
    value = record[key]
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValidationError(f"Invalid numeric value for {key}.")
