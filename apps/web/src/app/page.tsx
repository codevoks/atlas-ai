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
          <h1>Build the tenant-safe foundation before retrieval begins.</h1>
          <p className="lede">
            Phase 1 establishes the secure workspace, membership, RBAC, audit, and API contract
            layer that later ingestion, retrieval, and grounded answers will depend on.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/sign-in">
              Open workspace
            </Link>
            <a className="text-link" href="http://localhost:8000/docs">
              Explore Phase 1 API
            </a>
          </div>
        </div>
        <div className="architecture-card" aria-label="Phase 1 architecture summary">
          <p className="card-label">Phase 1 foundation</p>
          <ol className="flow-list">
            <li><span>01</span> Identity verified at the API boundary</li>
            <li><span>02</span> Workspace membership resolved server-side</li>
            <li><span>03</span> RBAC enforced in application use cases</li>
            <li><span>04</span> Mutations committed with audit evidence</li>
          </ol>
          <p className="mode">Auth mode: {authMode === "development" ? "local deterministic demo" : "OIDC / Clerk"}</p>
        </div>
      </section>
    </main>
  );
}
