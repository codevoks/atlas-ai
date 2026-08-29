# Phase 3 — Parsing, normalization, chunking, and metadata

## Scope

Implement safe parsers for a deliberately small supported-type set, canonical normalization, deterministic structure-aware chunking, provenance/metadata, derived artifact storage, and ingestion stages through `CHUNKED`. Establish parser/chunker golden fixtures and versioning. Unsupported formats fail clearly.

## Engineering concepts

Parsing trust boundaries, streaming/resource limits, text normalization, document structure, OCR tradeoffs, fixed/token/recursive/semantic chunking, overlap benefits/costs, boundary quality, stable identifiers, deduplication, lineage, deterministic pipelines.

## Architecture changes and modules

Add parser registry/adapters, isolated conversion runner boundary, normalized document schema, chunking strategies, metadata validators, content hashing, pipeline configuration registry, and worker stages `VERIFY/PARSE/NORMALIZE/CHUNK`. Derived artifacts remain versioned and rebuildable.

## Data model changes

Add parser and normalized-artifact provenance to document versions; add `chunks` with workspace/document-version, ordinal, structural/page/span coordinates, text/protected reference, token count, content hash, metadata, parser/chunker/config versions. Uniqueness is deterministic per version/config. Partial chunks never become searchable.

## APIs

Document/version detail exposes safe status, supported format, parser/chunker provenance, counts, and sanitized metadata. Admin-only preview/debug endpoint may show bounded extracted/chunk text with authorization and no unsafe HTML. Reprocess accepts a versioned pipeline configuration.

## Important interfaces

`Parser.can_parse/parse -> ParsedDocument`; `ConversionSandbox.run`; `Normalizer.normalize`; `Chunker.chunk -> ChunkDraft[]`; `TokenCounter`; `MetadataPolicy`; `ArtifactStore`; typed `ParsedBlock` and `SourceSpan`. Interfaces are deterministic and independent from embedding/model providers.

## Security requirements

Magic bytes over extension, allowlisted types, maximum bytes/pages/nesting/expansion/time/memory, parser isolation/no network, safe temporary storage, dependency patching, formula/macro/script stripping, HTML sanitization at display, metadata size/schema limits, no filesystem paths in errors, per-tenant compute quotas.

## Failure scenarios

Corrupt/encrypted/polyglot file; zip/archive bomb; parser hang/crash/OOM; malformed Unicode; huge table/page; normalization changes offsets; repeated headers create noise; chunker nondeterminism; worker restart between stages; derived artifact mismatch. Preserve failure class and allow corrected reprocessing without mutating old provenance.

## Testing strategy

Small golden fixtures for each type; property tests for chunk bounds/order/determinism; snapshot normalized structure (not library internals); malicious/corrupt/resource-limit cases; restart/idempotency tests; metadata fuzzing; quality inspection dataset; performance ceiling checks; full ingestion integration through atomic chunk publication.

## Acceptance criteria

Supported files produce deterministic bounded chunks with reconstructable provenance; unsupported/malicious files fail safely; repeated execution does not duplicate output; offsets/page references remain usable for citations; no incomplete version is searchable; parser/chunker versions enable reproducible reprocessing.

## Engineering review focus and implementation drills

Compare chunking strategies using evidence. Useful implementation drills: simple parser to typed blocks; token-aware chunker; overlap/dedup bug fix; table/header normalization tests; resource-limit wrapper; evaluate chunk boundary quality on a small corpus.

## System-design review focus

Explain parsing isolation, chunk-size/overlap tradeoffs, structure preservation, why semantic chunking is not automatically better, dedup/content hashes, version migrations, OCR pipeline placement, and throughput/cost bottlenecks.

## Explicit deferrals

No embeddings/search/generation. Exact chunk parameters remain an evaluation variable. OCR, broad office/media formats, semantic/contextual chunking, connector-specific parsing, and distributed parser pools require demand/benchmarks.
