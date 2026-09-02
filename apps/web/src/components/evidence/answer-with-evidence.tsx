"use client";

import { useState } from "react";

import { EvidencePanel } from "@/components/evidence/evidence-panel";
import type { EvidenceDetail } from "@/components/evidence/types";

interface AnswerWithEvidenceProps {
  answerText: string;
  evidence: EvidenceDetail[];
}

export function AnswerWithEvidence({ answerText, evidence }: AnswerWithEvidenceProps) {
  const [openId, setOpenId] = useState<string | null>(null);
  const open = evidence.find((item) => item.citationId === openId) ?? null;

  const ordered = [...evidence].sort((a, b) => a.answerStartChar - b.answerStartChar);
  const nodes: React.ReactNode[] = [];
  let cursor = 0;
  ordered.forEach((item, index) => {
    if (item.answerStartChar < cursor || item.answerEndChar <= item.answerStartChar) return;
    nodes.push(answerText.slice(cursor, item.answerStartChar));
    const verified = item.status === "verified" || item.status === "resolved";
    nodes.push(
      <button
        aria-label={`Inspect citation ${item.marker}, ${item.status}`}
        className={`cite-marker${verified ? "" : " rejected"}${openId === item.citationId ? " open" : ""}`}
        key={`${item.citationId}-${index}`}
        onClick={() => setOpenId(item.citationId)}
        type="button"
      >
        {item.marker.replace(/[[\]]/g, "") || index + 1}
        <span className="cite-tooltip">
          <strong>{item.documentTitle}</strong>
          &ldquo;{truncate(item.quote, 140)}&rdquo;
        </span>
      </button>,
    );
    cursor = item.answerEndChar;
  });
  nodes.push(answerText.slice(cursor));

  return (
    <>
      <p className="answer-text enter">{nodes}</p>
      {open ? <EvidencePanel evidence={open} onClose={() => setOpenId(null)} /> : null}
    </>
  );
}

function truncate(text: string, length: number): string {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}
