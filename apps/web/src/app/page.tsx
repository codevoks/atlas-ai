import Link from "next/link";

import { authMode } from "@/lib/config";

export default function HomePage() {
  return (
    <main className="landing">
      <nav className="nav shell">
        <Link className="brand" href="/">
          <span className="brand-mark">A</span>
          Atlas
        </Link>
        <Link className="button secondary" href="/sign-in">
          Sign in
        </Link>
      </nav>
      <section className="hero shell">
        <div>
          <p className="eyebrow">Enterprise knowledge, with evidence</p>
          <h1 className="display-1">
            Trustworthy answers from tenant-safe enterprise knowledge.
          </h1>
          <p className="lede" style={{ marginTop: 26, marginBottom: 32 }}>
            Upload team documents, search grounded evidence, ask citation-backed questions,
            run bounded research, and inspect security and operations posture from one
            local-first workspace.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/sign-in">
              Open workspace
            </Link>
            <a className="text-link" href="http://localhost:8000/docs">
              Explore API docs →
            </a>
          </div>
        </div>
        <div className="panel" aria-label="Atlas AI product flow" style={{ padding: 28 }}>
          <p className="eyebrow" style={{ marginBottom: 20 }}>Atlas workflow</p>
          <ol className="stack" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {[
              "Identity verified at the API boundary",
              "Workspace RBAC resolves source and document access",
              "Upload bytes verified by signed intent and digest",
              "Worker lease publishes the version after integrity checks",
            ].map((step, index) => (
              <li
                key={step}
                style={{
                  display: "grid",
                  gridTemplateColumns: "30px 1fr",
                  gap: 12,
                  padding: "14px 0",
                  borderTop: index === 0 ? "none" : "1px solid var(--line-soft)",
                  lineHeight: 1.5,
                  fontSize: "0.875rem",
                }}
              >
                <span className="mono" style={{ color: "var(--accent)" }}>
                  0{index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
          <p className="notice" style={{ marginTop: 20 }}>
            Auth mode: {authMode === "development" ? "local deterministic demo" : "OIDC / Clerk"}
          </p>
        </div>
      </section>
    </main>
  );
}
