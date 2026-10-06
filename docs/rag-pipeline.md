# RAG retrieval pipeline (Lane B)

How a company policy document becomes a searchable, answerable knowledge base — from upload
to grounded answer. Two paths share one vector store.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'ui-sans-serif, system-ui, sans-serif','fontSize':'13px','lineColor':'#94a3b8','clusterBkg':'#ffffff','clusterBorder':'#e2e8f0','edgeLabelBackground':'#ffffff'}}}%%
flowchart TD
    subgraph WRITE ["WRITE — ingest a policy (once)"]
        direction TB
        A["PDF upload / pasted text"] --> B["extract text"]
        B --> C["split into overlapping chunks<br/>380 words · 96 overlap"]
        C --> D["embed each chunk<br/>Gemini · 1536-d · L2-normalized"]
        D --> E[("Postgres + pgvector<br/>document · chunk · embedding")]
    end
    subgraph READ ["READ — answer a question (every query)"]
        direction TB
        Q["user question"] --> R["embed the query<br/>Gemini · 1536-d"]
        R --> S["cosine top-k search<br/>pgvector HNSW"]
        S --> T["top policy passages<br/>content · similarity · source"]
        T --> U{"search or ask?"}
        U -->|search| V["ranked passages + scores"]
        U -->|ask| W["grounded answer + citations<br/>Gemini Flash"]
    end
    E -. stored vectors .-> S
    classDef write fill:#fff7ed,stroke:#d97706,color:#7c2d12;
    classDef read fill:#eef2ff,stroke:#4f46e5,color:#1e1b4b;
    classDef store fill:#ecfeff,stroke:#0891b2,color:#164e63;
    class A,B,C,D write;
    class Q,R,S,T,U,V,W read;
    class E store;
```

## The two paths

- **Write (once per document):** a policy is uploaded, its text is split into overlapping
  chunks, each chunk is embedded into a 1536-dimension vector, and the vectors are stored in
  pgvector. This builds the index.
- **Read (every query):** a question is embedded the same way, matched against the stored
  vectors by cosine similarity, and the closest passages are returned — or, on "ask", fed to
  an LLM to produce an answer grounded only in those passages.

The search never re-reads the PDF; it reads the stored vectors. Changing a policy means
re-uploading (same filename replaces, a new filename adds alongside).

`R` = retrieval (this lane). `G` = generation, shown via `/ask` — that is Lane C's job; the
`/ask` endpoint is a scoped demo of the full loop.
