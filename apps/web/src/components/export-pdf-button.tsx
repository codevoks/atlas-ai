"use client";

import { useState } from "react";

interface ExportPdfButtonProps {
  workspaceId: string;
  runId: string;
}

type ExportState = "idle" | "pending" | "error";

export function ExportPdfButton({ workspaceId, runId }: ExportPdfButtonProps) {
  const [state, setState] = useState<ExportState>("idle");

  async function handleExport() {
    setState("pending");
    try {
      const response = await fetch(
        `/api/workspaces/${workspaceId}/research-runs/${runId}/export`,
      );
      if (!response.ok) {
        throw new Error(`Export failed with status ${response.status}`);
      }
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const filenameMatch = /filename="([^"]+)"/.exec(disposition);
      const filename = filenameMatch?.[1] ?? "atlas-research-report.pdf";

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  return (
    <button
      aria-live="polite"
      className="button ghost small"
      disabled={state === "pending"}
      onClick={handleExport}
      type="button"
    >
      {state === "pending" ? "Exporting…" : state === "error" ? "Export failed — retry" : "Export PDF"}
    </button>
  );
}
