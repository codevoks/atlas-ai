from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass

from atlas_api.config import Settings
from atlas_api.domain.errors import ResourceExhaustedError, ValidationError

PARSER_NAME = "atlas-text-parser"
PARSER_VERSION = "2026-08-27"
CHUNKER_NAME = "atlas-paragraph-chunker"
CHUNKER_VERSION = "2026-08-27"
SUPPORTED_MEDIA_TYPES = frozenset(
    {"text/plain", "text/markdown", "application/markdown"}
)
TEXT_LIKE_EXTENSIONS = (".txt", ".md", ".markdown")
MAX_METADATA_VALUE_LENGTH = 255


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    block_type: str
    text: str
    start_char: int
    end_char: int
    heading: str | None = None
    page_number: int | None = None


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    normalized_text: str
    blocks: list[ParsedBlock]
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    ordinal: int
    block_type: str
    heading: str | None
    page_number: int | None
    start_char: int
    end_char: int
    token_count: int
    content_hash: str
    text: str
    safe_metadata: dict[str, object]


def parse_document(
    *,
    object_key: str,
    media_type: str,
    body: bytes,
    settings: Settings,
) -> ParsedDocument:
    if len(body) > settings.parser_max_bytes:
        raise ResourceExhaustedError("The document exceeds the parser byte limit.")
    _reject_binary_magic(body)
    if not _is_supported_media_type(media_type, object_key):
        raise ValidationError(
            "The document media type is not supported by the Phase 3 parser."
        )
    try:
        raw_text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationError("The document must be valid UTF-8 text.") from error
    if "\x00" in raw_text:
        raise ValidationError(
            "The document contains null bytes and is not accepted as text."
        )

    normalized_text = _normalize_text(raw_text)
    if not normalized_text.strip():
        raise ValidationError("The document does not contain extractable text.")
    blocks = _blocks_from_text(normalized_text)
    return ParsedDocument(
        normalized_text=normalized_text,
        blocks=blocks,
        metadata={
            "parser": PARSER_NAME,
            "parser_version": PARSER_VERSION,
            "media_type": media_type,
            "block_count": len(blocks),
            "character_count": len(normalized_text),
            "line_count": normalized_text.count("\n") + 1,
        },
    )


def chunk_document(parsed: ParsedDocument, settings: Settings) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    current_parts: list[ParsedBlock] = []
    current_text = ""
    current_heading: str | None = None

    for block in parsed.blocks:
        block_text = block.text.strip()
        if not block_text:
            continue
        separator = "\n\n" if current_text else ""
        would_be = f"{current_text}{separator}{block_text}"
        if current_text and len(would_be) > settings.chunk_target_chars:
            drafts.append(
                _draft_from_blocks(
                    len(drafts), current_parts, current_text, current_heading
                )
            )
            current_parts = []
            current_text = ""
            current_heading = None
        if block.block_type == "heading":
            current_heading = _safe_heading(block.text)
        current_parts.append(block)
        current_text = f"{current_text}{separator if current_text else ''}{block_text}"

    if current_text:
        drafts.append(
            _draft_from_blocks(
                len(drafts), current_parts, current_text, current_heading
            )
        )

    bounded = _split_oversized_chunks(
        drafts, settings.chunk_target_chars, settings.chunk_overlap_chars
    )
    if len(bounded) > settings.max_chunks_per_document:
        raise ResourceExhaustedError("The document produces too many chunks.")
    return bounded


def normalized_artifact_key(workspace_id: uuid.UUID, version_id: uuid.UUID) -> str:
    return f"workspaces/{workspace_id}/derived/{version_id}/normalized.json"


def normalized_artifact_body(parsed: ParsedDocument, chunks: list[ChunkDraft]) -> bytes:
    payload = {
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "chunker": CHUNKER_NAME,
        "chunker_version": CHUNKER_VERSION,
        "metadata": parsed.metadata,
        "text": parsed.normalized_text,
        "chunks": [
            {
                "ordinal": chunk.ordinal,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "token_count": chunk.token_count,
                "content_hash": chunk.content_hash,
            }
            for chunk in chunks
        ],
    }
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def total_token_count(chunks: list[ChunkDraft]) -> int:
    return sum(chunk.token_count for chunk in chunks)


def _is_supported_media_type(media_type: str, object_key: str) -> bool:
    clean_media_type = media_type.split(";", 1)[0].strip().lower()
    return clean_media_type in SUPPORTED_MEDIA_TYPES or object_key.lower().endswith(
        TEXT_LIKE_EXTENSIONS
    )


def _reject_binary_magic(body: bytes) -> None:
    signatures = {
        b"%PDF": "PDF parsing is deferred beyond Phase 3.",
        b"PK\x03\x04": "Archive parsing is not supported.",
        b"\xd0\xcf\x11\xe0": "Office binary parsing is not supported.",
        b"\x89PNG": "Image parsing is not supported.",
    }
    prefix = body[:8]
    for signature, message in signatures.items():
        if prefix.startswith(signature):
            raise ValidationError(message)
    sample = body[:4096]
    if sample and sample.count(b"\x00") > 0:
        raise ValidationError("The document appears to be binary.")


def _normalize_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    lines = [" ".join(line.split()) for line in text.split("\n")]
    collapsed: list[str] = []
    blank_seen = False
    for line in lines:
        if not line:
            if not blank_seen:
                collapsed.append("")
            blank_seen = True
            continue
        collapsed.append(line)
        blank_seen = False
    return "\n".join(collapsed).strip()


def _blocks_from_text(text: str) -> list[ParsedBlock]:
    blocks: list[ParsedBlock] = []
    cursor = 0
    for raw_block in re.split(r"\n{2,}", text):
        block_text = raw_block.strip()
        if not block_text:
            cursor += len(raw_block) + 2
            continue
        start = text.find(block_text, cursor)
        end = start + len(block_text)
        block_type = "heading" if _is_heading(block_text) else "paragraph"
        blocks.append(
            ParsedBlock(
                block_type=block_type,
                text=block_text,
                start_char=start,
                end_char=end,
                heading=_safe_heading(block_text) if block_type == "heading" else None,
            )
        )
        cursor = end
    return blocks


def _is_heading(text: str) -> bool:
    if text.startswith("#") and len(text) <= 160:
        return True
    return len(text) <= 80 and text.endswith(":") and "\n" not in text


def _safe_heading(text: str) -> str:
    heading = text.lstrip("#").strip().rstrip(":").strip()
    return heading[:MAX_METADATA_VALUE_LENGTH]


def _draft_from_blocks(
    ordinal: int,
    blocks: list[ParsedBlock],
    text: str,
    heading: str | None,
) -> ChunkDraft:
    start = blocks[0].start_char
    end = blocks[-1].end_char
    chunk_text = text.strip()
    token_count = _count_tokens(chunk_text)
    return ChunkDraft(
        ordinal=ordinal,
        block_type="section"
        if any(block.block_type == "heading" for block in blocks)
        else "paragraph",
        heading=heading,
        page_number=None,
        start_char=start,
        end_char=end,
        token_count=token_count,
        content_hash=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
        text=chunk_text,
        safe_metadata={"source_blocks": len(blocks)},
    )


def _split_oversized_chunks(
    drafts: list[ChunkDraft], target_chars: int, overlap_chars: int
) -> list[ChunkDraft]:
    result: list[ChunkDraft] = []
    for draft in drafts:
        if len(draft.text) <= target_chars:
            result.append(_renumber(draft, len(result)))
            continue
        start = 0
        while start < len(draft.text):
            end = min(len(draft.text), start + target_chars)
            if end < len(draft.text):
                split_at = draft.text.rfind(" ", start, end)
                if split_at > start + target_chars // 2:
                    end = split_at
            piece = draft.text[start:end].strip()
            if piece:
                absolute_start = draft.start_char + start
                result.append(
                    ChunkDraft(
                        ordinal=len(result),
                        block_type=draft.block_type,
                        heading=draft.heading,
                        page_number=draft.page_number,
                        start_char=absolute_start,
                        end_char=absolute_start + len(piece),
                        token_count=_count_tokens(piece),
                        content_hash=hashlib.sha256(piece.encode("utf-8")).hexdigest(),
                        text=piece,
                        safe_metadata={**draft.safe_metadata, "split": True},
                    )
                )
            if end >= len(draft.text):
                break
            start = max(end - overlap_chars, start + 1)
    return result


def _renumber(draft: ChunkDraft, ordinal: int) -> ChunkDraft:
    if draft.ordinal == ordinal:
        return draft
    return ChunkDraft(
        ordinal=ordinal,
        block_type=draft.block_type,
        heading=draft.heading,
        page_number=draft.page_number,
        start_char=draft.start_char,
        end_char=draft.end_char,
        token_count=draft.token_count,
        content_hash=draft.content_hash,
        text=draft.text,
        safe_metadata=draft.safe_metadata,
    )


def _count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))
