/**
 * Pure formatting helpers for "copy to clipboard" actions. Kept dependency-
 * free and side-effect-free (no `navigator.clipboard` calls here) so they
 * are trivially unit-testable; the actual clipboard write lives in
 * `components/copy-button.tsx`. Every formatter only reformats text the UI
 * already renders to the user — nothing here surfaces a field that was not
 * already visible on screen.
 */

export interface CopyableAnswer {
  query: string;
  answerText: string;
}

export function formatAnswerForClipboard({ query, answerText }: CopyableAnswer): string {
  const trimmedQuery = query.trim();
  const trimmedAnswer = answerText.trim();
  if (!trimmedQuery) return trimmedAnswer;
  return `Q: ${trimmedQuery}\n\n${trimmedAnswer}`;
}

export interface CopyableResearchReport {
  question: string;
  reportText: string;
}

export function formatReportForClipboard({ question, reportText }: CopyableResearchReport): string {
  const trimmedQuestion = question.trim();
  const trimmedReport = reportText.trim();
  if (!trimmedQuestion) return trimmedReport;
  return `${trimmedQuestion}\n\n${trimmedReport}`;
}

export interface CopyableEvidence {
  marker: string;
  status: string;
  documentTitle: string;
  sourceName: string | null;
  chunkOrdinal: number | null;
  quote: string;
  retrievalStage: string | null;
  rank: number | null;
}

export function formatEvidenceForClipboard(evidence: CopyableEvidence): string {
  const lines: string[] = [];
  lines.push(`Citation ${evidence.marker} - ${evidence.status}`);
  lines.push(evidence.documentTitle);
  const meta: string[] = [];
  if (evidence.sourceName) meta.push(evidence.sourceName);
  if (evidence.chunkOrdinal !== null) meta.push(`chunk #${evidence.chunkOrdinal}`);
  if (evidence.retrievalStage) meta.push(evidence.retrievalStage);
  if (evidence.rank !== null) meta.push(`rank ${evidence.rank}`);
  if (meta.length > 0) lines.push(meta.join(" - "));
  lines.push("");
  lines.push(`"${evidence.quote.trim()}"`);
  return lines.join("\n");
}
