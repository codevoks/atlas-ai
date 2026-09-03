// Next.js's own build replaces the real `server-only` package with a no-op
// for server-side bundles. Vitest doesn't go through that build step, so we
// mirror the same no-op here purely for the test environment (see
// vitest.config.ts) — this file has no effect on the production build.
export {};
