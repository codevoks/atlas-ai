import { EvaluationIcon } from "@/components/icons";
import { getEvaluationRuns, loadWorkspaceContext } from "@/lib/api";

interface EvaluationPageProps {
  params: Promise<{ workspaceId: string }>;
}

export default async function EvaluationPage({ params }: EvaluationPageProps) {
  const { workspaceId } = await params;
  await loadWorkspaceContext(workspaceId);
  const runs = await getEvaluationRuns(workspaceId);

  return (
    <div className="app-content">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Evaluation</p>
          <h1 className="display-2">Latest regression runs</h1>
        </div>
        <span className="count">{runs.length}</span>
      </div>

      {runs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">
            <EvaluationIcon />
          </span>
          <strong>No evaluation runs yet</strong>
          <p>Use the evaluation API to run deterministic regression checks against approved datasets.</p>
        </div>
      ) : (
        <div className="stack-lg">
          {runs.map((run) => (
            <article className="panel" key={run.id} style={{ padding: 22 }}>
              <div className="result-card-header">
                <strong style={{ fontSize: "1.0625rem" }}>{run.run_name}</strong>
                <span className="pill dot verified">{run.status}</span>
              </div>
              <p className="muted text-sm" style={{ marginTop: 4 }}>
                {run.results.length} cases · ${run.total_cost_usd.toFixed(2)} · {run.latency_ms}ms
              </p>
              <div className="metric-grid" style={{ marginTop: 16 }}>
                <div className="metric-tile">
                  <span>Recall@K</span>
                  <strong>{formatMetric(nestedMetric(run.aggregate_metrics, "retrieval", "recall_at_k"))}</strong>
                </div>
                <div className="metric-tile">
                  <span>MRR</span>
                  <strong>{formatMetric(nestedMetric(run.aggregate_metrics, "retrieval", "mrr"))}</strong>
                </div>
                <div className="metric-tile">
                  <span>Citation verified</span>
                  <strong>
                    {formatMetric(nestedMetric(run.aggregate_metrics, "answer", "citation_verified_rate"))}
                  </strong>
                </div>
              </div>
              <p className="mono text-xs faint" style={{ marginTop: 16 }}>
                dataset {run.dataset_version_id} · code {run.code_revision}
              </p>
              {Object.keys(run.failure_summary).length > 0 ? (
                <p className="alert" style={{ marginTop: 12 }}>
                  Failures: {JSON.stringify(run.failure_summary)}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function nestedMetric(metrics: Record<string, unknown>, category: string, name: string): number | null {
  const group = metrics[category];
  if (!group || typeof group !== "object" || Array.isArray(group)) return null;
  const value = (group as Record<string, unknown>)[name];
  return typeof value === "number" ? value : null;
}

function formatMetric(value: number | null): string {
  return value === null ? "—" : value.toFixed(3);
}
