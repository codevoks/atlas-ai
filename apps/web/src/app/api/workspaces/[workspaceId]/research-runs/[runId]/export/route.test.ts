import { NextRequest } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AtlasApiError, type ResearchRun } from "@/lib/api";
import type * as AtlasApiModule from "@/lib/api";

const getResearchRun = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof AtlasApiModule>("@/lib/api");
  return {
    ...actual,
    getResearchRun: (...args: unknown[]) => getResearchRun(...args),
  };
});

import { GET } from "./route";

function baseRun(overrides: Partial<ResearchRun> = {}): ResearchRun {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    workspace_id: "33333333-3333-3333-3333-333333333333",
    created_by_user_id: "44444444-4444-4444-4444-444444444444",
    purpose: "Audit vendor payment controls",
    question: "What approvals are required for vendor payments?",
    status: "succeeded",
    graph_version: "phase9-deterministic-local-graph-v1",
    config_version: "phase9-bounded-research-v1",
    model_versions: {},
    input_hash: "hash",
    budget: {},
    usage: {},
    report_text: "# Research report\n\nFinance approval is required.",
    evidence: [
      {
        chunk_id: "chunk-1",
        document_title: "Vendor Payment Policy",
        retrieval_stage: "hybrid",
        retrieval_score: 0.42,
      },
    ],
    warnings: [],
    terminal_reason: "completed",
    cancellation_requested: false,
    version: 1,
    total_cost_usd: 0,
    started_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:05:00Z",
    completed_at: "2026-09-01T00:05:00Z",
    steps: [],
    tool_invocations: [],
    approvals: [],
    checkpoints: [],
    ...overrides,
  };
}

function makeRequest(): NextRequest {
  return new NextRequest("http://localhost/api/workspaces/w/research-runs/r/export");
}

function makeParams(workspaceId = "workspace-1", runId = "run-1") {
  return { params: Promise.resolve({ workspaceId, runId }) };
}

beforeEach(() => {
  getResearchRun.mockReset();
});

describe("GET /api/workspaces/[workspaceId]/research-runs/[runId]/export", () => {
  it("returns a PDF attachment for a successfully loaded run", async () => {
    getResearchRun.mockResolvedValue(baseRun());

    const response = await GET(makeRequest(), makeParams());

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("application/pdf");
    expect(response.headers.get("Content-Disposition")).toMatch(/^attachment; filename="[a-z0-9-]+\.pdf"$/);
    const body = await response.arrayBuffer();
    expect(body.byteLength).toBeGreaterThan(0);
  });

  it("propagates a non-disclosing 404 for a cross-tenant or missing run without leaking details", async () => {
    getResearchRun.mockRejectedValue(new AtlasApiError("Not found.", 404, "not_found"));

    const response = await GET(makeRequest(), makeParams());
    const payload = await response.json();

    expect(response.status).toBe(404);
    expect(payload.error.message).toBe("Not found.");
    expect(JSON.stringify(payload)).not.toMatch(/stack|trace/i);
  });

  it("returns 401 when the caller is unauthenticated", async () => {
    getResearchRun.mockRejectedValue(new AtlasApiError("Authentication is required.", 401, "unauthenticated"));

    const response = await GET(makeRequest(), makeParams());
    expect(response.status).toBe(401);
  });

  it("returns a safe generic 500 (no stack trace) for an unexpected upstream failure", async () => {
    getResearchRun.mockRejectedValue(new Error("connection reset"));

    const response = await GET(makeRequest(), makeParams());
    const payload = await response.json();

    expect(response.status).toBe(500);
    expect(payload.error.code).toBe("internal_error");
    expect(JSON.stringify(payload)).not.toContain("connection reset");
  });

  it("succeeds even when the report is not finished yet (no report_text)", async () => {
    getResearchRun.mockResolvedValue(baseRun({ report_text: null, status: "waiting_approval" }));

    const response = await GET(makeRequest(), makeParams());
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("application/pdf");
  });

  it("never includes internal budget/usage/checkpoint/tool-invocation fields in the exported allowlist", async () => {
    getResearchRun.mockResolvedValue(
      baseRun({
        budget: { max_cost_usd: 999, secret_note: "internal-only-value" },
        usage: { internal_debug_flag: true },
        tool_invocations: [{ id: "t1", input_summary: { secret: "should-not-export" } } as never],
      }),
    );

    const response = await GET(makeRequest(), makeParams());
    const body = Buffer.from(await response.arrayBuffer()).toString("latin1");

    expect(body).not.toContain("secret-note");
    expect(body).not.toContain("internal-only-value");
    expect(body).not.toContain("should-not-export");
    expect(body).not.toContain("internal_debug_flag");
  });

  it("derives a safe, non-traversal filename even from an adversarial purpose", async () => {
    getResearchRun.mockResolvedValue(baseRun({ purpose: "../../../etc/passwd", question: "" }));

    const response = await GET(makeRequest(), makeParams());
    const disposition = response.headers.get("Content-Disposition") ?? "";

    expect(disposition).not.toContain("..");
    expect(disposition).not.toContain("/");
  });
});
