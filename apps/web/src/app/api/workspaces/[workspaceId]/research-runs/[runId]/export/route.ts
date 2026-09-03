import { NextResponse, type NextRequest } from "next/server";

import { AtlasApiError, getResearchRun } from "@/lib/api";
import { buildResearchReportPdf, sanitizeExportFilename, type ResearchReportEvidenceRef } from "@/lib/pdf";

interface RouteParams {
  params: Promise<{ workspaceId: string; runId: string }>;
}

/**
 * Server-rendered PDF export for a completed research run.
 *
 * The run is re-fetched here from the authoritative Atlas API using the
 * caller's own session (`getResearchRun` -> `apiRequest` -> `getApiToken`),
 * not trusted from client-supplied request data. That means this route
 * inherits the exact same workspace-membership/tenant-isolation boundary as
 * every other authenticated read in the app: a cross-tenant or unauthenticated
 * request fails the same non-disclosing way it would anywhere else in Atlas,
 * with no new authorization logic introduced here.
 *
 * Only an explicit allowlist of already user-visible ResearchRun fields is
 * passed into the PDF — budgets, raw tool input/output summaries, checkpoint
 * state, and other internal fields are never included.
 */
export async function GET(_request: NextRequest, { params }: RouteParams): Promise<Response> {
  const { workspaceId, runId } = await params;

  let run;
  try {
    run = await getResearchRun(workspaceId, runId);
  } catch (error) {
    if (error instanceof AtlasApiError) {
      return NextResponse.json(
        { error: { code: error.code, message: error.message } },
        { status: error.status },
      );
    }
    console.error("research report export: failed to load research run", error);
    return NextResponse.json(
      { error: { code: "internal_error", message: "The research run could not be loaded." } },
      { status: 500 },
    );
  }

  const evidence: ResearchReportEvidenceRef[] = run.evidence.map((item) => {
    const documentTitle = typeof item.document_title === "string" ? item.document_title : "Untitled document";
    const chunkId = typeof item.chunk_id === "string" ? item.chunk_id : "unknown";
    const stage = typeof item.retrieval_stage === "string" ? item.retrieval_stage : null;
    const score = typeof item.retrieval_score === "number" ? item.retrieval_score : null;
    return { documentTitle, chunkId, stage, score };
  });

  try {
    const pdfBytes = await buildResearchReportPdf({
      id: run.id,
      purpose: run.purpose,
      question: run.question,
      status: run.status,
      reportText: run.report_text,
      evidence,
      totalCostUsd: run.total_cost_usd,
      configVersion: run.config_version,
      graphVersion: run.graph_version,
      startedAt: run.started_at,
      completedAt: run.completed_at,
      exportedAt: new Date(),
    });

    const filenameStem = sanitizeExportFilename(run.purpose || run.question, "atlas-research-report");
    const filename = `${filenameStem}-${run.id.slice(0, 8)}.pdf`;

    return new NextResponse(new Uint8Array(pdfBytes), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("research report export: PDF generation failed", error);
    return NextResponse.json(
      { error: { code: "export_failed", message: "The report could not be exported as a PDF." } },
      { status: 500 },
    );
  }
}
