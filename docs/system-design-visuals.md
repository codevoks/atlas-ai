# Atlas AI system-design visuals

These diagrams describe the current product architecture and runtime flows. They are intended to help developers understand component boundaries, trust boundaries, authoritative state, and operational behavior without relying on implementation-history sequencing.

## Product architecture

```mermaid
flowchart LR
    Browser[Browser UI] --> Web[Next.js web app / BFF]
    Web --> API[FastAPI control plane]
    API --> Postgres[(PostgreSQL)]
    API --> ObjectStore[(Local object-store adapter)]
    Worker[Ingestion worker] --> API
    Worker --> Postgres
    Worker --> ObjectStore

    API --> Retrieval[Retrieval services]
    Retrieval --> Postgres
    API --> AI[Deterministic local AI adapters]
    AI --> Postgres

    API --> Security[Guardrails and quota policy]
    API --> Telemetry[Local no-content telemetry]
```

## Trust and authority boundaries

```mermaid
flowchart TB
    User[User input and browser state\nuntrusted] --> Web[Web UI]
    Web -->|session only| API[API authorization boundary]
    API -->|server-derived tenant context| Domain[Domain use cases]
    Domain --> Postgres[(Authoritative tenant data)]
    Domain --> ObjectStore[(Tenant-prefixed blobs)]

    Uploaded[Uploaded files\nuntrusted] --> Parser[Parser and normalizer]
    Retrieved[Retrieved text\nuntrusted evidence] --> Generator[Grounded generator]
    Generator --> Validator[Citation and safety validator]

    Security[Guardrails] --> Domain
    Security --> Validator
```

## Ingestion and retrieval flow

```mermaid
sequenceDiagram
    participant User
    participant Web
    participant API
    participant Store as Object store
    participant DB as PostgreSQL
    participant Worker

    User->>Web: Upload text or Markdown
    Web->>API: Request signed upload intent
    API->>DB: Create source, upload intent, job metadata
    API-->>Web: Signed local upload URL
    Web->>Store: Upload bytes
    Web->>API: Finalize upload with digest
    API->>DB: Mark job ready
    Worker->>DB: Lease ready job
    Worker->>Store: Read source bytes
    Worker->>Worker: Parse, normalize, chunk, embed
    Worker->>DB: Publish version, chunks, embeddings atomically
    User->>Web: Search or ask a question
    Web->>API: Search / answer request
    API->>DB: Tenant-scoped retrieval
    API-->>Web: Evidence or citation-validated answer
```

## Grounded answer flow

```mermaid
flowchart LR
    Query[Question] --> Retrieve[Tenant-scoped hybrid retrieval]
    Retrieve --> Evidence[Typed evidence set]
    Evidence --> Context[Context builder]
    Context --> Generator[Deterministic grounded generator]
    Generator --> CitationCheck[Citation validator]
    CitationCheck --> SafetyCheck[Output guardrails]
    SafetyCheck --> Persist[Persist answer run, citations, warnings]
    Persist --> UI[Answer with verified citations]
```

## Bounded research workflow

```mermaid
stateDiagram-v2
    [*] --> Planned
    Planned --> RetrievingEvidence
    RetrievingEvidence --> Checkpointed
    Checkpointed --> AwaitingApproval
    AwaitingApproval --> Synthesizing: approved
    AwaitingApproval --> Cancelled: denied
    Synthesizing --> Completed
    RetrievingEvidence --> Failed: safe failure
    Synthesizing --> Failed: safety or citation failure
    Completed --> [*]
    Cancelled --> [*]
    Failed --> [*]
```

## Security and operations controls

```mermaid
flowchart TB
    Request[Incoming request] --> Auth[Authentication and RBAC]
    Auth --> Tenant[Tenant-scoped use case]
    Tenant --> Quota[Quota and abuse checks]
    Quota --> Guardrails[Input and content guardrails]
    Guardrails --> Work[Search, answer, research, or admin action]
    Work --> Validation[Output/citation/egress validation]
    Validation --> Response[Safe response]

    Auth --> Audit[(Audit/security events)]
    Guardrails --> Audit
    Validation --> Audit
    Work --> Metrics[Local no-content telemetry]
```
