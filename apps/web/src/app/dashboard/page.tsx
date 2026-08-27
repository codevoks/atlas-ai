import Link from "next/link";
import { redirect } from "next/navigation";

import { createWorkspaceAction, signOutAction } from "@/app/actions";
import { SubmitButton } from "@/components/submit-button";
import { AtlasApiError, getMe, getWorkspaces } from "@/lib/api";

interface DashboardPageProps {
  searchParams: Promise<{ error?: string }>;
}

export default async function DashboardPage({ searchParams }: DashboardPageProps) {
  const { error } = await searchParams;
  let me;
  let workspaces;
  try {
    [me, workspaces] = await Promise.all([getMe(), getWorkspaces()]);
  } catch (requestError) {
    if (requestError instanceof AtlasApiError && requestError.status === 401) {
      redirect("/sign-in");
    }
    throw requestError;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">A</span>
          Atlas AI
        </Link>
        <div className="user-menu">
          <span><strong>{me.display_name}</strong><small>{me.email}</small></span>
          <form action={signOutAction}><button className="button ghost" type="submit">Sign out</button></form>
        </div>
      </header>

      <section className="content-grid">
        <div className="main-column">
          <div className="section-heading">
            <div><p className="eyebrow">Your organizations</p><h1>Workspaces</h1></div>
            <span className="count">{workspaces.length}</span>
          </div>
          {error ? <p className="alert" role="alert">{error}</p> : null}
          <div className="workspace-grid">
            {workspaces.map((workspace) => (
              <Link className="workspace-card" href={`/workspaces/${workspace.id}`} key={workspace.id}>
                <span className="workspace-icon">{workspace.name.slice(0, 2).toUpperCase()}</span>
                <span><strong>{workspace.name}</strong><small>{workspace.role} · version {workspace.version}</small></span>
                <span aria-hidden="true">→</span>
              </Link>
            ))}
            {workspaces.length === 0 ? (
              <div className="empty-state"><strong>No workspaces yet</strong><p>Create one to establish its owner and tenant boundary.</p></div>
            ) : null}
          </div>
        </div>
        <aside className="side-panel">
          <p className="eyebrow">Create workspace</p>
          <h2>Start a tenant boundary</h2>
          <p className="muted">The creator becomes the first owner in the same database transaction.</p>
          <form action={createWorkspaceAction} className="stack-form">
            <label htmlFor="workspace-name">Workspace name</label>
            <input id="workspace-name" name="name" minLength={2} maxLength={120} placeholder="Northstar Research" required />
            <SubmitButton>Create workspace</SubmitButton>
          </form>
        </aside>
      </section>
    </main>
  );
}

