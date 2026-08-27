"use server";

import { createHash } from "node:crypto";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  apiRequest,
  AtlasApiError,
  type Member,
  type Source,
  type UploadFinalizeResult,
  type UploadIntent,
  type Workspace,
} from "@/lib/api";
import { authMode, sessionCookieName } from "@/lib/config";

function messageFor(error: unknown): string {
  if (error instanceof AtlasApiError) {
    return `${error.message}${error.requestId ? ` Request ID: ${error.requestId}` : ""}`;
  }
  return "The request could not be completed.";
}

export async function createWorkspaceAction(formData: FormData): Promise<void> {
  let destination = "/dashboard";
  try {
    const name = String(formData.get("name") ?? "");
    const workspace = await apiRequest<Workspace>("/v1/workspaces", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ name }),
    });
    revalidatePath("/dashboard");
    destination = `/workspaces/${workspace.id}`;
  } catch (error) {
    destination = `/dashboard?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function renameWorkspaceAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest<Workspace>(`/v1/workspaces/${workspaceId}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: String(formData.get("name") ?? ""),
        version: Number(formData.get("version")),
      }),
    });
    revalidatePath(`/workspaces/${workspaceId}`);
    revalidatePath("/dashboard");
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function addMemberAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest<Member>(`/v1/workspaces/${workspaceId}/members`, {
      method: "POST",
      body: JSON.stringify({
        email: String(formData.get("email") ?? ""),
        role: String(formData.get("role") ?? "member"),
      }),
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function updateMemberAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  const userId = String(formData.get("userId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest<Member>(`/v1/workspaces/${workspaceId}/members/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({
        role: String(formData.get("role") ?? "member"),
        version: Number(formData.get("version")),
      }),
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function removeMemberAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  const userId = String(formData.get("userId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest<void>(`/v1/workspaces/${workspaceId}/members/${userId}`, {
      method: "DELETE",
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function createSourceAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest<Source>(`/v1/workspaces/${workspaceId}/sources`, {
      method: "POST",
      body: JSON.stringify({ name: String(formData.get("name") ?? "") }),
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function uploadDocumentAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      throw new Error("Choose a non-empty file.");
    }
    const bytes = Buffer.from(await file.arrayBuffer());
    const digest = createHash("sha256").update(bytes).digest("hex");
    const mediaType = file.type || "application/octet-stream";
    const intent = await apiRequest<UploadIntent>(`/v1/workspaces/${workspaceId}/uploads`, {
      method: "POST",
      body: JSON.stringify({
        original_filename: file.name,
        media_type: mediaType,
        byte_size: bytes.length,
        digest_sha256: digest,
      }),
    });
    if (!intent.upload_url) {
      throw new Error("The API did not return an upload URL.");
    }
    const uploadResponse = await fetch(intent.upload_url, {
      method: "PUT",
      headers: { "Content-Type": mediaType },
      body: bytes,
    });
    if (!uploadResponse.ok) {
      throw new Error("The signed upload failed.");
    }
    await apiRequest<UploadFinalizeResult>(
      `/v1/workspaces/${workspaceId}/uploads/${intent.id}/finalize`,
      {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          source_id: String(formData.get("sourceId") ?? ""),
          title: String(formData.get("title") || file.name),
        }),
      },
    );
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function cancelIngestionJobAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  const jobId = String(formData.get("jobId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest(`/v1/workspaces/${workspaceId}/ingestion-jobs/${jobId}/cancel`, {
      method: "POST",
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function retryIngestionJobAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  const jobId = String(formData.get("jobId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest(`/v1/workspaces/${workspaceId}/ingestion-jobs/${jobId}/retry`, {
      method: "POST",
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function deleteDocumentAction(formData: FormData): Promise<void> {
  const workspaceId = String(formData.get("workspaceId") ?? "");
  const documentId = String(formData.get("documentId") ?? "");
  let destination = `/workspaces/${workspaceId}`;
  try {
    await apiRequest<void>(`/v1/workspaces/${workspaceId}/documents/${documentId}`, {
      method: "DELETE",
    });
    revalidatePath(`/workspaces/${workspaceId}`);
  } catch (error) {
    destination += `?error=${encodeURIComponent(messageFor(error))}`;
  }
  redirect(destination);
}

export async function signOutAction(): Promise<void> {
  if (authMode === "development") {
    const cookieStore = await cookies();
    cookieStore.delete(sessionCookieName);
  }
  redirect("/");
}
