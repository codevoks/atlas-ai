import "server-only";

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

export async function getMe(): Promise<Me> {
  return apiRequest<Me>("/v1/me");
}

export async function getWorkspaces(): Promise<Workspace[]> {
  const payload = await apiRequest<{ items: Workspace[] }>("/v1/workspaces");
  return payload.items;
}

export async function getWorkspace(workspaceId: string): Promise<Workspace> {
  return apiRequest<Workspace>(`/v1/workspaces/${workspaceId}`);
}

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
