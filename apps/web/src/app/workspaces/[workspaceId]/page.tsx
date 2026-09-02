import Link from "next/link";

import {
  AskIcon,
  DocumentsIcon,
  MembersIcon,
  ResearchIcon,
  SearchIcon,
} from "@/components/icons";
import { CopyableId } from "@/components/copyable-id";
import {
  getDocuments,
  getMembers,
  getSecurityPosture,
  getSources,
  loadWorkspaceContext,
} from "@/lib/api";

interface OverviewPageProps {
  params: Promise<{ workspaceId: string }>;
}

export default async function OverviewPage({ params }: OverviewPageProps) {
  const { workspaceId } = await params;
  const { workspace, canAdminister } = await loadWorkspaceContext(workspaceId);
  const [documents, sources, members, securityPosture] = await Promise.all([
    getDocuments(workspaceId),
    getSources(workspaceId),
    getMembers(workspaceId),
    canAdminister ? getSecurityPosture(workspaceId).catch(() => null) : Promise.resolve(null),
  ]);

  const readyDocuments = documents.filter((doc) => doc.latest_version_status === "ready").length;
  const isNewWorkspace = documents.length === 0 && sources.length === 0;

  return (
    <div className="app-content wide stack-lg">
      <div>
        <p className="eyebrow">Workspace · {workspace.role}</p>
        <h1 className="display-2">{workspace.name}</h1>
        <CopyableId value={workspace.id} />
      </div>

      {isNewWorkspace ? (
        <div className="empty-state" style={{ padding: "56px 32px" }}>
          <span className="empty-icon">
            <DocumentsIcon />
          </span>
          <strong>This workspace is ready for its first source</strong>
          <p>
            Create a source, upload a text or Markdown document, and Atlas will parse, chunk,
            and embed it — ready to search and cite within seconds.
          </p>
          <Link className="button" href={`/workspaces/${workspace.id}/documents`} style={{ marginTop: 6 }}>
            Add a document
          </Link>
        </div>
      ) : (
        <div className="metric-grid">
          <div className="metric-tile">
            <span>Documents</span>
            <strong>
              {readyDocuments}
              <span className="faint" style={{ fontSize: "0.7rem" }}>
                {" "}
                / {documents.length} ready
              </span>
            </strong>
          </div>
          <div className="metric-tile">
            <span>Sources</span>
            <strong>{sources.length}</strong>
          </div>
          <div className="metric-tile">
            <span>Members</span>
            <strong>{members.length}</strong>
          </div>
          {securityPosture ? (
            <div className="metric-tile">
              <span>Guardrail controls</span>
              <strong>{securityPosture.deterministic_controls.length} deterministic</strong>
            </div>
          ) : null}
        </div>
      )}

      <div>
        <p className="eyebrow">Get to work</p>
        <div className="row-list" style={{ gridTemplateColumns: "1fr" }}>
          <ShortcutRow
            description="Ask a question and read an answer with per-citation verification."
            href={`/workspaces/${workspace.id}/ask`}
            icon={<AskIcon />}
            title="Ask with verified citations"
          />
          <ShortcutRow
            description="Run semantic, lexical, or hybrid retrieval over workspace evidence."
            href={`/workspaces/${workspace.id}/search`}
            icon={<SearchIcon />}
            title="Search grounded evidence"
          />
          <ShortcutRow
            description="Plan bounded sub-questions and synthesize a cited report, with a human approval gate."
            href={`/workspaces/${workspace.id}/research`}
            icon={<ResearchIcon />}
            title="Run bounded research"
          />
          <ShortcutRow
            description="Review roles and invite teammates into this tenant boundary."
            href={`/workspaces/${workspace.id}/members`}
            icon={<MembersIcon />}
            title="Manage access"
          />
        </div>
      </div>
    </div>
  );
}

function ShortcutRow({
  href,
  icon,
  title,
  description,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Link className="row card interactive" href={href} style={{ textDecoration: "none" }}>
      <span className="avatar">{icon}</span>
      <span className="row-identity">
        <strong>{title}</strong>
        <span className="row-meta">{description}</span>
      </span>
      <span aria-hidden="true" className="faint">
        →
      </span>
    </Link>
  );
}
