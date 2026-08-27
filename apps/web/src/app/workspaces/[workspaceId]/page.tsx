import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  addMemberAction,
  cancelIngestionJobAction,
  createSourceAction,
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
  getDocumentChunks,
  getDocumentVersions,
  getDocuments,
  getIngestionJob,
  getMe,
  getMembers,
  getSources,
  getWorkspace,
} from "@/lib/api";

interface WorkspacePageProps {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ error?: string }>;
}

export default async function WorkspacePage({ params, searchParams }: WorkspacePageProps) {
  const { workspaceId } = await params;
  const { error } = await searchParams;
  let me;
  let workspace;
  let members;
  let sources;
  let documents;
  try {
    [me, workspace, members, sources, documents] = await Promise.all([
      getMe(),
      getWorkspace(workspaceId),
      getMembers(workspaceId),
      getSources(workspaceId),
      getDocuments(workspaceId),
    ]);
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
        {error ? <p className="alert" role="alert">{error}</p> : null}

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
                Phase 3 parses UTF-8 text/Markdown and publishes deterministic chunks. Retrieval is introduced later.
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
              <p className="muted">For Phase 1, a user must sign in once before an administrator can add them.</p>
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
