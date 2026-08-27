import Link from "next/link";

export default function NotFoundPage() {
  return <main className="centered-page"><section className="auth-panel"><p className="eyebrow">Not found</p><h1>This workspace is unavailable.</h1><p className="muted">It may not exist, or your current identity may not be a member.</p><Link className="button" href="/dashboard">Return to workspaces</Link></section></main>;
}

