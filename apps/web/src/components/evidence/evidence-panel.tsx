"use client";

import { useEffect } from "react";

import { CopyableId } from "@/components/copyable-id";
import { CloseIcon } from "@/components/icons";
import type { EvidenceDetail } from "@/components/evidence/types";

interface EvidencePanelProps {
  evidence: EvidenceDetail;
  onClose: () => void;
}

export function EvidencePanel({ evidence, onClose }: EvidencePanelProps) {
  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const verified = evidence.status === "verified" || evidence.status === "resolved";

  return (
    <>
      <button
        aria-label="Close evidence panel"
        className="evidence-scrim"
        onClick={onClose}
        type="button"
      />
      <aside aria-label="Evidence detail" className="evidence-panel" role="dialog">
        <div className="evidence-panel-header">
          <div>
            <p className="eyebrow" style={{ marginBottom: 4 }}>
              Citation {evidence.marker}
            </p>
            <h2 className="display-3" style={{ fontSize: "1.2rem" }}>
              {evidence.documentTitle}
            </h2>
          </div>
          <button className="button ghost icon" onClick={onClose} type="button">
            <CloseIcon />
          </button>
        </div>
        <div className="evidence-panel-body">
          <span className={`pill ${verified ? "verified" : "danger"} dot`} style={{ width: "fit-content" }}>
            {evidence.status}
          </span>

          <div>
            <p className="eyebrow" style={{ marginBottom: 10 }}>
              Cited passage
            </p>
            <p className="evidence-passage">{highlightedPassage(evidence)}</p>
          </div>

          <div>
            <p className="eyebrow" style={{ marginBottom: 4 }}>
              Provenance
            </p>
            <div className="evidence-meta-list">
              {evidence.sourceName ? (
                <MetaRow label="Source" value={evidence.sourceName} />
              ) : null}
              {evidence.chunkOrdinal !== null ? (
                <MetaRow label="Chunk" value={`#${evidence.chunkOrdinal}`} />
              ) : null}
              {evidence.retrievalStage ? (
                <MetaRow label="Retrieval stage" value={evidence.retrievalStage} />
              ) : null}
              {evidence.rank !== null ? <MetaRow label="Evidence rank" value={String(evidence.rank)} /> : null}
              {evidence.semanticScore !== null ? (
                <MetaRow label="Semantic score" value={evidence.semanticScore.toFixed(3)} />
              ) : null}
              {evidence.lexicalScore !== null ? (
                <MetaRow label="Lexical score" value={evidence.lexicalScore.toFixed(3)} />
              ) : null}
              {evidence.rrfScore !== null ? (
                <MetaRow label="RRF score" value={evidence.rrfScore.toFixed(3)} />
              ) : null}
              {evidence.embeddingModel ? (
                <MetaRow
                  label="Embedding model"
                  value={`${evidence.embeddingModel}@${evidence.embeddingModelVersion}`}
                />
              ) : null}
              {evidence.parserName ? (
                <MetaRow label="Parser" value={`${evidence.parserName}@${evidence.parserVersion}`} />
              ) : null}
              {evidence.chunkerName ? (
                <MetaRow label="Chunker" value={`${evidence.chunkerName}@${evidence.chunkerVersion}`} />
              ) : null}
            </div>
          </div>

          <div>
            <p className="eyebrow" style={{ marginBottom: 8 }}>
              Identifiers
            </p>
            <div className="stack" style={{ gap: 4 }}>
              <CopyableId label="chunk" value={evidence.chunkId} />
              <CopyableId label="document" value={evidence.documentId} />
              <CopyableId label="version" value={evidence.documentVersionId} />
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="evidence-meta-row">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function highlightedPassage(evidence: EvidenceDetail): React.ReactNode {
  if (!evidence.chunkText) {
    return `“${evidence.quote}”`;
  }
  const { chunkText, highlightStart, highlightEnd } = evidence;
  const validRange =
    highlightStart >= 0 && highlightEnd > highlightStart && highlightEnd <= chunkText.length;
  if (!validRange) {
    return chunkText;
  }
  return (
    <>
      {chunkText.slice(0, highlightStart)}
      <mark>{chunkText.slice(highlightStart, highlightEnd)}</mark>
      {chunkText.slice(highlightEnd)}
    </>
  );
}
