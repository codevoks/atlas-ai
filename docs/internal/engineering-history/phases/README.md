# Phase specifications

Implement exactly one approved phase at a time:

0. `phase-0-system-design.md`
1. `phase-1-foundation-auth-tenancy.md`
2. `phase-2-storage-ingestion.md`
3. `phase-3-parsing-chunking.md`
4. `phase-4-embeddings-semantic.md`
5. `phase-5-hybrid-retrieval.md`
6. `phase-6-rag-citations.md`
7. `phase-7-evaluations.md`
8. `phase-8-advanced-rag.md`
9. `phase-9-agentic-research.md`
10. `phase-10-security-guardrails.md`
11. `phase-11-production-hardening.md`

Every file is a contract. If implementation evidence requires a change, update the phase file, `docs/decisions.md`, architecture/threat model as needed, and explain the tradeoff before proceeding. Never use a later phase to excuse a missing security or correctness invariant in the current phase.

All phase documents are internal engineering-history contracts. Keep them professional, implementation-grade, and free of private/personal workflow material.
