import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  addMemberAction,
  cancelIngestionJobAction,
  createSourceAction,
  createResearchRunAction,
  decideResearchApprovalAction,
  deleteDocumentAction,
  removeMemberAction,
  renameWorkspaceAction,
  retryIngestionJobAction,
  signOutAction,
  updateMemberAction,
  uploadDocumentAction,
} from "@/app/actions";
import { SubmitButton } from "@/components/submit-button";
import {
  AtlasApiError,
  answerQuestion,
  getDocumentChunks,
  getDocumentVersions,
  getDocuments,
  getEvaluationRuns,
  getIngestionJob,
  getMe,
  getMembers,
  getOperationsPosture,
  getResearchRuns,
  getSecurityEvents,
  getSecurityPosture,
  getSources,
  getWorkspace,
  searchEvidence,
  type AnswerResult,
  type RetrievalConfigVersion,
  type OperationsPosture,
  type ResearchRun,
  type SecurityEvent,
  type SecurityPosture,
  type SearchMode,
  type SearchResult,
} from "@/lib/api";

interface WorkspacePageProps {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{
    answerConfig?: string;
    answerMode?: string;
    answerQuery?: string;
    error?: string;
    searchConfig?: string;
    semanticQuery?: string;
    searchMode?: string;
  }>;
}

function safeRequestMessage(error: unknown): string {
  if (error instanceof AtlasApiError) {
    return `${error.message}${error.requestId ? ` Request ID: ${error.requestId}` : ""}`;
  }
  return "The request could not be completed.";
}

export default async function WorkspacePage({ params, searchParams }: WorkspacePageProps) {
  const { workspaceId } = await params;
  const { answerConfig, answerMode, answerQuery, error, searchConfig, semanticQuery, searchMode } =
    await searchParams;
  let me;
  let workspace;
  let members;
  let sources;
  let documents;
  let evaluationRuns;
  let researchRuns;
  let securityPosture: SecurityPosture | null = null;
  let securityEvents: SecurityEvent[] = [];
  let operationsPosture: OperationsPosture | null = null;
  let pageError = error ?? "";
  try {
    [me, workspace, members, sources, documents, evaluationRuns, researchRuns] = await Promise.all([
      getMe(),
      getWorkspace(workspaceId),
      getMembers(workspaceId),
      getSources(workspaceId),
      getDocuments(workspaceId),
      getEvaluationRuns(workspaceId),
      getResearchRuns(workspaceId),
    ]);
    if (workspace.role === "owner" || workspace.role === "admin") {
      [securityPosture, securityEvents, operationsPosture] = await Promise.all([
        getSecurityPosture(workspaceId),
        getSecurityEvents(workspaceId),
        getOperationsPosture(workspaceId),
      ]);
    }
  } catch (requestError) {
    if (requestError instanceof AtlasApiError && requestError.status === 401) redirect("/sign-in");
    if (requestError instanceof AtlasApiError && requestError.status === 404) notFound();
    throw requestError;
  }

  const canAdminister = workspace.role === "owner" || workspace.role === "admin";
  const canUpload = workspace.role === "owner" || workspace.role === "admin" || workspace.role === "member";
  const jobIds = documents
    .map((document) => document.latest_job_id)
    .filter((jobId): jobId is string => Boolean(jobId));
  const jobs = await Promise.all(jobIds.map((jobId) => getIngestionJob(workspaceId, jobId)));
  const jobsById = new Map(jobs.map((job) => [job.id, job]));
  const versionPairs = await Promise.all(
    documents.map(async (document) => ({
      documentId: document.id,
      versions: await getDocumentVersions(workspaceId, document.id),
    })),
  );
  const latestVersionByDocument = new Map(
    versionPairs.map((pair) => [pair.documentId, pair.versions[0]]),
  );
  const previewPairs = await Promise.all(
    versionPairs
      .map((pair) => ({ documentId: pair.documentId, version: pair.versions[0] }))
      .filter((pair) => pair.version?.chunk_count > 0)
      .map(async (pair) => ({
        documentId: pair.documentId,
        chunks: await getDocumentChunks(workspaceId, pair.documentId, pair.version.id),
      })),
  );
  const firstChunkByDocument = new Map(
    previewPairs.map((pair) => [pair.documentId, pair.chunks[0]]),
  );
  const cleanSemanticQuery = semanticQuery ? semanticQuery.split(/\s+/).join(" ").slice(0, 4000) : "";
  const selectedSearchMode: SearchMode =
    searchMode === "semantic" || searchMode === "lexical" || searchMode === "hybrid"
      ? searchMode
      : "hybrid";
  let semanticResults: SearchResult | null = null;
  if (cleanSemanticQuery) {
    try {
      semanticResults = await searchEvidence(
        workspaceId,
        cleanSemanticQuery,
        selectedSearchMode,
        selectedRetrievalConfig(searchConfig),
      );
    } catch (requestError) {
      pageError = safeRequestMessage(requestError);
    }
  }
  const cleanAnswerQuery = answerQuery ? answerQuery.split(/\s+/).join(" ").slice(0, 4000) : "";
  const selectedAnswerMode: SearchMode =
    answerMode === "semantic" || answerMode === "lexical" || answerMode === "hybrid"
      ? answerMode
      : "hybrid";
  let answerResult: AnswerResult | null = null;
  if (cleanAnswerQuery) {
    try {
      answerResult = await answerQuestion(
        workspaceId,
        cleanAnswerQuery,
        selectedAnswerMode,
        selectedRetrievalConfig(answerConfig),
      );
    } catch (requestError) {
      pageError = safeRequestMessage(requestError);
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <Link className="brand" href="/dashboard"><span className="brand-mark">A</span>Atlas AI</Link>
        <div className="user-menu"><span><strong>{me.display_name}</strong><small>{me.email}</small></span><form action={signOutAction}><button className="button ghost" type="submit">Sign out</button></form></div>
      </header>
      <section className="workspace-page">
        <Link className="back-link" href="/dashboard">← All workspaces</Link>
        <div className="workspace-title-row">
          <div><p className="eyebrow">Workspace · {workspace.role}</p><h1>{workspace.name}</h1><p className="muted mono">{workspace.id}</p></div>
          {canAdminister ? (
            <form action={renameWorkspaceAction} className="inline-form">
              <input name="workspaceId" type="hidden" value={workspace.id} />
              <input name="version" type="hidden" value={workspace.version} />
              <label className="sr-only" htmlFor="rename-workspace">New workspace name</label>
              <input id="rename-workspace" name="name" minLength={2} maxLength={120} defaultValue={workspace.name} required />
              <SubmitButton>Rename</SubmitButton>
            </form>
          ) : null}
        </div>
        {pageError ? <p className="alert" role="alert">{pageError}</p> : null}

        {securityPosture ? (
          <section className="search-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Security assurance</p>
                <h2>Guardrail posture</h2>
              </div>
              <span className="count">{securityEvents.length}</span>
            </div>
            <div className="result-card">
              <div className="result-card-header">
                <strong>Active protection policy</strong>
                <span>{securityPosture.zero_cost ? "$0.00 local path" : "external cost enabled"}</span>
              </div>
              <div className="metric-grid">
                <div><span>Paid services</span><strong>{securityPosture.paid_services_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Policy</span><strong>{displayPolicyName(securityPosture.policy_config_version)}</strong></div>
                <div><span>Fail-closed</span><strong>{securityPosture.fail_closed_controls.length}</strong></div>
                <div><span>Deterministic</span><strong>{securityPosture.deterministic_controls.length}</strong></div>
              </div>
              <p className="muted">
                Controls: {securityPosture.deterministic_controls.slice(0, 6).map(displayControlName).join(", ")}
              </p>
            </div>
            <div className="results-list">
              {securityEvents.length ? (
                securityEvents.map((event) => (
                  <article className="result-card compact" key={event.id}>
                    <div className="result-card-header">
                      <strong>{event.event_type}</strong>
                      <span>{event.outcome} · {event.severity}</span>
                    </div>
                    <p className="muted mono">control {displayControlName(event.control_version)} · request {event.request_id}</p>
                    <p className="muted">{formatFindings(event.safe_metadata)}</p>
                  </article>
                ))
              ) : (
                <p className="muted">No security events recorded yet.</p>
              )}
            </div>
          </section>
        ) : null}

        {operationsPosture ? (
          <section className="search-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Operations</p>
                <h2>Production readiness posture</h2>
              </div>
              <span className="count">{operationsPosture.routes.length}</span>
            </div>
            <div className="result-card">
              <div className="result-card-header">
                <strong>Operational readiness</strong>
                <span>{operationsPosture.zero_cost ? "$0.00 local validation" : "external cost enabled"}</span>
              </div>
              <div className="metric-grid">
                <div><span>Telemetry</span><strong>{operationsPosture.telemetry_exporter}</strong></div>
                <div><span>Content capture</span><strong>{operationsPosture.telemetry_content_capture_enabled ? "enabled" : "disabled"}</strong></div>
                <div><span>Traces</span><strong>{operationsPosture.retained_trace_count}</strong></div>
                <div><span>Paid services</span><strong>{operationsPosture.paid_services_enabled ? "enabled" : "disabled"}</strong></div>
              </div>
              <p className="muted">
                SLO status: {formatSloStatus(operationsPosture.slo_summary)} · DB{" "}
                {String(operationsPosture.dependency_status.database ?? "unknown")}
              </p>
              <p className="muted">
                Search backend: {displaySearchProjection(operationsPosture.capacity_envelope.search_projection)}
              </p>
            </div>
            <div className="results-list">
              {operationsPosture.routes.slice(0, 6).map((metric) => (
                <article className="result-card compact" key={`${metric.method}-${metric.route}`}>
                  <div className="result-card-header">
                    <strong>{metric.method} {metric.route}</strong>
                    <span>p95 {metric.p95_ms.toFixed(1)}ms</span>
                  </div>
                  <p className="muted">
                    count {metric.count} · errors {metric.error_count} · max{" "}
                    {metric.max_ms.toFixed(1)}ms
                  </p>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section className="search-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Bounded research</p>
              <h2>Run a cited research workflow</h2>
            </div>
            <span className="count">{researchRuns.length}</span>
          </div>
          <form action={createResearchRunAction} className="search-form">
            <input name="workspaceId" type="hidden" value={workspace.id} />
            <label className="sr-only" htmlFor="research-purpose">Research purpose</label>
            <input
              id="research-purpose"
              name="purpose"
              minLength={2}
              maxLength={160}
              defaultValue="Access policy review"
              placeholder="Research purpose"
              required
            />
            <label className="sr-only" htmlFor="research-question">Research question</label>
            <input
              id="research-question"
              name="question"
              maxLength={4000}
              defaultValue="How should finance approval be handled for SAML access before payment?"
              placeholder="Research question"
              required
            />
            <button className="button primary" type="submit">Start bounded research</button>
          </form>
          {researchRuns.length > 0 ? (
            <div className="search-results">
              {researchRuns.map((run) => (
                <ResearchRunCard key={run.id} run={run} workspaceId={workspace.id} />
              ))}
            </div>
          ) : (
            <p className="muted">
              Start a run to plan bounded questions, retrieve Atlas evidence, pause for approval,
              and synthesize a cited report.
            </p>
          )}
        </section>

        <section className="search-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Grounded answer</p>
              <h2>Ask with verified citations</h2>
            </div>
            {answerResult ? <span className="count">{answerResult.citations.length}</span> : null}
          </div>
          <form className="search-form" method="get">
            <label className="sr-only" htmlFor="answer-query">Answer query</label>
            <input
              id="answer-query"
              name="answerQuery"
              maxLength={4000}
              defaultValue={cleanAnswerQuery}
              placeholder="Ask a question that should be answered from evidence..."
            />
            <label className="sr-only" htmlFor="answer-mode">Answer retrieval mode</label>
            <select id="answer-mode" name="answerMode" defaultValue={selectedAnswerMode}>
              <option value="hybrid">Hybrid</option>
              <option value="lexical">Lexical</option>
              <option value="semantic">Semantic</option>
            </select>
            <label className="sr-only" htmlFor="answer-config">Answer retrieval config</label>
            <select
              id="answer-config"
              name="answerConfig"
              defaultValue={selectedRetrievalOption(answerConfig)}
            >
              <option value="balanced">Balanced retrieval</option>
              <option value="expanded">
                Expanded retrieval
              </option>
            </select>
            <button className="button primary" type="submit">Generate answer</button>
          </form>
          {answerResult ? (
            <div className="search-results">
              <p className="muted">
                {answerResult.status} · {answerResult.grounding_status} ·{" "}
                {answerResult.generation_model}@{answerResult.generation_model_version} · $
                {answerResult.total_cost_usd.toFixed(2)}
              </p>
              <article className="search-result">
                <div>
                  <strong>Answer</strong>
                  <small>
                    input {answerResult.input_tokens} · output {answerResult.output_tokens} ·{" "}
                    {answerResult.latency_ms}ms
                  </small>
                </div>
                <p>{answerResult.answer_text}</p>
                <small className="mono">
                  run {answerResult.id} · retrieval{" "}
                  {displayRetrievalConfig(answerResult.retrieval_config_version)} · prompt{" "}
                  {displayPromptVersion(answerResult.prompt_version)}
                </small>
              </article>
              {answerResult.citations.map((citation) => (
                <article className="search-result" key={citation.id}>
                  <div>
                    <strong>
                      Citation {citation.marker} · {citation.status}
                    </strong>
                    <small>evidence rank {citation.evidence_rank}</small>
                  </div>
                  <p>“{citation.quote}”</p>
                  <small className="mono">
                    chunk {citation.chunk_id} · span {citation.evidence_start_char}–
                    {citation.evidence_end_char}
                  </small>
                </article>
              ))}
              {answerResult.warnings.length > 0 ? (
                <p className="alert">Warnings: {answerResult.warnings.join(", ")}</p>
              ) : null}
            </div>
          ) : (
            <p className="muted">
              Ask a question and Atlas will answer only from retrieved workspace evidence.
            </p>
          )}
        </section>

        <section className="search-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Evaluation</p>
              <h2>Latest regression runs</h2>
            </div>
            <span className="count">{evaluationRuns.length}</span>
          </div>
          {evaluationRuns.length > 0 ? (
            <div className="search-results">
              {evaluationRuns.map((run) => (
                <article className="search-result" key={run.id}>
                  <div>
                    <strong>{run.run_name}</strong>
                    <small>
                      {run.status} · {run.results.length} cases · $
                      {run.total_cost_usd.toFixed(2)}
                    </small>
                  </div>
                  <div className="metric-grid">
                    <span>
                      Recall@K
                      <strong>{formatMetric(nestedMetric(run.aggregate_metrics, "retrieval", "recall_at_k"))}</strong>
                    </span>
                    <span>
                      MRR
                      <strong>{formatMetric(nestedMetric(run.aggregate_metrics, "retrieval", "mrr"))}</strong>
                    </span>
                    <span>
                      Citation verified
                      <strong>{formatMetric(nestedMetric(run.aggregate_metrics, "answer", "citation_verified_rate"))}</strong>
                    </span>
                  </div>
                  <small className="mono">
                    run {run.id} · dataset {run.dataset_version_id} · code {run.code_revision} ·{" "}
                    {run.latency_ms}ms
                  </small>
                  {run.results.map((result, index) => (
                    <small className="mono" key={result.id}>
                      case {index + 1}: {result.status} · retrieved{" "}
                      {result.retrieved_chunk_ids.length} chunks · answer{" "}
                      {result.answer_run_id ?? "none"}
                    </small>
                  ))}
                  {Object.keys(run.failure_summary).length > 0 ? (
                    <p className="alert">Failures: {JSON.stringify(run.failure_summary)}</p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <p className="muted">
              No evaluation runs yet. Use the evaluation API to run regression checks against approved datasets.
            </p>
          )}
        </section>

        <section className="search-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Hybrid retrieval</p>
              <h2>Search grounded evidence</h2>
            </div>
            {semanticResults ? <span className="count">{semanticResults.items.length}</span> : null}
          </div>
          <form className="search-form" method="get">
            <label className="sr-only" htmlFor="semantic-query">Semantic query</label>
            <input
              id="semantic-query"
              name="semanticQuery"
              maxLength={4000}
              defaultValue={cleanSemanticQuery}
              placeholder="Search incidents, policies, customer themes..."
            />
            <label className="sr-only" htmlFor="search-mode">Search mode</label>
            <select id="search-mode" name="searchMode" defaultValue={selectedSearchMode}>
              <option value="hybrid">Hybrid</option>
              <option value="lexical">Lexical</option>
              <option value="semantic">Semantic</option>
            </select>
            <label className="sr-only" htmlFor="search-config">Search retrieval config</label>
            <select
              id="search-config"
              name="searchConfig"
              defaultValue={selectedRetrievalOption(searchConfig)}
            >
              <option value="balanced">Balanced retrieval</option>
              <option value="expanded">
                Expanded retrieval
              </option>
            </select>
            <button className="button primary" type="submit">Search evidence</button>
          </form>
          {semanticResults ? (
            <div className="search-results">
              <p className="muted">
                {semanticResults.mode} retrieval · {displayRetrievalConfig(semanticResults.retrieval_config_version)} · trace{" "}
                {semanticResults.trace_id}
              </p>
              {semanticResults.debug?.retrieval_plan ? (
                <article className="search-result">
                  <div>
                    <strong>Retrieval plan</strong>
                    <small>{displayRetrievalConfig(semanticResults.retrieval_config_version)}</small>
                  </div>
                  <small className="mono">
                    {retrievalPlanSummary(semanticResults.debug.retrieval_plan)}
                  </small>
                </article>
              ) : null}
              {semanticResults.items.map((item) => (
                <article className="search-result" key={item.chunk_id}>
                  <div>
                    <strong>{item.document_title}</strong>
                    <small>
                      chunk {item.ordinal} · {item.retrieval_stage} · score{" "}
                      {item.score.toFixed(3)}
                    </small>
                  </div>
                  <p>“{item.snippet}”</p>
                  <small>
                    semantic rank {item.semantic_rank ?? "—"} · lexical rank{" "}
                    {item.lexical_rank ?? "—"} · RRF {item.rrf_score?.toFixed(3) ?? "—"}
                  </small>
                  <small className="mono">
                    variants {matchedVariants(item.retrieval_provenance).join(" | ") || "original query"}
                  </small>
                  <small className="mono">
                    {item.embedding_model
                      ? `${item.embedding_model}@${item.embedding_model_version} · set ${item.embedding_set_id}`
                      : "PostgreSQL full-text search"}
                  </small>
                </article>
              ))}
              {semanticResults.items.length === 0 ? (
                <div className="empty-state">
                  <p>No authorized evidence matched this query yet.</p>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="muted">
              Upload and ingest text or Markdown, then search embedded chunks with semantic, lexical, or hybrid retrieval.
            </p>
          )}
        </section>

        <div className="members-layout">
          <section>
            <div className="section-heading">
              <div><p className="eyebrow">Storage pipeline</p><h2>Documents</h2></div>
              <span className="count">{documents.length}</span>
            </div>
            {documents.length === 0 ? (
              <div className="empty-state">
                <p>No documents have been finalized in this workspace yet.</p>
              </div>
            ) : (
              <div className="member-list">
                {documents.map((document) => {
                  const job = document.latest_job_id ? jobsById.get(document.latest_job_id) : undefined;
                  const latestVersion = latestVersionByDocument.get(document.id);
                  const firstChunk = firstChunkByDocument.get(document.id);
                  return (
                    <article className="member-row" key={document.id}>
                      <span className="avatar">D</span>
                      <span className="member-identity">
                        <strong>{document.title}</strong>
                        <small>
                          version {document.version} · {document.latest_version_status ?? "pending"}
                        </small>
                        {latestVersion ? (
                          <small>
                            {latestVersion.chunk_count} chunks · {latestVersion.token_count} tokens ·{" "}
                            {latestVersion.parser_name ?? "parser pending"}
                          </small>
                        ) : null}
                        {firstChunk ? (
                          <small className="chunk-preview">
                            “{firstChunk.text.slice(0, 180)}{firstChunk.text.length > 180 ? "…" : ""}”
                          </small>
                        ) : null}
                        <small className="mono">{document.id}</small>
                      </span>
                      {job ? (
                        <span className="role-badge">{job.state} · {job.progress}%</span>
                      ) : null}
                      {job && canAdminister && !["succeeded", "cancelled", "failed"].includes(job.state) ? (
                        <form action={cancelIngestionJobAction}>
                          <input name="workspaceId" type="hidden" value={workspace.id} />
                          <input name="jobId" type="hidden" value={job.id} />
                          <SubmitButton destructive>Cancel</SubmitButton>
                        </form>
                      ) : null}
                      {job && canAdminister && ["failed", "retry_wait"].includes(job.state) ? (
                        <form action={retryIngestionJobAction}>
                          <input name="workspaceId" type="hidden" value={workspace.id} />
                          <input name="jobId" type="hidden" value={job.id} />
                          <SubmitButton>Retry</SubmitButton>
                        </form>
                      ) : null}
                      {canUpload ? (
                        <form action={deleteDocumentAction}>
                          <input name="workspaceId" type="hidden" value={workspace.id} />
                          <input name="documentId" type="hidden" value={document.id} />
                          <SubmitButton destructive>Delete</SubmitButton>
                        </form>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
          {canUpload ? (
            <aside className="side-panel">
              <p className="eyebrow">Direct upload</p><h2>Add a document</h2>
              <p className="muted">
                Atlas parses UTF-8 text/Markdown, embeds deterministic chunks, and exposes hybrid evidence search.
              </p>
              {sources.length === 0 ? (
                <p className="alert">Create a source before uploading documents.</p>
              ) : null}
              <form action={uploadDocumentAction} className="stack-form">
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <label htmlFor="document-title">Title</label>
                <input id="document-title" name="title" maxLength={255} placeholder="Security policy" />
                <label htmlFor="document-source">Source</label>
                <select id="document-source" name="sourceId" required>
                  {sources.map((source) => (
                    <option key={source.id} value={source.id}>{source.name}</option>
                  ))}
                </select>
                <label htmlFor="document-file">File</label>
                <input
                  id="document-file"
                  name="file"
                  type="file"
                  accept=".txt,.md,.markdown,text/plain,text/markdown,application/markdown"
                  required
                />
                <SubmitButton disabled={sources.length === 0}>Upload and finalize</SubmitButton>
              </form>
            </aside>
          ) : null}
        </div>

        <div className="members-layout">
          <section>
            <div className="section-heading">
              <div><p className="eyebrow">Source registry</p><h2>Sources</h2></div>
              <span className="count">{sources.length}</span>
            </div>
            <div className="member-list">
              {sources.map((source) => (
                <article className="member-row" key={source.id}>
                  <span className="avatar">S</span>
                  <span className="member-identity">
                    <strong>{source.name}</strong>
                    <small>{source.source_type} · {source.status}</small>
                    <small className="mono">{source.id}</small>
                  </span>
                </article>
              ))}
              {sources.length === 0 ? <p className="muted">No sources yet.</p> : null}
            </div>
          </section>
          {canUpload ? (
            <aside className="side-panel">
              <p className="eyebrow">Source metadata</p><h2>Create source</h2>
              <form action={createSourceAction} className="stack-form">
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <label htmlFor="source-name">Name</label>
                <input id="source-name" name="name" minLength={2} maxLength={160} placeholder="Manual uploads" required />
                <SubmitButton>Create source</SubmitButton>
              </form>
            </aside>
          ) : null}
        </div>

        <div className="members-layout">
          <section>
            <div className="section-heading"><div><p className="eyebrow">Access control</p><h2>Members</h2></div><span className="count">{members.length}</span></div>
            <div className="member-list">
              {members.map((member) => (
                <article className="member-row" key={member.user_id}>
                  <span className="avatar">{member.display_name.split(" ").map((part) => part[0]).join("").slice(0, 2)}</span>
                  <span className="member-identity"><strong>{member.display_name}</strong><small>{member.email}</small></span>
                  {canAdminister ? (
                    <form action={updateMemberAction} className="member-actions">
                      <input name="workspaceId" type="hidden" value={workspace.id} />
                      <input name="userId" type="hidden" value={member.user_id} />
                      <input name="version" type="hidden" value={member.version} />
                      <label className="sr-only" htmlFor={`role-${member.user_id}`}>Role</label>
                      <select id={`role-${member.user_id}`} name="role" defaultValue={member.role}>
                        <option value="viewer">viewer</option><option value="member">member</option><option value="admin">admin</option><option value="owner">owner</option>
                      </select>
                      <SubmitButton>Save</SubmitButton>
                    </form>
                  ) : <span className="role-badge">{member.role}</span>}
                  {canAdminister ? (
                    <form action={removeMemberAction}>
                      <input name="workspaceId" type="hidden" value={workspace.id} /><input name="userId" type="hidden" value={member.user_id} />
                      <SubmitButton destructive>Remove</SubmitButton>
                    </form>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
          {canAdminister ? (
            <aside className="side-panel">
              <p className="eyebrow">Grant access</p><h2>Add an existing user</h2>
              <p className="muted">A user must sign in once before an administrator can add them.</p>
              <form action={addMemberAction} className="stack-form">
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <label htmlFor="member-email">Email</label><input id="member-email" name="email" type="email" placeholder="bob@atlas.local" required />
                <label htmlFor="member-role">Role</label><select id="member-role" name="role" defaultValue="member"><option value="viewer">viewer</option><option value="member">member</option><option value="admin">admin</option><option value="owner">owner</option></select>
                <SubmitButton>Add member</SubmitButton>
              </form>
            </aside>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function ResearchRunCard({ run, workspaceId }: { run: ResearchRun; workspaceId: string }) {
  const pendingApproval = run.approvals.find((approval) => approval.status === "pending");
  const latestCheckpoint = run.checkpoints.at(-1);
  return (
    <article className="search-result">
      <div>
        <strong>{run.purpose}</strong>
        <small>
          {run.status} · {run.steps.length} steps · {run.tool_invocations.length} tools · $
          {run.total_cost_usd.toFixed(2)}
        </small>
      </div>
      <p>{run.question}</p>
      <div className="metric-grid">
        <span>
          Steps
          <strong>{String(run.usage.steps ?? 0)}/{String(run.budget.max_steps ?? "—")}</strong>
        </span>
        <span>
          Tools
          <strong>
            {String(run.usage.tool_calls ?? 0)}/{String(run.budget.max_tool_calls ?? "—")}
          </strong>
        </span>
        <span>
          Cost
          <strong>${Number(run.usage.cost_usd ?? 0).toFixed(2)}</strong>
        </span>
      </div>
      <small className="mono">
        run {run.id} · workflow {displayResearchConfig(run.config_version)} · engine{" "}
        {displayResearchConfig(run.graph_version)} · version {run.version}
      </small>
      {latestCheckpoint ? (
        <small className="mono">
          checkpoint {latestCheckpoint.schema_version} · next{" "}
          {String(latestCheckpoint.state_summary.next_node ?? "none")} · evidence{" "}
          {String(latestCheckpoint.state_summary.evidence_count ?? 0)}
        </small>
      ) : null}
      {run.tool_invocations.map((tool) => (
        <small className="mono" key={tool.id}>
          tool {tool.tool_name} · {tool.status} · key {tool.idempotency_key}
        </small>
      ))}
      {pendingApproval ? (
        <div className="approval-box">
          <strong>Approval required: {pendingApproval.approval_type}</strong>
          <p>{pendingApproval.reason}</p>
          <small className="mono">
            approval {pendingApproval.id} · version {pendingApproval.version}
          </small>
          <div className="button-row">
            <form action={decideResearchApprovalAction}>
              <input name="workspaceId" type="hidden" value={workspaceId} />
              <input name="runId" type="hidden" value={run.id} />
              <input name="approvalId" type="hidden" value={pendingApproval.id} />
              <input name="version" type="hidden" value={pendingApproval.version} />
              <input name="approved" type="hidden" value="true" />
              <SubmitButton>Approve synthesis</SubmitButton>
            </form>
            <form action={decideResearchApprovalAction}>
              <input name="workspaceId" type="hidden" value={workspaceId} />
              <input name="runId" type="hidden" value={run.id} />
              <input name="approvalId" type="hidden" value={pendingApproval.id} />
              <input name="version" type="hidden" value={pendingApproval.version} />
              <input name="approved" type="hidden" value="false" />
              <SubmitButton destructive>Deny</SubmitButton>
            </form>
          </div>
        </div>
      ) : null}
      {run.report_text ? (
        <div className="report-preview">
          <strong>Report</strong>
          <pre>{run.report_text}</pre>
        </div>
      ) : null}
      {run.evidence.slice(0, 3).map((item, index) => (
        <small className="mono" key={`${run.id}-${String(item.chunk_id)}-${index}`}>
          evidence {index + 1}: {String(item.document_title ?? "Untitled")} · chunk{" "}
          {String(item.chunk_id ?? "unknown")}
        </small>
      ))}
      {run.warnings.length > 0 ? <p className="alert">Warnings: {run.warnings.join(", ")}</p> : null}
    </article>
  );
}

function nestedMetric(
  metrics: Record<string, unknown>,
  category: string,
  name: string,
): number | null {
  const group = metrics[category];
  if (!group || typeof group !== "object" || Array.isArray(group)) return null;
  const value = (group as Record<string, unknown>)[name];
  return typeof value === "number" ? value : null;
}

function formatMetric(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}

function selectedRetrievalConfig(value: string | undefined): RetrievalConfigVersion {
  return value === "expanded" || value === "phase8-multi-query-expansion-v1"
    ? "phase8-multi-query-expansion-v1"
    : "phase5-postgres-fts-rrf-v1";
}

function selectedRetrievalOption(value: string | undefined): "balanced" | "expanded" {
  return value === "expanded" || value === "phase8-multi-query-expansion-v1"
    ? "expanded"
    : "balanced";
}

function displayRetrievalConfig(value: string): string {
  if (value === "phase8-multi-query-expansion-v1") return "Expanded retrieval";
  if (value === "phase5-postgres-fts-rrf-v1") return "Balanced retrieval";
  return "Custom retrieval";
}

function displayPromptVersion(value: string): string {
  if (value === "phase6-grounded-answer-v1") return "Grounded answer";
  return "Custom prompt";
}

function displayPolicyName(value: string): string {
  if (value === "phase10-default-policy-v1") return "Default workspace policy";
  return "Custom workspace policy";
}

function displayControlName(value: string): string {
  return value
    .replace(/^phase\d+-/i, "")
    .replace(/-v\d+$/i, "")
    .replaceAll("_", " ")
    .replaceAll("-", " ");
}

function displaySearchProjection(value: unknown): string {
  if (value === "postgresql_authoritative_no_opensearch_trigger") return "PostgreSQL authoritative search";
  return typeof value === "string" && value ? value.replaceAll("_", " ") : "unknown";
}

function displayResearchConfig(value: string): string {
  if (value === "phase9-bounded-research-v1") return "Bounded research";
  if (value === "phase9-deterministic-local-graph-v1") return "Deterministic local graph";
  return "Custom research workflow";
}

function retrievalPlanSummary(plan: unknown): string {
  if (!plan || typeof plan !== "object" || Array.isArray(plan)) return "No plan details";
  const record = plan as Record<string, unknown>;
  const variants = Array.isArray(record.variants) ? record.variants : [];
  const rendered = variants
    .map((variant) => {
      if (!variant || typeof variant !== "object" || Array.isArray(variant)) return null;
      const item = variant as Record<string, unknown>;
      return `${String(item.rank ?? "?")}: ${String(item.text ?? "")}`;
    })
    .filter((item): item is string => Boolean(item));
  return rendered.join(" · ") || "No query variants";
}

function matchedVariants(provenance: Record<string, unknown>): string[] {
  const value = provenance.matched_query_variants;
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function formatFindings(metadata: Record<string, unknown>): string {
  const findings = metadata.findings;
  if (!Array.isArray(findings) || findings.length === 0) return "No finding details.";
  return findings
    .slice(0, 3)
    .map((finding) => {
      if (!finding || typeof finding !== "object" || Array.isArray(finding)) return null;
      const item = finding as Record<string, unknown>;
      return `${String(item.code ?? "finding")} (${String(item.action ?? "detected")})`;
    })
    .filter((item): item is string => Boolean(item))
    .join(", ");
}

function formatSloStatus(summary: Record<string, unknown>): string {
  const value = summary.within_objective;
  if (!value || typeof value !== "object" || Array.isArray(value)) return "unknown";
  const statuses = value as Record<string, unknown>;
  const failing = Object.entries(statuses)
    .filter(([, passed]) => passed === false)
    .map(([name]) => name);
  return failing.length === 0 ? "within objectives" : `needs attention: ${failing.join(", ")}`;
}
