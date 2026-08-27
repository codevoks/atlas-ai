from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from atlas_api.application.embeddings import (
    DeterministicLocalEmbeddingProvider,
    EmbeddingBatchPlanner,
    EmbeddingRequest,
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
    IngestionJobRecord,
    MemberRecord,
    SearchCandidate,
    SearchFilter,
    SourceRecord,
    TransactionFactory,
    UploadIntentRecord,
    WorkspaceRecord,
)
from atlas_api.config import Settings
from atlas_api.domain.errors import (
    ForbiddenError,
    IntegrityViolationError,
    ResourceExhaustedError,
    ResourceNotFoundError,
    ValidationError,
)
from atlas_api.domain.models import Actor, AnswerRunStatus, Permission, Role
from atlas_api.domain.policy import can_manage_role, require_permission
from atlas_api.infrastructure.object_store import LocalObjectStore

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

    async def search(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        top_k: int | None,
        filters: SearchFilter,
        mode: Literal["semantic", "lexical", "hybrid"] = "semantic",
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

        batch = None
        query_vector: list[float] | None = None
        if mode in {"semantic", "hybrid"}:
            batch = await self._provider.embed(
                [EmbeddingRequest(item_id=uuid.uuid4(), text=clean_query)]
            )
            query_vector = batch.items[0].vector
        async with self._transactions() as tx:
            membership = await tx.workspaces.membership_context(workspace_id, actor.user_id)
            if membership is None:
                raise ResourceNotFoundError()
            require_permission(membership, Permission.DOCUMENT_READ)
            candidate_limit = min(
                self._settings.semantic_search_max_top_k,
                limit * self._settings.hybrid_search_candidate_multiplier,
            )
            semantic_candidates: list[SearchCandidate] = []
            lexical_candidates: list[SearchCandidate] = []
            embedding_set = None
            if batch is not None and query_vector is not None:
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
                semantic_candidates = await tx.documents.semantic_search(
                    actor=actor,
                    workspace_id=workspace_id,
                    embedding_set_id=embedding_set.id,
                    query_vector=query_vector,
                    top_k=candidate_limit if mode == "hybrid" else limit,
                    filters=filters,
                )
            if mode in {"lexical", "hybrid"}:
                lexical_candidates = await tx.documents.lexical_search(
                    actor=actor,
                    workspace_id=workspace_id,
                    query=clean_query,
                    top_k=candidate_limit if mode == "hybrid" else limit,
                    filters=filters,
                    language=self._settings.lexical_search_language,
                )
        if mode == "semantic":
            candidates = semantic_candidates[:limit]
        elif mode == "lexical":
            candidates = lexical_candidates[:limit]
        else:
            candidates = self._fuse_rrf(semantic_candidates, lexical_candidates, limit=limit)
        debug = {
            "mode": mode,
            "retrieval_config_version": self._settings.retrieval_config_version,
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

    async def answer(
        self,
        *,
        actor: Actor,
        workspace_id: uuid.UUID,
        query: str,
        top_k: int | None,
        filters: SearchFilter,
        retrieval_mode: Literal["semantic", "lexical", "hybrid"] = "hybrid",
    ) -> AnswerRunRecord:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValidationError("Answer query must not be empty.")
        if len(clean_query) > self._settings.embedding_max_text_chars:
            raise ValidationError("Answer query exceeds the configured length limit.")
        candidates, retrieval_debug = await self._search.search(
            actor=actor,
            workspace_id=workspace_id,
            query=clean_query,
            top_k=top_k,
            filters=filters,
            mode=retrieval_mode,
        )
        reranked = self._reranker.rerank(candidates)
        context = self._context_builder.build(reranked)
        generated = self._generator.generate(query=clean_query, context=context)
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
