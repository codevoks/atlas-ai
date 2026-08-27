# Requirement traceability

| Requirement family | Owning design or phase |
|---|---|
| Product/functional/non-functional/users/tenants/APIs/entities/flows/consistency/availability | Architecture, data model, Phase 0 |
| Diagram-first architecture, ingestion, RAG, lineage, and scaling explanations | System-design visuals; maintain whenever those boundaries change |
| Capacity estimates, bottlenecks, cost, 100× and 10M redesign | Capacity model, Phases 0 and 11 |
| Threat boundaries, tenancy, uploads, secrets, abuse, AI security | Threat model, every phase, consolidation in Phase 10 |
| Turborepo/pnpm, Next.js/React/TypeScript/Tailwind CSS, FastAPI/Pydantic/asyncio, SQL | Phase 1 and permanent rules |
| PostgreSQL/object storage/Redis/durable jobs | Phases 1–2; failure/data model |
| Parsing/normalization/chunking/metadata | Phase 3 |
| Embeddings/pgvector/semantic/ANN/migration | Phase 4 |
| Lexical/hybrid/RRF/filters/debug | Phase 5 |
| Reranking/context/grounding/citations | Phase 6 |
| Golden data/custom metrics/Ragas/judges/human review/regressions | Phase 7 |
| Query rewrite/multi-query/contextual retrieval/LlamaIndex if justified | Phase 8 evidence gate |
| LangGraph/tools/state/checkpoints/termination/HITL/agentic RAG | Phase 9 |
| Multi-agent patterns and reasons not to implement | Phase 9 design review; runtime evidence gate |
| Deterministic/model-assisted guardrails/adversarial tests | Every phase and Phase 10 |
| OpenAI/Anthropic/Bedrock-capable abstractions | Decisions and Phases 4/6/9; one provider initially |
| Langfuse/OpenTelemetry | Schemas/provenance early, integration Phase 11 |
| OpenSearch comparison | Phase 11 evidence gate |
| Docker/AWS/Terraform/GitHub Actions/load/DR/production hardening | Phase 11 |
| Clean code, focused resource use, product gates | Permanent rules and every phase |
| Public repository professionalism and private-material exclusion | Permanent rules, `.gitignore`, and phase gate Git-safety checks |
