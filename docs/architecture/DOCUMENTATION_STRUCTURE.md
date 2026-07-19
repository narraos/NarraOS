# NarraOS — Documentation Structure

**Version:** 0.1.0
**Last Updated:** 2026-07-18

This defines where every piece of project knowledge lives, so nothing ends up scattered across chats, Slack, or someone's memory. The actual folder skeleton has been created at `/docs` alongside this spec.

---

## 1. Root-Level Documents (repo root, not inside `/docs`)

These are the "must find in 5 seconds" documents — deliberately kept at root:

```
DEVELOPER_HANDBOOK.md      Engineering standards & workflow
PROJECT_ARCHITECTURE.md    System design
ROADMAP.md                 Phased plan
AI_CONTEXT.md              Orientation file for AI agents
PROJECT_STATE.json         Machine-readable live status
DAILY_DEVELOPMENT_PLAN.md  Execution cadence
README.md                  (to be created at Phase 1 start) — public-facing project summary
```

Rule: root-level docs describe **the whole project**. Anything specific to one module/platform/decision belongs under `/docs`.

---

## 2. `/docs` Folder Layout

```
docs/
├── architecture/         # Deep-dive design docs per subsystem (one file per major component,
│                          #  e.g. orchestration-engine.md, model-gateway.md, schema-versioning.md)
├── api/                   # API reference (generated + hand-written notes), once core/API layer exists
├── agents/                 # Design docs for each autonomous agent (trend, research, QA/fact-check,
│                          #  virality prediction) — reasoning, prompts, evaluation criteria
├── platforms/
│   ├── youtube/            # YouTube-specific integration notes, API quirks, constraints
│   ├── tiktok/               # (stub, populated at Phase 4)
│   ├── instagram/             # (stub, populated at Phase 4)
│   ├── x/                       # (stub, populated at Phase 4)
│   └── facebook/                 # (stub, populated at Phase 4)
├── runbooks/                # Operational procedures — "what to do when X breaks," incident response,
│                          #  manual override procedures
├── decisions/                # Architecture Decision Records (ADRs) — one file per significant
│                          #  decision, immutable once written (superseded, not edited)
└── onboarding/                # Setup guides for new contributors (human or agent), local dev
                             #  environment, credentials setup (references, never real secrets)
```

---

## 3. Document Types & Conventions

| Type | Location | Convention |
|---|---|---|
| Architecture Decision Record (ADR) | `docs/decisions/NNNN-short-title.md` | Numbered sequentially, never edited after acceptance — superseded by a new ADR that references it |
| Subsystem deep-dive | `docs/architecture/<subsystem>.md` | Written when a subsystem's design exceeds what fits reasonably in `PROJECT_ARCHITECTURE.md` |
| Agent design doc | `docs/agents/<agent-name>.md` | Includes: purpose, inputs, decision logic/prompting approach, evaluation metrics, known failure modes |
| Platform integration notes | `docs/platforms/<platform>/*.md` | API quirks, rate limits, content policy constraints, auth setup |
| Runbook | `docs/runbooks/<scenario>.md` | Imperative, step-by-step, written for "it's 11pm and something broke" |
| Onboarding guide | `docs/onboarding/*.md` | Assumes zero prior context; a new agent or contributor should be productive after reading it |

---

## 4. ADR Template (used for every entry in `docs/decisions/`)

```markdown
# ADR-000X: <Decision Title>

Status: Proposed | Accepted | Superseded by ADR-000Y
Date: YYYY-MM-DD

## Context
What situation/problem prompted this decision?

## Decision
What was decided.

## Alternatives Considered
What else was on the table, and why it wasn't chosen.

## Consequences
What this makes easier, what it makes harder, what it locks in.
```

The two open items flagged in `PROJECT_ARCHITECTURE.md` §9 (orchestration engine choice, model provider selection) should become the first two ADRs once resolved.

---

## 5. Ownership & Freshness Rules

- Any PR that changes system behavior updates the relevant doc **in the same PR** — docs drift is treated as a bug, not cleanup debt (per `DEVELOPER_HANDBOOK.md` §11).
- `PROJECT_STATE.json` is the only place "current status" is asserted — narrative docs (architecture, roadmap) describe design and plan, not live state, to avoid two sources of truth going stale independently.
- ADRs are never edited post-acceptance; corrections happen via a new superseding ADR, preserving decision history.

---

## 6. Folder Skeleton (created)

```
docs/
├── architecture/.gitkeep
├── api/.gitkeep
├── agents/.gitkeep
├── platforms/
│   ├── youtube/.gitkeep
│   ├── tiktok/.gitkeep
│   ├── instagram/.gitkeep
│   ├── x/.gitkeep
│   └── facebook/.gitkeep
├── runbooks/.gitkeep
├── decisions/.gitkeep
└── onboarding/.gitkeep
```

`.gitkeep` placeholders exist purely so the empty structure is version-controlled from day one; they get deleted as real content lands in each folder.
