export const authMode = process.env.AUTH_MODE ?? "development";
export const apiUrl = process.env.API_URL ?? "http://localhost:8000";
export const sessionCookieName = "atlas_session";

export function assertDevelopmentAuth(): void {
  if (authMode !== "development" || process.env.NODE_ENV === "production") {
    throw new Error("Development authentication is unavailable");
  }
}

