"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { apiRequest, AtlasApiError, type Member, type Workspace } from "@/lib/api";
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

export async function signOutAction(): Promise<void> {
  if (authMode === "development") {
    const cookieStore = await cookies();
    cookieStore.delete(sessionCookieName);
  }
  redirect("/");
}

