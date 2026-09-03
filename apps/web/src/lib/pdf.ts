import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from "pdf-lib";

/**
 * Deterministic, dependency-light PDF export for a completed research report.
 *
 * All content is drawn as literal text via pdf-lib's `drawText`, never parsed
 * or rendered as HTML/markup, so retrieved/model-controlled content (report
 * text, document titles) cannot become executable HTML, scripts, or markup of
 * any kind — it is always rasterized to plain PDF text operators. pdf-lib
 * performs no network, filesystem, or process access, so SSRF/path-traversal/
 * command-execution surfaces are architecturally absent, not just guarded.
 */

export interface ResearchReportEvidenceRef {
  documentTitle: string;
  chunkId: string;
  stage: string | null;
  score: number | null;
}

export interface ResearchReportPdfInput {
  id: string;
  purpose: string;
  question: string;
  status: string;
  reportText: string | null;
  evidence: ResearchReportEvidenceRef[];
  totalCostUsd: number;
  configVersion: string;
  graphVersion: string;
  startedAt: string;
  completedAt: string | null;
  exportedAt: Date;
}

const PAGE_WIDTH = 612; // US Letter, points
const PAGE_HEIGHT = 792;
const MARGIN = 56;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
const FOOTER_Y = 34;

const INK = rgb(0.11, 0.11, 0.1);
const MUTED = rgb(0.44, 0.42, 0.38);
const ACCENT = rgb(0.62, 0.5, 0.24);
const LINE = rgb(0.83, 0.81, 0.75);

/**
 * Common typographic punctuation Atlas's own deterministic generators emit
 * (e.g. "chunk 0 - hybrid" uses a middle dot) has no glyph in pdf-lib's
 * StandardFonts unless the exact WinAnsi/CP1252 codepoint is used. Rather
 * than special-case font encoding, we normalize these to their plain-ASCII
 * equivalent up front — cleaner output than a replacement character, and it
 * keeps every downstream character within the guaranteed-safe ASCII range.
 */
const TYPOGRAPHIC_ASCII_EQUIVALENTS: Record<string, string> = {
  "·": "-", // middle dot
  "•": "-", // bullet
  "–": "-", // en dash
  "—": "-", // em dash
  "‘": "'",
  "’": "'",
  "“": '"',
  "”": '"',
  "…": "...",
};

/**
 * pdf-lib's built-in StandardFonts only guarantee WinAnsi-safe glyphs.
 * Rather than embed a Unicode font (a real dependency-weight decision — see
 * the learning notes), we deliberately degrade unsupported characters to
 * `?` so export can never throw on unexpected input. This keeps the whole
 * pipeline dependency-free and crash-proof for the zero-cost, English/ASCII
 * deterministic content Atlas actually produces today.
 */
export function sanitizeTextForPdf(input: string): string {
  let out = "";
  for (const ch of input) {
    const mapped = TYPOGRAPHIC_ASCII_EQUIVALENTS[ch];
    if (mapped !== undefined) {
      out += mapped;
      continue;
    }
    const code = ch.codePointAt(0) ?? 0;
    if (ch === "\n" || ch === "\t") {
      out += " ";
    } else if (code >= 0x20 && code <= 0x7e) {
      out += ch;
    } else {
      out += "?";
    }
  }
  return out;
}

/** Safe, path-traversal-proof filename derived from user/model-controlled text. */
export function sanitizeExportFilename(input: string, fallback = "atlas-research-report"): string {
  const ascii = sanitizeTextForPdf(input).toLowerCase();
  const slug = ascii
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
  return slug || fallback;
}

function wrapLine(text: string, font: PDFFont, fontSize: number, maxWidth: number): string[] {
  if (text.length === 0) return [""];
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (font.widthOfTextAtSize(candidate, fontSize) <= maxWidth) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    if (font.widthOfTextAtSize(word, fontSize) <= maxWidth) {
      current = word;
    } else {
      // Hard-break a single "word" too long to fit (e.g. a long id or URL)
      // so it can never overflow the page or stall wrapping.
      let chunk = "";
      for (const char of word) {
        const attempt = chunk + char;
        if (font.widthOfTextAtSize(attempt, fontSize) <= maxWidth || chunk.length === 0) {
          chunk = attempt;
        } else {
          lines.push(chunk);
          chunk = char;
        }
      }
      current = chunk;
    }
  }
  if (current) lines.push(current);
  return lines;
}

class ReportWriter {
  doc: PDFDocument;
  page: PDFPage;
  y: number;
  pageNumber = 1;
  regular: PDFFont;
  bold: PDFFont;
  italic: PDFFont;
  footerNote: string;

  constructor(doc: PDFDocument, regular: PDFFont, bold: PDFFont, italic: PDFFont, footerNote: string) {
    this.doc = doc;
    this.regular = regular;
    this.bold = bold;
    this.italic = italic;
    this.footerNote = footerNote;
    this.page = doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
    this.y = PAGE_HEIGHT - MARGIN;
    this.drawFooter();
  }

  private drawFooter(): void {
    this.page.drawText(this.footerNote, {
      x: MARGIN,
      y: FOOTER_Y,
      size: 8,
      font: this.regular,
      color: MUTED,
    });
    const pageLabel = `Page ${this.pageNumber}`;
    const width = this.regular.widthOfTextAtSize(pageLabel, 8);
    this.page.drawText(pageLabel, {
      x: PAGE_WIDTH - MARGIN - width,
      y: FOOTER_Y,
      size: 8,
      font: this.regular,
      color: MUTED,
    });
  }

  private newPage(): void {
    this.page = this.doc.addPage([PAGE_WIDTH, PAGE_HEIGHT]);
    this.pageNumber += 1;
    this.y = PAGE_HEIGHT - MARGIN;
    this.drawFooter();
  }

  private ensureSpace(height: number): void {
    if (this.y - height < MARGIN + 24) {
      this.newPage();
    }
  }

  spacer(height: number): void {
    this.ensureSpace(height);
    this.y -= height;
  }

  rule(): void {
    this.ensureSpace(12);
    this.page.drawLine({
      start: { x: MARGIN, y: this.y },
      end: { x: PAGE_WIDTH - MARGIN, y: this.y },
      thickness: 0.75,
      color: LINE,
    });
    this.y -= 14;
  }

  heading(text: string, size: number, color = INK): void {
    const clean = sanitizeTextForPdf(text);
    const lines = wrapLine(clean, this.bold, size, CONTENT_WIDTH);
    for (const line of lines) {
      this.ensureSpace(size + 6);
      this.page.drawText(line, { x: MARGIN, y: this.y, size, font: this.bold, color });
      this.y -= size + 6;
    }
  }

  paragraph(text: string, options: { size?: number; font?: PDFFont; color?: [number, number, number]; leading?: number } = {}): void {
    const size = options.size ?? 10.5;
    const font = options.font ?? this.regular;
    const color = options.color ? rgb(...options.color) : INK;
    const leading = options.leading ?? size + 4;
    const clean = sanitizeTextForPdf(text);
    const lines = wrapLine(clean, font, size, CONTENT_WIDTH);
    for (const line of lines) {
      this.ensureSpace(leading);
      this.page.drawText(line, { x: MARGIN, y: this.y, size, font, color });
      this.y -= leading;
    }
  }

  bullet(text: string): void {
    const size = 10.5;
    const leading = size + 4;
    const indent = 14;
    const clean = sanitizeTextForPdf(text);
    const lines = wrapLine(clean, this.regular, size, CONTENT_WIDTH - indent);
    lines.forEach((line, index) => {
      this.ensureSpace(leading);
      if (index === 0) {
        this.page.drawText("-", { x: MARGIN, y: this.y, size, font: this.regular, color: ACCENT });
      }
      this.page.drawText(line, { x: MARGIN + indent, y: this.y, size, font: this.regular, color: INK });
      this.y -= leading;
    });
  }

  /** Renders the free-text report body with light, safe structure: lines
   * starting with `#` become headings, lines starting with `-`/`*` become
   * bullets — everything else is a wrapped paragraph. No markup is parsed
   * or interpreted; this is purely a per-line font/size choice. */
  reportBody(text: string): void {
    const rawLines = text.split(/\r?\n/);
    for (const rawLine of rawLines) {
      const line = rawLine.trim();
      if (line.length === 0) {
        this.spacer(8);
        continue;
      }
      const headingMatch = /^(#{1,6})\s+(.*)$/.exec(line);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const size = level === 1 ? 15 : level === 2 ? 13 : 11.5;
        this.spacer(4);
        this.heading(headingMatch[2], size);
        continue;
      }
      if (/^[-*]\s+/.test(line)) {
        this.bullet(line.replace(/^[-*]\s+/, ""));
        continue;
      }
      this.paragraph(line);
    }
  }
}

function formatTimestamp(date: Date): string {
  return `${date.toISOString().slice(0, 19).replace("T", " ")} UTC`;
}

function formatMaybeTimestamp(value: string | null): string {
  if (!value) return "n/a";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "n/a" : formatTimestamp(parsed);
}

export async function buildResearchReportPdf(input: ResearchReportPdfInput): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  doc.setTitle(sanitizeTextForPdf(input.question || input.purpose || "Atlas research report"));
  doc.setProducer("Atlas AI");
  doc.setCreator("Atlas AI research export");
  doc.setCreationDate(input.exportedAt);
  doc.setModificationDate(input.exportedAt);

  const regular = await doc.embedFont(StandardFonts.Helvetica);
  const bold = await doc.embedFont(StandardFonts.HelveticaBold);
  const italic = await doc.embedFont(StandardFonts.HelveticaOblique);

  const footerNote = "Atlas AI - zero-cost local research export";
  const writer = new ReportWriter(doc, regular, bold, italic, footerNote);

  writer.paragraph("ATLAS AI - RESEARCH REPORT", { size: 9, font: bold, color: [0.62, 0.5, 0.24], leading: 20 });
  writer.heading(input.question || "Untitled research question", 18);
  if (input.purpose) {
    writer.spacer(2);
    writer.paragraph(input.purpose, { size: 11, font: italic, color: [0.44, 0.42, 0.38] });
  }
  writer.spacer(10);
  writer.paragraph(
    `Status: ${input.status}    Cost: $${input.totalCostUsd.toFixed(2)}    Exported: ${formatTimestamp(input.exportedAt)}`,
    { size: 8.5, color: [0.44, 0.42, 0.38] },
  );
  writer.paragraph(
    `Started: ${formatMaybeTimestamp(input.startedAt)}    Completed: ${formatMaybeTimestamp(input.completedAt)}`,
    { size: 8.5, color: [0.44, 0.42, 0.38] },
  );
  writer.paragraph(`Run ${input.id}  -  workflow ${input.configVersion} / ${input.graphVersion}`, {
    size: 8,
    font: regular,
    color: [0.55, 0.53, 0.48],
  });
  writer.spacer(6);
  writer.rule();

  const body = input.reportText?.trim();
  if (body) {
    writer.reportBody(body);
  } else {
    writer.paragraph(
      "This research run has not produced a report yet. Export it again once synthesis completes.",
      { font: italic, color: [0.44, 0.42, 0.38] },
    );
  }

  if (input.evidence.length > 0) {
    writer.spacer(10);
    writer.rule();
    writer.heading("Evidence & sources", 13);
    writer.spacer(2);
    input.evidence.forEach((item, index) => {
      const stage = item.stage ? ` - ${item.stage}` : "";
      const score = item.score !== null ? ` - score ${item.score.toFixed(3)}` : "";
      writer.bullet(`${index + 1}. ${item.documentTitle}${stage}${score}`);
      writer.paragraph(`chunk ${item.chunkId}`, { size: 8.5, color: [0.55, 0.53, 0.48], leading: 12 });
    });
  }

  return doc.save();
}
