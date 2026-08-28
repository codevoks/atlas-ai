# System-design visuals

These diagrams summarize the system architecture; the prose specifications remain authoritative. A boundary or flow change must update both the diagram and its owning design document.

## 1. System context, ownership, and trust boundaries

```mermaid
flowchart LR
    User[Workspace user] -->|HTTPS| Browser[Browser\nuntrusted client]
    Browser -->|session and BFF requests| Web[Next.js web and BFF]
    Web -->|service-authenticated HTTPS| API[FastAPI\ncontrol and query plane]
    Web -.->|OIDC| IdP[Identity provider]

    subgraph Atlas[Atlas service boundary]
        Web
        API
        Worker[Worker fleet\ndurable processing]
        DB[(PostgreSQL\nauthoritative state and exact vector baseline)]
        Redis[(Redis\nephemeral coordination)]
        API -->|transactions and retrieval| DB
        API -->|publish or claim durable intent| Worker
        API -->|cache and rate coordination| Redis
        Worker -->|leases, checkpoints, derived data| DB
        Worker -->|coordination only| Redis
    end

    API -->|signed operations and metadata| Objects[(Object storage\nimmutable source blobs)]
    Worker -->|stream source and artifacts| Objects
    API -->|typed generation and retrieval calls| Models[Provider adapters\nlocal fakes by default]
    Worker -->|embedding and model batches| Models
    Worker -->|isolated input| Parser[Parser sandbox\nuntrusted file boundary]
    API -->|redacted signals| Obs[OpenTelemetry\nlocal/no-export default]
    Worker -->|redacted signals| Obs

    classDef authority fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    classDef untrusted fill:var(--viz-series-2),color:var(--foreground),stroke:var(--border);
    classDef external fill:var(--muted),color:var(--foreground),stroke:var(--border);
    class DB authority;
    class Browser,Parser untrusted;
    class IdP,Objects,Models,Obs external;
```

The database decides tenant, membership, document publication, job, budget, and approval truth. Object storage is authoritative for blob bytes but never authorization. Redis, caches, embeddings, and later search projections must be recoverable from durable state.

## 1A. Zero-cost default execution path

```mermaid
flowchart TB
    Dev[Developer workstation] --> Web[Next.js web]
    Dev --> API[FastAPI API]
    Dev --> Worker[Worker]

    Web --> API
    API --> PG[(Local PostgreSQL)]
    Worker --> PG
    API --> FS[(Local filesystem\nobject-store adapter)]
    Worker --> FS
    API --> FakeAI[Deterministic provider fakes\nfor embeddings, generation, judges, tools]
    Worker --> FakeAI
    API --> LocalOTel[OpenTelemetry SDK\nlocal/no-export default]
    Worker --> LocalOTel

    FakeAI -. explicit opt-in only .-> PaidAI[Paid/hosted model APIs]
    FS -. explicit opt-in only .-> CloudStorage[Cloud object storage]
    LocalOTel -. explicit opt-in only .-> HostedObs[Hosted observability]

    classDef local fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    classDef optin fill:var(--muted),color:var(--foreground),stroke:var(--border),stroke-dasharray: 4 4;
    class Web,API,Worker,PG,FS,FakeAI,LocalOTel local;
    class PaidAI,CloudStorage,HostedObs optin;
```

The product gate runs through the local path. Optional hosted providers preserve production-grade architecture, but they are disabled by default and require explicit approval before any billable execution.

## 1B. Phase 1 implemented auth, tenancy, and RBAC slice

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant W as Next.js web/BFF
    participant A as FastAPI API
    participant P as Policy/use cases
    participant D as PostgreSQL

    U->>W: Choose local dev identity or OIDC session
    W->>W: Store/resolve API token server-side
    W->>A: Bearer token + request ID
    A->>A: Verify issuer, audience, expiry, subject, email
    A->>D: Resolve user by issuer + subject
    U->>W: Create workspace
    W->>A: POST /v1/workspaces + Idempotency-Key
    A->>P: create_workspace(actor, name, key)
    P->>D: Transaction: idempotency lock and replay check
    P->>D: Insert workspace, owner membership, audit event, idempotency record
    A-->>W: Workspace with owner role
    U->>W: Manage members or rename workspace
    W->>A: Workspace-scoped command
    A->>P: Load active membership and require named permission
    P->>D: Tenant-scoped mutation + audit; reject last-owner loss
    A-->>W: Success or stable error envelope
```

```mermaid
flowchart LR
    Browser[Browser\nuntrusted IDs and forms]
    Web[Next.js BFF\nsession UX and typed API client]
    API[FastAPI\ncurrent actor and use cases]
    Policy[RBAC policy\nnamed permissions]
    Repo[SQLAlchemy repositories\ntenant-scoped queries]
    DB[(PostgreSQL\nusers workspaces memberships audits idempotency)]

    Browser -->|forms/navigation| Web
    Web -->|Bearer token, no-store fetch| API
    API -->|IdentityClaims -> Actor| DB
    API --> Policy
    Policy --> Repo
    Repo --> DB

    classDef untrusted fill:var(--viz-series-2),color:var(--foreground),stroke:var(--border);
    classDef trusted fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    class Browser untrusted;
    class API,Policy,Repo,DB trusted;
```

Phase 1 proves the control-plane boundary before any document, retrieval, or AI state exists. Browser-supplied workspace IDs never grant authority by themselves; membership lookup plus policy decides access.

## 1B. Phase 2 implemented storage and metadata-ingestion slice

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant W as Next.js web/BFF
    participant A as FastAPI API
    participant O as Local object-store adapter
    participant D as PostgreSQL
    participant K as Worker

    U->>W: Create source and choose file
    W->>W: Compute SHA-256 digest server-side
    W->>A: POST /v1/workspaces/{id}/uploads
    A->>D: Authorize document:create and persist upload intent
    A-->>W: HMAC signed PUT URL and tenant-prefixed object key
    W->>A: PUT /v1/uploads/{intent}/content?token=...
    A->>A: Verify token, expiry, size, media type, digest
    A->>O: Store immutable bytes under workspace prefix
    A->>D: Mark upload intent uploaded
    W->>A: POST finalize + Idempotency-Key
    A->>O: Verify stored object metadata
    A->>D: Transaction: document, version, job, events, idempotency
    A-->>W: Document, version, and pending job status
    K->>D: Claim job with lease and expected version
    K->>O: HEAD object and verify digest/size
    K->>D: Publish document version atomically as READY
    W->>A: Poll document/job status
    A->>D: Read authoritative status
```

```mermaid
stateDiagram-v2
    [*] --> Pending: upload intent created
    Pending --> Uploaded: signed PUT verified
    Uploaded --> Finalized: document version and job created
    Pending --> Expired: expiry reached before upload/finalize

    state "Ingestion job" as Job {
        [*] --> JobPending
        JobPending --> Claimed: lease acquired
        Claimed --> Verifying: expected version matched
        Verifying --> Parsing: object digest and size matched
        Parsing --> Normalizing: supported text extracted
        Normalizing --> Chunking: normalized artifact stored
        Chunking --> Embedding: deterministic chunks prepared
        Embedding --> Publishing: complete embedding set coverage
        Publishing --> Succeeded: chunks, embeddings, and version marked READY
        Verifying --> Failed: missing or corrupt object
        Parsing --> Failed: unsupported, binary, invalid UTF-8, or oversized input
        Chunking --> Failed: chunk limits exceeded
        JobPending --> CancelRequested: user cancel
        Claimed --> CancelRequested: user cancel
        CancelRequested --> Cancelled: cooperative worker stop
        Failed --> JobPending: authorized retry
    }
```

Phase 2 uses API-hosted local signed upload handling for development. The adapter boundary preserves the production design: later S3-compatible storage replaces the local adapter without changing the document or ingestion state model.

## 1C. Phase 5 implemented parsing, chunking, embedding, and hybrid retrieval slice

```mermaid
sequenceDiagram
    autonumber
    participant K as Worker
    participant O as Local object-store adapter
    participant P as Text parser
    participant N as Normalizer
    participant C as Chunker
    participant E as Deterministic embedding provider
    participant D as PostgreSQL

    K->>D: Claim pending ingestion job lease
    K->>O: Read uploaded object bytes
    K->>K: Verify size, digest, media type, and binary signatures
    K->>P: Parse allowlisted text/Markdown input
    P-->>K: Typed blocks or safe validation failure
    K->>N: Normalize Unicode, newlines, and whitespace
    K->>O: Store normalized derived artifact under workspace prefix
    K->>C: Build deterministic bounded chunks
    K->>E: Embed chunks in bounded zero-cost batches
    E-->>K: Normalized vectors with model/version/dimension provenance
    K->>D: Transaction: replace version chunks, persist embeddings/provenance/counts, mark version READY and job SUCCEEDED
```

```mermaid
flowchart LR
    Upload[Uploaded object\nworkspace-prefixed bytes]
    Verify[Integrity and type verification]
    Reject[Safe failed job\nno ready version]
    Parsed[Parsed blocks\nheadings and paragraphs]
    Normalized[Normalized artifact\nSHA-256 addressed]
    Chunks[Chunk rows\nordinal span hash text metadata]
    Embeddings[Chunk embeddings\nprovider model version dimension]
    Search[Semantic evidence\nscores snippets trace ID]
    Ready[Ready document version\nparser chunker embedding provenance]

    Upload --> Verify
    Verify -->|unsupported binary PDF archive invalid UTF-8 oversized| Reject
    Verify -->|supported text or Markdown| Parsed
    Parsed --> Normalized
    Normalized --> Chunks
    Chunks --> Embeddings
    Embeddings --> Ready
    Ready --> Search
```

Phase 5 publishes chunks and embeddings only inside the final database transaction. Partial parser/chunker/embedding output is never visible as a ready document version. Semantic, lexical, and hybrid search return evidence only; answer generation remains deferred.

## 1D. Phase 5 hybrid retrieval flow

```mermaid
flowchart LR
    Query[Validated query\nmode and safe filters]
    Auth[Workspace membership\nand document:read policy]
    Semantic[Semantic branch\nlocal deterministic embedding\nexact cosine over ready embeddings]
    Lexical[Lexical branch\nPostgreSQL FTS\nGIN expression index]
    Policy[Identical tenant/status/filter predicates\ninside each branch]
    Fuse[RRF fusion\nchunk + version dedup]
    Evidence[Typed evidence\nsnippet scores ranks trace]
    Debug[Redacted diagnostics\nconfig branch counts ranks]

    Query --> Auth
    Auth --> Policy
    Policy --> Semantic
    Policy --> Lexical
    Semantic --> Fuse
    Lexical --> Fuse
    Fuse --> Evidence
    Fuse --> Debug
```

Hybrid retrieval keeps lexical and semantic candidate generation as separate ranked lists, then fuses ranks with RRF rather than mixing raw branch scores. This makes exact-term/entity matches and semantic paraphrase matches visible through one deterministic evidence API while preserving branch provenance for debugging.

## 1E. Phase 6 grounded answer and citation validation flow

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant W as Next.js web/BFF
    participant A as FastAPI answer orchestrator
    participant R as Hybrid retrieval
    participant C as Context builder
    participant G as Deterministic generator
    participant V as Citation validator
    participant D as PostgreSQL

    U->>W: Ask question in workspace
    W->>A: POST /v1/workspaces/{id}/answers
    A->>D: Resolve active membership and document:read permission
    A->>R: Retrieve semantic/lexical/hybrid candidates with tenant filters
    R-->>A: Typed evidence with chunk/version identity
    A->>C: Build bounded context from untrusted evidence
    C-->>A: Context package and warnings
    A->>G: Generate structured answer from evidence only
    G-->>A: Answer text plus citation drafts
    A->>V: Validate markers, evidence IDs, quotes, and spans
    V-->>A: Verified citations or fail-closed error
    A->>D: Persist answer run, frozen evidence, citations, provenance
    A-->>W: Grounded answer with verified citations
```

```mermaid
flowchart LR
    Evidence[Retrieved evidence\nuntrusted text]
    Context[Budgeted context\nranked excerpts]
    Generator[Deterministic local generator\nno network or tools]
    Draft[Structured answer\ncitation drafts]
    Validator[Citation validator\nallowlist + quote/span checks]
    Refusal[No-evidence refusal]
    Store[(PostgreSQL\nanswer_runs answer_evidence citations)]
    UI[Answer UI\nverified citations and provenance]

    Evidence --> Context
    Context -->|no evidence| Refusal
    Context -->|evidence available| Generator
    Generator --> Draft
    Draft --> Validator
    Validator -->|verified| Store
    Refusal --> Store
    Store --> UI
```

Phase 6 proves the answer/citation integrity boundary before introducing hosted LLMs, streaming, tools, or agentic workflows. Prompts remain implementation details; authorization and citation truth come from typed evidence and persisted validation.

## 2. Durable ingestion and atomic publication

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant A as API
    participant O as Object storage
    participant D as PostgreSQL
    participant W as Worker
    participant P as Parser sandbox
    participant E as Embedding provider

    U->>A: Request upload intent
    A->>D: Authorize workspace and record intent
    A-->>U: Short-lived tenant-scoped upload URL
    U->>O: Upload immutable bytes
    U->>A: Finalize with digest and idempotency key
    A->>O: Verify object metadata and digest
    A->>D: Transaction: version plus durable job
    A-->>U: 202 Accepted with status resource

    W->>D: Claim job lease
    W->>O: Stream source
    W->>P: Parse within time and resource limits
    P-->>W: Typed blocks or safe failure
    W->>D: Persist normalized chunks and provenance
    W->>E: Bounded embedding batches
    E-->>W: Per-item vectors or classified failure
    W->>D: Persist embedding-set coverage
    W->>D: Atomic publish only when complete
    U->>A: Poll status
    A->>D: Read authoritative job and version state
    A-->>U: Ready, retrying, failed, or cancelled
```

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Claimed: lease acquired
    Claimed --> Verifying
    Verifying --> Parsing
    Parsing --> Normalizing
    Normalizing --> Chunking
    Chunking --> Embedding
    Embedding --> Publishing
    Publishing --> Succeeded: complete version atomically visible

    Claimed --> RetryWait: transient failure
    Verifying --> RetryWait: transient failure
    Parsing --> RetryWait: transient failure
    Embedding --> RetryWait: transient failure
    RetryWait --> Claimed: backoff elapsed and new lease

    Pending --> Cancelled: cancellation accepted
    Claimed --> CancelRequested
    Verifying --> CancelRequested
    Parsing --> CancelRequested
    Normalizing --> CancelRequested
    Chunking --> CancelRequested
    Embedding --> CancelRequested
    CancelRequested --> Cancelled: cooperative stop

    Verifying --> Failed: permanent or exhausted
    Parsing --> Failed: permanent or exhausted
    Embedding --> Failed: permanent or exhausted
```

## 3. Retrieval, grounded generation, and citation integrity

```mermaid
flowchart LR
    Q[User query and typed filters] --> Auth[Authenticate, authorize,\nrate and budget check]
    Auth --> Spec[Workspace-scoped QuerySpec]
    Spec --> S[Semantic candidates\nPostgreSQL exact cosine baseline]
    Spec --> L[Lexical candidates\nPostgreSQL FTS]
    S --> F[RRF fusion and dedup]
    L --> F
    F --> R[Optional reranking]
    R --> C[Context builder\ntoken, diversity, provenance]
    C --> E[Typed immutable Evidence]
    E --> G[Structured generation\nevidence is untrusted data]
    G --> V[Schema, policy, citation ID\nand span validation]
    E --> V
    V -->|valid| A[Grounded answer\nwith resolvable citations]
    V -->|invalid or dependency failure| D[Safe degraded result\nor explicit failure]

    classDef trusted fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    classDef untrusted fill:var(--viz-series-2),color:var(--foreground),stroke:var(--border);
    class Auth,Spec,V trusted;
    class Q,E,G untrusted;
```

Authorization predicates execute inside every retrieval branch. A model never invents an acceptable evidence identity: validation compares its claims only with the exact evidence supplied to the run.

## 4. Immutable lineage and safe migrations

```mermaid
flowchart TB
    Source[Source] --> Document[Logical document]
    Document --> V1[Document version v1]
    Document --> V2[Document version v2]
    V1 --> C1[Chunks\nparser and chunker config A]
    V2 --> C2[Chunks\nparser and chunker config B]
    C2 --> ES1[Embedding set 1\nmodel, dimension, normalization]
    C2 --> ES2[Embedding set 2\nparallel migration]
    ES1 --> Retrieval1[Retrieval config baseline]
    ES2 --> Retrieval2[Retrieval config candidate]
    Retrieval1 --> Eval[Versioned evaluation run]
    Retrieval2 --> Eval
    Eval --> Decision{Quality, latency, cost,\nand security evidence}
    Decision -->|promote| Active[Atomic configuration promotion]
    Decision -->|reject| Rollback[Keep baseline and record result]
    Active --> Answer[Answer run]
    Answer --> Evidence[Exact chunk-version evidence]
    Evidence --> Citation[Citation and validation status]
```

Old content, vectors, and configurations coexist during migrations. Evaluation precedes promotion, and rollback remains possible until retention deliberately removes superseded derived data.

## 5. Phase 7 deterministic evaluation run

```mermaid
flowchart TB
    User[Authorized workspace member] --> API[Evaluation API]
    API --> Auth[RBAC and tenant checks]
    Auth --> Dataset[(evaluation_datasets)]
    Auth --> Version[(immutable dataset version)]
    Version --> Cases[(labeled evaluation_cases)]
    Cases --> LabelCheck[Validate relevant chunk IDs\nready, active, same workspace]
    LabelCheck --> Run[(evaluation_runs\nconfig + code revision)]
    Run --> SUT[System under test\nproduction retrieval + answer services]
    SUT --> Search[Semantic, lexical, or hybrid retrieval]
    Search --> Answer[Grounded answer + citation validator]
    Answer --> Metrics[Deterministic local metrics\nRecall, Precision, MRR, NDCG,\nanswer/citation coverage]
    Cases --> Metrics
    Metrics --> Results[(evaluation_results)]
    Results --> Aggregate[Aggregate, slice,\nand failure summaries]
    Aggregate --> Run
    Run --> Baseline[(append-only baseline approval)]

    classDef trusted fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    classDef labels fill:var(--viz-series-4),color:var(--foreground),stroke:var(--border);
    classDef untrusted fill:var(--viz-series-2),color:var(--foreground),stroke:var(--border);
    class API,Auth,LabelCheck,Metrics trusted;
    class Dataset,Version,Cases labels;
    class SUT,Search,Answer untrusted;
```

Expected labels are intentionally separated from the production retrieval and answer path. They are consumed only by the metric layer after the system-under-test has produced outputs, which prevents expected-answer leakage and keeps evaluation evidence meaningful.

## 6. Phase 8 evidence-gated query expansion

```mermaid
flowchart TB
    Client[Search, answer, or evaluation request] --> Config{Retrieval config}
    Config -->|phase5 baseline| Original[Original query only]
    Config -->|phase8 candidate| Transform[Deterministic query transformer]
    Transform --> Guard{Injection-like text?}
    Guard -->|yes| Original
    Guard -->|no| Variants[Bounded query variants\nmax 3]
    Original --> Plan[Retrieval plan executor]
    Variants --> Plan
    Plan --> Budget[Fan-out budget\nmax 6 branch queries]
    Budget --> Sem[Semantic branches\nsame tenant filters]
    Budget --> Lex[Lexical branches\nsame tenant filters]
    Sem --> Aggregate[Dedup + RRF/best-score\n+ optional diversity]
    Lex --> Aggregate
    Aggregate --> Evidence[Typed evidence\nwith query-variant provenance]
    Evidence --> Answer[Grounded answer\nor evaluation metrics]
    Evidence --> Ablation[Phase 7 evaluation run\nbaseline vs candidate]
    Ablation --> Decision{Measured slice benefit\nwithout unsafe tradeoff?}
    Decision -->|yes| Keep[Config remains enabled]
    Decision -->|no| Rollback[Use baseline config]

    classDef trusted fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    classDef untrusted fill:var(--viz-series-2),color:var(--foreground),stroke:var(--border);
    class Config,Transform,Guard,Plan,Budget,Aggregate,Decision trusted;
    class Client,Sem,Lex,Evidence,Answer,Ablation untrusted;
```

The Phase 8 transformer changes only query text used for candidate generation. It does not change workspace membership, source/document filters, citation validation, or generation policy. The baseline configuration remains available for rollback and comparison.

## 7. Phase 9 bounded research workflow

```mermaid
flowchart TB
    User[Authorized workspace member] --> API[Research API]
    API --> Auth[RBAC and tenant checks]
    Auth --> Run[(research_runs)]
    Run --> Plan[Planner node\nbounded subquestions]
    Plan --> Step1[(research_steps)]
    Plan --> Budget[Budget ledger\nsteps, tools, tokens, cost]
    Budget --> ToolPolicy{Tool policy}
    ToolPolicy -->|allowlisted| Retrieval[atlas_retrieval tool\nPhase 8 search service]
    ToolPolicy -->|allowlisted| Catalog[local_policy_catalog tool]
    ToolPolicy -->|forbidden URL/tool/prompt| Reject[Validation failure\nno tool execution]
    Retrieval --> ToolRows[(tool_invocations)]
    Catalog --> ToolRows
    Retrieval --> Evidence[Workspace evidence\nchunk/version provenance]
    Catalog --> Evidence
    Evidence --> Checkpoint[(checkpoints\nschema-versioned state)]
    Checkpoint --> Approval[(approvals\npending)]
    Approval -->|deny| Cancelled[research_runs.cancelled]
    Approval -->|approve current version| Synthesis[Synthesis node\ncited report]
    Synthesis --> Report[research_runs.succeeded\nreport + evidence]
    Checkpoint -->|resume| Plan

    classDef trusted fill:var(--viz-series-1),color:var(--foreground),stroke:var(--border);
    classDef untrusted fill:var(--viz-series-2),color:var(--foreground),stroke:var(--border);
    class API,Auth,Budget,ToolPolicy,Approval,Synthesis trusted;
    class User,Retrieval,Catalog,Evidence untrusted;
```

Phase 9 deliberately implements a single bounded workflow rather than a general autonomous assistant. The default graph uses deterministic local tools and pauses before final synthesis so evidence and tool provenance can be inspected before a report is produced.

## 8. Evidence-driven scale evolution

```mermaid
flowchart LR
    Base[Baseline\nmodular API, worker, PostgreSQL,\npgvector, object storage, Redis]
    Measure[Measure\nlatency, recall, queue age, DB load,\nprovider limits, tenant skew, cost]
    Base --> Measure
    Measure --> Bottleneck{Observed bottleneck}
    Bottleneck -->|parsing or embeddings| Pools[Separate worker pools, batching,\nquotas and backpressure]
    Bottleneck -->|DB connections or I/O| DBScale[Query and index tuning, pooling,\nreplicas and partitioning]
    Bottleneck -->|large-tenant skew| Placement[Tenant fairness and\nlarge-tenant placement]
    Bottleneck -->|search feature or SLO gap| Shadow[OpenSearch derived projection\nwith shadow comparison]
    Bottleneck -->|no material gap| Stay[Keep simpler architecture]
    Pools --> Measure
    DBScale --> Measure
    Placement --> Measure
    Shadow --> Compare{Quality, latency, cost,\noperations and recovery improve?}
    Compare -->|yes| Cutover[Controlled cutover\nwith reconciliation and rollback]
    Compare -->|no| Stay
```

Scale decisions follow the constrained resource. “Ten million documents” alone does not select an engine; tenant distribution, filters, freshness, query mix, availability, cost, and operational skill determine the design.
