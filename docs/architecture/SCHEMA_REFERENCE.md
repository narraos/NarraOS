# NarraOS — Schema Reference (Initial)

**Version:** 0.1.0
**Status:** Specification — foundational envelope schemas only
**Last Updated:** 2026-07-18
**Scope note:** Defines only the core shared schemas — `Task`, `Result`, `Error`, `Metadata`, `Configuration`, `AgentMessage`. Domain-specific payload schemas already named across other documents (`TopicResearchInput_v1`, `ComplianceReviewOutput_v1`, `ScriptOutput_v1`, and every other per-stage/per-agent schema referenced in `AGENT_SPECIFICATIONS.md`, `COMPLIANCE_ARCHITECTURE.md`, and `PROJECT_ARCHITECTURE.md` §7) are **not** redefined here — they will be formalized during implementation, built on top of the envelope this document defines. No implementation code.

---

## 1. What These Six Schemas Are

Every domain-specific schema in NarraOS — every stage's input/output, every agent's input/output — is versioned per `DEVELOPER_HANDBOOK.md` §7, but none of them exist in isolation. They're always carried inside a common **envelope**: something dispatches a unit of work (`Task`), something comes back (`Result` or `Error`), everything is described (`Metadata`), everything was governed by some active configuration (`Configuration`), and if the work was done by an Agent, its reasoning is recorded as a sequence of (`AgentMessage`).

These six schemas are that envelope layer. They are deliberately generic — a `Task` doesn't know or care whether it's dispatching Topic Research or Thumbnail Generation. That's what makes them reusable across all 9 Agents and 10 Stages (`AGENT_SPECIFICATIONS.md` §1.1) rather than needing their own bespoke plumbing.

**Versioning convention** (per `DEVELOPER_HANDBOOK.md` §7, applied identically here): these are `Task_v1`, `Result_v1`, `Error_v1`, `Metadata_v1`, `Configuration_v1`, `AgentMessage_v1`. A breaking change to any of them is a `_v2`, never an in-place mutation.

**Location:** `core/schemas/v1/common.py`. This is an addition to `REPOSITORY_STRUCTURE.md` §2, which listed `core/schemas/v1/` files grouped by pipeline phase (`research.py`, `story.py`, etc.) but didn't yet call out that those phase-grouped files all depend on a shared, phase-agnostic `common.py`. Noting that gap and closing it here.

---

## 2. Task_v1

The unit of dispatch — what gets sent to an Agent or a Stage.

```
Task_v1:
  task_id: UUID
  run_id: UUID                          # links to the db/models/runs.py record — Handbook §8 traceability
  target_id: str                          # the agent_id or stage_id being invoked, e.g. "fact_verification"
  target_type: AGENT | STAGE                # per AGENT_SPECIFICATIONS.md §1.1 classification — governs execution model downstream
  payload: <DomainSchemaInstance>              # the specific versioned domain input, e.g. an instance of TopicResearchInput_v1
  idempotency_key: str                            # mandatory, not optional — Handbook §2 principle 3
  priority: NORMAL | HIGH
  config_ref: Configuration_v1.config_id             # which Configuration snapshot governs this dispatch (§6)
  parent_task_id: UUID | null                          # set when this Task was spawned inside an Agent's own tool-use loop
  created_at: timestamp
  dispatched_at: timestamp | null
```

- `idempotency_key` is required on every `Task_v1`, no exceptions — this is what makes retries (`PROVIDER_ARCHITECTURE.md` §17) and re-runs after a crash-recovered checkpoint (`core/pipeline/checkpointer.py`, per `REPOSITORY_STRUCTURE.md` §2) safe rather than merely convenient.
- `parent_task_id` exists specifically because Agents (unlike Stages) may spawn internal tool-use sub-steps (`AGENT_SPECIFICATIONS.md` §2's `max_iterations` loop) — this lets a full reasoning tree be reconstructed from flat `Task_v1` records rather than needing a separate tree structure.
- `payload` is a full instance of the relevant domain schema, not a reference to one — unlike `AssetReference` (`PROVIDER_ARCHITECTURE.md` §9), structured task/result data is small enough to embed directly and gains nothing from indirection; the "reference, don't embed" rule is specifically about large binary assets, not structured records.

---

## 3. Result_v1

What comes back from a `Task_v1` on completion — success, partial success, or an explicit non-answer.

```
Result_v1:
  result_id: UUID
  task_id: UUID                           # 1:1 with the Task it resolves
  run_id: UUID
  status: SUCCESS | LOW_CONFIDENCE | HALTED | FAILED
  payload: <DomainSchemaInstance> | null       # present for SUCCESS / LOW_CONFIDENCE, null for HALTED / FAILED
  confidence_flags: List[str] | null              # free-form flags defined by the domain schema itself
                                                     # (e.g. "insufficient_sourcing", "narrative_depends_on_unverified" —
                                                     #  see AGENT_SPECIFICATIONS.md §3 for the specific flags each agent defines)
  error_ref: Error_v1.error_id | null                # present only when status = FAILED
  cost_actual: CostEstimate                              # actual cost consumed, checked against Task's configured cost_ceiling
  duration: Duration
  iterations_used: int | null                              # AGENT target_type only — actual vs. max_iterations ceiling
  reasoning_trace_ref: List[AgentMessage_v1.message_id] | null   # AGENT target_type only — see §5
  metadata_ref: Metadata_v1.metadata_id
  completed_at: timestamp
```

- The four `status` values are exactly the four terminal states in `AGENT_SPECIFICATIONS.md` §4's shared failure/escalation model, extended here to apply uniformly to Stage results too — a Stage can also legitimately report `LOW_CONFIDENCE` or `HALTED` (e.g., a generation Stage whose output failed a downstream quality check), not just Agents.
- `HALTED` and `FAILED` are deliberately distinct: `HALTED` means the work terminated on purpose (iteration/timeout/cost ceiling reached without resolution, `AGENT_SPECIFICATIONS.md` §4) — an expected, honest non-answer. `FAILED` means something broke (`Error_v1` is populated). Conflating these into one "unsuccessful" status would hide exactly the distinction that matters for figuring out whether a human needs to review a judgment call or fix a technical fault.
- `reasoning_trace_ref` is null for Stage results — Stages, by definition (`AGENT_SPECIFICATIONS.md` §1), don't produce a multi-step reasoning trace.

---

## 4. Error_v1

The persisted form of the shared error taxonomy already defined in `PROVIDER_ARCHITECTURE.md` §16 — this schema is that taxonomy's storage record, not a new taxonomy.

```
Error_v1:
  error_id: UUID
  task_id: UUID
  run_id: UUID
  error_type: TransientError | RateLimitError | QuotaExceededError | AuthError
            | ContentPolicyError | ValidationError | PermanentError | ProviderUnavailableError
              # exact enum values from PROVIDER_ARCHITECTURE.md §16 — no additional error types introduced here
  origin: OriginRef                       # { origin_type: PROVIDER | AGENT | STAGE, origin_id: str }
  message: str                              # human-readable; must never contain raw secrets/credentials (Handbook §6)
  retriable: bool
  retry_after: Duration | null
  raw_reference: str | null                     # opaque pointer to a redacted vendor error log entry — never the raw
                                                   # vendor payload embedded inline, so vendor-specific structure never
                                                   # leaks into NarraOS records (PROVIDER_ARCHITECTURE.md §16)
  occurred_at: timestamp
```

- `origin` is mandatory and structured (not a free-text string) specifically so error patterns can be queried by source — "how often is `ContentPolicyError` originating from the `story_generation` agent versus the `compliance_review` agent" is a question the schema should answer directly, not one that requires parsing free text.
- Per `COMPLIANCE_ARCHITECTURE.md` §8: a `ContentPolicyError` record is never deleted as part of a subject's memory redaction — `Error_v1` records live in the Database Layer (canonical, per `MEMORY_ARCHITECTURE.md` §2), not the Memory Layer, and are governed by the same retention discipline as compliance audit records.

---

## 5. AgentMessage_v1

The atomic unit of an Agent's reasoning trace — this is the concrete storage form of `BaseAgent.explain() -> ReasoningTrace` (`AGENT_SPECIFICATIONS.md` §2) and satisfies that document's §5 mandatory logging requirement structurally, not just as a stated obligation.

```
AgentMessage_v1:
  message_id: UUID
  task_id: UUID                      # only populated for target_type = AGENT tasks
  run_id: UUID
  sequence: int                        # strict ordering within the reasoning trace
  role: REASONING | TOOL_CALL | TOOL_RESULT | DECISION | ESCALATION
  content: str                           # reasoning text, tool call description, tool output summary, or decision rationale
  tool_ref: str | null                     # provider_id or tool identifier invoked, when role = TOOL_CALL
  cost_delta: CostEstimate | null            # incremental cost of this specific step
  timestamp: timestamp
```

- A `Result_v1` for an Agent-type Task is reconstructible as a full, ordered reasoning trace purely by querying `AgentMessage_v1` records by `task_id`, ordered by `sequence` — there is no separate, denormalized "trace" blob stored redundantly on the `Result_v1` record itself. One source of truth.
- `role = ESCALATION` is the message type written the moment an Agent hits `AGENT_SPECIFICATIONS.md` §4's halt conditions (max iterations, timeout, cost ceiling) — this is what lets a human reviewer see not just *that* an agent halted, but the exact reasoning step at which it did, in context with everything that led up to it.
- `role = DECISION` specifically marks the message(s) representing the agent's actual judgment call (as opposed to intermediate `REASONING` or `TOOL_CALL`/`TOOL_RESULT` steps) — this is what a compliance or fact-verification audit review would filter to first.

---

## 6. Metadata_v1

The generic descriptive envelope attached to records and assets across the system — one shape, reused everywhere something needs "who made this, when, from what, tagged how."

```
Metadata_v1:
  metadata_id: UUID
  subject_ref: SubjectRef                  # { subject_type: TASK | RESULT | ASSET | CONTENT_RECORD, subject_id: str }
  created_by: CreatorRef                     # { creator_type: AGENT | STAGE | HUMAN | SYSTEM, creator_id: str }
  schema_version: str                          # which domain schema version describes the subject, e.g. "ScriptOutput_v1"
  tags: List[str]
  source_refs: List[SourceReference] | null       # populated when the subject has citations — feeds directly into
                                                     # COMPLIANCE_ARCHITECTURE.md §4/§6 citation_refs and the audit trail
  run_id: UUID
  created_at: timestamp
```

- `source_refs` is the single field that ties `Metadata_v1` directly to two other documents' requirements: `COMPLIANCE_ARCHITECTURE.md` §4's `citation_refs` on every `ComplianceReviewOutput_v1`, and the general audit-trail requirement in that document's §6. Rather than each of those defining its own citation structure, they both populate this shared field.
- `creator_type = HUMAN` exists specifically for the override/approval cases already specified elsewhere — a human-approved `BLOCKED` override (`COMPLIANCE_ARCHITECTURE.md` §5) or a manual topic selection (`AGENT_SPECIFICATIONS.md` §3.1) both produce records whose `Metadata_v1.created_by` correctly attributes the decision to a person, not a system component — this is what makes those decisions distinguishable in an audit review.

---

## 7. Configuration_v1

The versioned snapshot of what settings governed a given `Task_v1` at dispatch time — the schema form of the configuration layering already described narratively in `PROVIDER_ARCHITECTURE.md` §15 and `PLUGIN_ARCHITECTURE.md` §7.

```
Configuration_v1:
  config_id: UUID
  scope: GLOBAL | PROVIDER | AGENT | STAGE | PLUGIN
  scope_target_id: str | null              # e.g. "fact_verification" when scope = AGENT; null when scope = GLOBAL
  environment: local | production
  values: Dict[str, ConfigValue]              # typed key-value settings — never raw secret VALUES, see below
  secret_refs: List[str]                        # environment variable NAMES only (Handbook §6, PROVIDER_ARCHITECTURE.md §15)
  version: str                                    # semver
  effective_at: timestamp
```

- `Task_v1.config_ref` (§2) points to a specific `Configuration_v1.config_id`, not to a mutable "current config" pointer — this means a `Result_v1` produced under one configuration remains explainable after that configuration is later changed. A quality regression traced back to a config change (`PROVIDER_ARCHITECTURE.md` §15's explicit goal) requires exactly this — an immutable snapshot per dispatch, not a live reference.
- `values` never contains a secret's actual value under any circumstance — only `secret_refs` (names) does. This is the same rule already established for provider credentials, applied here as a schema-level guarantee rather than a convention someone could accidentally violate when populating the `values` dict.

---

## 8. Cross-Schema Relationships

```
Configuration_v1 ──governs──▶ Task_v1 ──produces──▶ Result_v1 ──(on FAILED)──▶ Error_v1
                                  │                        │
                                  │ (if AGENT)              └──describes via──▶ Metadata_v1
                                  ▼
                        AgentMessage_v1 (sequence of reasoning steps, task_id-linked)
```

- Every arrow above is a foreign-key-style reference by ID, never an embedded copy of the referenced record — this keeps each schema's storage form normalized and each record independently queryable/auditable (a `Configuration_v1` snapshot doesn't need to be duplicated into every `Task_v1` that used it).
- `run_id` appears on every one of the six schemas independently, not derived by joining through `task_id` alone — this is deliberate redundancy in service of `DEVELOPER_HANDBOOK.md` §8's observability principle: any of these six record types should be queryable directly by `run_id` without requiring a multi-hop join first.

---

## 9. Rules Governing All Six Schemas

1. **Immutability.** Once written, `Task_v1`, `Result_v1`, `Error_v1`, `AgentMessage_v1`, and `Metadata_v1` records are never updated in place — they are the audit trail (`DEVELOPER_HANDBOOK.md` §8, `COMPLIANCE_ARCHITECTURE.md` §6). Corrections are new records referencing the original, never overwrites. `Configuration_v1` is likewise immutable per snapshot — a "change" is always a new `config_id` with a new `version`, never a mutation of an existing one (§7).
2. **Envelope vs. domain payload separation.** These six schemas never encode domain-specific meaning themselves (no `Task_v1` field like `topic_string` — that belongs inside the embedded domain payload). This is what keeps the envelope reusable across all 19 pipeline steps (`AGENT_SPECIFICATIONS.md` §1.1) without modification as new domain schemas are added.
3. **`run_id` is mandatory, everywhere, no exceptions.** Every one of the six schemas requires it. A record without a `run_id` is not a valid record under this specification.
4. **No secret values, ever, in any of the six schemas.** Only reference-by-name (`Configuration_v1.secret_refs`) is permitted. This applies transitively — `Error_v1.message` and `AgentMessage_v1.content` must be constructed so they never accidentally interpolate a secret value either.

---

## 10. Deferred to Implementation

Explicitly out of scope for this initial reference, consistent with the stated scope:

- Every domain-specific payload schema already named across other documents — `TopicResearchInput_v1`/`Output_v1`, `ComplianceReviewInput_v1`/`Output_v1`, `ScriptOutput_v1`, `StoryConceptOutput_v1`, and the rest listed throughout `AGENT_SPECIFICATIONS.md` §3 and `COMPLIANCE_ARCHITECTURE.md` §4. These will be formalized in their respective phase-grouped files (`core/schemas/v1/research.py`, `story.py`, `production.py`, `compliance.py`, `packaging.py`, `feedback.py`, per `REPOSITORY_STRUCTURE.md` §2) as each stage/agent is implemented, each one embedding into `Task_v1.payload` / `Result_v1.payload` as defined here.
- Supporting primitive types referenced inline above (`Duration`, `CostEstimate`, `TimeWindow`, `SourceReference`, `OriginRef`, `SubjectRef`, `CreatorRef`, `ConfigValue`) — these are shared primitives, not full schemas, and will be defined alongside `common/types.py` (`REPOSITORY_STRUCTURE.md` §2) during implementation rather than specified in document form here.
- Database table design for these six schemas (`db/models/`) — this document defines the schema contract; physical storage/indexing is an implementation decision made against it.

---

*This document, together with `DEVELOPER_HANDBOOK.md` §7's schema-versioning rules, is the foundation every phase-specific schema file will be built on. Additional domain schemas are added during implementation, not specified in advance here, per this document's stated scope.*
