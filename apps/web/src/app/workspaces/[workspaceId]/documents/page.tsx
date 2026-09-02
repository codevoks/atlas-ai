import {
  cancelIngestionJobAction,
  createSourceAction,
  deleteDocumentAction,
  retryIngestionJobAction,
  uploadDocumentAction,
} from "@/app/actions";
import { CopyableId } from "@/components/copyable-id";
import { DocumentsIcon, UploadIcon } from "@/components/icons";
import { SubmitButton } from "@/components/submit-button";
import {
  getDocumentChunks,
  getDocumentVersions,
  getDocuments,
  getIngestionJob,
  getSources,
  loadWorkspaceContext,
} from "@/lib/api";

interface DocumentsPageProps {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ error?: string }>;
}

const ACTIVE_JOB_STATES = new Set(["pending", "claimed", "running", "retry_wait"]);

export default async function DocumentsPage({ params, searchParams }: DocumentsPageProps) {
  const { workspaceId } = await params;
  const { error } = await searchParams;
  const { workspace, canUpload } = await loadWorkspaceContext(workspaceId);
  const [documents, sources] = await Promise.all([
    getDocuments(workspaceId),
    getSources(workspaceId),
  ]);

  const jobIds = documents
    .map((doc) => doc.latest_job_id)
    .filter((id): id is string => Boolean(id));
  const jobs = await Promise.all(jobIds.map((id) => getIngestionJob(workspaceId, id)));
  const jobsById = new Map(jobs.map((job) => [job.id, job]));

  const versionPairs = await Promise.all(
    documents.map(async (doc) => ({
      documentId: doc.id,
      versions: await getDocumentVersions(workspaceId, doc.id),
    })),
  );
  const latestVersionByDocument = new Map(versionPairs.map((pair) => [pair.documentId, pair.versions[0]]));
  const chunkPairs = await Promise.all(
    versionPairs
      .map((pair) => ({ documentId: pair.documentId, version: pair.versions[0] }))
      .filter((pair) => (pair.version?.chunk_count ?? 0) > 0)
      .map(async (pair) => ({
        documentId: pair.documentId,
        chunks: await getDocumentChunks(workspaceId, pair.documentId, pair.version.id),
      })),
  );
  const firstChunkByDocument = new Map(chunkPairs.map((pair) => [pair.documentId, pair.chunks[0]]));

  const returnTo = `/workspaces/${workspace.id}/documents`;

  return (
    <div className="app-content wide">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Storage pipeline</p>
          <h1 className="display-2">Documents</h1>
        </div>
        <span className="count">{documents.length}</span>
      </div>
      {error ? (
        <p className="alert" role="alert" style={{ marginBottom: 20 }}>
          {error}
        </p>
      ) : null}

      <div className="content-split">
        <section>
          {documents.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">
                <DocumentsIcon />
              </span>
              <strong>No documents yet</strong>
              <p>Upload a text or Markdown file to see Atlas parse, chunk, and embed it here.</p>
            </div>
          ) : (
            <div className="row-list">
              {documents.map((document) => {
                const job = document.latest_job_id ? jobsById.get(document.latest_job_id) : undefined;
                const version = latestVersionByDocument.get(document.id);
                const chunk = firstChunkByDocument.get(document.id);
                const active = job ? ACTIVE_JOB_STATES.has(job.state) : false;
                return (
                  <article className="row" key={document.id} style={{ alignItems: "flex-start" }}>
                    <span className="avatar" style={{ marginTop: 2 }}>
                      <DocumentsIcon />
                    </span>
                    <span className="row-identity">
                      <strong>{document.title}</strong>
                      <span className="row-meta">
                        <span>version {document.version}</span>
                        <StatusPill state={document.latest_version_status ?? "pending"} />
                        {version ? (
                          <>
                            <span>{version.chunk_count} chunks</span>
                            <span>{version.token_count} tokens</span>
                            {version.parser_name ? (
                              <span className="mono">{version.parser_name}</span>
                            ) : null}
                          </>
                        ) : null}
                      </span>
                      {job && active ? (
                        <span className="status-row" style={{ marginTop: 4 }}>
                          <span className="progress-track">
                            <span className="progress-fill" style={{ width: `${job.progress}%` }} />
                          </span>
                          <span className="faint text-xs">
                            {job.state} · {job.progress}%
                          </span>
                        </span>
                      ) : null}
                      {chunk ? <p className="row-quote">&ldquo;{truncate(chunk.text, 200)}&rdquo;</p> : null}
                      <CopyableId value={document.id} />
                    </span>
                    <span className="row-actions">
                      {job && canUpload && ["failed", "retry_wait"].includes(job.state) ? (
                        <form action={retryIngestionJobAction}>
                          <input name="workspaceId" type="hidden" value={workspace.id} />
                          <input name="jobId" type="hidden" value={job.id} />
                          <input name="redirectTo" type="hidden" value={returnTo} />
                          <SubmitButton>Retry</SubmitButton>
                        </form>
                      ) : null}
                      {job && canUpload && active ? (
                        <form action={cancelIngestionJobAction}>
                          <input name="workspaceId" type="hidden" value={workspace.id} />
                          <input name="jobId" type="hidden" value={job.id} />
                          <input name="redirectTo" type="hidden" value={returnTo} />
                          <SubmitButton destructive>Cancel</SubmitButton>
                        </form>
                      ) : null}
                      {canUpload ? (
                        <form action={deleteDocumentAction}>
                          <input name="workspaceId" type="hidden" value={workspace.id} />
                          <input name="documentId" type="hidden" value={document.id} />
                          <input name="redirectTo" type="hidden" value={returnTo} />
                          <SubmitButton destructive>Delete</SubmitButton>
                        </form>
                      ) : null}
                    </span>
                  </article>
                );
              })}
            </div>
          )}

          <div style={{ marginTop: 40 }}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Source registry</p>
                <h2 className="display-3">Sources</h2>
              </div>
              <span className="count">{sources.length}</span>
            </div>
            {sources.length === 0 ? (
              <p className="muted text-sm">No sources yet — create one to start uploading.</p>
            ) : (
              <div className="row-list">
                {sources.map((source) => (
                  <article className="row" key={source.id}>
                    <span className="avatar alt">S</span>
                    <span className="row-identity">
                      <strong>{source.name}</strong>
                      <span className="row-meta">
                        <span>{source.source_type}</span>
                        <StatusPill state={source.status} />
                      </span>
                      <CopyableId value={source.id} />
                    </span>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>

        {canUpload ? (
          <aside className="panel stack-lg" style={{ padding: 24, alignSelf: "start" }}>
            <div>
              <p className="eyebrow">Direct upload</p>
              <h2 className="display-3">Add a document</h2>
              <p className="muted text-sm" style={{ marginTop: 8 }}>
                Atlas parses UTF-8 text and Markdown, embeds deterministic chunks, and exposes
                hybrid evidence search immediately after ingestion.
              </p>
            </div>
            {sources.length === 0 ? (
              <p className="alert">Create a source before uploading documents.</p>
            ) : (
              <form action={uploadDocumentAction} className="field-group">
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <input name="redirectTo" type="hidden" value={returnTo} />
                <div>
                  <label htmlFor="document-title">Title</label>
                  <input id="document-title" name="title" maxLength={255} placeholder="Security policy" />
                </div>
                <div>
                  <label htmlFor="document-source">Source</label>
                  <select id="document-source" name="sourceId" required>
                    {sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="document-file">File</label>
                  <div className="dropzone">
                    <div className="dropzone-inner">
                      <UploadIcon />
                      <p style={{ marginTop: 8 }}>Drop a .txt or .md file, or click to browse</p>
                    </div>
                    <input
                      accept=".txt,.md,.markdown,text/plain,text/markdown,application/markdown"
                      id="document-file"
                      name="file"
                      required
                      type="file"
                    />
                  </div>
                </div>
                <SubmitButton disabled={sources.length === 0}>Upload and finalize</SubmitButton>
              </form>
            )}

            <div style={{ borderTop: "1px solid var(--line-soft)", paddingTop: 20 }}>
              <p className="eyebrow">Source metadata</p>
              <h2 className="display-3" style={{ fontSize: "1.15rem" }}>
                Create source
              </h2>
              <form action={createSourceAction} className="field-group" style={{ marginTop: 14 }}>
                <input name="workspaceId" type="hidden" value={workspace.id} />
                <input name="redirectTo" type="hidden" value={returnTo} />
                <div>
                  <label htmlFor="source-name">Name</label>
                  <input
                    id="source-name"
                    minLength={2}
                    maxLength={160}
                    name="name"
                    placeholder="Manual uploads"
                    required
                  />
                </div>
                <SubmitButton>Create source</SubmitButton>
              </form>
            </div>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function StatusPill({ state }: { state: string }) {
  const isReady = state === "ready" || state === "active" || state === "succeeded";
  const isFailed = state === "failed" || state === "error";
  const cls = isReady ? "pill verified dot" : isFailed ? "pill danger dot" : "pill dot";
  return <span className={cls}>{state}</span>;
}

function truncate(text: string, length: number): string {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}
