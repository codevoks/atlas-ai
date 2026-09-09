from __future__ import annotations

import hashlib
import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from atlas_api.config import Settings
from atlas_api.domain.errors import ResourceExhaustedError, ValidationError
from atlas_worker.ingestion import chunk_document, parse_document


def build_pdf_bytes(*page_texts: str) -> bytes:
    """Hand-build a minimal, valid single-font PDF so tests don't need a rendering library."""
    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        font = writer._add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


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


def test_pdf_parser_extracts_text_per_page_with_page_numbered_chunks() -> None:
    body = build_pdf_bytes("Tenant data stays isolated.", "Audit events are safe.")
    pdf_settings = settings().model_copy(update={"chunk_target_chars": 30})
    parsed = parse_document(
        object_key="workspaces/test/uploads/policy.pdf",
        media_type="application/pdf",
        body=body,
        settings=pdf_settings,
    )
    chunks = chunk_document(parsed, pdf_settings)

    assert parsed.metadata["parser"] == "atlas-pdf-parser"
    assert parsed.metadata["page_count"] == 2
    assert "Tenant data stays isolated." in parsed.normalized_text
    assert "Audit events are safe." in parsed.normalized_text
    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert chunks[0].text == "Tenant data stays isolated."
    assert chunks[1].text == "Audit events are safe."


def test_parser_rejects_malformed_pdf_and_obvious_binary() -> None:
    with pytest.raises(ValidationError, match="not a valid PDF file"):
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
