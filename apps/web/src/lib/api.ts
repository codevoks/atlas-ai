import "server-only";

import type { components } from "@atlas/shared-types";

import { AtlasApiError } from "@/lib/api-error";
import { apiUrl } from "@/lib/config";
import { getApiToken } from "@/lib/session";

export type Me = components["schemas"]["MeResponse"];
export type Workspace = components["schemas"]["WorkspaceResponse"];
export type Member = components["schemas"]["MemberResponse"];

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
