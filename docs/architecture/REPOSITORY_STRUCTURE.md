# NarraOS — Repository Structure

**Version:** 0.1.0
**Status:** Specification — authoritative repo layout for repository initialization and all subsequent development
**Last Updated:** 2026-07-18
**Resolves:** `CURRENT_STATE.md`'s "Repository Structure" pending item; Moderate Gap §2.4 in `ARCHITECTURE_APPROVAL_REPORT.md` (dual `requirements.txt`/`pyproject.toml` ambiguity); reconciles two layout inconsistencies introduced by later documents (§9)

> This document is the single source of truth for where code lives, how it's named, and what may import what. `DEVELOPER_HANDBOOK.md` §3 sketched an early version of this layout before `PROVIDER_ARCHITECTURE.md`, `MEMORY_ARCHITECTURE.md`, `COMPLIANCE_ARCHITECTURE.md`, and `AGENT_SPECIFICATIONS.md` existed — this document supersedes that sketch and is now authoritative. No implementation code.

---

## 1. Layout Philosophy

1. **`src/` layout, not flat package.** The installable package lives at `src/narraos/`, not `narraos/` at repo root. This is standard, production-grade Python packaging practice — it prevents accidentally importing the package from the working directory instead of the installed version, which is exactly the kind of subtle bug that's expensive to debug in an autonomous system where nobody may be watching a given run.
2. **Directory structure mirrors architectural layers, not implementation convenience.** Every top-level directory under `src/narraos/` corresponds to a specific layer or concern already defined in `PROJECT_ARCHITECTURE.md`, `PROVIDER_ARCHITECTURE.md`, `MEMORY_ARCHITECTURE.md`, `COMPLIANCE_ARCHITECTURE.md`, or `AGENT_SPECIFICATIONS.md`. If a proposed new directory doesn't map to something already specified in those documents, that's a signal to update the architecture first, not to add a directory ad hoc.
3. **One class of thing per file, grouped by domain, not by type.** A given agent's schema, logic, and configuration live together under that agent's own directory — the repo is not organized into a top-level `schemas/` bucket for everything and a top-level `logic/` bucket for everything else. Domain cohesion beats type-based grouping.
4. **Dependencies point in one direction, enforced, not just documented.** §6 defines the allowed import graph. This is intended to be mechanically enforced (via an import-linter-style tool in CI), not left to reviewer memory.

---

## 2. Full Repository Layout

```
narraos/
├── src/
│   └── narraos/
│       ├── __init__.py
│       │
│       ├── core/
│       │   ├── pipeline/                  # LangGraph graph assembly & orchestration engine integration
│       │   │   ├── graph.py                 # DAG/graph construction wiring agents + stages together
│       │   │   ├── checkpointer.py            # Postgres-backed LangGraph checkpointer (Working Memory, MEMORY_ARCHITECTURE.md §3.1)
│       │   │   ├── run_context.py               # RunContext object threaded through every agent/stage invocation
│       │   │   └── human_checkpoint.py            # Approval-gate interrupt/resume logic (Handbook §9 autonomy levels)
│       │   │
│       │   ├── agents/                     # The 9 Agents per AGENT_SPECIFICATIONS.md §1.1 and §3
│       │   │   ├── base.py                    # BaseAgent contract (AGENT_SPECIFICATIONS.md §2)
│       │   │   ├── trend_discovery/
│       │   │   ├── competitor_analysis/
│       │   │   ├── virality_prediction/
│       │   │   ├── topic_research/
│       │   │   ├── fact_verification/
│       │   │   ├── compliance_review/           # Implements COMPLIANCE_ARCHITECTURE.md; three scope configs, one implementation (that doc §2)
│       │   │   ├── story_generation/
│       │   │   ├── retention_optimization/
│       │   │   └── feedback_loop/                 # Sole writer to procedural-feedback memory (MEMORY_ARCHITECTURE.md §9)
│       │   │
│       │   ├── stages/                     # The 10 Stages per AGENT_SPECIFICATIONS.md §1.1
│       │   │   ├── base.py                    # Shared Stage contract (deterministic transform, single/fixed provider call sequence)
│       │   │   ├── script_writing/
│       │   │   ├── storyboard_generation/
│       │   │   ├── image_generation/
│       │   │   ├── animation_generation/
│       │   │   ├── voice_synthesis/
│       │   │   ├── video_editing/                 # Local ffmpeg/MoviePy/OpenCV assembly — NOT provider-backed, see §9.1
│       │   │   ├── thumbnail_generation/
│       │   │   ├── seo_generation/
│       │   │   ├── asset_packaging/
│       │   │   ├── upload_preparation/
│       │   │   ├── publish/
│       │   │   └── analytics_collection/
│       │   │
│       │   └── schemas/                    # Versioned Pydantic contracts (Handbook §7)
│       │       ├── v1/                        # Current schema version for all stage/agent I/O
│       │       │   ├── research.py               # ResearchOutput_v1, TopicResearchInput_v1, etc. — grouped by pipeline phase
│       │       │   ├── story.py
│       │       │   ├── production.py
│       │       │   ├── compliance.py             # ComplianceReviewInput_v1 / Output_v1 (COMPLIANCE_ARCHITECTURE.md §4)
│       │       │   ├── packaging.py
│       │       │   └── feedback.py
│       │       └── v2/                        # Created only when a breaking change is introduced (Handbook §7) — empty until then
│       │
│       ├── providers/                     # Provider interfaces + implementations (PROVIDER_ARCHITECTURE.md)
│       │   ├── base.py                        # BaseProvider contract (that doc §3)
│       │   ├── registry.py                     # ProviderRegistry — the ONLY place implementations are imported (§6, §9.2)
│       │   ├── errors.py                         # Shared error taxonomy (PROVIDER_ARCHITECTURE.md §16)
│       │   ├── llm/
│       │   │   ├── interface.py                    # LLMProvider abstract interface
│       │   │   └── implementations/                  # OpenAI/Anthropic/etc. — vendor-specific, isolated
│       │   ├── image/         (interface.py + implementations/)
│       │   ├── video/          (interface.py + implementations/)
│       │   ├── tts/             (interface.py + implementations/)
│       │   ├── stt/              (interface.py + implementations/)
│       │   ├── storage/           (interface.py + implementations/)
│       │   ├── embedding/          (interface.py + implementations/)
│       │   ├── vector_store/        (interface.py + implementations/)     # MEMORY_ARCHITECTURE.md §5
│       │   ├── analytics/            (interface.py + implementations/)
│       │   └── publishing/            (interface.py + implementations/)
│       │
│       ├── memory/                        # MemoryStore facade (MEMORY_ARCHITECTURE.md §6)
│       │   ├── store.py                       # MemoryStore.remember() / recall() / forget()
│       │   ├── namespaces.py                    # episodic, semantic-research, semantic-competitor, procedural-feedback constants
│       │   └── redaction.py                      # forget_by_filter() enforcement, cascade-delete hooks (MEMORY_ARCHITECTURE.md §8)
│       │
│       ├── compliance/                    # Supporting logic for the compliance_review agent — taxonomy, not the agent itself
│       │   ├── risk_taxonomy.py               # DEFAMATION / PRIVACY / PLATFORM_POLICY / COPYRIGHT definitions (COMPLIANCE_ARCHITECTURE.md §3)
│       │   ├── jurisdiction_rules.py            # US/CA/UK/AU calibration config (that doc §3.1)
│       │   └── audit_trail.py                    # Persistence helpers for the mandatory audit record (that doc §6)
│       │
│       ├── platforms/                     # Layer 4 adapters (PROJECT_ARCHITECTURE.md §4)
│       │   ├── base.py                        # PlatformAdapter interface: validate(), publish(), fetch_analytics(), constraints()
│       │   ├── youtube/                         # First and only implemented adapter in Phase 1
│       │   ├── tiktok/                            # Stub only — Phase 4
│       │   ├── instagram/                          # Stub only — Phase 4
│       │   ├── x/                                   # Stub only — Phase 4
│       │   └── facebook/                             # Stub only — Phase 4
│       │
│       ├── api/                           # FastAPI application (Phase 2+, per DEVELOPER_HANDBOOK.md §4)
│       │   ├── main.py
│       │   ├── routes/
│       │   │   ├── runs.py                       # Trigger/inspect pipeline runs
│       │   │   ├── approvals.py                    # Human-checkpoint approval endpoints
│       │   │   └── state.py                          # PROJECT_STATE.json-equivalent live status, served not just filed
│       │   └── dependencies.py                    # FastAPI DI wiring — thin, delegates to providers/registry.py, not a parallel DI system
│       │
│       ├── config/                        # Configuration loading (PROVIDER_ARCHITECTURE.md §15)
│       │   ├── settings.py                    # Typed settings object, environment-aware
│       │   ├── loader.py                        # Loads providers.base/local/production.yaml + .env
│       │   └── schema.py                          # Pydantic schema for config files themselves — config gets the same validation discipline as pipeline data
│       │
│       ├── db/                            # Database Layer (PostgreSQL) — MEMORY_ARCHITECTURE.md §2's canonical store
│       │   ├── models/
│       │   │   ├── runs.py                       # run_id, stage status, timing (Handbook §8)
│       │   │   ├── content.py                      # published content metadata, platform records
│       │   │   ├── compliance_records.py             # Audit trail, retained even if derived memory is redacted (COMPLIANCE_ARCHITECTURE.md §6)
│       │   │   └── analytics.py                       # Numeric performance data from AnalyticsProvider
│       │   ├── migrations/                        # Alembic migrations, timestamp-prefixed
│       │   └── session.py
│       │
│       ├── observability/                 # Handbook §8 — structured logging, cost tracking, run tracing
│       │   ├── logging.py
│       │   ├── tracing.py
│       │   └── cost_tracking.py                   # Per-run, per-agent, per-provider-call cost ledger
│       │
│       └── common/                        # Genuinely cross-cutting utilities only — see §5 for what belongs here
│           ├── errors.py                      # Non-provider-specific exceptions (distinct from providers/errors.py)
│           └── types.py                         # Shared primitive types (Duration, TimeWindow, etc.) used across multiple layers
│
├── dashboard/                          # Phase 2+ TypeScript/React control panel (Handbook §4) — does not exist in Phase 0/1
│
├── infra/                              # Deployment, queue, storage config, IaC
│   ├── docker/
│   │   ├── Dockerfile.api
│   │   └── Dockerfile.worker                     # Separate image for queue workers vs. the API process
│   └── local/
│       └── docker-compose.override.yml
│
├── tests/                              # Mirrors src/narraos/ exactly — see §4
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       └── golden_run/                            # The "golden fixture" integration test from Handbook §10
│
├── docs/                               # Per DOCUMENTATION_STRUCTURE.md — not redefined here
│
├── scripts/                            # One-off dev/ops scripts (Handbook §3)
│
├── .github/
│   └── workflows/
│       ├── ci.yml                                 # lint, typecheck, test — every PR
│       └── dependency-boundary-check.yml            # Enforces §6's import graph — see §6.3
│
├── pyproject.toml                      # SOLE dependency + tooling manifest — see §8
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
├── CHANGELOG.md
└── (all root-level docs already established: DEVELOPER_HANDBOOK.md, PROJECT_ARCHITECTURE.md,
     ROADMAP.md, AI_CONTEXT.md, PROJECT_STATE.json, CURRENT_STATE.md, DAILY_DEVELOPMENT_PLAN.md,
     ARCHITECTURE_APPROVAL_REPORT.md, PROVIDER_ARCHITECTURE.md, MEMORY_ARCHITECTURE.md,
     COMPLIANCE_ARCHITECTURE.md, AGENT_SPECIFICATIONS.md, REPOSITORY_STRUCTURE.md)
```

---

## 3. Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Package/module directories | `snake_case`, singular concept, plural only when genuinely a collection (`agents/`, `providers/`) | `trend_discovery/`, `vector_store/` |
| Python files | `snake_case.py` | `run_context.py`, `risk_taxonomy.py` |
| Classes / interfaces | `PascalCase` | `BaseAgent`, `LLMProvider`, `PlatformAdapter` |
| Schema classes | `<Concept><Direction>_v<N>` per Handbook §7 | `TopicResearchInput_v1`, `ComplianceReviewOutput_v1` |
| Agent/Stage package contents | Each agent/stage directory contains, at minimum: `agent.py` (or `stage.py`), `config.py`, and is referenced by — not required to contain — its schema (schemas live centrally under `core/schemas/v1/`, grouped by pipeline phase, not duplicated per-agent) | `core/agents/fact_verification/agent.py` |
| Test files | `test_<module_name>.py`, path-mirrored | `tests/unit/core/agents/fact_verification/test_agent.py` |
| Provider implementations | `<vendor>_<type>.py` inside `implementations/` | `providers/tts/implementations/elevenlabs_tts.py` |
| Migrations | Alembic default: `<timestamp>_<short_description>.py` | `20260901_1200_add_compliance_records.py` |
| Config files | `providers.<environment>.yaml` per `PROVIDER_ARCHITECTURE.md` §15 | `providers.production.yaml` |
| Environment variables | `NARRAOS_<COMPONENT>_<SETTING>`, upper snake case | `NARRAOS_LLM_OPENAI_API_KEY` |

**Rule:** a schema is never defined inline inside an agent or stage file. All versioned schemas live in `core/schemas/v<N>/`, imported by the agents/stages that use them. This keeps the schema surface — the actual contract between every pipeline component — reviewable in one place rather than scattered across dozens of files.

---

## 4. Test Directory Mirroring

`tests/unit/` and `tests/integration/` mirror `src/narraos/` path-for-path:

```
src/narraos/core/agents/fact_verification/agent.py
  → tests/unit/core/agents/fact_verification/test_agent.py

src/narraos/providers/tts/implementations/elevenlabs_tts.py
  → tests/unit/providers/tts/implementations/test_elevenlabs_tts.py
```

`tests/integration/` does not mirror path-for-path in the same way — it's organized by pipeline flow (`tests/integration/full_run/`, `tests/integration/compliance_gate/`) since integration tests by nature cross module boundaries that unit tests deliberately don't.

`tests/fixtures/golden_run/` holds the fixed input topic and expected output *structure* (not exact content, since generation is non-deterministic — Handbook §10) used by the CI-run full pipeline integration test.

---

## 5. What Belongs in `common/` (and What Doesn't)

`common/` is the most easily-abused directory in any repository — it accretes anything a contributor doesn't want to think hard about placing. Two rules keep it honest:

1. **A utility belongs in `common/` only if it's used by at least two of: `core/`, `providers/`, `platforms/`, `memory/`, `compliance/`.** A helper used by only one of those belongs inside that layer's own directory instead.
2. **`common/` may never import from `core/`, `providers/`, `platforms/`, `memory/`, or `compliance/`.** It sits below everything (this is enforced the same way as §6's rules — `common/` has zero inbound dependency exceptions and zero outbound dependencies on domain code). If a "common" utility needs to import from a domain layer, it isn't actually common — it belongs in that layer.

---

## 6. Dependency Boundaries (the enforced import graph)

This extends `DEVELOPER_HANDBOOK.md` §3's original rule ("no module in `core/` or `media/` may import from `platforms/`") with the full graph now that `providers/`, `memory/`, and `compliance/` exist as distinct layers.

### 6.1 Allowed Dependency Directions

```
platforms/          → core/agents/, core/stages/, core/schemas/, providers/*/interface.py (never implementations/)
core/pipeline/       → core/agents/, core/stages/, core/schemas/, db/ (checkpointer only), observability/
core/agents/          → providers/*/interface.py, memory/, core/schemas/, compliance/ (compliance_review agent only), common/, config/
core/stages/           → providers/*/interface.py, core/schemas/, common/, config/
memory/                 → providers/embedding/interface.py, providers/vector_store/interface.py, db/ (source_ref linking only)
compliance/              → db/ (audit_trail.py), memory/ (redaction hooks)
providers/*/interface.py  → common/ only (interfaces are pure contracts, no domain dependencies)
providers/*/implementations/ → external SDKs ONLY. Never core/, never platforms/, never memory/. See §6.2.
providers/registry.py       → providers/*/implementations/ (the one sanctioned exception, see §6.2)
api/                          → core/pipeline/, db/, observability/ (thin — no business logic lives in api/)
common/                        → (nothing above it — see §5.2)
```

### 6.2 The One Sanctioned Exception

`providers/registry.py` is the only file in the entire repository permitted to import from `providers/*/implementations/`. This is deliberate and narrow: something has to construct concrete provider instances and register their factories (`PROVIDER_ARCHITECTURE.md` §14), and centralizing that single point of contact is what makes the DI strategy in that document actually true in code, not just true in the document. If a second file starts importing a concrete implementation directly, that's a violation regardless of how convenient it seems locally.

### 6.3 Enforcement, Not Just Documentation

This graph is intended to be checked automatically in CI (`.github/workflows/dependency-boundary-check.yml`, §2), using an import-linter-style tool configured against the rules in §6.1 — a PR that violates the graph fails CI the same way a failing test does. This is a deliberate escalation from `DEVELOPER_HANDBOOK.md` §3's original phrasing ("Rule: ...") to a mechanically enforced constraint, because a rule that only lives in a document degrades under time pressure; a rule a CI job enforces doesn't.

---

## 7. File Organization Principles Within a Module

1. **An agent or stage directory is self-contained.** `core/agents/topic_research/` contains everything specific to that agent's *logic and configuration* (not its schema, per §3's rule) — there is no scattering of one agent's behavior across multiple top-level directories.
2. **Interfaces and implementations are always physically separated**, even within a single provider type — `providers/llm/interface.py` vs. `providers/llm/implementations/*.py` — so that the DI boundary (§6.2) is visually obvious in the file tree, not just enforced by import rules a contributor has to remember.
3. **No file exceeds roughly 400 lines as a soft ceiling.** This isn't dogma — it's a proxy for "this file is doing too many distinct things and should be split along an existing seam" (e.g., a provider implementation handling both API calls and retry logic should likely split those into the implementation file and a shared retry helper).
4. **Config lives in `config/`, never inline as literals inside domain code** — this restates `DEVELOPER_HANDBOOK.md` §6's "no magic values" rule as a structural/directory-level guarantee rather than a code-review reminder.

---

## 8. Dependency Management: `pyproject.toml` as Sole Source

Resolving Moderate Gap §2.4 directly: **`pyproject.toml` is the only manually maintained dependency manifest.** There is no hand-maintained `requirements.txt` anywhere in this repository.

- All runtime and development dependencies are declared in `pyproject.toml`'s `[project.dependencies]` and `[project.optional-dependencies]` (or the equivalent for the chosen build backend).
- If a specific deployment target requires a `requirements.txt` (some container base images or platform-specific tooling expect one), it is **generated** as a CI/build step from `pyproject.toml` — never edited by hand, never committed as a second source of truth.
- Lockfile discipline (exact pinned versions for reproducible builds) is handled by whatever lockfile mechanism the chosen packaging tool provides, committed to version control, and treated as a build artifact of `pyproject.toml`, not an independent document.

---

## 9. Reconciling This Document With Earlier Ones

Two inconsistencies exist between `DEVELOPER_HANDBOOK.md` §3's original sketch and everything specified since. Flagging and resolving both explicitly here, since this document is now authoritative for layout:

### 9.1 The original top-level `media/` directory is superseded

`DEVELOPER_HANDBOOK.md` §3 originally proposed a top-level `media/` module (`image_gen/`, `animation_gen/`, `voice_synth/`, `video_editor/`, `thumbnail_gen/`). Since then, `PROVIDER_ARCHITECTURE.md` established that image, video, and voice *generation* are provider-backed calls (`ImageProvider`, `VideoProvider`, `TTSProvider`), and `AGENT_SPECIFICATIONS.md` §1.1 classified Image Generation, Animation Generation, Voice Synthesis, and Thumbnail Generation as **Stages** — meaning their logic belongs in `core/stages/`, calling into `providers/`, not in a separate top-level `media/` module.

The one genuine exception is Video Editing: `PROVIDER_ARCHITECTURE.md` §6 explicitly notes that video *assembly* (ffmpeg/MoviePy/OpenCV) is local processing, not an external provider call. That logic lives at `core/stages/video_editing/` (§2 above) — still under `core/stages/`, for consistency with how every other Stage is organized, not carved out into a separate top-level directory just because its implementation happens to be local rather than provider-backed. **The top-level `media/` directory from `DEVELOPER_HANDBOOK.md` §3 no longer exists in this layout; that document's repo structure section should be treated as superseded by this one.**

### 9.2 The original top-level `core/feedback/` directory is superseded

`DEVELOPER_HANDBOOK.md` §3 originally proposed `core/feedback/` for "analytics ingestion + feedback loop logic," written before `AGENT_SPECIFICATIONS.md` classified Feedback Loop as an **Agent** (§3.9 of that document) and Analytics Collection as a **Stage**. Their logic now lives at `core/agents/feedback_loop/` and `core/stages/analytics_collection/` respectively (§2 above), consistent with every other Agent/Stage. **The top-level `core/feedback/` directory no longer exists in this layout.**

---

## 10. Open Items Not Resolved by This Document

- The specific import-linter-style tool for §6.3's enforcement — a tooling choice, not an architecture decision, to be made when CI is actually configured.
- Whether `dashboard/` gets its own `package.json`/build tooling now or only when Phase 2 actually begins — per `DEVELOPER_HANDBOOK.md` §4, building it early is explicitly discouraged; this document only reserves its place in the tree.
- Exact Alembic configuration and migration-review process — an operational detail for when `db/migrations/` first gets populated, not a layout question.

---

*This document is now authoritative for repository layout. `DEVELOPER_HANDBOOK.md` §3 should be treated as historical context, superseded by §2 and §9 above. Any future new top-level directory must trace back to a concept already defined in one of the architecture documents, per §1 rule 2.*
