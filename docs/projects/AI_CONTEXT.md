# AI_CONTEXT.md

**Purpose:** This file is the first thing any AI agent (Claude Code, or any other coding agent) should read before touching this repository. It is written for machine consumption first, human readability second.

---

## 1. What This Project Is

NarraOS is an **Autonomous AI Media Operating System**. It automates the full lifecycle of AI-generated media content: trend discovery → research → fact verification → story/script generation → image/animation/voice generation → video editing → thumbnail/SEO → packaging → publishing → analytics → feedback loop.

**First platform:** YouTube.
**Architecture requirement:** platform-agnostic core; platform logic isolated to adapters. This is a hard constraint, not a nice-to-have — see `PROJECT_ARCHITECTURE.md` §4 and §7.

NarraOS is an **AI Operating System**, not a "YouTube bot." If a proposed change makes sense only because "it's for YouTube," it belongs in `platforms/youtube/`, never in `core/` or `media/`.

---

## 2. Required Reading Order

Before generating code, an agent must have context from, in this order:

1. `AI_CONTEXT.md` (this file)
2. `DEVELOPER_HANDBOOK.md` — how we work, standards, git workflow, autonomy levels
3. `PROJECT_ARCHITECTURE.md` — system design, layers, stage contracts, platform adapter interface
4. `ROADMAP.md` — what phase we're in, what's in scope right now
5. `PROJECT_STATE.json` — current live status (what's built, what's next, what's blocked)

If any instruction given in a chat/task conflicts with these documents, the documents win unless a human explicitly says they're being updated (and then the docs must be updated in the same change).

---

## 3. Current Phase (check `PROJECT_STATE.json` for authoritative value)

As of this writing: **Phase 0 — Engineering Foundation.** No pipeline code has been written yet. Do not start implementing pipeline stages until Phase 0 exit criteria (see `ROADMAP.md`) are met and a human explicitly moves the project into Phase 1.

---

## 4. Hard Rules for Any Agent Working on This Repo

1. **Never hardcode platform-specific logic outside `platforms/<name>/`.** If you find yourself importing YouTube API types in `core/` or `media/`, stop — that's a contract violation.
2. **Never let a pipeline stage publish content without checking its current Autonomy Level** (`DEVELOPER_HANDBOOK.md` §9). Default to the most conservative level (L0/manual) if unclear.
3. **Never introduce a new external dependency without justifying it in one line in the PR description.**
4. **Never merge to `main` or `develop` directly.** Open a PR, even as an agent.
5. **Never silently change a stage's input/output schema.** Schema changes are versioned (`_v1` → `_v2`), and the architecture doc's data-flow section must be updated in the same change.
6. **Never fabricate progress in `PROJECT_STATE.json`.** If something is partially done, it's `in_progress`, not `done`.
7. **Always flag assumptions explicitly** rather than silently picking a default when a decision materially affects architecture, cost, or platform behavior.
8. **Always write tests alongside code** — see Handbook §10. Code without tests is not complete.

---

## 5. Vocabulary / Glossary

| Term | Meaning |
|---|---|
| **Stage** | A single unit of the pipeline (e.g., Script Writing, Voice Synthesis) with a defined input/output schema |
| **Run** | One end-to-end (or partial) execution of the pipeline for one piece of content, tracked by `run_id` |
| **AssetPackage** | The platform-agnostic bundle (video/image + metadata + platform flags) handed to a platform adapter |
| **Adapter** | Platform-specific implementation satisfying the `PlatformAdapter` interface (validate/publish/fetch_analytics/constraints) |
| **Model Gateway** | Internal single point of access to external AI providers (LLM, image, voice, video generation) |
| **Autonomy Level (L0–L3)** | How much human checkpoint gating a stage requires before proceeding (see Handbook §9) |
| **Feedback Loop** | The mechanism by which post-publish analytics influence future Discovery/Research/Story stages |

---

## 6. Where Things Live (quick index)

```
core/pipeline/       → DAG runner, orchestration engine integration
core/stages/          → Individual stage implementations (platform-agnostic)
core/schemas/          → Versioned Pydantic contracts between stages
core/agents/            → Autonomous decision agents (trend, research, QA/fact-check, etc.)
core/feedback/           → Analytics ingestion + feedback loop logic
platforms/youtube/       → YouTube adapter (only platform implemented in Phase 1)
media/image_gen/         → Image generation engine
media/animation_gen/      → Animation generation engine
media/voice_synth/         → Voice synthesis engine
media/video_editor/         → Video assembly/editing engine
media/thumbnail_gen/         → Thumbnail generation engine
infra/                        → Deployment, queue, storage config, IaC
dashboard/                     → (Phase 2+) React control panel — do not build early
docs/                            → All documentation, see documentation structure doc
```

---

## 7. Decision-Making Heuristics for Agents

When facing an ambiguous implementation choice:

1. **Does the architecture doc already answer this?** Check before asking or guessing.
2. **Does it affect the platform-agnostic guarantee?** If yes, default to the more agnostic option even if slower to build.
3. **Does it affect cost at scale?** Flag it — this is a business, not just a codebase.
4. **Is it reversible?** Prefer reversible, inspectable choices during Phase 0–2 while trust is still being established.
5. **When truly unresolved,** implement the smallest reasonable version, flag the assumption clearly in the PR, and note it as an open decision rather than blocking indefinitely.

---

## 8. What NOT to Build Right Now

Per `PROJECT_ARCHITECTURE.md` §8 (Non-Goals) and current roadmap phase:

- No dashboard/UI yet
- No multi-tenant/SaaS scaffolding
- No second platform adapter until Phase 4
- No Kubernetes or multi-region infra
- No fully unattended publishing (L3) — not earned yet

If a task seems to require one of these, stop and flag it rather than building around the constraint.

---

*This file should be updated whenever `PROJECT_ARCHITECTURE.md` or `ROADMAP.md` changes in a way that affects how an agent should reason about the codebase.*

## Architecture Status

The following architecture documents have been completed and approved:

- Provider Architecture
- Memory Architecture
- Compliance Architecture
- Agent Specifications
- Repository Structure
- Plugin Architecture
- Schema Reference

The architecture is awaiting one final review before implementation begins.

No additional architectural documents should be generated unless a critical issue is discovered.

The next expected milestone is Repository Initialization (Day 0).
