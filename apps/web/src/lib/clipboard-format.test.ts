import { describe, expect, it } from "vitest";

import {
  formatAnswerForClipboard,
  formatEvidenceForClipboard,
  formatReportForClipboard,
} from "./clipboard-format";

describe("formatAnswerForClipboard", () => {
  it("prefixes the answer with the question for context", () => {
    const result = formatAnswerForClipboard({
      query: "What approval is required for a large payment?",
      answerText: "Finance director approval is required.",
    });
    expect(result).toBe(
      "Q: What approval is required for a large payment?\n\nFinance director approval is required.",
    );
  });

  it("returns just the answer when there is no query", () => {
    expect(formatAnswerForClipboard({ query: "", answerText: "Answer only." })).toBe("Answer only.");
  });

  it("trims surrounding whitespace", () => {
    const result = formatAnswerForClipboard({ query: "  Q?  ", answerText: "  A.  " });
    expect(result).toBe("Q: Q?\n\nA.");
  });
});

describe("formatReportForClipboard", () => {
  it("prefixes the report with the research question", () => {
    const result = formatReportForClipboard({
      question: "What controls apply to vendor payments?",
      reportText: "# Research report\n\nFindings...",
    });
    expect(result).toBe("What controls apply to vendor payments?\n\n# Research report\n\nFindings...");
  });

  it("returns just the report when there is no question", () => {
    expect(formatReportForClipboard({ question: "", reportText: "Report body." })).toBe("Report body.");
  });
});

describe("formatEvidenceForClipboard", () => {
  it("formats a full citation with all optional fields present", () => {
    const result = formatEvidenceForClipboard({
      marker: "[1]",
      status: "verified",
      documentTitle: "Vendor Payment Authorization Policy",
      sourceName: "Manual uploads",
      chunkOrdinal: 0,
      quote: "Before a new vendor can receive payment...",
      retrievalStage: "hybrid",
      rank: 1,
    });
    expect(result).toBe(
      [
        "Citation [1] - verified",
        "Vendor Payment Authorization Policy",
        "Manual uploads - chunk #0 - hybrid - rank 1",
        "",
        '"Before a new vendor can receive payment..."',
      ].join("\n"),
    );
  });

  it("omits the metadata line entirely when no optional fields are present", () => {
    const result = formatEvidenceForClipboard({
      marker: "[1]",
      status: "verified",
      documentTitle: "Doc",
      sourceName: null,
      chunkOrdinal: null,
      quote: "Quote",
      retrievalStage: null,
      rank: null,
    });
    expect(result).toBe(["Citation [1] - verified", "Doc", "", '"Quote"'].join("\n"));
  });

  it("never includes raw document/chunk/version UUIDs that were not passed in", () => {
    const result = formatEvidenceForClipboard({
      marker: "[1]",
      status: "verified",
      documentTitle: "Doc",
      sourceName: "Source",
      chunkOrdinal: 2,
      quote: "Quote text",
      retrievalStage: "semantic",
      rank: 1,
    });
    expect(result).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
  });
});
