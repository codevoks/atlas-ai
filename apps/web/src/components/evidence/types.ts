export interface EvidenceDetail {
  citationId: string;
  marker: string;
  status: string;
  answerStartChar: number;
  answerEndChar: number;
  documentTitle: string;
  sourceName: string | null;
  chunkOrdinal: number | null;
  chunkText: string | null;
  highlightStart: number;
  highlightEnd: number;
  quote: string;
  retrievalStage: string | null;
  retrievalScore: number | null;
  semanticScore: number | null;
  lexicalScore: number | null;
  rrfScore: number | null;
  rank: number | null;
  embeddingModel: string | null;
  embeddingModelVersion: string | null;
  parserName: string | null;
  parserVersion: string | null;
  chunkerName: string | null;
  chunkerVersion: string | null;
  chunkId: string;
  documentId: string;
  documentVersionId: string;
}
