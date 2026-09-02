import { CopyableId } from "@/components/copyable-id";
import { SearchIcon } from "@/components/icons";
import {
  AtlasApiError,
  loadWorkspaceContext,
  searchEvidence,
  type RetrievalConfigVersion,
  type SearchMode,
  type SearchResult,
} from "@/lib/api";

interface SearchPageProps {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ q?: string; mode?: string; config?: string }>;
}

export default async function SearchPage({ params, searchParams }: SearchPageProps) {
  const { workspaceId } = await params;
  const { q, mode, config } = await searchParams;
  await loadWorkspaceContext(workspaceId);

  const query = q ? q.split(/\s+/).join(" ").slice(0, 4000) : "";
  const selectedMode: SearchMode = mode === "semantic" || mode === "lexical" ? mode : "hybrid";
  const selectedConfig = selectedRetrievalOption(config);

  let results: SearchResult | null = null;
  let errorMessage = "";
  if (query) {
    try {
      results = await searchEvidence(
        workspaceId,
        query,
        selectedMode,
        selectedRetrievalConfig(config),
      );
    } catch (error) {
      errorMessage = error instanceof AtlasApiError ? error.message : "The search could not be completed.";
    }
  }

  return (
    <div className="app-content wide">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Hybrid retrieval</p>
          <h1 className="display-2">Search grounded evidence</h1>
        </div>
        {results ? <span className="count">{results.items.length} results</span> : null}
      </div>

      <form className="panel" method="get" style={{ padding: 20, marginBottom: 28 }}>
        <div className="inline-form" style={{ flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 320px" }}>
            <label className="sr-only" htmlFor="q">
              Search query
            </label>
            <input
              defaultValue={query}
              id="q"
              maxLength={4000}
              name="q"
              placeholder="Search incidents, policies, customer themes…"
            />
          </div>
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
            Search
          </button>
        </div>
      </form>

      {errorMessage ? (
        <p className="alert" role="alert" style={{ marginBottom: 20 }}>
          {errorMessage}
        </p>
      ) : null}

      {!results ? (
        <div className="empty-state">
          <span className="empty-icon">
            <SearchIcon />
          </span>
          <strong>Search workspace evidence</strong>
          <p>
            Semantic, lexical, and hybrid retrieval all run under the same tenant and
            authorization filters — try a phrase from an uploaded document.
          </p>
        </div>
      ) : results.items.length === 0 ? (
        <div className="empty-state">
          <strong>No authorized evidence matched this query</strong>
          <p>Try a different phrase, or switch retrieval mode.</p>
        </div>
      ) : (
        <div className="stack">
          <p className="muted text-sm">
            {results.mode} retrieval · {displayRetrievalConfig(results.retrieval_config_version)} · trace{" "}
            <span className="mono">{results.trace_id}</span>
          </p>
          {results.items.map((item) => (
            <article className="result-card" key={item.chunk_id}>
              <div className="result-card-header">
                <strong>{item.document_title}</strong>
                <span className="pill">
                  chunk {item.ordinal} · {item.retrieval_stage}
                </span>
              </div>
              <p className="quote">&ldquo;{item.snippet}&rdquo;</p>
              <div className="metric-grid">
                <div className="metric-tile">
                  <span>Score</span>
                  <strong>{item.score.toFixed(3)}</strong>
                </div>
                <div className="metric-tile">
                  <span>Semantic rank</span>
                  <strong>{item.semantic_rank ?? "—"}</strong>
                </div>
                <div className="metric-tile">
                  <span>Lexical rank</span>
                  <strong>{item.lexical_rank ?? "—"}</strong>
                </div>
                <div className="metric-tile">
                  <span>RRF</span>
                  <strong>{item.rrf_score?.toFixed(3) ?? "—"}</strong>
                </div>
              </div>
              <div className="row-meta" style={{ fontSize: "0.75rem" }}>
                <span className="mono">
                  {item.embedding_model
                    ? `${item.embedding_model}@${item.embedding_model_version}`
                    : "PostgreSQL full-text search"}
                </span>
                <CopyableId label="chunk" value={item.chunk_id} />
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function selectedRetrievalOption(value: string | undefined): "balanced" | "expanded" {
  return value === "expanded" ? "expanded" : "balanced";
}

function selectedRetrievalConfig(value: string | undefined): RetrievalConfigVersion {
  return value === "expanded" ? "phase8-multi-query-expansion-v1" : "phase5-postgres-fts-rrf-v1";
}

function displayRetrievalConfig(value: string): string {
  if (value === "phase8-multi-query-expansion-v1") return "Expanded retrieval";
  if (value === "phase5-postgres-fts-rrf-v1") return "Balanced retrieval";
  return "Custom retrieval";
}
