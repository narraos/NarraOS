# NarraOS — Memory Architecture

**Version:** 0.1.0
**Status:** Specification — required reading before Core Infrastructure implementation
**Last Updated:** 2026-07-18
**Resolves:** Gap §1.1 in `ARCHITECTURE_APPROVAL_REPORT.md` (Vector DB / Memory Layer has no architectural home)

> This document defines what "memory" means in NarraOS, draws the boundary between it and the Database Layer, and specifies the interfaces that give the approved FAISS→Qdrant vector store an actual place in the architecture. No implementation code.

---

## 1. Why This Document Exists

`CURRENT_STATE.md` approves a vector database (FAISS now, Qdrant later) and lists "Memory Layer" as a Core Infrastructure deliverable, alongside — and separate from — "Database Layer." Neither term was previously defined in `PROJECT_ARCHITECTURE.md`, which created a real risk: two persistence systems being built in the same milestone with no boundary between them, likely to overlap or duplicate responsibility. This document draws that boundary before any of that code is written.

---

## 2. Core Distinction: Memory Layer vs. Database Layer

These are **not** two names for the same thing. They store fundamentally different kinds of information and answer different kinds of questions.

| | **Database Layer** (PostgreSQL) | **Memory Layer** (Vector store + facade) |
|---|---|---|
| **Answers** | "What exactly happened, and what is the current state?" | "What is similar to this, and what have we learned?" |
| **Data shape** | Structured, relational — run records, stage status, publish records, analytics numbers | Unstructured/semantic — embedded text representing content, research, feedback |
| **Query pattern** | Exact match, joins, transactional (`WHERE run_id = X`) | Similarity search (`find items semantically close to Y`) |
| **Source of truth for** | Facts: did this run happen, did this video publish, what did the analytics say (the numbers) | Recall: what does this remind us of, what worked before, what have we already researched |
| **Consistency model** | Strong (ACID) — this is the ledger | Eventually consistent is acceptable — this is a recall aid, not a ledger |
| **Backing technology** | PostgreSQL (already specified in `PROJECT_ARCHITECTURE.md` §6) | FAISS (current) → Qdrant (future), per `CURRENT_STATE.md` |

**The rule that resolves the ambiguity:** the Database Layer is always the canonical record. The Memory Layer never stores anything that isn't also, in structured form, recoverable from Postgres. A memory item is a *semantic index onto* a Postgres record, not an alternate copy of the truth. This mirrors the same principle already established for `StorageProvider` in `PROVIDER_ARCHITECTURE.md` §9: pipeline state carries a *reference*, never the payload itself. Here, a memory item carries a reference back to its canonical Postgres row.

---

## 3. Memory Taxonomy

"Memory Layer" is not one undifferentiated store. NarraOS needs four distinct kinds of memory, each with different lifetime and retrieval characteristics:

### 3.1 Working Memory (per-run, ephemeral)
The in-progress state of a single pipeline run — what stage it's on, intermediate outputs, checkpoint state for resume-after-crash. **This is not part of the Memory Layer described in this document.** It is the LangGraph orchestration engine's own checkpointing, backed by a Postgres checkpointer (per `PROVIDER_ARCHITECTURE.md` §20 / `ARCHITECTURE_APPROVAL_REPORT.md` §2.2 — still pending its own ADR). Called out here only to explicitly exclude it and prevent the same ambiguity resurfacing under a different name.

### 3.2 Episodic Memory (cross-run history)
A semantically searchable record of past runs and their content: what topic was covered, what angle was taken, what the outcome was. Backed by embeddings of run summaries, linked back to the canonical `runs` table in Postgres. Used to avoid unintentionally repeating a topic/angle and to retrieve "what did we do the last time something like this came up."

### 3.3 Semantic Knowledge (research & competitive corpus)
Embedded research material, competitor content transcripts (via `STTProvider`), and verified facts, used for retrieval-augmented generation during Topic Research and Fact Verification. This is the largest and fastest-growing store, and the primary reason Qdrant (not FAISS) is the intended long-term backend — FAISS is adequate for early volume, Qdrant is approved specifically for when this corpus outgrows an in-process index.

### 3.4 Procedural / Feedback Memory (learned patterns)
Distilled, embedded representations of *what worked* — hooks, structures, pacing patterns, topic categories, correlated with actual analytics outcomes from `AnalyticsProvider`. This is what the Feedback Loop stage writes and what Virality Prediction and Retention Optimization read. It is the mechanism, described narratively in `ROADMAP.md` Phase 3, that actually closes the feedback loop — this document gives it a concrete architectural home.

---

## 4. Placement in the System Architecture

Updating `PROJECT_ARCHITECTURE.md` §2's Layer 1 (Foundation Services) — this is the missing piece:

```
LAYER 1 — FOUNDATION SERVICES
Storage (assets) · Database (state/metadata) · Memory Layer (semantic recall) · Queue (jobs)
· Model Gateway (LLM/image/voice/video providers) · Config · Secrets · Observability
```

The Memory Layer sits alongside, not inside, the Database Layer. It is composed of two provider-level components, both governed by `PROVIDER_ARCHITECTURE.md`'s existing rules:

- `EmbeddingProvider` (already specified in `PROVIDER_ARCHITECTURE.md` §11) — generates vectors from text.
- `VectorStoreProvider` (**new**, specified below in §5) — stores and retrieves vectors.

A `MemoryStore` facade (§6) sits above both and is what pipeline stages/agents actually depend on — they do not call `EmbeddingProvider` or `VectorStoreProvider` directly, for the same reason stages don't call raw LLM providers directly (Provider Architecture §14 DI principle: depend on the narrowest interface that expresses the need).

---

## 5. VectorStoreProvider (new provider type)

Per the extension process defined in `PROVIDER_ARCHITECTURE.md` §19.2, this is a genuinely new provider category — vector storage/retrieval is a distinct capability from embedding generation, and swapping FAISS → Qdrant must not require touching `EmbeddingProvider` or any calling code.

```
VectorStoreProvider extends BaseProvider:
  upsert(namespace: str, items: List[VectorRecord]) -> None
  query(namespace: str, vector: EmbeddingVector, top_k: int, filters: MetadataFilter) -> List[ScoredRecord]
  delete(namespace: str, ids: List[str]) -> None
  delete_by_filter(namespace: str, filters: MetadataFilter) -> int      # required for §8 redaction/erasure
  create_namespace(namespace: str, dimensions: int) -> None
  namespace_stats(namespace: str) -> NamespaceStats
```

- `VectorRecord` = `{id, vector, metadata}`, where `metadata` **must** include a reference back to the canonical Postgres row (§2 rule) plus the `model_identifier()` (from `EmbeddingProvider`, per `PROVIDER_ARCHITECTURE.md` §11) that produced the vector — required for the re-embedding strategy in §7.
- `namespace` maps to the four memory kinds in §3 (e.g., `episodic`, `semantic-research`, `semantic-competitor`, `procedural-feedback`) — kept as separate namespaces rather than one undifferentiated index, so retrieval for one purpose (e.g., "what worked before") never accidentally surfaces irrelevant results from another (e.g., raw competitor transcripts).
- This interface is intentionally identical in shape whether FAISS or Qdrant backs it — that's what makes the approved FAISS→Qdrant migration a configuration and provider-registration change (per `PROVIDER_ARCHITECTURE.md` §14), not a rewrite.

---

## 6. MemoryStore Facade

The actual dependency stages and agents take:

```
MemoryStore:
  remember(kind: MemoryKind, content: str, source_ref: PostgresRef, metadata: dict) -> MemoryRef
  recall(kind: MemoryKind, query: str, top_k: int, filters: dict) -> List[MemoryResult]
  forget(kind: MemoryKind, source_ref: PostgresRef) -> None
  forget_by_filter(kind: MemoryKind, filters: dict) -> int
```

- `remember()` internally calls `EmbeddingProvider.embed()` then `VectorStoreProvider.upsert()` — calling stages never touch either provider directly, and never construct vectors themselves.
- `source_ref` is mandatory on `remember()` — this enforces the §2 rule structurally (a memory item literally cannot be created without a canonical Postgres reference) rather than relying on convention.
- `forget()` / `forget_by_filter()` exist as first-class operations, not an afterthought — see §8.

---

## 7. Embedding Model Versioning & Re-embedding

Because `VectorRecord.metadata` carries `model_identifier()`, the Memory Layer can detect when a stored vector was produced by a since-superseded embedding model (e.g., after an `EmbeddingProvider` config change per `PROVIDER_ARCHITECTURE.md` §15). Policy:

- Mixed-model vectors are never compared directly in a single `query()` call — `namespace_stats()` reports model-version distribution so this is detectable rather than silently producing degraded similarity results.
- Re-embedding is a deliberate, tracked operation (batch job reading canonical Postgres rows and re-running `remember()`), not an automatic background process — given the volume risk flagged for the semantic knowledge store (§3.3), uncontrolled automatic re-embedding could be a meaningful, silent cost.

---

## 8. Retention, Redaction, and Right-to-Erasure

This is not a generic engineering nicety in NarraOS's case — it connects directly to the still-open Compliance/Risk gap (`ARCHITECTURE_APPROVAL_REPORT.md` §1.2). The approved content niche (Scams, Corporate Crimes) means memory will contain embedded text referencing real, named individuals and organizations.

- `forget_by_filter()` (§5, §6) exists specifically so that if a legal/compliance action requires removing all memory associated with a particular subject, source, or run, it can be done as a single filtered operation rather than requiring a manual audit of the entire vector store.
- Deleting a canonical Postgres record **must** cascade to deleting its associated memory items (via `source_ref`) — the Memory Layer must never outlive the canonical record it was derived from. This is a hard rule, not a best-effort cleanup task, precisely because of the defamation/compliance exposure already flagged for this project.
- Retention windows per namespace (§5) are an open configuration decision (§10) but the *mechanism* to enforce whatever window is chosen must exist from day one — bolting on deletion capability after the store has grown is materially harder than building it in from the start.

---

## 9. Which Stages Read/Write Which Memory Kind

| Stage | Reads | Writes |
|---|---|---|
| Trend Discovery | Procedural (past pattern performance) | — |
| Competitor Analysis | Semantic-competitor (past analyses, avoid redundant work) | Semantic-competitor (new transcripts via `STTProvider` → embedded) |
| Virality Prediction | Procedural (feedback-informed patterns) | — |
| Topic Research | Semantic-research (related past research) | Semantic-research (new research findings) |
| Fact Verification | Semantic-research (previously verified claims — avoids re-verifying the same claim from scratch) | Semantic-research (verified claim + source, tied to the audit-trail note in `ARCHITECTURE_APPROVAL_REPORT.md` §3) |
| Story Generation / Retention Optimization | Procedural (what hooks/structures performed) | — |
| Feedback Loop | Episodic (run history) + Analytics data from `AnalyticsProvider` | Procedural (distilled performance patterns), Episodic (run outcome summary) |

This table is what makes §3's taxonomy concrete rather than abstract — every pipeline stage's memory dependency is now explicit and traceable, closing the ambiguity that `ARCHITECTURE_APPROVAL_REPORT.md` §1.1 originally flagged.

---

## 10. Open Items Not Resolved by This Document

- Specific retention windows per namespace (e.g., how long raw competitor transcripts are kept before summarization-and-deletion) — an ADR-level decision, not architecture-level.
- Exact embedding dimensionality and chosen embedding model — depends on the `EmbeddingProvider` implementation selected (`PROVIDER_ARCHITECTURE.md` §20 already flags provider vendor selection as ADR-level).
- FAISS-to-Qdrant migration procedure/timing — a runbook (`docs/runbooks/`), not an architecture document, once the migration is actually scheduled.
- Whether Working Memory's LangGraph checkpointer (§3.1) shares the same Postgres instance as the Database Layer or a logically separate one — this remains part of the still-pending orchestration-engine ADR (`ARCHITECTURE_APPROVAL_REPORT.md` §2.2).

---

*This document, together with `PROVIDER_ARCHITECTURE.md`, closes Gap §1.1 and Gap §1.3 from `ARCHITECTURE_APPROVAL_REPORT.md`. Remaining before Core Infrastructure implementation: the Compliance/Risk Review stage design (§1.2) and the YouTube quota strategy inside the Publishing `PlatformAdapter` (§1.4).*
