# NarraOS — Project Architecture

**Version:** 0.1.0
**Status:** Foundational Design — Pre-Implementation
**Last Updated:** 2026-07-18

---

## 1. What NarraOS Is

NarraOS is an **Autonomous AI Media Operating System** — an operating system for content, not a single-purpose automation script. It owns the full lifecycle of a piece of media content from trend discovery to post-publish learning, and is designed so that lifecycle is **identical in shape regardless of platform**. YouTube is the first platform implementation; it is not the architecture.

The distinction matters structurally: a "YouTube automation tool" would hardcode YouTube's upload API, title length, thumbnail spec, and analytics format throughout the codebase. NarraOS instead treats YouTube as one **adapter** plugged into a platform-agnostic core.

---

## 2. System Layers

```
┌──────────────────────────────────────────────────────────────┐
│  LAYER 5 — CONTROL & OVERSIGHT                                 │
│  Dashboard (human approval, monitoring, overrides)              │
├──────────────────────────────────────────────────────────────┤
│  LAYER 4 — PLATFORM ADAPTERS                                    │
│  youtube/  tiktok/  instagram/  x/  facebook/  (pluggable)      │
├──────────────────────────────────────────────────────────────┤
│  LAYER 3 — ORCHESTRATION ENGINE                                 │
│  Pipeline DAG runner · stage scheduler · retry/idempotency       │
│  · state persistence · human-checkpoint gating                  │
├──────────────────────────────────────────────────────────────┤
│  LAYER 2 — CORE PIPELINE STAGES (platform-agnostic)              │
│  Discovery → Research → Generation → Production → Packaging       │
├──────────────────────────────────────────────────────────────┤
│  LAYER 1 — FOUNDATION SERVICES                                  │
│  Storage (assets) · Database (state/metadata) · Queue (jobs)      │
│  · Model Gateway (LLM/image/voice/video providers) · Config       │
│  · Secrets · Observability (logs/metrics/cost tracking)          │
└──────────────────────────────────────────────────────────────┘
```

Data and control flow downward and upward: Layer 3 orchestrates Layer 2 stages using Layer 1 services, and hands finished content to Layer 4 for platform-specific delivery. Layer 5 sits alongside, observing and gating Layer 3 at defined checkpoints.

---

## 3. The Core Pipeline (Platform-Agnostic)

This is the lifecycle NarraOS automates, grouped into five phases. Every stage below is a swappable module with a defined input/output contract (see `DEVELOPER_HANDBOOK.md` §7).

### Phase A — Discovery & Strategy
| Stage | Function |
|---|---|
| Trend Discovery | Scans signals (search trends, platform trending data, social listening) for emerging topics/niches |
| Competitor Analysis | Analyzes competitor content performance, formats, cadence, gaps |
| Virality Prediction | Scores candidate topics/formats against a learned performance model before any content is made |

### Phase B — Research & Story
| Stage | Function |
|---|---|
| Topic Research | Gathers source material, data, context for the chosen topic |
| Fact Verification | Cross-checks claims against sources; flags unverifiable claims for human review |
| Story Generation | Converts research into a narrative concept — angle, hook, arc |
| Retention Optimization | Structures the narrative against known retention patterns (pacing, open loops, payoff placement) |

### Phase C — Creative Production
| Stage | Function |
|---|---|
| Script Writing | Full script generation from the optimized story structure |
| Storyboard Generation | Shot-by-shot / scene-by-scene visual plan derived from the script |
| Image Generation | Generates required visual assets per storyboard |
| Animation Generation | Animates/motions static assets where required |
| Voice Synthesis | Generates narration/voiceover audio from the script |
| Video Editing | Assembles visuals, audio, pacing, transitions into a rendered video |
| Thumbnail Generation | Produces platform-optimized thumbnail candidates |

### Phase D — Packaging & Distribution
| Stage | Function |
|---|---|
| SEO Generation | Titles, descriptions, tags/hashtags, metadata per platform |
| Asset Packaging | Bundles final video, thumbnail, and metadata into a platform-ready package |
| Upload Preparation | Validates package against target platform's constraints (Layer 4 adapter contract) |
| Publish | Executes platform-specific publish via the adapter |

### Phase E — Learning
| Stage | Function |
|---|---|
| Analytics Collection | Pulls post-publish performance data from the platform adapter |
| Feedback Loop | Feeds performance data back into Virality Prediction, Retention Optimization, and Story Generation models/prompts to improve future runs |

The Feedback Loop is what makes this an *operating system* rather than a linear pipeline: Phase E output becomes Phase A/B input for future runs, closing the loop.

---

## 4. Platform Adapter Contract (Layer 4)

Every platform adapter (`platforms/<name>/`) must implement a single interface so the core never needs platform-specific logic:

```
PlatformAdapter:
  - validate(package: AssetPackage) -> ValidationResult
  - publish(package: AssetPackage) -> PublishResult
  - fetch_analytics(content_id: str) -> AnalyticsSnapshot
  - constraints() -> PlatformConstraints   # title length, formats, aspect ratio, etc.
```

Adding TikTok, Instagram, X, or Facebook later means writing a new adapter that satisfies this interface — **zero changes to Layers 1–3**. This contract is the single most important architectural guarantee in the system and should not be weakened for convenience.

---

## 5. Orchestration Engine (Layer 3)

- Pipeline runs are modeled as a **DAG**, not a linear script — some stages can run in parallel (e.g., thumbnail generation can start once the script is final, without waiting for full video editing).
- Each run is assigned a `run_id` and persists its state after every stage (crash recovery, resumability).
- Human-checkpoint gating gets implemented here: the orchestrator can pause a run at any stage boundary until an approval event is received (see Handbook §9, Autonomy Levels).
- Retry policy is stage-specific and declared in that stage's module (e.g., transient API failure → retry 3x with backoff; content-quality failure → route to human review, don't retry blindly).

---

## 6. Foundation Services (Layer 1)

- **Model Gateway** — a single internal interface for calling external AI providers (LLM, image gen, voice synth, video gen). Stages never call provider SDKs directly; they call the gateway. This lets us swap providers (e.g., change voice synth vendor) and track cost/usage centrally.
- **Storage** — all generated assets (images, audio, video, thumbnails) versioned in object storage, referenced by ID in Postgres, never embedded in pipeline state directly.
- **Database** — pipeline run state, content metadata, platform publish records, analytics history.
- **Queue** — long-running generation/render jobs are dispatched to workers, not run inline in request handlers.
- **Observability** — structured logs, per-stage cost tracking, run tracing (see Handbook §8).

---

## 7. Why Platform-Agnostic Matters Here Specifically

Two design decisions exist *only* because of the multi-platform requirement, and should not be "simplified away" during MVP build-out:

1. **AssetPackage is a generic bundle**, not a "YouTube video." It contains a video/image asset, metadata, and a set of platform-target flags. The YouTube adapter interprets it for YouTube; a future TikTok adapter interprets the same object differently (e.g., different aspect ratio requirement triggers a re-render request back through Video Editing, not a hack inside the adapter).
2. **Virality Prediction and Retention Optimization are platform-parameterized, not platform-hardcoded.** The underlying models/prompts take a platform profile as input (audience behavior, format norms) rather than encoding YouTube assumptions into the logic itself.

---

## 8. Non-Goals (For Now)

To keep the architecture honest about sequencing, these are explicitly **not** part of the current design scope:

- Multi-tenant SaaS (this is a single-operator system for now; multi-tenant is a future architecture decision, not a v1 concern)
- Real-time/live content
- Full autonomous publish with zero human checkpoints (see Autonomy Levels — earned incrementally, not assumed)
- Kubernetes/multi-region infra (premature before there's real load)

---

## 9. Open Architecture Decisions

These are flagged, not resolved, and should be revisited as the roadmap progresses:

- Which orchestration engine specifically (Prefect vs Temporal vs custom DAG runner) — needs a short spike before Phase 1 build.
- Which model providers per generation stage (image/voice/video) — cost/quality tradeoffs, revisit once budget is defined.
- Dashboard build timing — Phase 1 may only need a CLI/API; React dashboard can wait until manual review volume justifies it.

---

*This document is a living contract. Any change to stage boundaries, the platform adapter interface, or layer responsibilities must be reflected here in the same PR that changes the code.*
