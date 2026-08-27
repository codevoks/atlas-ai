import { SignJWT } from "jose";
import { NextResponse, type NextRequest } from "next/server";

import { assertDevelopmentAuth, sessionCookieName } from "@/lib/config";

const identities = {
  alice: { sub: "dev-alice", email: "alice@atlas.local", name: "Alice Owner" },
  bob: { sub: "dev-bob", email: "bob@atlas.local", name: "Bob Member" },
} as const;

export async function POST(request: NextRequest): Promise<NextResponse> {
  assertDevelopmentAuth();
  const requestHost = request.headers.get("host") ?? request.nextUrl.host;
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== requestHost) {
    return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  }
  const formData = await request.formData();
  const identityKey = String(formData.get("identity") ?? "") as keyof typeof identities;
  const identity = identities[identityKey];
  if (!identity) {
    return NextResponse.json({ error: "Unknown development identity" }, { status: 400 });
  }
  const secret = process.env.ATLAS_DEV_AUTH_SECRET;
  if (!secret || secret.length < 32) {
    return NextResponse.json({ error: "Development auth is not configured" }, { status: 503 });
  }
  const issuer = process.env.AUTH_ISSUER ?? "https://dev.atlas.local";
  const audience = process.env.AUTH_AUDIENCE ?? "atlas-api";
  const token = await new SignJWT({ email: identity.email, name: identity.name })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer(issuer)
    .setAudience(audience)
    .setSubject(identity.sub)
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(new TextEncoder().encode(secret));

  const redirectUrl = new URL("/dashboard", request.url);
  redirectUrl.host = requestHost;
  const response = NextResponse.redirect(redirectUrl, 303);
  response.cookies.set(sessionCookieName, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: false,
    path: "/",
    maxAge: 60 * 60,
  });
  return response;
}
