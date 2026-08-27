import { SignIn } from "@clerk/nextjs";
import Link from "next/link";

import { authMode } from "@/lib/config";

export default function SignInPage() {
  if (authMode === "oidc") {
    return (
      <main className="centered-page">
        <SignIn />
      </main>
    );
  }
  return (
    <main className="centered-page">
      <section className="auth-panel">
        <Link className="brand" href="/">
          <span className="brand-mark">A</span>
          Atlas AI
        </Link>
        <div>
          <p className="eyebrow">Development authentication</p>
          <h1>Choose a local identity</h1>
          <p className="muted">
            These signed sessions are available only in development. Production uses the configured
            OIDC identity provider.
          </p>
        </div>
        <form action="/api/dev/session" method="post" className="identity-options">
          <button className="identity-card" name="identity" value="alice" type="submit">
            <span className="avatar">AO</span>
            <span><strong>Alice Owner</strong><small>alice@atlas.local</small></span>
          </button>
          <button className="identity-card" name="identity" value="bob" type="submit">
            <span className="avatar alt">BM</span>
            <span><strong>Bob Member</strong><small>bob@atlas.local</small></span>
          </button>
        </form>
      </section>
    </main>
  );
}

