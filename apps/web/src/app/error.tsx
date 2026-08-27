"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <main className="centered-page"><section className="auth-panel"><p className="eyebrow">Request failed</p><h1>Atlas could not load this view.</h1><p className="muted">Check that the API and database are healthy, then try again.</p><button className="button" onClick={reset} type="button">Try again</button></section></main>;
}

