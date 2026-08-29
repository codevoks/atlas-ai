# Phase 3 completion — parsing, normalization, chunking, and metadata

Phase 3 extends the ingestion pipeline from metadata-only publication to deterministic parsed and chunked document versions for a deliberately narrow supported-type set.

## Implemented scope

- Text and Markdown-like uploads are parsed into typed heading/paragraph blocks.
- Parser validation rejects unsupported media types, binary signatures, PDF/archive/OLE/PNG inputs, null bytes, invalid UTF-8, empty extracted text, oversized parser inputs, and excessive chunk output.
- Text normalization canonicalizes Unicode, newlines, and whitespace.
- Normalized derived artifacts are written through the object-store adapter under workspace-prefixed keys with SHA-256 provenance.
- Deterministic structure-aware chunks are persisted with ordinal, span, token count, content hash, text, and safe metadata.
- Document-version responses expose safe parser/chunker provenance, normalized artifact metadata, and aggregate counts.
- A chunk listing endpoint returns authorized chunks for one document version.
- The web UI displays version chunk/provenance metadata and bounded chunk previews.

## Architecture and data flow

The worker remains the only long-running ingestion executor. It claims a durable PostgreSQL job lease, verifies the uploaded object, reads bytes from object storage, parses and normalizes supported text inputs, writes the normalized artifact, creates deterministic chunk drafts, and publishes chunks plus ready document-version state in one transaction.

PostgreSQL remains authoritative for document status, chunk identity, and tenant scoping. Object storage remains authoritative for raw and normalized bytes but never for authorization. No model provider, paid SaaS, cloud storage, or large local model is required for Phase 3.

## Security and failure handling

- Every chunk row is workspace-scoped and tied to an immutable document version.
- Chunk APIs require active workspace membership and document-read permission.
- Cross-tenant chunk access returns a non-disclosing not-found response.
- Extracted content is treated as untrusted data and rendered as text, not HTML.
- Unsupported or unsafe inputs fail the job/version without creating ready chunks.
- Parser and chunker configuration is versioned so later reprocessing can coexist with old output.

## Validation summary

Phase 3 validation covered:

- `pnpm db:migrate`
- `pnpm --filter @atlas/worker lint && pnpm --filter @atlas/worker typecheck && pnpm --filter @atlas/worker test`
- `pnpm --filter @atlas/api lint && pnpm --filter @atlas/api typecheck && pnpm --filter @atlas/api test`
- `pnpm --filter @atlas/web lint && pnpm --filter @atlas/web typecheck`
- `pnpm contracts && pnpm lint && pnpm typecheck && pnpm build && pnpm test`
- Local browser rendering check for the web app with no console errors.
- Zero-cost local API/worker demo: health checks passed; text/Markdown upload finalized; worker parsed, normalized, chunked, and published the version; chunk listing returned tenant-authorized chunks; cross-tenant chunk lookup returned `404`; PDF-like input failed safely as a permanent validation failure.

## Deferred scope

Embeddings, semantic retrieval, lexical retrieval, grounded generation, evaluations, broad office/PDF/OCR parsing, malware scanning, parser sandboxing for third-party converters, and retrieval-tuned chunk-parameter optimization remain deferred to later phases.
