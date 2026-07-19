# NarraOS — Daily Development Plan

**Version:** 0.1.0
**Last Updated:** 2026-07-18
**Applies to:** Founder + AI coding agents, Phase 0 → Phase 2

> This is the operating rhythm — how work actually happens day to day, not just what the roadmap says should eventually exist.

---

## 1. Daily Loop (Standard Working Day)

```
1. STATE CHECK        Read PROJECT_STATE.json — what's the current phase, what's next_actions,
                        what's blocked. This is the day's starting point, not memory or habit.

2. PLAN THE DAY        Pick 1–3 concrete tasks from the current phase's checklist in ROADMAP.md.
                        Prefer finishing something over starting something new.

3. BUILD               Work the task. If an AI agent is doing the implementation, it reads
                        AI_CONTEXT.md + DEVELOPER_HANDBOOK.md first, opens a feature/agent branch,
                        and works against the schema contracts in PROJECT_ARCHITECTURE.md.

4. REVIEW              Every PR reviewed against DEVELOPER_HANDBOOK.md §12 (Definition of Done)
                        before merge to develop. No self-merging of agent-authored PRs without
                        at least a founder skim during Phase 0–2.

5. UPDATE STATE        PROJECT_STATE.json updated to reflect what actually happened — not
                        aspirational status. Docs updated in the same PR if architecture/schemas
                        changed.

6. LOG OPEN QUESTIONS   Anything ambiguous that came up gets written down (as an ADR draft in
                        docs/decisions/ if architectural, or as a next_action if just sequencing)
                        rather than resolved silently and forgotten.
```

---

## 2. Weekly Rhythm

| Day | Focus |
|---|---|
| Mon | State check, week planning against current roadmap phase, resolve any open architecture decisions blocking the week's work |
| Tue–Thu | Build days — implementation, following the daily loop above |
| Fri | Review week's PRs collectively, update `PROJECT_STATE.json` with weekly summary, revisit `ROADMAP.md` exit criteria progress, write any ADRs for decisions made during the week |

---

## 3. Phase 0 Daily Breakdown (Right Now)

Since we're in Phase 0, here's what "today" and the following days concretely look like until Phase 1 starts:

**Day 1 (today):**
- [x] Generate all Phase 0 foundational documents
- [ ] Founder reads and either approves or requests changes to each doc
- [ ] Flagged assumptions (tech stack, team structure, orchestration engine, model providers) get resolved or explicitly deferred with an owner and date

**Day 2:**
- [ ] Write ADR-0001 for orchestration engine choice (spike: compare 2–3 candidates against NarraOS's specific needs — human-checkpoint gating, DAG parallelism, retry semantics)
- [ ] Write ADR-0002 for initial model provider selection (LLM, image gen, voice synth) with rough cost-per-run estimate

**Day 3:**
- [ ] Scaffold the repository structure exactly per `PROJECT_ARCHITECTURE.md` §2 (empty modules, no logic)
- [ ] Set up CI skeleton (lint, type check, test runner — even with zero tests initially)
- [ ] Set up `.env.example` and secrets-handling approach

**Day 4:**
- [ ] Stand up foundation services locally via docker-compose (Postgres, Redis, object storage emulation)
- [ ] Confirm Model Gateway interface design (even before real provider integration) — this unblocks all generation stages in Phase 1

**Day 5:**
- [ ] Phase 0 review: check every exit criterion in `ROADMAP.md` Phase 0 section
- [ ] If met — formally transition `PROJECT_STATE.json` current_phase to `phase_1`
- [ ] If not met — identify the specific blocker and address it before moving on (don't start Phase 1 work with Phase 0 loose ends)

---

## 4. Phase 1 Daily Pattern (Preview — once Phase 0 closes)

Phase 1 is about proving each stage in isolation before wiring them together. Recommended daily pattern once there:

- One stage implemented and tested per 1–2 days (text-generation stages faster, media-generation stages slower due to external API integration and quality tuning)
- Each stage's completion updates `PROJECT_STATE.json`'s `pipeline_stages` block
- No stage is "done" without: schema defined, unit tests passing, cost-per-run logged, and a manual test run producing real output reviewed by the founder

---

## 5. Rules That Keep the Daily Loop Honest

1. **No day ends with `PROJECT_STATE.json` reflecting fiction.** If something is half-done, it says so.
2. **No task starts that isn't traceable to the current roadmap phase.** Enthusiasm for a Phase 3 feature during Phase 0 gets written down as a future roadmap note, not built early.
3. **Blockers get logged the day they're discovered**, in `PROJECT_STATE.json`'s `blockers` array, not carried silently in someone's head.
4. **Every week, roadmap exit criteria are actually checked against reality**, not assumed met because time has passed.

---

*This plan is intentionally lightweight for a solo-founder + AI-agent operation. If/when the team grows (Roadmap Phase 5), this document should be revisited alongside `DEVELOPER_HANDBOOK.md`'s contributor conduct rules.*
