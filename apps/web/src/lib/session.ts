import { cookies } from "next/headers";

import { authMode, sessionCookieName } from "@/lib/config";

export async function getApiToken(): Promise<string | null> {
  if (authMode === "development") {
    const cookieStore = await cookies();
    return cookieStore.get(sessionCookieName)?.value ?? null;
  }

  const { auth } = await import("@clerk/nextjs/server");
  const session = await auth();
  if (!session.userId) {
    return null;
  }
  return session.getToken({ template: "atlas-api" });
}

