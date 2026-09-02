import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { signOutAction } from "@/app/actions";
import { Sidebar } from "@/components/app-shell/sidebar";
import { AtlasApiError, loadWorkspaceContext } from "@/lib/api";

interface WorkspaceLayoutProps {
  children: React.ReactNode;
  params: Promise<{ workspaceId: string }>;
}

export default async function WorkspaceLayout({ children, params }: WorkspaceLayoutProps) {
  const { workspaceId } = await params;
  let context;
  try {
    context = await loadWorkspaceContext(workspaceId);
  } catch (error) {
    if (error instanceof AtlasApiError && error.status === 401) redirect("/sign-in");
    if (error instanceof AtlasApiError && error.status === 404) notFound();
    throw error;
  }
  const { me, workspace, canAdminister } = context;

  return (
    <div className="app-frame">
      <Sidebar
        canAdminister={canAdminister}
        onSignOut={signOutAction}
        role={workspace.role}
        userEmail={me.email}
        userName={me.display_name}
        workspaceId={workspace.id}
        workspaceName={workspace.name}
      />
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-topbar-crumb">
            <Link className="back-link" href="/dashboard">
              All workspaces
            </Link>
            <span className="faint">/</span>
            <strong>{workspace.name}</strong>
          </div>
          <span className="pill">{workspace.role}</span>
        </header>
        {children}
      </div>
    </div>
  );
}
