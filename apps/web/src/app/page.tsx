import Link from "next/link";

import { authMode } from "@/lib/config";

export default function HomePage() {
  return (
    <main className="landing">
      <nav className="nav shell">
        <Link className="brand" href="/">
          <span className="brand-mark">A</span>
          Atlas AI
        </Link>
        <Link className="button secondary" href="/sign-in">
          Sign in
        </Link>
      </nav>
      <section className="hero shell">
        <div>
          <p className="eyebrow">Enterprise knowledge, with evidence</p>
          <h1>Tenant-safe knowledge storage before retrieval begins.</h1>
          <p className="lede">
            Phase 2 establishes secure workspaces, source metadata, signed uploads, durable
            ingestion jobs, and metadata-only publication before parsing and retrieval are added.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/sign-in">
              Open workspace
            </Link>
            <a className="text-link" href="http://localhost:8000/docs">
              Explore Phase 2 API
            </a>
          </div>
        </div>
        <div className="architecture-card" aria-label="Phase 2 architecture summary">
          <p className="card-label">Phase 2 pipeline</p>
          <ol className="flow-list">
            <li><span>01</span> Identity verified at the API boundary</li>
            <li><span>02</span> Workspace RBAC resolves source and document access</li>
            <li><span>03</span> Upload bytes verified by signed intent and digest</li>
            <li><span>04</span> Worker lease publishes the version after integrity checks</li>
          </ol>
          <p className="mode">Auth mode: {authMode === "development" ? "local deterministic demo" : "OIDC / Clerk"}</p>
        </div>
      </section>
    </main>
  );
}
