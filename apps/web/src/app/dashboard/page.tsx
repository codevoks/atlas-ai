import Link from "next/link";
import { redirect } from "next/navigation";

import { createWorkspaceAction, signOutAction } from "@/app/actions";
import { CopyableId } from "@/components/copyable-id";
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
    <main>
      <header className="nav shell">
        <Link className="brand" href="/dashboard">
          <span className="brand-mark">A</span>
          Atlas
        </Link>
        <div className="inline-form">
          <span className="text-sm muted">{me.display_name}</span>
          <form action={signOutAction}>
            <button className="button ghost" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </header>

      <section className="shell content-split" style={{ paddingBlock: 56 }}>
        <div>
          <div className="section-heading">
            <div>
              <p className="eyebrow">Your organizations</p>
              <h1 className="display-2">Workspaces</h1>
            </div>
            <span className="count">{workspaces.length}</span>
          </div>
          {error ? (
            <p className="alert" role="alert" style={{ marginBottom: 16 }}>
              {error}
            </p>
          ) : null}
          <div className="row-list">
            {workspaces.map((workspace) => (
              <Link
                className="row card interactive"
                href={`/workspaces/${workspace.id}`}
                key={workspace.id}
                style={{ textDecoration: "none" }}
              >
                <span className="avatar">{workspace.name.slice(0, 2).toUpperCase()}</span>
                <span className="row-identity">
                  <strong>{workspace.name}</strong>
                  <span className="row-meta">
                    <span>{workspace.role}</span>
                    <span>version {workspace.version}</span>
                  </span>
                </span>
                <span aria-hidden="true" className="faint">
                  →
                </span>
              </Link>
            ))}
            {workspaces.length === 0 ? (
              <div className="empty-state">
                <strong>No workspaces yet</strong>
                <p>Create one to establish its owner and tenant boundary.</p>
              </div>
            ) : null}
          </div>
        </div>
        <aside className="panel" style={{ padding: 24, alignSelf: "start" }}>
          <p className="eyebrow">Create workspace</p>
          <h2 className="display-3" style={{ fontSize: "1.2rem" }}>
            Start a tenant boundary
          </h2>
          <p className="muted text-sm" style={{ marginTop: 8, marginBottom: 18 }}>
            The creator becomes the first owner in the same database transaction.
          </p>
          <form action={createWorkspaceAction} className="field-group">
            <div>
              <label htmlFor="workspace-name">Workspace name</label>
              <input
                id="workspace-name"
                maxLength={120}
                minLength={2}
                name="name"
                placeholder="Northstar Research"
                required
              />
            </div>
            <SubmitButton>Create workspace</SubmitButton>
          </form>
          <div style={{ marginTop: 18 }}>
            <CopyableId label="you" value={me.email} />
          </div>
        </aside>
      </section>
    </main>
  );
}
