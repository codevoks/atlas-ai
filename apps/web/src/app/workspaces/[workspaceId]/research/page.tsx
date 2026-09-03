import { createResearchRunAction, decideResearchApprovalAction } from "@/app/actions";
import { formatReportForClipboard } from "@/lib/clipboard-format";
import { CopyableId } from "@/components/copyable-id";
import { CopyButton } from "@/components/copy-button";
import { ExportPdfButton } from "@/components/export-pdf-button";
import { ResearchIcon } from "@/components/icons";
import { SubmitButton } from "@/components/submit-button";
import { getResearchRuns, loadWorkspaceContext, type ResearchRun } from "@/lib/api";

interface ResearchPageProps {
  params: Promise<{ workspaceId: string }>;
}

export default async function ResearchPage({ params }: ResearchPageProps) {
  const { workspaceId } = await params;
  const { workspace } = await loadWorkspaceContext(workspaceId);
  const runs = await getResearchRuns(workspaceId);
  const returnTo = `/workspaces/${workspace.id}/research`;

  return (
    <div className="app-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Bounded research</p>
          <h1 className="display-2">Run a cited research workflow</h1>
        </div>
        <span className="count">{runs.length}</span>
      </div>

      <form action={createResearchRunAction} className="panel field-group" style={{ padding: 20, marginBottom: 32 }}>
        <input name="workspaceId" type="hidden" value={workspace.id} />
        <input name="redirectTo" type="hidden" value={returnTo} />
        <div>
          <label htmlFor="research-purpose">Research purpose</label>
          <input
            defaultValue="Access policy review"
            id="research-purpose"
            maxLength={160}
            minLength={2}
            name="purpose"
            placeholder="Research purpose"
            required
          />
        </div>
        <div>
          <label htmlFor="research-question">Research question</label>
          <textarea
            defaultValue="How should finance approval be handled for SAML access before payment?"
            id="research-question"
            maxLength={4000}
            name="question"
            placeholder="Research question"
            required
            rows={2}
          />
        </div>
        <SubmitButton>Start bounded research</SubmitButton>
      </form>

      {runs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">
            <ResearchIcon />
          </span>
          <strong>No research runs yet</strong>
          <p>
            Start a run to plan bounded questions, retrieve Atlas evidence, pause for human
            approval, and synthesize a cited report.
          </p>
        </div>
      ) : (
        <div className="stack-lg">
          {runs.map((run) => (
            <ResearchRunCard key={run.id} run={run} workspaceId={workspace.id} />
          ))}
        </div>
      )}
    </div>
  );
}

function ResearchRunCard({ run, workspaceId }: { run: ResearchRun; workspaceId: string }) {
  const pendingApproval = run.approvals.find((approval) => approval.status === "pending");
  const returnTo = `/workspaces/${workspaceId}/research`;
  return (
    <article className="panel" style={{ padding: 22 }}>
      <div className="result-card-header">
        <div>
          <strong style={{ fontSize: "1.0625rem" }}>{run.purpose}</strong>
          <p className="muted text-sm" style={{ marginTop: 4 }}>
            {run.question}
          </p>
        </div>
        <span className={`pill dot ${statusTone(run.status)}`}>{run.status}</span>
      </div>

      <div className="metric-grid" style={{ marginTop: 16 }}>
        <div className="metric-tile">
          <span>Steps</span>
          <strong>
            {String(run.usage.steps ?? 0)}/{String(run.budget.max_steps ?? "—")}
          </strong>
        </div>
        <div className="metric-tile">
          <span>Tool calls</span>
          <strong>
            {String(run.usage.tool_calls ?? 0)}/{String(run.budget.max_tool_calls ?? "—")}
          </strong>
        </div>
        <div className="metric-tile">
          <span>Cost</span>
          <strong>${Number(run.usage.cost_usd ?? 0).toFixed(2)}</strong>
        </div>
      </div>

      {run.tool_invocations.length > 0 ? (
        <div className="stack" style={{ gap: 6, marginTop: 16 }}>
          <p className="eyebrow" style={{ marginBottom: 0 }}>
            Tool trace
          </p>
          {run.tool_invocations.map((tool) => (
            <p className="mono text-xs muted" key={tool.id}>
              {tool.tool_name} · {tool.status}
            </p>
          ))}
        </div>
      ) : null}

      {pendingApproval ? (
        <div className="notice" style={{ marginTop: 18, borderColor: "var(--accent-line)", background: "var(--accent-soft)" }}>
          <strong style={{ color: "var(--ink)", display: "block", marginBottom: 4 }}>
            Approval required: {pendingApproval.approval_type}
          </strong>
          <p style={{ marginBottom: 14 }}>{pendingApproval.reason}</p>
          <div className="inline-form">
            <form action={decideResearchApprovalAction}>
              <input name="workspaceId" type="hidden" value={workspaceId} />
              <input name="runId" type="hidden" value={run.id} />
              <input name="approvalId" type="hidden" value={pendingApproval.id} />
              <input name="version" type="hidden" value={pendingApproval.version} />
              <input name="approved" type="hidden" value="true" />
              <input name="redirectTo" type="hidden" value={returnTo} />
              <SubmitButton>Approve synthesis</SubmitButton>
            </form>
            <form action={decideResearchApprovalAction}>
              <input name="workspaceId" type="hidden" value={workspaceId} />
              <input name="runId" type="hidden" value={run.id} />
              <input name="approvalId" type="hidden" value={pendingApproval.id} />
              <input name="version" type="hidden" value={pendingApproval.version} />
              <input name="approved" type="hidden" value="false" />
              <input name="redirectTo" type="hidden" value={returnTo} />
              <SubmitButton destructive>Deny</SubmitButton>
            </form>
          </div>
        </div>
      ) : null}

      {run.report_text ? (
        <div style={{ marginTop: 18 }}>
          <div className="result-card-header" style={{ marginBottom: 8 }}>
            <p className="eyebrow" style={{ marginBottom: 0 }}>Report</p>
            <div className="inline-form">
              <CopyButton
                copiedLabel="Report copied"
                label="Copy report"
                text={formatReportForClipboard({ question: run.question, reportText: run.report_text ?? "" })}
              />
              <ExportPdfButton runId={run.id} workspaceId={workspaceId} />
            </div>
          </div>
          <pre
            className="mono"
            style={{
              margin: 0,
              maxHeight: 360,
              overflow: "auto",
              whiteSpace: "pre-wrap",
              fontSize: "0.8125rem",
              lineHeight: 1.6,
              color: "var(--ink-muted)",
            }}
          >
            {run.report_text}
          </pre>
        </div>
      ) : null}

      <div className="inline-form" style={{ marginTop: 16 }}>
        <CopyableId label="run" value={run.id} />
      </div>
      {run.warnings.length > 0 ? (
        <p className="alert" style={{ marginTop: 12 }}>
          {run.warnings.join(", ")}
        </p>
      ) : null}
    </article>
  );
}

function statusTone(status: string): string {
  if (["succeeded"].includes(status)) return "verified";
  if (["failed", "cancelled", "timed_out", "budget_exhausted"].includes(status)) return "danger";
  return "accent";
}
