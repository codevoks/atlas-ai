import { AnswerWithEvidence } from "@/components/evidence/answer-with-evidence";
import type { EvidenceDetail } from "@/components/evidence/types";
import { AskIcon } from "@/components/icons";
import { CopyableId } from "@/components/copyable-id";
import { CopyButton } from "@/components/copy-button";
import { formatAnswerForClipboard } from "@/lib/clipboard-format";
import {
  AtlasApiError,
  answerQuestion,
  getDocumentChunks,
  getDocumentVersions,
  getSources,
  loadWorkspaceContext,
  type AnswerResult,
  type SearchMode,
} from "@/lib/api";

interface AskPageProps {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ q?: string; mode?: string; config?: string }>;
}

export default async function AskPage({ params, searchParams }: AskPageProps) {
  const { workspaceId } = await params;
  const { q, mode, config } = await searchParams;
  await loadWorkspaceContext(workspaceId);

  const query = q ? q.split(/\s+/).join(" ").slice(0, 4000) : "";
  const selectedMode: SearchMode = mode === "semantic" || mode === "lexical" ? mode : "hybrid";
  const selectedConfig = config === "expanded" ? "expanded" : "balanced";

  let answer: AnswerResult | null = null;
  let evidence: EvidenceDetail[] = [];
  let errorMessage = "";
  if (query) {
    try {
      answer = await answerQuestion(
        workspaceId,
        query,
        selectedMode,
        selectedConfig === "expanded" ? "phase8-multi-query-expansion-v1" : "phase5-postgres-fts-rrf-v1",
      );
      evidence = await buildEvidenceDetails(workspaceId, answer);
    } catch (error) {
      errorMessage = error instanceof AtlasApiError ? error.message : "The answer could not be generated.";
    }
  }

  return (
    <div className="app-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Grounded answer</p>
          <h1 className="display-2">Ask with verified citations</h1>
        </div>
      </div>

      <form className="panel" method="get" style={{ padding: 20, marginBottom: 32 }}>
        <div className="field-group">
          <div>
            <label className="sr-only" htmlFor="q">
              Question
            </label>
            <textarea
              defaultValue={query}
              id="q"
              maxLength={4000}
              name="q"
              placeholder="Ask a question that should be answered from evidence…"
              rows={2}
            />
          </div>
          <div className="inline-form">
            <div style={{ width: 150 }}>
              <label className="sr-only" htmlFor="mode">
                Retrieval mode
              </label>
              <select defaultValue={selectedMode} id="mode" name="mode">
                <option value="hybrid">Hybrid</option>
                <option value="lexical">Lexical</option>
                <option value="semantic">Semantic</option>
              </select>
            </div>
            <div style={{ width: 190 }}>
              <label className="sr-only" htmlFor="config">
                Retrieval configuration
              </label>
              <select defaultValue={selectedConfig} id="config" name="config">
                <option value="balanced">Balanced retrieval</option>
                <option value="expanded">Expanded retrieval</option>
              </select>
            </div>
            <button className="button" type="submit">
              Generate answer
            </button>
          </div>
        </div>
      </form>

      {errorMessage ? (
        <p className="alert" role="alert" style={{ marginBottom: 20 }}>
          {errorMessage}
        </p>
      ) : null}

      {!answer ? (
        <div className="empty-state">
          <span className="empty-icon">
            <AskIcon />
          </span>
          <strong>Ask a question grounded in your evidence</strong>
          <p>
            Atlas answers only from retrieved workspace evidence. Every citation marker in the
            answer can be opened to inspect the exact passage it came from.
          </p>
        </div>
      ) : (
        <div className="stack-lg">
          <div className="panel" style={{ padding: 24 }}>
            <div className="result-card-header" style={{ marginBottom: 14 }}>
              <span className="pill">
                {answer.status} · {answer.grounding_status}
              </span>
              <div className="inline-form">
                <span className="faint text-xs">${answer.total_cost_usd.toFixed(2)}</span>
                <CopyButton
                  copiedLabel="Answer copied"
                  label="Copy answer"
                  text={formatAnswerForClipboard({ query, answerText: answer.answer_text })}
                />
              </div>
            </div>
            <AnswerWithEvidence answerText={answer.answer_text} evidence={evidence} />
            <p className="faint text-xs" style={{ marginTop: 18 }}>
              {answer.generation_model}@{answer.generation_model_version} · input{" "}
              {answer.input_tokens} · output {answer.output_tokens} · {answer.latency_ms}ms
            </p>
            <div style={{ marginTop: 6 }}>
              <CopyableId label="run" value={answer.id} />
            </div>
            {answer.warnings.length > 0 ? (
              <p className="alert" style={{ marginTop: 14 }}>
                {answer.warnings.join(", ")}
              </p>
            ) : null}
          </div>

          {evidence.length > 0 ? (
            <div>
              <p className="eyebrow">
                {evidence.length} citation{evidence.length === 1 ? "" : "s"} · click a marker above to
                inspect
              </p>
              <div className="row-list">
                {evidence.map((item) => (
                  <div className="row" key={item.citationId} style={{ alignItems: "flex-start" }}>
                    <span
                      className={`pill dot ${item.status === "verified" || item.status === "resolved" ? "verified" : "danger"}`}
                    >
                      {item.marker}
                    </span>
                    <span className="row-identity">
                      <strong>{item.documentTitle}</strong>
                      <p className="row-quote">&ldquo;{item.quote}&rdquo;</p>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

async function buildEvidenceDetails(
  workspaceId: string,
  answer: AnswerResult,
): Promise<EvidenceDetail[]> {
  if (answer.citations.length === 0) return [];

  const evidenceById = new Map(answer.evidence.map((item) => [item.id, item]));

  const chunkKeys = new Map<string, { documentId: string; documentVersionId: string }>();
  const versionKeys = new Map<string, string>();
  for (const evidenceItem of answer.evidence) {
    chunkKeys.set(`${evidenceItem.document_id}:${evidenceItem.document_version_id}`, {
      documentId: evidenceItem.document_id,
      documentVersionId: evidenceItem.document_version_id,
    });
    versionKeys.set(evidenceItem.document_id, evidenceItem.document_version_id);
  }

  const [chunkGroups, versionGroups, sources] = await Promise.all([
    Promise.all(
      [...chunkKeys.values()].map(async (key) => ({
        key: `${key.documentId}:${key.documentVersionId}`,
        chunks: await getDocumentChunks(workspaceId, key.documentId, key.documentVersionId),
      })),
    ),
    Promise.all(
      [...versionKeys.keys()].map(async (documentId) => ({
        documentId,
        versions: await getDocumentVersions(workspaceId, documentId),
      })),
    ),
    getSources(workspaceId),
  ]);

  const chunkByPairAndId = new Map<string, Map<string, { text: string; ordinal: number }>>();
  for (const group of chunkGroups) {
    chunkByPairAndId.set(group.key, new Map(group.chunks.map((chunk) => [chunk.id, chunk])));
  }
  const versionById = new Map<string, (typeof versionGroups)[number]["versions"][number]>();
  for (const group of versionGroups) {
    for (const version of group.versions) {
      versionById.set(version.id, version);
    }
  }
  const sourceNameById = new Map(sources.map((source) => [source.id, source.name]));

  return answer.citations.map((citation) => {
    const evidenceItem = evidenceById.get(citation.answer_evidence_id);
    const pairKey = evidenceItem
      ? `${evidenceItem.document_id}:${evidenceItem.document_version_id}`
      : "";
    const chunk = chunkByPairAndId.get(pairKey)?.get(citation.chunk_id);
    const version = evidenceItem ? versionById.get(evidenceItem.document_version_id) : undefined;
    const provenance = evidenceItem?.retrieval_provenance ?? {};
    const embeddingModel = typeof provenance.embedding_model === "string" ? provenance.embedding_model : null;
    const embeddingModelVersion =
      typeof provenance.embedding_model_version === "string" ? provenance.embedding_model_version : null;

    return {
      citationId: citation.id,
      marker: citation.marker,
      status: citation.status,
      answerStartChar: citation.answer_start_char,
      answerEndChar: citation.answer_end_char,
      documentTitle: evidenceItem?.document_title ?? "Untitled document",
      sourceName: evidenceItem ? (sourceNameById.get(evidenceItem.source_id) ?? null) : null,
      chunkOrdinal: chunk?.ordinal ?? null,
      chunkText: chunk?.text ?? null,
      highlightStart: citation.evidence_start_char,
      highlightEnd: citation.evidence_end_char,
      quote: citation.quote,
      retrievalStage: evidenceItem?.retrieval_stage ?? null,
      retrievalScore: evidenceItem?.retrieval_score ?? null,
      semanticScore: evidenceItem?.semantic_score ?? null,
      lexicalScore: evidenceItem?.lexical_score ?? null,
      rrfScore: evidenceItem?.rrf_score ?? null,
      rank: evidenceItem?.rank ?? null,
      embeddingModel,
      embeddingModelVersion,
      parserName: version?.parser_name ?? null,
      parserVersion: version?.parser_version ?? null,
      chunkerName: version?.chunker_name ?? null,
      chunkerVersion: version?.chunker_version ?? null,
      chunkId: citation.chunk_id,
      documentId: citation.document_id,
      documentVersionId: citation.document_version_id,
    } satisfies EvidenceDetail;
  });
}
