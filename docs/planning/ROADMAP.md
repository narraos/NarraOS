# NarraOS — Roadmap

**Version:** 0.1.0
**Last Updated:** 2026-07-18
**Planning Horizon:** Phase 0 → Phase 5 (foundation → multi-platform scale)

> This roadmap sequences NarraOS from zero to a working, trustworthy, revenue-viable autonomous media system. Each phase has an explicit **exit criteria** — we don't move on because we're bored of a phase, we move on because it's proven.

---
 
## Phase 0 — Engineering Foundation (Current Phase)
 
**Goal:** Have a real engineering foundation before any code is written.
 
- [x] DEVELOPER_HANDBOOK.md
- [x] PROJECT_ARCHITECTURE.md
- [x] ROADMAP.md
- [x] AI_CONTEXT.md
- [x] PROJECT_STATE.json
- [x] Documentation structure
- [x] PROVIDER_ARCHITECTURE.md
- [x] MEMORY_ARCHITECTURE.md
- [x] COMPLIANCE_ARCHITECTURE.md
- [x] AGENT_SPECIFICATIONS.md
- [x] REPOSITORY_STRUCTURE.md
- [x] PLUGIN_ARCHITECTURE.md
- [x] SCHEMA_REFERENCE.md (initial)
- [x] YOUTUBE_ADAPTER_ARCHITECTURE.md
- [x] Resolve open architecture decisions — orchestration engine (LangGraph, per `CURRENT_STATE.md`; validation tracked as ADR-0001, first Core Infrastructure task) and budget/niche (per `CURRENT_STATE.md`). Model provider *vendor* selection remains open but is non-blocking — see `PROJECT_STATE.json`.
- [ ] Repo scaffolding created matching `REPOSITORY_STRUCTURE.md` layer structure (no business logic yet) — first Phase 1 action, not a Phase 0 exit requirement
**Exit criteria:** Founder has reviewed and approved all foundation docs; no ambiguity remains about "what are we building and how do we work." **Met — see `ARCHITECTURE_APPROVAL_CERTIFICATE.md`.** Repo scaffolding is sequenced as the first Phase 1 action rather than a precondition of architecture approval.
## Phase 1 — Single-Stage Proof, Manual Pipeline (MVP-0)

**Goal:** Prove each core pipeline stage works in isolation, wired together manually, for ONE video, on YouTube, with a human approving every step (Autonomy Level L0).

- [ ] Foundation services stood up: Postgres, object storage, Redis queue, Model Gateway
- [ ] Implement stages: Topic Research → Fact Verification → Story Generation → Script Writing (text-only chain first — cheapest to validate)
- [ ] Implement stages: Storyboard Generation → Image Generation → Voice Synthesis (media generation chain)
- [ ] Implement stage: Video Editing (assemble the above into a rendered video)
- [ ] Implement stage: Thumbnail Generation
- [ ] Implement stage: SEO Generation
- [ ] Implement YouTube adapter: `validate()`, `publish()`, `constraints()`
- [ ] Manually trigger and review a full run end-to-end, producing ONE real published video

**Exit criteria:** One real video, produced start-to-finish through the pipeline (with human review at every stage), successfully published to YouTube.

---

## Phase 2 — Orchestrated Pipeline, Supervised Autonomy (MVP-1)

**Goal:** Replace manual stage-chaining with the real orchestration engine (DAG runner, state persistence, retries). Move stages from L0 → L1 (supervised: runs automatically, held for approval at checkpoints).

- [ ] Orchestration engine selected and integrated (resolves Phase 0's open decision)
- [ ] Full pipeline runnable via a single trigger (topic in → package ready for approval out)
- [ ] Human-checkpoint gating implemented (script approval, thumbnail approval, pre-publish approval)
- [ ] Cost tracking per run implemented and visible
- [ ] Run history + state queryable (via API or CLI; dashboard not required yet)
- [ ] Produce 5–10 videos through the orchestrated pipeline; track quality and cost per video

**Exit criteria:** Pipeline runs unattended between checkpoints; founder spends minutes, not hours, per video; cost-per-video is known and trending in the right direction.

---

## Phase 3 — Feedback Loop & Trust-Based Autonomy

**Goal:** Close the loop. Analytics inform future generations. Reliable stages graduate to L2/L3 autonomy.

- [ ] Analytics Collection stage implemented against YouTube adapter
- [ ] Feedback Loop implemented: performance data feeds back into Virality Prediction and Retention Optimization
- [ ] Per-stage reliability tracked against defined quality metrics (Handbook §9)
- [ ] Stages with sustained reliable performance promoted to L2 (spot-checked)
- [ ] Define and implement quality gates that must pass before ANY stage reaches L3 (fully autonomous)
- [ ] Discovery & Strategy phase (Trend Discovery, Competitor Analysis, Virality Prediction) implemented — previously the pipeline started from a human-chosen topic; now the system can propose topics itself

**Exit criteria:** The system can propose its own topics, generate content, and improve future output from past performance — with publishing still gated by human approval (L1 minimum) until explicitly raised.

---

## Phase 4 — Multi-Platform Expansion

**Goal:** Prove the platform-agnostic architecture by shipping a second platform adapter without touching the core.

- [ ] Choose second platform (TikTok or Instagram, based on audience/content-format fit)
- [ ] Build platform adapter satisfying the existing `PlatformAdapter` contract
- [ ] Extend AssetPackage handling for platform-specific format requirements (aspect ratio, length limits) — verify this requires ONLY adapter + media-stage parameterization, not core changes
- [ ] Run pipeline producing platform-native content for two platforms from the same underlying story/research stages where appropriate
- [ ] Repeat for remaining platforms (X, Facebook, future platforms) as strategy dictates

**Exit criteria:** Second platform live with content published, and — critically — the architecture held: no core pipeline code changed to support it, only adapter + config.

---

## Phase 5 — Scale, Team & Monetization

**Goal:** Move from "founder's autonomous system" to a real operating business.

- [ ] Dashboard (Layer 5) built out for full human oversight without needing to read logs/DB directly
- [ ] Decide and implement business model (owned channel network vs platform-as-a-service for other creators vs licensing)
- [ ] If multi-tenant SaaS direction chosen: revisit architecture for tenant isolation (explicitly deferred in Phase 0)
- [ ] Team scaling: contributor onboarding uses this same documentation set; Handbook's AI-agent conduct rules extended to human contributor conduct
- [ ] Infra scaling decisions revisited only when real load justifies them (avoid premature Kubernetes/multi-region)

**Exit criteria:** Revenue-generating, multi-platform, partially-autonomous media operation with a defined business model and a team (human and/or AI) that can operate from documented process, not founder memory.

---

## Roadmap Discipline

- No phase starts before the previous phase's exit criteria are met, unless explicitly and consciously overridden by the founder (and logged in `PROJECT_STATE.json`).
- Every phase transition updates `PROJECT_STATE.json`.
- This roadmap is revisited at the end of every phase, not rewritten mid-phase on impulse.

---

*See `DAILY_DEVELOPMENT_PLAN.md` for how Phase 0/1 work breaks down into daily execution.*
