# NarraOS — Agent Specifications

**Version:** 0.1.0
**Status:** Specification — required reading before Core Infrastructure implementation (LangGraph graph shape depends on this)
**Last Updated:** 2026-07-18
**Resolves:** Moderate Gap §2.3 in `ARCHITECTURE_APPROVAL_REPORT.md` (no boundary defined between a "workflow stage" and an "agent"); `CURRENT_STATE.md`'s "Agent Specifications" pending item

> This document specifies every planned autonomous agent — purpose, inputs, outputs, dependencies, configuration, error handling, retry policy, logging, and contracts. It also formally draws the line between an **Agent** and a **Stage**, since that boundary determines how the LangGraph orchestration graph is actually shaped. No implementation code.

---

## 1. Agent vs. Stage: The Boundary

`PROJECT_ARCHITECTURE.md` §3 lists pipeline stages as a flat sequence. `CURRENT_STATE.md`'s `core/agents/` directory implies some of those stages are autonomous decision-makers rather than deterministic transforms. Left undefined, this ambiguity would leak directly into the LangGraph graph — agent nodes and simple nodes have different retry semantics, different cost profiles, and different failure handling, and the graph has to be built knowing which is which.

**Definition — a pipeline step is an Agent, not a Stage, if it meets at least one of these criteria:**

1. It exercises **judgment** over an open-ended or ambiguous input (there is no single deterministic correct output — e.g., "is this topic likely to perform well," "does this claim create defamation risk").
2. It requires **multiple tool calls** and reasons about their results before producing an output (e.g., searching multiple sources, cross-referencing, iterating).
3. It may **loop or revise its own output** before terminating, rather than producing one output from one provider call.
4. Its output meaningfully **shapes downstream strategy**, not just downstream content (e.g., Virality Prediction's score changes what gets made next, not just how one asset looks).

A **Stage** is everything else: a well-defined transform, typically one or a small fixed sequence of provider calls, with a single deterministic path from input schema to output schema, per `DEVELOPER_HANDBOOK.md` §7.

### 1.1 Full Pipeline Classification

| Pipeline Step | Classification | Rationale |
|---|---|---|
| Trend Discovery | **Agent** | Judgment over ambiguous signals, multi-source tool use |
| Competitor Analysis | **Agent** | Multi-source retrieval + comparative reasoning |
| Virality Prediction | **Agent** | Judgment call shaping downstream strategy |
| Topic Research | **Agent** | Multi-tool retrieval + synthesis, iterative |
| Fact Verification | **Agent** | Cross-referencing, judgment on claim confidence |
| Compliance & Risk Review | **Agent** | Judgment-heavy by definition — see `COMPLIANCE_ARCHITECTURE.md` |
| Story Generation | **Agent** | Creative judgment, not a fixed transform |
| Retention Optimization | **Agent** | Judgment against learned patterns (reads Procedural memory) |
| Script Writing | Stage | Deterministic transform of an already-approved story structure into prose |
| Storyboard Generation | Stage | Deterministic transform of an approved script into shot list |
| Image Generation | Stage | Single `ImageProvider` call per asset |
| Animation Generation | Stage | Single `VideoProvider` call per asset |
| Voice Synthesis | Stage | Single `TTSProvider` call |
| Video Editing | Stage | Deterministic local assembly (ffmpeg/MoviePy/OpenCV), not provider-based reasoning |
| Thumbnail Generation | Stage | Single/small fixed set of `ImageProvider` calls |
| SEO Generation | Stage | Deterministic transform of approved metadata inputs |
| Asset Packaging | Stage | Deterministic bundling |
| Upload Preparation | Stage | Deterministic validation against `PlatformAdapter.constraints()` |
| Publish | Stage | Deterministic transport call via `PublishingProvider` |
| Analytics Collection | Stage | Deterministic data pull via `AnalyticsProvider` |
| Feedback Loop | **Agent** | Judgment: distilling raw analytics into procedural patterns is interpretive, not mechanical |

This is the authoritative classification. Nine pipeline steps are Agents; the rest are Stages. Any future new pipeline step must be classified against §1's four criteria before it's built, and this table updated in the same change (per `DEVELOPER_HANDBOOK.md` §11 documentation-drift rule).

---

## 2. Common Agent Contract

Every agent shares a base contract — the LangGraph-level equivalent of `PROVIDER_ARCHITECTURE.md` §3's `BaseProvider`:

```
BaseAgent (interface, all agents implement this):
  agent_id: str
  purpose: str
  input_schema: SchemaRef
  output_schema: SchemaRef
  tools: List[ProviderDependency]         # which providers/tools this agent may invoke
  memory_access: MemoryAccessSpec          # which MemoryStore namespaces (MEMORY_ARCHITECTURE.md §9), read/write
  max_iterations: int                       # hard ceiling on internal reasoning/tool-call loops
  timeout: Duration                          # wall-clock ceiling regardless of iteration count
  cost_ceiling: CostEstimate                   # hard budget per invocation, checked against PROVIDER_ARCHITECTURE.md §3 cost_estimate()

  invoke(input: AgentInput, context: RunContext) -> AgentOutput
  explain(output: AgentOutput) -> ReasoningTrace     # mandatory — see §5 logging requirements
```

**Rules that apply to every agent, not repeated per-agent below:**

- `max_iterations` and `timeout` are both mandatory and both enforced — an agent that would loop indefinitely reasoning about an ambiguous case must terminate and escalate (§4), never hang the run.
- `cost_ceiling` breach is treated as a distinct termination condition, not a retry trigger — see §4.
- Every agent's `AgentInput`/`AgentOutput` are versioned schemas per `DEVELOPER_HANDBOOK.md` §7, same rule as Stage schemas — the Agent/Stage distinction changes internal execution model, not the external contract discipline.
- Every agent depends on providers only through the `ProviderRegistry` (`PROVIDER_ARCHITECTURE.md` §14) and on memory only through `MemoryStore` (`MEMORY_ARCHITECTURE.md` §6) — never directly on a concrete provider or the vector store.

---

## 3. Agent Registry (per-agent specifications)

### 3.1 Trend Discovery Agent

- **Purpose:** Scans available signal sources for emerging topics/niches relevant to the approved content categories (Dark True Stories, Internet Mysteries, Scams, Corporate Crimes) and produces ranked topic candidates.
- **Pipeline Phase:** A — Discovery & Strategy (first agent in a run when no topic has been pre-selected)
- **Input:** `TrendDiscoveryInput_v1` — `{ content_categories, target_platforms, target_jurisdictions, exclusion_list }`
- **Output:** `TrendDiscoveryOutput_v1` — `{ candidate_topics: List[TopicCandidate], reasoning }`
- **Tools/Providers:** requires a signal-source tool not yet specified in `PROVIDER_ARCHITECTURE.md` — flagged in §6 as an open provider extension.
- **Memory access:** reads `procedural-feedback` (past pattern performance, per `MEMORY_ARCHITECTURE.md` §9); does not write.
- **Configuration:** candidate count ceiling, recency window for signal freshness, per-category weighting.
- **Error handling:** signal-source unavailability maps to `ProviderUnavailableError` (`PROVIDER_ARCHITECTURE.md` §16) → falls back to a secondary signal source if configured, else halts and surfaces empty-candidate-set explicitly (never fabricates plausible-sounding but ungrounded topic candidates to fill the gap).
- **Retry policy:** agent-level retry limited to 1 re-attempt with the same inputs on transient tool failure; exhausting `max_iterations` without a confident candidate set is not retried automatically — surfaces for human topic selection instead.
- **Logging:** every candidate topic's `reasoning` field is mandatory and persisted (§5) — an unranked list with no rationale is an incomplete output, not a valid one.
- **Autonomy:** general Handbook §9 levels apply (no niche-specific override, unlike Compliance).

### 3.2 Competitor Analysis Agent

- **Purpose:** Analyzes competitor content (via transcription and metadata) for format, cadence, and performance patterns relevant to a candidate topic or the channel's overall strategy.
- **Pipeline Phase:** A
- **Input:** `CompetitorAnalysisInput_v1` — `{ topic_or_niche, competitor_refs, analysis_depth }`
- **Output:** `CompetitorAnalysisOutput_v1` — `{ format_patterns, cadence_observations, gap_opportunities, reasoning }`
- **Tools/Providers:** `STTProvider` (transcription of competitor video audio, per `PROVIDER_ARCHITECTURE.md` §8), plus the same not-yet-specified content-discovery tool flagged in §6.
- **Memory access:** reads and writes `semantic-competitor` namespace (`MEMORY_ARCHITECTURE.md` §9) — checks for prior analysis of the same competitor content before re-transcribing/re-analyzing.
- **Configuration:** number of competitor items sampled per run, transcription confidence threshold below which an item is excluded from analysis rather than analyzed on unreliable transcript data.
- **Error handling:** low-confidence `TranscriptResult` (`PROVIDER_ARCHITECTURE.md` §8) is excluded, not force-analyzed — the agent must not silently reason over a transcript it has reason to distrust.
- **Retry policy:** per-item transcription failures are skipped (not retried indefinitely) so one bad source doesn't block the whole analysis; agent surfaces which items were skipped and why.
- **Logging:** which competitor items were included/excluded and why (confidence threshold), full reasoning trace for gap-opportunity conclusions.
- **Autonomy:** general Handbook §9 levels apply.

### 3.3 Virality Prediction Agent

- **Purpose:** Scores candidate topics/formats against learned performance patterns before any content is produced, gating what proceeds to research.
- **Pipeline Phase:** A
- **Input:** `ViralityPredictionInput_v1` — `{ candidate_topics: List[TopicCandidate], competitor_context, format_options }`
- **Output:** `ViralityPredictionOutput_v1` — `{ scored_candidates: List[ScoredTopic], recommended_selection, reasoning }`
- **Tools/Providers:** `LLMProvider` for reasoning; no external tool calls required beyond memory retrieval.
- **Memory access:** reads `procedural-feedback` heavily (this is the primary consumer of Feedback Loop output, per `MEMORY_ARCHITECTURE.md` §9); does not write.
- **Configuration:** score threshold below which a candidate is excluded from recommendation; whether ties are broken by recency or by novelty (avoiding repeated angles, cross-checked against `episodic` memory).
- **Error handling:** if `procedural-feedback` memory is empty or sparse (e.g., very early in the project, before enough Feedback Loop cycles have run), the agent must explicitly flag `low_confidence: true` in its output rather than silently scoring as if it had a mature pattern base.
- **Retry policy:** no automated retry on a low-confidence result — that's an expected, valid state early in the project's life, not a failure.
- **Logging:** score justification per candidate, explicit `low_confidence` flag state, which procedural memory items most influenced the ranking.
- **Autonomy:** its output shapes strategy (§1 criterion 4) — recommend keeping this at L1 (supervised) longer than typical stages even after general reliability is established, since a bad recommendation here wastes an entire downstream run's cost, not just one asset's.

### 3.4 Topic Research Agent

- **Purpose:** Gathers source material, data, and context for the selected topic, producing a structured research corpus for downstream Story Generation.
- **Pipeline Phase:** B — Research & Story
- **Input:** `TopicResearchInput_v1` — `{ topic, required_depth, source_constraints }`
- **Output:** `TopicResearchOutput_v1` — `{ findings: List[ResearchFinding], sources: List[SourceReference], reasoning }`
- **Tools/Providers:** web/document retrieval tool (not yet specified — §6), `LLMProvider` for synthesis.
- **Memory access:** reads and writes `semantic-research` namespace (`MEMORY_ARCHITECTURE.md` §9, §3.3) — checks for prior research on the same or related topics before re-researching from scratch.
- **Configuration:** minimum source count, source credibility floor (a configured tier system, not a binary), maximum research iterations before forcing termination with whatever has been gathered.
- **Error handling:** insufficient credible sources found within `max_iterations` is a valid, explicitly-flagged output state (`insufficient_sourcing: true`), not a forced pass — this agent must never pad out a thin research corpus with lower-credibility sources just to hit a target count.
- **Retry policy:** re-invocation with expanded `source_constraints` is a human-triggered re-run, not an automatic retry — insufficient sourcing on a sensitive topic (per the niche) should surface for a human decision on how to proceed, not be silently worked around.
- **Logging:** full source list with credibility tier per source; this list is exactly what feeds `citation_refs` in `COMPLIANCE_ARCHITECTURE.md` §4 and §6's audit trail — the two documents share this data, not duplicate it.
- **Autonomy:** general Handbook §9 levels apply, though see §6 note on Fact Verification's shared dependency.

### 3.5 Fact Verification Agent

- **Purpose:** Cross-checks claims produced or gathered during research against sources, scoring confidence and flagging unverifiable claims. **Distinct from Compliance & Risk Review** — see `COMPLIANCE_ARCHITECTURE.md` §1 for the explicit boundary.
- **Pipeline Phase:** B
- **Input:** `FactVerificationInput_v1` — `{ claims: List[Claim], available_sources: List[SourceReference] }`
- **Output:** `FactVerificationOutput_v1` — `{ verified_claims: List[VerifiedClaim], unverifiable_claims: List[Claim], reasoning }`
- **Tools/Providers:** `LLMProvider`, same retrieval tool as Topic Research for cross-checking against sources not already in-hand.
- **Memory access:** reads and writes `semantic-research` (previously-verified claims, per `MEMORY_ARCHITECTURE.md` §9 and `COMPLIANCE_ARCHITECTURE.md` §8) — avoids re-verifying an identical claim from scratch each run.
- **Configuration:** confidence threshold for a claim to be marked `verified` vs. routed to `unverifiable`.
- **Error handling:** a claim that cannot be verified within `max_iterations` is marked `unverifiable`, never silently dropped and never marked verified by default — absence of disproof is not verification.
- **Retry policy:** no automatic retry on `unverifiable` claims; they route downstream as explicitly unverified, and Story Generation/Compliance must handle that state rather than assuming everything reaching them has been confirmed.
- **Logging:** verification reasoning and source cross-references per claim — this is the other half of the audit trail referenced in `COMPLIANCE_ARCHITECTURE.md` §6.
- **Autonomy:** general Handbook §9 levels apply, but promotion should be considered jointly with Compliance & Risk Review's trust-building process (`COMPLIANCE_ARCHITECTURE.md` §7), since both agents' reliability affects the same downstream risk.

### 3.6 Compliance & Risk Review Agent

- **Purpose:** Fully specified in `COMPLIANCE_ARCHITECTURE.md`. Included in this registry for completeness and cross-referencing only — **that document is authoritative for this agent**, not this entry.
- **Pipeline Phase:** B (research pass), C (script pass), D (pre-publish pass) — see `COMPLIANCE_ARCHITECTURE.md` §2.
- **Input/Output:** `ComplianceReviewInput_v1` / `ComplianceReviewOutput_v1`, per `COMPLIANCE_ARCHITECTURE.md` §4.
- **Autonomy:** permanently pinned below L3 — see `COMPLIANCE_ARCHITECTURE.md` §5. This is the one agent in the registry where general Handbook §9 promotion rules explicitly do **not** apply uniformly.
- **Cross-reference note:** this agent's `max_iterations`/`timeout`/`cost_ceiling` (§2 of this document) still apply as engineering guardrails — they govern how long the agent may reason before terminating, which is separate from and does not relax the autonomy/human-review policy defined in `COMPLIANCE_ARCHITECTURE.md`.

### 3.7 Story Generation Agent

- **Purpose:** Converts verified research and a selected topic into a narrative concept — angle, hook, arc — before script prose is written.
- **Pipeline Phase:** B
- **Input:** `StoryGenerationInput_v1` — `{ verified_claims, unverifiable_claims (flagged), topic_candidate, compliance_findings_research_pass }`
- **Output:** `StoryConceptOutput_v1` — `{ narrative_arc, hook, angle, reasoning }`
- **Tools/Providers:** `LLMProvider` only.
- **Memory access:** reads `procedural-feedback` (which narrative structures have performed well, per `MEMORY_ARCHITECTURE.md` §9); does not write directly (Feedback Loop is the sole writer to that namespace, keeping a single writer per namespace to avoid conflicting/competing updates).
- **Configuration:** creative constraint set (tone, pacing targets), whether unverifiable claims may be referenced at all in the narrative (default: no — an unverifiable claim should not become a load-bearing story beat).
- **Error handling:** if research input includes `unverifiable_claims` that the agent would otherwise want to build the narrative around, it must produce an explicit flag (`narrative_depends_on_unverified: true`) rather than quietly incorporating them — this is a direct input to why Compliance & Risk Review's script-pass exists.
- **Retry policy:** low-quality/low-confidence narrative output triggers one automated re-generation attempt with adjusted parameters before routing to human review — creative quality has more legitimate retry value than, e.g., a verification question, since regeneration genuinely can improve it.
- **Logging:** full reasoning for the chosen angle/hook, and explicit note of which research findings were used vs. discarded and why.
- **Autonomy:** general Handbook §9 levels apply.

### 3.8 Retention Optimization Agent

- **Purpose:** Structures the narrative concept against known retention patterns (pacing, open loops, payoff placement) before Script Writing.
- **Pipeline Phase:** B
- **Input:** `RetentionOptimizationInput_v1` — `{ narrative_arc, hook, angle, target_platform }`
- **Output:** `RetentionOptimizationOutput_v1` — `{ structured_outline: List[Beat], pacing_notes, reasoning }`
- **Tools/Providers:** `LLMProvider` only.
- **Memory access:** reads `procedural-feedback` (retention-specific patterns, per `MEMORY_ARCHITECTURE.md` §9); does not write, same single-writer rule as §3.7.
- **Configuration:** target runtime/length (platform-dependent, sourced from `PlatformAdapter.constraints()`), minimum/maximum open-loop count per structure.
- **Error handling:** if platform-specific pacing constraints conflict with the narrative agent's intended arc (e.g., a platform's typical retention curve doesn't fit the hook as structured), the agent flags this conflict explicitly rather than silently overriding Story Generation's output — resolution routes back for a joint revision rather than one agent unilaterally overwriting another's creative decision.
- **Retry policy:** same one-automated-attempt pattern as §3.7 before human routing.
- **Logging:** pacing reasoning, and explicit record when platform constraints forced a structural compromise.
- **Autonomy:** general Handbook §9 levels apply.

### 3.9 Feedback Loop Agent

- **Purpose:** Distills raw post-publish analytics into procedural patterns that inform future Virality Prediction, Story Generation, and Retention Optimization — the mechanism that actually closes the loop described in `ROADMAP.md` Phase 3.
- **Pipeline Phase:** E — Learning
- **Input:** `FeedbackLoopInput_v1` — `{ content_id, run_id, metrics_snapshot, audience_snapshot }` (from `AnalyticsProvider`, per `PROVIDER_ARCHITECTURE.md` §12)
- **Output:** `FeedbackLoopOutput_v1` — `{ distilled_patterns: List[ProceduralPattern], episodic_summary, reasoning }`
- **Tools/Providers:** `LLMProvider` for interpretive distillation; `AnalyticsProvider` output is its primary raw input (already fetched by the Analytics Collection *stage*, not this agent — this agent interprets, it does not fetch).
- **Memory access:** the sole writer to `procedural-feedback` (per §3.7/§3.8's single-writer rule) and a writer to `episodic` (run outcome summary), per `MEMORY_ARCHITECTURE.md` §9.
- **Configuration:** minimum data-maturity window before analytics are considered stable enough to distill from (avoiding drawing conclusions from a video's first hour of performance), pattern-confidence threshold before a `ProceduralPattern` is written to memory at all.
- **Error handling:** analytics data that hasn't matured past the configured window is not distilled prematurely — the agent explicitly defers rather than drawing conclusions from incomplete performance data.
- **Retry policy:** re-invoked on a schedule (not error-triggered retry) as analytics data matures over a content item's lifecycle — this is closer to a recurring re-evaluation than a failure-recovery retry.
- **Logging:** which raw metrics led to which distilled pattern — this reasoning trace is what lets a future audit explain why Virality Prediction is favoring a particular pattern, rather than that preference being an opaque emergent property of the memory store.
- **Autonomy:** general Handbook §9 levels apply to the distillation step itself; but because its output directly shapes future content strategy (§1 criterion 4, same reasoning as §3.3), keep at L1/L2 longer than typical, consistent with `COMPLIANCE_ARCHITECTURE.md`'s general principle that strategy-shaping agents warrant more conservative promotion than content-generation stages.

---

## 4. Shared Failure & Escalation Model

All nine agents share this termination/escalation model, layered on top of the individual per-agent error handling in §3:

```
Agent invoked
  → reasons / calls tools, within max_iterations and timeout
  → produces output within cost_ceiling
       ├─ SUCCESS (confident output) → proceeds downstream
       ├─ LOW CONFIDENCE (explicit, not hidden) → proceeds downstream WITH the flag intact —
       │    never silently upgraded to look confident by a downstream stage
       ├─ max_iterations / timeout reached without resolution → HALTS, routes to human review
       └─ cost_ceiling breached → HALTS immediately, routes to human review
              (never silently truncated to "finish within budget" — a truncated compliance
               or fact-check reasoning pass is worse than an explicit halt)
```

**Rule:** an agent's job is to produce either a confident answer or an honest, explicit statement that it doesn't have one. Neither `PROVIDER_ARCHITECTURE.md`'s retry taxonomy (§17 of that document) nor this shared model permit an agent to paper over genuine uncertainty to satisfy a run's completion — this is the agent-level equivalent of the Handbook §2 principle "fail loud, fail safe."

---

## 5. Logging Requirements (applies to all agents)

Beyond the per-agent notes in §3, every agent invocation must persist:

- Full `ReasoningTrace` (`BaseAgent.explain()`, §2) — not just the final output, but the tool calls made and intermediate reasoning that produced it. This is what makes an agent's decision auditable after the fact, which matters most acutely for Compliance & Risk Review and Fact Verification but is required uniformly, not selectively.
- `run_id` linkage (per `DEVELOPER_HANDBOOK.md` §8) so any agent invocation is traceable to its full pipeline run context.
- Cost actually consumed vs. `cost_ceiling` configured, per invocation — feeds the cost-awareness principle in `DEVELOPER_HANDBOOK.md` §2.
- Iteration count actually used vs. `max_iterations` configured — a persistent pattern of agents running close to their iteration ceiling is itself a signal worth surfacing, not just a per-run detail.

---

## 6. Open Items Not Resolved by This Document

- **Two provider types referenced above are not yet specified:** a signal-source/trend-data tool (Trend Discovery Agent, §3.1) and a content-discovery tool for retrieving competitor content (Competitor Analysis Agent, §3.2). Per `PROVIDER_ARCHITECTURE.md` §19.2's extension process, these need their own provider interface specifications before those two agents can be implemented — flagged here rather than silently assumed.
- Exact `max_iterations`, `timeout`, and `cost_ceiling` values per agent — these are operational tuning parameters, not architecture, and should be set (and revised) based on real usage data once Phase 1 begins.
- Whether Compliance & Risk Review (§3.6) and Fact Verification (§3.5) should share a single retrieval/tool-use pass to avoid redundant source-fetching, given how closely their inputs overlap — an implementation-level optimization question, deferred so it doesn't compromise the clean conceptual separation `COMPLIANCE_ARCHITECTURE.md` §1 establishes.

---

*This document, together with `PROVIDER_ARCHITECTURE.md`, `MEMORY_ARCHITECTURE.md`, and `COMPLIANCE_ARCHITECTURE.md`, gives Core Infrastructure everything it needs to shape the LangGraph graph correctly — which nodes carry internal reasoning loops (Agents) and which are simple deterministic nodes (Stages).*
