import "server-only";

import { cache } from "react";

import type { components } from "@atlas/shared-types";

import { AtlasApiError } from "@/lib/api-error";
import { apiUrl } from "@/lib/config";
import { getApiToken } from "@/lib/session";

export type Me = components["schemas"]["MeResponse"];
export type Workspace = components["schemas"]["WorkspaceResponse"];
export type Member = components["schemas"]["MemberResponse"];
export type Source = components["schemas"]["SourceResponse"];
export type Document = components["schemas"]["DocumentResponse"];
export type DocumentVersion = components["schemas"]["DocumentVersionResponse"];
export type Chunk = components["schemas"]["ChunkResponse"];
export type IngestionJob = components["schemas"]["IngestionJobResponse"];
export type UploadIntent = components["schemas"]["UploadIntentResponse"];
export type UploadFinalizeResult = components["schemas"]["UploadFinalizeResponse"];

export interface Evidence {
  chunk_id: string;
  document_id: string;
  document_version_id: string;
  source_id: string;
  document_title: string;
  ordinal: number;
  heading: string | null;
  block_type: string;
  start_char: number;
  end_char: number;
  snippet: string;
  distance: number;
  score: number;
  retrieval_stage: "semantic" | "lexical" | "hybrid";
  semantic_score: number | null;
  lexical_score: number | null;
  rrf_score: number | null;
  semantic_rank: number | null;
  lexical_rank: number | null;
  embedding_set_id: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  embedding_model_version: string | null;
  retrieval_provenance: Record<string, unknown>;
}

export interface SemanticSearchResult {
  items: Evidence[];
  trace_id: string;
  debug: Record<string, unknown> | null;
}

export type SearchMode = "semantic" | "lexical" | "hybrid";
export type RetrievalConfigVersion =
  | "phase5-postgres-fts-rrf-v1"
  | "phase8-multi-query-expansion-v1";

export interface SearchResult extends SemanticSearchResult {
  mode: SearchMode;
  retrieval_config_version: string;
}

export interface AnswerEvidence {
  id: string;
  rank: number;
  chunk_id: string;
  document_id: string;
  document_version_id: string;
  source_id: string;
  document_title: string;
  retrieval_stage: string;
  retrieval_score: number;
  semantic_score: number | null;
  lexical_score: number | null;
  rrf_score: number | null;
  quote: string;
  start_char: number;
  end_char: number;
  retrieval_provenance: Record<string, unknown>;
}

export interface Citation {
  id: string;
  marker: string;
  evidence_rank: number;
  answer_evidence_id: string;
  chunk_id: string;
  document_id: string;
  document_version_id: string;
  quote: string;
  evidence_start_char: number;
  evidence_end_char: number;
  answer_start_char: number;
  answer_end_char: number;
  status: string;
}

export interface AnswerResult {
  id: string;
  workspace_id: string;
  status: string;
  query: string;
  answer_text: string;
  retrieval_mode: SearchMode;
  retrieval_config_version: string;
  generation_provider: string;
  generation_model: string;
  generation_model_version: string;
  prompt_version: string;
  grounding_status: string;
  warnings: string[];
  input_tokens: number;
  output_tokens: number;
  total_cost_usd: number;
  latency_ms: number;
  evidence: AnswerEvidence[];
  citations: Citation[];
  created_at: string;
}

export interface EvaluationResult {
  id: string;
  evaluation_case_id: string;
  status: string;
  metrics: Record<string, unknown>;
  retrieved_chunk_ids: string[];
  answer_run_id: string | null;
  error_code: string | null;
  error_message: string | null;
  latency_ms: number;
  total_cost_usd: number;
  created_at: string;
}

export interface EvaluationRun {
  id: string;
  workspace_id: string;
  dataset_version_id: string;
  status: string;
  run_name: string;
  evaluation_config: Record<string, unknown>;
  metric_versions: Record<string, string>;
  code_revision: string;
  aggregate_metrics: Record<string, unknown>;
  slice_metrics: Record<string, unknown>;
  failure_summary: Record<string, unknown>;
  total_cost_usd: number;
  latency_ms: number;
  started_at: string;
  completed_at: string | null;
  results: EvaluationResult[];
}

export interface ResearchApproval {
  id: string;
  status: "pending" | "approved" | "denied" | "stale";
  approval_type: string;
  reason: string;
  approval_payload: Record<string, unknown>;
  version: number;
  created_at: string;
  decided_at: string | null;
}

export interface ResearchStep {
  id: string;
  ordinal: number;
  node_name: string;
  status: string;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  latency_ms: number;
  started_at: string;
  completed_at: string | null;
}

export interface ResearchToolInvocation {
  id: string;
  research_step_id: string;
  tool_name: string;
  status: string;
  input_summary: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  idempotency_key: string;
  latency_ms: number;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ResearchCheckpoint {
  id: string;
  schema_version: string;
  state_summary: Record<string, unknown>;
  created_at: string;
}

export interface ResearchRun {
  id: string;
  workspace_id: string;
  created_by_user_id: string;
  purpose: string;
  question: string;
  status:
    | "pending"
    | "running"
    | "waiting_approval"
    | "paused"
    | "succeeded"
    | "failed"
    | "cancelled"
    | "budget_exhausted"
    | "timed_out";
  graph_version: string;
  config_version: string;
  model_versions: Record<string, string>;
  input_hash: string;
  budget: Record<string, unknown>;
  usage: Record<string, unknown>;
  report_text: string | null;
  evidence: Record<string, unknown>[];
  warnings: string[];
  terminal_reason: string | null;
  cancellation_requested: boolean;
  version: number;
  total_cost_usd: number;
  started_at: string;
  updated_at: string;
  completed_at: string | null;
  steps: ResearchStep[];
  tool_invocations: ResearchToolInvocation[];
  approvals: ResearchApproval[];
  checkpoints: ResearchCheckpoint[];
}

export interface SecurityEvent {
  id: string;
  workspace_id: string;
  actor_user_id: string | null;
  event_type: string;
  severity: "info" | "low" | "medium" | "high" | "critical";
  outcome: "allowed" | "blocked" | "detected";
  request_id: string;
  target_type: string | null;
  target_id: string | null;
  control_version: string;
  safe_metadata: Record<string, unknown>;
  created_at: string;
}

export interface SecurityPosture {
  policy_config_version: string;
  guardrail_version: string;
  zero_cost: boolean;
  paid_services_enabled: boolean;
  fail_closed_controls: string[];
  deterministic_controls: string[];
  residual_risks: Record<string, unknown>[];
}

export interface RouteMetric {
  route: string;
  method: string;
  count: number;
  error_count: number;
  p95_ms: number;
  max_ms: number;
}

export interface OperationsPosture {
  posture_version: string;
  telemetry_schema_version: string;
  zero_cost: boolean;
  paid_services_enabled: boolean;
  telemetry_exporter: string;
  telemetry_content_capture_enabled: boolean;
  retained_trace_count: number;
  dropped_trace_count: number;
  dependency_status: Record<string, unknown>;
  slo_summary: Record<string, unknown>;
  capacity_envelope: Record<string, unknown>;
  cost_summary: Record<string, unknown>;
  runbooks: Record<string, unknown>[];
  routes: RouteMetric[];
}

interface ApiErrorPayload {
  error?: { code?: string; message?: string; request_id?: string };
}
export { AtlasApiError } from "@/lib/api-error";

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getApiToken();
  if (!token) {
    throw new AtlasApiError("Authentication is required.", 401, "unauthenticated");
  }
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");
  headers.set("X-Request-ID", crypto.randomUUID());

  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    throw new AtlasApiError(
      payload.error?.message ?? "The Atlas API request failed.",
      response.status,
      payload.error?.code ?? "api_error",
      payload.error?.request_id,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const getMe = cache(async (): Promise<Me> => {
  return apiRequest<Me>("/v1/me");
});

export async function getWorkspaces(): Promise<Workspace[]> {
  const payload = await apiRequest<{ items: Workspace[] }>("/v1/workspaces");
  return payload.items;
}

export const getWorkspace = cache(async (workspaceId: string): Promise<Workspace> => {
  return apiRequest<Workspace>(`/v1/workspaces/${workspaceId}`);
});

export interface WorkspaceContext {
  me: Me;
  workspace: Workspace;
  canAdminister: boolean;
  canUpload: boolean;
}

/**
 * Shared per-request identity + workspace membership resolution used by the
 * workspace shell layout and every section page. React's `cache()` on
 * `getMe`/`getWorkspace` above collapses these into one API call each per
 * request even though multiple server components call this helper.
 */
export const loadWorkspaceContext = cache(
  async (workspaceId: string): Promise<WorkspaceContext> => {
    const [me, workspace] = await Promise.all([getMe(), getWorkspace(workspaceId)]);
    const canAdminister = workspace.role === "owner" || workspace.role === "admin";
    const canUpload = canAdminister || workspace.role === "member";
    return { me, workspace, canAdminister, canUpload };
  },
);

export async function getMembers(workspaceId: string): Promise<Member[]> {
  const payload = await apiRequest<{ items: Member[] }>(
    `/v1/workspaces/${workspaceId}/members`,
  );
  return payload.items;
}

export async function getSources(workspaceId: string): Promise<Source[]> {
  const payload = await apiRequest<{ items: Source[] }>(
    `/v1/workspaces/${workspaceId}/sources`,
  );
  return payload.items;
}

export async function getDocuments(workspaceId: string): Promise<Document[]> {
  const payload = await apiRequest<{ items: Document[] }>(
    `/v1/workspaces/${workspaceId}/documents`,
  );
  return payload.items;
}

export async function getDocumentVersions(
  workspaceId: string,
  documentId: string,
): Promise<DocumentVersion[]> {
  const payload = await apiRequest<{ items: DocumentVersion[] }>(
    `/v1/workspaces/${workspaceId}/documents/${documentId}/versions`,
  );
  return payload.items;
}

export async function getDocumentChunks(
  workspaceId: string,
  documentId: string,
  versionId: string,
): Promise<Chunk[]> {
  const payload = await apiRequest<{ items: Chunk[] }>(
    `/v1/workspaces/${workspaceId}/documents/${documentId}/versions/${versionId}/chunks`,
  );
  return payload.items;
}

export async function getIngestionJob(
  workspaceId: string,
  jobId: string,
): Promise<IngestionJob> {
  return apiRequest<IngestionJob>(`/v1/workspaces/${workspaceId}/ingestion-jobs/${jobId}`);
}

export async function semanticSearch(
  workspaceId: string,
  query: string,
): Promise<SemanticSearchResult> {
  return apiRequest<SemanticSearchResult>(`/v1/workspaces/${workspaceId}/search/semantic`, {
    method: "POST",
    body: JSON.stringify({ query, top_k: 5, debug: true }),
  });
}

export async function searchEvidence(
  workspaceId: string,
  query: string,
  mode: SearchMode,
  retrievalConfigVersion: RetrievalConfigVersion,
): Promise<SearchResult> {
  return apiRequest<SearchResult>(`/v1/workspaces/${workspaceId}/search`, {
    method: "POST",
    body: JSON.stringify({
      query,
      mode,
      retrieval_config_version: retrievalConfigVersion,
      top_k: 5,
      debug: true,
    }),
  });
}

export async function answerQuestion(
  workspaceId: string,
  query: string,
  retrievalMode: SearchMode,
  retrievalConfigVersion: RetrievalConfigVersion,
): Promise<AnswerResult> {
  return apiRequest<AnswerResult>(`/v1/workspaces/${workspaceId}/answers`, {
    method: "POST",
    body: JSON.stringify({
      query,
      retrieval_mode: retrievalMode,
      retrieval_config_version: retrievalConfigVersion,
      top_k: 5,
    }),
  });
}

export async function getEvaluationRuns(workspaceId: string): Promise<EvaluationRun[]> {
  const payload = await apiRequest<{ items: EvaluationRun[] }>(
    `/v1/workspaces/${workspaceId}/evaluation-runs?limit=5`,
  );
  return payload.items;
}

export async function getResearchRuns(workspaceId: string): Promise<ResearchRun[]> {
  const payload = await apiRequest<{ items: ResearchRun[] }>(
    `/v1/workspaces/${workspaceId}/research-runs?limit=5`,
  );
  return payload.items;
}

export async function getSecurityPosture(workspaceId: string): Promise<SecurityPosture> {
  return apiRequest<SecurityPosture>(`/v1/workspaces/${workspaceId}/security/posture`);
}

export async function getSecurityEvents(workspaceId: string): Promise<SecurityEvent[]> {
  const payload = await apiRequest<{ items: SecurityEvent[] }>(
    `/v1/workspaces/${workspaceId}/security/events?limit=8`,
  );
  return payload.items;
}

export async function getOperationsPosture(workspaceId: string): Promise<OperationsPosture> {
  return apiRequest<OperationsPosture>(`/v1/workspaces/${workspaceId}/operations/posture`);
}

export async function createResearchRun(
  workspaceId: string,
  purpose: string,
  question: string,
): Promise<ResearchRun> {
  return apiRequest<ResearchRun>(`/v1/workspaces/${workspaceId}/research-runs`, {
    method: "POST",
    headers: {
      "Idempotency-Key": `research-${workspaceId}-${Buffer.from(`${purpose}:${question}`)
        .toString("base64")
        .replace(/[^a-zA-Z0-9]/g, "")
        .slice(0, 64)}`,
    },
    body: JSON.stringify({ purpose, question }),
  });
}

export async function decideResearchApproval(
  workspaceId: string,
  runId: string,
  approvalId: string,
  version: number,
  approved: boolean,
): Promise<ResearchRun> {
  return apiRequest<ResearchRun>(
    `/v1/workspaces/${workspaceId}/research-runs/${runId}/approvals/${approvalId}`,
    {
      method: "POST",
      body: JSON.stringify({ version, approved }),
    },
  );
}
