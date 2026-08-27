import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  addMemberAction,
  removeMemberAction,
  renameWorkspaceAction,
  signOutAction,
  updateMemberAction,
} from "@/app/actions";
import { SubmitButton } from "@/components/submit-button";
import { AtlasApiError, getMe, getMembers, getWorkspace } from "@/lib/api";

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
  try {
    [me, workspace, members] = await Promise.all([
      getMe(),
      getWorkspace(workspaceId),
      getMembers(workspaceId),
    ]);
  } catch (requestError) {
    if (requestError instanceof AtlasApiError && requestError.status === 401) redirect("/sign-in");
    if (requestError instanceof AtlasApiError && requestError.status === 404) notFound();
    throw requestError;
  }

  const canAdminister = workspace.role === "owner" || workspace.role === "admin";

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

