# NarraOS — YouTube Adapter Architecture

**Version:** 0.1.0
**Status:** Specification — required before the YouTube plugin's `Publish` path is implemented
**Last Updated:** 2026-07-18
**Resolves:** Gap §1.4 in `ARCHITECTURE_APPROVAL_REPORT.md` — the last of the four originally-flagged critical gaps (YouTube publish quota was unaddressed anywhere in the architecture)

> This document specifies the YouTube plugin's `constraints()` (`PROJECT_ARCHITECTURE.md` §4), its quota management, scheduling, retry, queueing, and degradation behavior. It is a plugin-level specification under `PLUGIN_ARCHITECTURE.md`, not a change to core — nothing here requires modifying `core/`. No implementation code.

---

## 1. The Problem This Solves

The YouTube Data API enforces a daily quota, denominated in **quota units**, not raw request count — different operations cost different amounts, and a single video upload is disproportionately expensive relative to most other calls. A default project quota supports only a small number of uploads per day before every other call NarraOS also needs (metadata updates, analytics pulls) is competing for the same shrinking budget. Google's process for requesting a quota increase requires demonstrated usage history — meaning the ceiling is at its tightest exactly when the project is newest.

**Note on precision:** the exact unit costs and default ceiling are values Google publishes and occasionally revises. This document specifies the *architecture* for managing quota as a scarce, trackable resource — the specific numbers plugged into that architecture (§3) should be verified against current API documentation at implementation time, not assumed frozen from whatever was true when this document was written.

**A critical technical nuance that shapes this entire design:** the YouTube Data API does not return a live "quota remaining" value on its responses. Unlike some APIs where `rate_limit_status()` (`PROVIDER_ARCHITECTURE.md` §10) can simply reflect a header the server sends back, YouTube quota consumption is only visible after the fact, in Google Cloud Console — not in-band on individual API responses. **This means NarraOS must be the source of truth for its own quota consumption**, tracked locally and proactively, with actual API quota-exceeded errors treated as a backstop/correction signal, not the primary control mechanism. Every design decision below follows from this constraint.

---

## 2. Where This Fits

This is a specification for the YouTube plugin (`platforms/youtube/`, per `REPOSITORY_STRUCTURE.md` §2), governed by `PLUGIN_ARCHITECTURE.md`. Nothing here changes `core/`. Two things are deliberately designed to be **more general than YouTube alone**, even though YouTube is the only plugin implementing them today:

- The **Quota Ledger** pattern (§4) is a generic mechanism any future plugin with a hard operation-cost budget can reuse — it is described here in YouTube-specific terms but is not YouTube-specific in structure.
- The **Upload Queue** pattern (§6) likewise — any platform with publish scheduling constraints follows the same shape.

Per `PLUGIN_ARCHITECTURE.md` §9's extension rule, neither required a change to the `PlatformAdapter` or `PluginCapabilities` contracts to exist — they compose entirely within what those contracts already expose (`constraints()`, `rate_limit_model`).

---

## 3. YouTube Constraints Specification

Extending the generic `PlatformConstraints` referenced in `PROJECT_ARCHITECTURE.md` §4:

```
YouTubeConstraints extends PlatformConstraints:
  daily_quota_ceiling: int                    # project's current daily unit allowance (verify against current Google docs)
  operation_costs: Dict[OperationType, int]      # e.g. UPLOAD, METADATA_UPDATE, ANALYTICS_READ, LIST/SEARCH — unit cost per call
  quota_reset_time: TimeOfDay                     # daily reset boundary (Pacific Time, per API behavior)
  safety_margin_pct: float                          # fraction of daily_quota_ceiling never intentionally consumed — buffer for
                                                       # retries, manual operations, and estimation error (§4)
  max_uploads_per_day: int                            # derived: floor((daily_quota_ceiling * (1 - safety_margin_pct)) / operation_costs[UPLOAD])
  title_max_length: int
  description_max_length: int
  supported_aspect_ratios: List[AspectRatio]
  thumbnail_spec: ImageSpec
```

- `max_uploads_per_day` is **derived**, not independently configured — it always follows from the ledger math, so a change to `daily_quota_ceiling` (e.g., after Google approves a quota increase) automatically propagates to scheduling behavior (§5) without a separate manual adjustment.
- `safety_margin_pct` exists because self-tracked estimates (§1) can drift from reality — reserving a buffer means a small accounting discrepancy results in a slightly conservative schedule, never an actual quota-exceeded failure on a real publish attempt.

---

## 4. Quota Ledger

The mechanism that makes the YouTube `PublishingProvider.rate_limit_status()` call (`PROVIDER_ARCHITECTURE.md` §10) meaningful, given §1's constraint that the API itself won't tell us:

```
QuotaLedger (scoped per plugin, per day):
  record_consumption(operation_type: OperationType, units: int) -> None       # called immediately after every API call, success or failure
  remaining_budget() -> int                                                       # daily_quota_ceiling - sum(consumed) - safety_margin reserve
  would_exceed(operation_type: OperationType) -> bool                                # pre-flight check before attempting a call
  reconcile(actual_error: QuotaExceededError | null) -> None                           # corrects the ledger if reality disagrees with estimate
  reset() -> None                                                                        # invoked at quota_reset_time (§3)
```

**Rules:**

1. **Every** call through the YouTube `PublishingProvider` or `AnalyticsProvider` implementation — successful or not — records its estimated cost via `record_consumption()` immediately, before the result is known. A failed call still consumed quota on Google's side (in most cases) and must be accounted for the same way, not silently excluded because it didn't succeed.
2. **Pre-flight, not post-hoc.** `would_exceed()` is checked before dispatching any call, not after. This is what §1's "NarraOS must be the source of truth" principle actually means operationally — the system decides not to attempt a call it believes would fail, rather than attempting it and discovering the failure from a `QuotaExceededError` response.
3. **`reconcile()` is the correction path**, not the primary mechanism. If a call NarraOS believed was within budget nonetheless returns `QuotaExceededError` (`PROVIDER_ARCHITECTURE.md` §16), the ledger's running total is corrected upward to match — the estimate was wrong, and the ledger self-heals for the remainder of the day rather than repeating the same misjudgment.
4. This ledger is exactly the `VectorStoreProvider`-style extension pattern: it lives inside the YouTube plugin's implementation, not core, but is structured generically enough (§2) that a future plugin facing the same "API doesn't expose live quota" problem reuses the pattern rather than reinventing it.

---

## 5. Quota Allocation Priority

Not all YouTube operations are equally important when budget is tight. The Quota Ledger enforces a priority order, so a Publish attempt is never starved by lower-priority calls consuming the day's remaining budget first:

| Priority | Operation | Rationale |
|---|---|---|
| 1 (highest) | `Publish` (upload) | The entire point of the pipeline; never sacrificed for a lower-priority call |
| 2 | `Upload Preparation` validation calls (metadata checks) | Directly gates a pending Publish |
| 3 | Metadata updates to already-published content | Important but deferrable without losing the publish itself |
| 4 (lowest) | `Analytics Collection` | Deferrable — a delayed analytics pull loses freshness, not correctness; a blocked publish loses the content entirely |

**Mechanism:** before consuming budget for a priority-3 or priority-4 operation, the Quota Ledger checks whether doing so would jeopardize the day's remaining scheduled priority-1/2 operations (per the Upload Queue's committed schedule, §6) — if so, the lower-priority call is deferred, not the higher-priority one. This directly extends `PROVIDER_ARCHITECTURE.md` §12's `polling_interval_recommendation()` for `AnalyticsProvider`: under quota pressure, the YouTube plugin widens its own analytics polling interval beyond that baseline recommendation, specifically to protect publish budget.

---

## 6. Upload Queue

Publishing to YouTube is **queue-mediated**, not a direct synchronous call from the `Publish` stage on run completion. This is a deliberate divergence from the generic pipeline flow in `PROJECT_ARCHITECTURE.md` §3, scoped to this plugin: the `Publish` stage's job becomes *enqueueing* a validated `AssetPackage`, not immediately calling `PublishingProvider.upload()`.

```
YouTubeUploadQueueEntry:
  entry_id: UUID
  run_id: UUID                          # Handbook §8 traceability
  content_id: str
  package_ref: AssetPackage
  target_publish_time: timestamp | null      # null = "as soon as budget allows," otherwise a specific scheduled time
  status: QUEUED | SCHEDULED | UPLOADING | PUBLISHED | DEFERRED | FAILED
  attempts: int
  idempotency_key: str                          # per SCHEMA_REFERENCE.md §2's Task_v1 requirement — mandatory
  created_at: timestamp
  last_attempted_at: timestamp | null
```

**Queue processing loop** (a worker consuming from the Layer 1 Queue foundation service, per `PROJECT_ARCHITECTURE.md` §6):

1. Worker wakes on schedule (or on new entry arrival).
2. For each `QUEUED`/`SCHEDULED` entry whose `target_publish_time` has arrived (or is null and budget allows): check `QuotaLedger.would_exceed(UPLOAD)` (§4).
3. If budget allows: attempt upload, transition to `UPLOADING`, then `PUBLISHED` or `FAILED` per the retry policy (§7).
4. If budget does not allow: transition to `DEFERRED` (§8) — explicitly, not left `QUEUED` indefinitely without explanation.
5. `PUBLISHED`/`FAILED` are terminal for that entry; `DEFERRED` entries are re-evaluated on the next cycle after `quota_reset_time` (§3).

**Scheduling strategy within the queue:** entries are dequeued oldest-`created_at`-first within the same priority tier (§5), not last-in-first-out — a run that finished earlier in the day shouldn't be bumped by one that finished later, absent an explicit `target_publish_time` override. `target_publish_time` support is itself gated by `PluginCapabilities.supports_scheduling` (`PLUGIN_ARCHITECTURE.md` §5) — if a future platform's plugin doesn't support scheduled publish, its queue only ever processes "as soon as budget allows" entries.

---

## 7. Retry Policy (YouTube-specific error mapping)

Extending `PROVIDER_ARCHITECTURE.md` §16/§17's general taxonomy and retry rules with YouTube's specific mapping:

| YouTube API Response | Maps To | Retry? |
|---|---|---|
| HTTP 403, reason `quotaExceeded` | `QuotaExceededError` | No — never retried within the day; entry transitions to `DEFERRED` (§8), ledger reconciled (§4) |
| HTTP 401 / invalid credentials | `AuthError` | No — surfaced immediately for human intervention, per `PROVIDER_ARCHITECTURE.md` §17 |
| HTTP 429 | `RateLimitError` | Yes — honor any provided backoff signal; distinct from `quotaExceeded`, this is short-term throttling, not the daily ceiling |
| HTTP 500 / 503 | `TransientError` | Yes — standard exponential backoff, max attempts per `PROVIDER_ARCHITECTURE.md` §17 |
| Content rejected on upload (policy grounds) | `ContentPolicyError` | No — routes to human review per `PROVIDER_ARCHITECTURE.md` §16 and correlates with the `COMPLIANCE_ARCHITECTURE.md` §8 audit record for that run |
| Malformed request (e.g. metadata exceeds `title_max_length`) | `ValidationError` | No — this indicates `Upload Preparation` (`core/stages/upload_preparation/`) let an invalid package through; treated as a defect, not a retry candidate |

**Upload-specific idempotency note:** a retried upload attempt after a partial failure (e.g., connection dropped mid-upload) must use the queue entry's `idempotency_key` to avoid creating a duplicate video on YouTube — per `SCHEMA_REFERENCE.md` §2's idempotency requirement and `DEVELOPER_HANDBOOK.md` §2 principle 3. The specific mechanism (resumable upload session reuse) is an implementation detail deferred to §9, but the *requirement* that no retry may result in two published copies of the same content is architectural, not optional.

---

## 8. Graceful Degradation When Limits Are Reached

This is the behavior that makes quota exhaustion a normal, handled operating state rather than an incident:

1. **Approaching the ceiling (within `safety_margin_pct` of `daily_quota_ceiling`):** the queue stops dequeuing new `Publish` attempts for the remainder of the day. Entries already `SCHEDULED` for a `target_publish_time` still within budget proceed; everything else transitions to `DEFERRED`.
2. **`DEFERRED` is not `FAILED`.** This distinction matters for the same reason `SCHEMA_REFERENCE.md` §3 distinguishes `HALTED` from `FAILED` at the Result level — a deferred upload is an expected, correctly-handled scheduling outcome, not a defect. It does not trigger error-rate alerting the way a genuine `FAILED` entry does.
3. **Lower-priority operations degrade first, automatically** (§5) — analytics polling widens, metadata-update calls queue behind publish, before any publish is ever deferred.
4. **Human notification, not silent deferral.** When any entry transitions to `DEFERRED`, this is logged (`DEVELOPER_HANDBOOK.md` §8) with enough context (how many entries deferred, when the next reset occurs, current ledger state) that a human checking `PROJECT_STATE.json`-equivalent status doesn't have to reconstruct the situation from raw logs.
5. **Automatic resumption.** At `quota_reset_time`, `QuotaLedger.reset()` runs and the queue processing loop (§6) re-evaluates all `DEFERRED` entries in their original priority/age order — no manual intervention required to resume normal operation the next day.
6. **Sustained, repeated deferral is itself a signal.** If entries are being deferred on multiple consecutive days (i.e., production volume has genuinely outgrown `daily_quota_ceiling`, not just an unusual single-day spike), this should surface as an explicit operational flag — the answer at that point is requesting a quota increase from Google (§9), not further tightening the scheduling algorithm around an insufficient ceiling.

---

## 9. Open Items Not Resolved by This Document

- **Exact current quota unit costs and default ceiling** — verify against Google's current published values at implementation time, per §1's note; this document specifies the mechanism, not the numbers.
- **The quota increase request process itself** is an operational/business step (contacting Google, demonstrating usage history and compliant behavior) — not an engineering task, and not something this architecture can resolve in advance. Flagged in `ROADMAP.md` Phase 2/3 as a factor in realistic publish pace.
- **Resumable-upload session reuse mechanics** for the idempotency guarantee in §7 — an implementation detail once the YouTube `PublishingProvider` implementation is actually built.
- **`safety_margin_pct`'s specific value** — an operational tuning parameter, not an architectural decision; likely to start conservative and tighten as the Quota Ledger's estimation accuracy is validated against real `reconcile()` history.

---

*This document closes Gap §1.4 — the last of the four originally-flagged critical architecture gaps in `ARCHITECTURE_APPROVAL_REPORT.md` §1. Remaining open items across the full documentation set: Phase 0 status reconciliation between `CURRENT_STATE.md` and `PROJECT_STATE.json` (§2.1), and the LangGraph orchestration engine ADR (§2.2).*
