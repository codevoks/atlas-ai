from __future__ import annotations

import hashlib

import pytest

from atlas_api.config import Settings
from atlas_api.domain.errors import ResourceExhaustedError, ValidationError
from atlas_worker.ingestion import chunk_document, parse_document


def settings() -> Settings:
    return Settings(
        atlas_env="test",
        auth_mode="development",
        auth_dev_secret="atlas-worker-test-development-secret",
        upload_signing_secret="atlas-worker-test-upload-signing-secret",
        parser_max_bytes=2048,
        chunk_target_chars=220,
        chunk_overlap_chars=20,
        max_chunks_per_document=10,
    )


def test_text_parser_normalizes_and_chunks_deterministically() -> None:
    raw = b"# Atlas Policy\r\n\r\nTenant data   stays isolated.\r\n\r\nAudit events are safe."
    parsed = parse_document(
        object_key="workspaces/test/uploads/policy.md",
        media_type="text/markdown",
        body=raw,
        settings=settings(),
    )
    chunks = chunk_document(parsed, settings())

    assert (
        parsed.normalized_text
        == "# Atlas Policy\n\nTenant data stays isolated.\n\nAudit events are safe."
    )
    assert parsed.metadata["parser"] == "atlas-text-parser"
    assert len(chunks) == 1
    assert chunks[0].heading == "Atlas Policy"
    assert chunks[0].token_count == 11
    assert chunks[0].content_hash == hashlib.sha256(chunks[0].text.encode()).hexdigest()


def test_parser_rejects_obvious_binary_and_unsupported_pdf() -> None:
    with pytest.raises(ValidationError, match="PDF parsing is deferred"):
        parse_document(
            object_key="workspaces/test/uploads/file.pdf",
            media_type="application/pdf",
            body=b"%PDF-1.7\n...",
            settings=settings(),
        )

    with pytest.raises(ValidationError, match="binary"):
        parse_document(
            object_key="workspaces/test/uploads/file.txt",
            media_type="text/plain",
            body=b"hello\x00world",
            settings=settings(),
        )


def test_parser_enforces_byte_and_chunk_count_limits() -> None:
    with pytest.raises(ResourceExhaustedError, match="parser byte limit"):
        parse_document(
            object_key="workspaces/test/uploads/large.txt",
            media_type="text/plain",
            body=b"a" * 2049,
            settings=settings(),
        )

    tiny_chunk_settings = Settings(
        atlas_env="test",
        auth_mode="development",
        auth_dev_secret="atlas-worker-test-development-secret",
        upload_signing_secret="atlas-worker-test-upload-signing-secret",
        parser_max_bytes=4096,
        chunk_target_chars=200,
        chunk_overlap_chars=10,
        max_chunks_per_document=1,
    )
    parsed = parse_document(
        object_key="workspaces/test/uploads/many.txt",
        media_type="text/plain",
        body=((b"word " * 60) + b"\n\n" + (b"next " * 60)),
        settings=tiny_chunk_settings,
    )
    with pytest.raises(ResourceExhaustedError, match="too many chunks"):
        chunk_document(parsed, tiny_chunk_settings)
