import { SecurityIcon } from "@/components/icons";
import {
  getOperationsPosture,
  getSecurityEvents,
  getSecurityPosture,
  loadWorkspaceContext,
} from "@/lib/api";

interface SecurityPageProps {
  params: Promise<{ workspaceId: string }>;
}

export default async function SecurityPage({ params }: SecurityPageProps) {
  const { workspaceId } = await params;
  const { canAdminister } = await loadWorkspaceContext(workspaceId);

  if (!canAdminister) {
    return (
      <div className="app-content">
        <div className="empty-state">
          <span className="empty-icon">
            <SecurityIcon />
          </span>
          <strong>Restricted to owners and admins</strong>
          <p>Security and operations posture is visible only to workspace owners and admins.</p>
        </div>
      </div>
    );
  }

  const [securityPosture, securityEvents, operationsPosture] = await Promise.all([
    getSecurityPosture(workspaceId),
    getSecurityEvents(workspaceId),
    getOperationsPosture(workspaceId),
  ]);

  return (
    <div className="app-content wide stack-lg">
      <div>
        <p className="eyebrow">Security assurance</p>
        <h1 className="display-2">Guardrail posture</h1>
      </div>

      <div className="result-card">
        <div className="result-card-header">
          <strong>Active protection policy</strong>
          <span className="pill">{securityPosture.zero_cost ? "$0.00 local path" : "external cost enabled"}</span>
        </div>
        <div className="metric-grid">
          <div className="metric-tile">
            <span>Paid services</span>
            <strong>{securityPosture.paid_services_enabled ? "enabled" : "disabled"}</strong>
          </div>
          <div className="metric-tile">
            <span>Policy</span>
            <strong>{displayPolicyName(securityPosture.policy_config_version)}</strong>
          </div>
          <div className="metric-tile">
            <span>Fail-closed controls</span>
            <strong>{securityPosture.fail_closed_controls.length}</strong>
          </div>
          <div className="metric-tile">
            <span>Deterministic controls</span>
            <strong>{securityPosture.deterministic_controls.length}</strong>
          </div>
        </div>
        <p className="muted text-sm">
          Controls: {securityPosture.deterministic_controls.slice(0, 6).map(displayControlName).join(", ")}
        </p>
      </div>

      <div>
        <p className="eyebrow">Recent security events</p>
        {securityEvents.length ? (
          <div className="row-list">
            {securityEvents.map((event) => (
              <article className="row" key={event.id}>
                <span className={`pill dot ${event.outcome === "blocked" ? "danger" : "verified"}`}>
                  {event.outcome}
                </span>
                <span className="row-identity">
                  <strong>{event.event_type}</strong>
                  <span className="row-meta">
                    <span>{event.severity}</span>
                    <span className="mono">{event.request_id}</span>
                  </span>
                </span>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted text-sm">No security events recorded yet.</p>
        )}
      </div>

      <div>
        <p className="eyebrow">Operations</p>
        <h2 className="display-3">Production readiness posture</h2>
        <div className="result-card" style={{ marginTop: 16 }}>
          <div className="result-card-header">
            <strong>Operational readiness</strong>
            <span className="pill">{operationsPosture.zero_cost ? "$0.00 local validation" : "external cost enabled"}</span>
          </div>
          <div className="metric-grid">
            <div className="metric-tile">
              <span>Telemetry</span>
              <strong>{operationsPosture.telemetry_exporter}</strong>
            </div>
            <div className="metric-tile">
              <span>Content capture</span>
              <strong>{operationsPosture.telemetry_content_capture_enabled ? "enabled" : "disabled"}</strong>
            </div>
            <div className="metric-tile">
              <span>Traces</span>
              <strong>{operationsPosture.retained_trace_count}</strong>
            </div>
            <div className="metric-tile">
              <span>Paid services</span>
              <strong>{operationsPosture.paid_services_enabled ? "enabled" : "disabled"}</strong>
            </div>
          </div>
          <p className="muted text-sm">
            SLO status: {formatSloStatus(operationsPosture.slo_summary)} · DB{" "}
            {String(operationsPosture.dependency_status.database ?? "unknown")}
          </p>
        </div>
        <div className="row-list" style={{ marginTop: 12 }}>
          {operationsPosture.routes.slice(0, 6).map((metric) => (
            <article className="row" key={`${metric.method}-${metric.route}`}>
              <span className="row-identity">
                <strong className="mono" style={{ fontSize: "0.8125rem" }}>
                  {metric.method} {metric.route}
                </strong>
                <span className="row-meta">
                  <span>count {metric.count}</span>
                  <span>errors {metric.error_count}</span>
                  <span>p95 {metric.p95_ms.toFixed(1)}ms</span>
                </span>
              </span>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
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

function formatSloStatus(summary: Record<string, unknown>): string {
  const value = summary.within_objective;
  if (!value || typeof value !== "object" || Array.isArray(value)) return "unknown";
  const statuses = value as Record<string, unknown>;
  const failing = Object.entries(statuses)
    .filter(([, passed]) => passed === false)
    .map(([name]) => name);
  return failing.length === 0 ? "within objectives" : `needs attention: ${failing.join(", ")}`;
}
