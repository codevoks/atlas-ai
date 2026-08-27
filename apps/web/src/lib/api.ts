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
}

export interface SemanticSearchResult {
  items: Evidence[];
  trace_id: string;
  debug: Record<string, unknown> | null;
}

export type SearchMode = "semantic" | "lexical" | "hybrid";

export interface SearchResult extends SemanticSearchResult {
  mode: SearchMode;
  retrieval_config_version: string;
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
): Promise<SearchResult> {
  return apiRequest<SearchResult>(`/v1/workspaces/${workspaceId}/search`, {
    method: "POST",
    body: JSON.stringify({ query, mode, top_k: 5, debug: true }),
  });
}
