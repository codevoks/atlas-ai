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
          <h1>Trustworthy answers from tenant-safe enterprise knowledge.</h1>
          <p className="lede">
            Upload team documents, search grounded evidence, ask citation-backed questions,
            run bounded research, and inspect security and operations posture from one local-first
            workspace experience.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/sign-in">
              Open workspace
            </Link>
            <a className="text-link" href="http://localhost:8000/docs">
              Explore API docs
            </a>
          </div>
        </div>
        <div className="architecture-card" aria-label="Atlas AI product flow">
          <p className="card-label">Atlas workflow</p>
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
