# NarraOS Developer Handbook

**Version:** 0.1.0
**Status:** Foundational — Planning Stage
**Last Updated:** 2026-07-18
**Owner:** Founder / Core Maintainer

> This handbook is the single source of truth for how NarraOS is built. Every contributor — human or AI agent — follows it. If a rule here conflicts with convenience, the rule wins unless this document is formally updated.

---

## 1. Purpose of This Document

NarraOS is being built as a real, investable AI startup, not a weekend project. That means the engineering foundation has to support:

- Multiple contributors (human and AI) working without stepping on each other
- A codebase that survives platform expansion (YouTube → TikTok → Instagram → X → Facebook → future)
- Long-lived autonomous agents making decisions without a human in the loop for every step
- Auditable, debuggable, and reversible automation (content gets published on your behalf — mistakes are public)

This handbook defines **how we work**, not **what we build**. See `PROJECT_ARCHITECTURE.md` for system design and `ROADMAP.md` for sequencing.

---

## 2. Core Engineering Principles

1. **Platform-agnostic core, platform-specific edges.** Nothing in the core pipeline (research, scripting, generation, editing) may import or reference a specific platform (e.g. YouTube API types). Platform logic lives only in `platforms/<platform_name>/`.
2. **Every pipeline stage is a contract, not a function call.** Stages communicate through well-defined, versioned data schemas (see §7), not shared in-memory objects. This is what lets us swap a stage's implementation (e.g. change the image generator) without touching anything downstream.
3. **Idempotency by default.** Every stage must be safely re-runnable on the same input without duplicating side effects (double-uploading a video, double-charging an API). Side-effecting operations are wrapped and logged with idempotency keys.
4. **Observability is not optional.** If a stage runs and nobody can see what it did, why, and with what inputs/outputs, it isn't done. Structured logging + state tracking (§8) is part of the definition of "complete," not a follow-up task.
5. **Fail loud, fail safe.** Autonomous systems that fail silently produce garbage content at scale. Every stage must fail explicitly, roll back cleanly, and never auto-publish content that hasn't passed its quality gates.
6. **Human override is always possible.** Even at full autonomy, every pipeline run must be pausable, inspectable, and manually approvable at key checkpoints (script, thumbnail, pre-publish) until trust in a stage is proven.
7. **Cost-aware by design.** Every AI-generation stage (LLM calls, image gen, voice synth, video render) tracks token/compute cost per run. This is a media *business*; unit economics matter from day one.

---

## 3. Repository Structure (top-level)

```
narraos/
├── core/                     # Platform-agnostic pipeline engine & orchestration
│   ├── pipeline/              # DAG/workflow definitions, stage runner
│   ├── stages/                 # Individual pipeline stage implementations
│   ├── schemas/                # Pydantic/JSON-schema contracts between stages
│   ├── agents/                  # Autonomous decision-making agents (trend, research, QA, etc.)
│   └── feedback/                # Analytics ingestion + feedback loop logic
├── platforms/
│   ├── youtube/                # YouTube adapter (upload, metadata, analytics pull)
│   ├── tiktok/                 # (future) stub only
│   ├── instagram/              # (future) stub only
│   ├── x/                      # (future) stub only
│   └── facebook/                # (future) stub only
├── media/                     # Generation & editing engines
│   ├── image_gen/
│   ├── animation_gen/
│   ├── voice_synth/
│   ├── video_editor/
│   └── thumbnail_gen/
├── infra/                     # Deployment, queues, storage, IaC
├── dashboard/                  # (Phase 2+) TypeScript/React control panel
├── tests/                      # Mirrors core/ + platforms/ + media/ structure
├── docs/                       # All project documentation (see DOCUMENTATION structure doc)
├── scripts/                    # One-off dev/ops scripts
├── PROJECT_STATE.json
└── AI_CONTEXT.md
```

Rule: **no module in `core/` or `media/` may import from `platforms/`.** Dependency direction is always `platforms/ → core/`, never reversed.

---

## 4. Languages, Frameworks & Tooling

| Layer | Choice | Rationale |
|---|---|---|
| Core pipeline & agents | Python 3.12+ | Best ecosystem for AI/ML, ffmpeg bindings, TTS/image SDKs |
| Orchestration | Task-graph engine (e.g. Prefect/Temporal-style) | Retries, observability, human-in-the-loop checkpoints |
| Data validation | Pydantic v2 | Enforces stage-to-stage schema contracts |
| Queue / async jobs | Redis + worker pool (Celery/RQ-style) | Decouples long-running generation jobs from API layer |
| Database | PostgreSQL | Relational integrity for pipeline runs, content metadata, analytics |
| Object storage | S3-compatible bucket | Video/image/audio assets, versioned |
| API layer | FastAPI | Typed, async, self-documenting |
| Dashboard (Phase 2+) | TypeScript + React | Human oversight UI, approvals, analytics views |
| Testing | pytest (backend), Vitest (dashboard, later) | Standard, well-supported |
| CI/CD | GitHub Actions | Free tier sufficient at this stage |
| Containerization | Docker + docker-compose (local), Kubernetes (later, not now) | Don't over-engineer infra pre-revenue |

**Assumption flagged:** This stack was chosen by Claude based on the pipeline's AI/media-heavy nature. If you have existing infra preferences or team expertise, tell me and I'll revise this table and the architecture doc together.

---

## 5. Branching & Git Workflow

- `main` — always deployable. Protected. No direct commits.
- `develop` — integration branch for the current milestone.
- `feature/<module>-<short-description>` — e.g. `feature/voice-synth-elevenlabs-adapter`
- `fix/<short-description>`
- `agent/<agent-name>-<task>` — branches created by autonomous AI coding agents, always reviewed before merge to `develop`

**Commit convention:** [Conventional Commits](https://www.conventionalcommits.org/)
```
feat(voice-synth): add ElevenLabs adapter with retry logic
fix(pipeline): prevent duplicate publish on retry
docs(architecture): add feedback loop diagram
chore(deps): bump pydantic to 2.9
```

**PR requirements before merge to `develop`:**
1. Passes CI (lint, type check, tests)
2. Touches only its declared module boundary (no silent cross-module coupling)
3. Includes/updates schema definitions if it changes a stage's I/O
4. Includes a one-paragraph "what changed and why" — no empty PR descriptions
5. If written by an AI agent, is reviewed by a human before merge until that module reaches "trusted" status (see §9)

---

## 6. Coding Standards

- **Style:** `ruff` + `black` for Python (auto-formatted, enforced in CI, not debated in review)
- **Typing:** Full type hints required in `core/`, `platforms/`, `media/`. `mypy --strict` on core.
- **Naming:** Modules and functions describe *what*, not *how* (`generate_thumbnail()`, not `run_sdxl_call()`), so implementations can be swapped without renaming call sites.
- **No magic values:** Model names, thresholds, platform limits (e.g. YouTube title length) live in `core/config/` or platform-specific config, never hardcoded inline.
- **Every stage module includes:**
  - Its input schema
  - Its output schema
  - Its failure modes and retry policy
  - Its cost profile (approx tokens/compute/time per run)
- **Secrets:** Never committed. `.env.example` documents every required variable with no real values. Secrets management (Doppler/1Password/Vault) added before any production credential is used.

---

## 7. Data Contracts Between Stages

Every pipeline stage consumes and emits a versioned schema (`core/schemas/`), e.g.:

```
ResearchOutput_v1 → StoryConceptInput_v1
StoryConceptOutput_v1 → ScriptInput_v1
ScriptOutput_v1 → StoryboardInput_v1
...
```

Rules:
- Schemas are versioned (`_v1`, `_v2`); breaking changes bump the version, they don't mutate it in place.
- A stage may only depend on the schema version it declares support for.
- Schema changes require updating `PROJECT_ARCHITECTURE.md`'s data-flow section in the same PR.

This is what makes the system genuinely platform-agnostic and swap-friendly (e.g., replacing the voice synth provider touches one adapter, not the whole pipeline).

---

## 8. Observability & State Tracking

- Every pipeline run gets a unique `run_id`, persisted in Postgres, traceable end-to-end.
- Every stage logs: inputs (or references to them), outputs, duration, cost, success/failure, retry count.
- `PROJECT_STATE.json` tracks project-level status (see that file); run-level state lives in the database, not in static files.
- Failed runs are never silently dropped — they land in a review queue.

---

## 9. Autonomy Levels (Human-in-the-Loop Policy)

Each pipeline stage is assigned a trust level that governs whether it runs unattended:

| Level | Meaning | Applies When |
|---|---|---|
| L0 – Manual | Human triggers and reviews every run | New/unproven stage |
| L1 – Supervised | Runs automatically, output held for human approval before proceeding | Default for new stages after initial testing |
| L2 – Spot-checked | Runs and proceeds automatically; a sample is reviewed post-hoc | Stage has a track record of reliability |
| L3 – Autonomous | Runs and proceeds fully unattended | Only after sustained L2 performance against defined quality metrics |

Publishing to a real platform account is **never below L1** until the founder explicitly raises it, regardless of how well upstream stages perform.

---

## 10. Testing Standards

- Unit tests for every stage's core logic (mock external AI/API calls).
- Contract tests verifying schema compatibility between adjacent stages.
- Integration test: one full pipeline run against a "golden" fixture topic, run in CI on every merge to `develop`, output diffed against expected structure (not exact content, since generation is non-deterministic).
- No stage ships to `develop` without tests. No exceptions for "AI wrote it fast."

---

## 11. AI Coding Agent Conduct Rules

Since AI agents (including Claude Code) will write meaningful parts of this codebase:

1. Agents work from `AI_CONTEXT.md` and this handbook — not from ad hoc chat instructions that contradict them.
2. Agents open PRs; they do not merge to `main` or `develop` themselves.
3. Agents must update relevant docs (architecture, schemas, roadmap status) in the same PR as the code change — docs drift is treated as a bug.
4. Agents flag assumptions explicitly in PR descriptions rather than silently guessing.
5. Agents do not introduce new external dependencies without a one-line justification in the PR.

---

## 12. Definition of Done (any task)

A task is done when:
- [ ] Code merged to `develop` with passing CI
- [ ] Tests written and passing
- [ ] Docs updated (architecture/schemas/roadmap as applicable)
- [ ] `PROJECT_STATE.json` reflects the new status
- [ ] No hardcoded secrets, no TODOs without a linked issue

---

*This handbook will evolve. Changes go through a PR against this file itself, same as code.*
