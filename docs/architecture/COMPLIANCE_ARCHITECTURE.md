# NarraOS — Compliance Architecture

**Version:** 0.1.0
**Status:** Specification — required reading before Script Writing, Publish, or any human-facing content stage is implemented
**Last Updated:** 2026-07-18
**Resolves:** Gap §1.2 in `ARCHITECTURE_APPROVAL_REPORT.md` (No compliance/legal-risk stage, despite a niche that structurally requires one)

> This document defines a Compliance & Risk Review capability as a first-class part of the pipeline — distinct from Fact Verification — because the approved content niche (Dark True Stories, Internet Mysteries, Scams, Corporate Crimes) routinely involves real, named people and organizations. No implementation code.

---

## 1. Why This Is Its Own Document, Not a Sub-Section of Fact Verification

Fact Verification and Compliance Review sound similar and are frequently conflated. They are not the same job, and collapsing them into one stage was the actual flaw identified in the approval report:

| | **Fact Verification** | **Compliance & Risk Review** |
|---|---|---|
| **Question it answers** | "Is this claim accurate and sourced?" | "Even if accurate, is publishing this safe — legally and platform-wise?" |
| **Fails on** | Unsupported or false claims | True claims stated in a way that creates defamation exposure, privacy violation, platform policy risk, or copyright exposure |
| **Example failure it catches** | "The article claims $2M was stolen; the source says $200K" | "The claim is accurate and sourced, but the phrasing implies the named individual was criminally convicted when they were only investigated and never charged" |
| **Grounded in** | Source material, citations | Defamation law fundamentals, platform community guidelines, privacy norms, copyright status of referenced media |

A true claim can still be a liability. A pipeline that only checks truth has no mechanism to catch that. This is why Compliance & Risk Review is specified here as its own pipeline stage with its own schema, its own gate, and — critically — its own Autonomy Level policy (§5), separate from whatever level Fact Verification eventually earns.

---

## 2. Where It Sits in the Pipeline

Extends the pipeline table in `PROJECT_ARCHITECTURE.md` §3, Phase B (Research & Story):

```
Topic Research → Fact Verification → Compliance & Risk Review → Story Generation → Retention Optimization → ...
```

And, because a script can introduce new risk that wasn't present in the research (dramatization, phrasing, implication, juxtaposition of B-roll with a named individual's image), Compliance & Risk Review runs **twice**, not once:

```
... → Retention Optimization → Script Writing → Compliance & Risk Review (script pass) → Storyboard Generation → ...
```

And a final, narrower pass immediately before publish, checking the assembled package as a whole (thumbnail text, title, description) rather than re-running full risk analysis:

```
... → Asset Packaging → Compliance & Risk Review (pre-publish pass) → Upload Preparation → Publish
```

**Rule:** these three passes are the same stage implementation with different scope configurations (§4), not three separate stages to build and maintain. This keeps the compliance logic in one place, which matters both for engineering maintainability and for having one consistent, auditable standard applied throughout the pipeline rather than three drifting implementations.

---

## 3. Risk Categories

Compliance & Risk Review evaluates content against four distinct risk categories. Each is scored and reasoned about separately — they are not collapsed into a single pass/fail, because they require different evidence and different remediation.

### 3.1 Defamation Exposure
Applies whenever content makes or implies a factual claim about an identifiable living person or an active organization that could harm their reputation. Key distinctions the stage must evaluate:

- **Accusation vs. established fact** — "was investigated for," "was accused of," "pleaded guilty to," and "was convicted of" are not interchangeable, and the niche (Scams, Corporate Crimes) makes this distinction load-bearing, not pedantic.
- **Public figure vs. private individual** — different legal standards apply; the stage must classify the subject, not assume one standard.
- **Opinion vs. assertion of fact** — clearly-framed opinion/commentary carries different exposure than a flat factual assertion.
- **Jurisdictional variance** — given the approved target audience (US, Canada, UK, Australia per `CURRENT_STATE.md`), defamation standards differ meaningfully across these (notably, UK/Australia have historically been more claimant-friendly than the US). The stage's risk threshold is calibrated to the **most conservative** applicable jurisdiction among the target audience set, not the most permissive, given content is published once and reaches all four simultaneously.

### 3.2 Privacy Exposure
Distinct from defamation — content can be entirely true and non-defamatory while still being a privacy violation (e.g., publishing a private individual's home address, private medical information, or details about a minor connected to a case).

### 3.3 Platform Policy Exposure
Independent of legal risk — content can be legally safe but still violate a platform's community guidelines (harassment policy, impersonation policy, sensitive-topic monetization restrictions). This is scored against the target `PlatformAdapter`'s declared policy constraints (extending `constraints()` in `PROJECT_ARCHITECTURE.md` §4), so the check is genuinely platform-aware rather than a generic legal-only pass — a video that is fine legally may still need re-editing to avoid a platform strike or demonetization.

### 3.4 Copyright/Media-Rights Exposure
Specific to this niche's reliance on real-world source material: news footage, mugshots, court documents, screenshots of real websites/scam pages. The stage checks whether referenced or incorporated media has a clear usage basis (fair use rationale, licensed, public domain, or NarraOS-generated original) — this connects directly to Image Generation and Video Editing stage outputs, not just script text.

---

## 4. Compliance & Risk Review — Interface Specification

```
ComplianceReviewInput_v1:
  content: str | ScriptPayload | AssetPackage        # scope-dependent, per pass (§2)
  scope: ReviewScope                                    # RESEARCH | SCRIPT | PRE_PUBLISH
  subjects: List[IdentifiedSubject]                       # named individuals/orgs detected in content
  target_platforms: List[PlatformIdentifier]                # drives §3.3 policy check
  target_jurisdictions: List[Jurisdiction]                    # US, CA, UK, AU per CURRENT_STATE.md

ComplianceReviewOutput_v1:
  overall_verdict: CLEAR | FLAGGED | BLOCKED
  findings: List[RiskFinding]
    RiskFinding:
      category: DEFAMATION | PRIVACY | PLATFORM_POLICY | COPYRIGHT
      severity: LOW | MEDIUM | HIGH | CRITICAL
      location: ContentLocation                    # what specific passage/asset triggered this
      reasoning: str
      suggested_remediation: str | null
  requires_human_review: bool                         # see §5 — never fully autonomous while niche remains high-risk
  citation_refs: List[SourceReference]                 # ties into the audit-trail requirement, §6
```

- `subjects` (`IdentifiedSubject`) is populated by a named-entity extraction step preceding the risk categorization itself — every real person/organization referenced must be explicitly enumerated before risk scoring runs, not inferred implicitly. This makes the stage's reasoning auditable: a human reviewer can see exactly who was flagged as a subject and why.
- A `CRITICAL` severity finding in any category forces `overall_verdict = BLOCKED` regardless of other findings — this is a hard gate, not a weighted average that a run could route around by having otherwise-clean content.

---

## 5. Autonomy Level Policy (stricter than the general Handbook default)

`DEVELOPER_HANDBOOK.md` §9 defines general Autonomy Levels L0–L3. Compliance & Risk Review has its own, stricter policy layered on top:

| Verdict | Required Action |
|---|---|
| `CLEAR` | May proceed automatically — but only after Compliance & Risk Review itself has been operating long enough to have an established false-negative track record (see §7). Until then, `CLEAR` verdicts are still spot-checked per the general L2 policy. |
| `FLAGGED` | **Always** routes to human review, regardless of the pipeline's general autonomy level elsewhere. A `FLAGGED` verdict cannot be auto-approved by any future autonomy promotion. |
| `BLOCKED` | Run halts at this stage. Cannot proceed without either (a) content revision and re-review, or (b) explicit human override with a logged justification (§6). |

**Hard rule, not subject to future relaxation without a deliberate, documented decision:** unlike other pipeline stages, which can graduate to L3 (fully autonomous) per Handbook §9, Compliance & Risk Review's `FLAGGED` and `BLOCKED` paths are **permanently pinned below L3**. The stage evaluating whether it's safe to publish content about real people is not a candidate for the same trust-graduation process as, say, thumbnail generation — the asymmetry between "occasionally regenerate a mediocre thumbnail" and "occasionally publish something defamatory" means the two are not comparable risk profiles, and Handbook §9's general graduation criteria should not be read as applying uniformly here.

---

## 6. Audit Trail Requirement

Every Compliance & Risk Review output is persisted with full reasoning, findings, and — critically — the `citation_refs` connecting each finding back to its source material. This directly addresses the audit-trail gap noted as a "minor note" in `ARCHITECTURE_APPROVAL_REPORT.md` §3, which this document now treats as a firm requirement rather than a nice-to-have, given the niche.

- Persisted in the Database Layer (Postgres), linked to the `run_id` — this is exactly the kind of structured, exact-match, transactional record `MEMORY_ARCHITECTURE.md` §2 describes as belonging in the Database Layer, not the Memory Layer.
- Additionally indexed into Semantic Knowledge memory (`MEMORY_ARCHITECTURE.md` §3.3, §9) so that Fact Verification and future Compliance passes can retrieve "have we evaluated a claim like this before" rather than starting from zero each time.
- Human override decisions (§5, `BLOCKED` overrides) are logged with the specific human who approved it, their stated justification, and a timestamp — this is a non-negotiable record given it represents a deliberate decision to publish over an automated risk flag.
- If a subject or run is later deleted per `MEMORY_ARCHITECTURE.md` §8's redaction mechanism, the compliance record itself is **retained** (not deleted) as the legal audit trail of the decision-making process — only the derived memory embeddings are subject to the forget mechanism, not the Postgres compliance record itself. This distinction matters and should not be conflated.

---

## 7. Establishing Trust Before Any Autonomy Promotion

Per §5, `CLEAR` verdicts remain spot-checked until a track record exists. That track record is defined here so it isn't left ambiguous:

- A rolling sample of `CLEAR`-verdict content is manually reviewed (percentage and cadence to be set as an operational parameter, not hardcoded in this document — see §9).
- A **false negative** (content the stage cleared that a human reviewer would have flagged) resets the trust-accumulation clock rather than being averaged away by a larger sample size — a single missed defamation risk is not something volume-of-correct-calls should be allowed to statistically dilute.
- This mirrors, but is stricter than, the general L1→L2 promotion criteria in `DEVELOPER_HANDBOOK.md` §9 — deliberately, per the hard rule in §5.

---

## 8. Relationship to Other Providers and Stages

- **`LLMProvider` (`PROVIDER_ARCHITECTURE.md` §4):** Compliance & Risk Review is itself implemented using LLM-based reasoning over content, but per `PROVIDER_ARCHITECTURE.md` §15's `per_stage_overrides`, this stage should pin a specific, deliberately-chosen provider rather than following the pipeline's general default — the choice of model for legal-risk reasoning is a decision worth its own ADR, not an inherited default.
- **`ContentPolicyError` (`PROVIDER_ARCHITECTURE.md` §16):** if any *other* provider in the pipeline (an `LLMProvider` or `PublishingProvider`) independently raises a `ContentPolicyError`, that event is routed here as additional input to the Compliance & Risk Review record for that run, not handled as an isolated, disconnected error — a provider-level content rejection and a compliance-stage finding about the same content are two views of the same underlying risk and should be correlated in the audit trail.
- **`PlatformAdapter.constraints()` (`PROJECT_ARCHITECTURE.md` §4):** the Platform Policy Exposure check (§3.3) reads platform-specific policy constraints from here, so adding a new platform (Phase 4) automatically extends what this stage checks against, without needing stage-level code changes — consistent with the platform-agnostic core principle.

---

## 9. Open Items Not Resolved by This Document

- The specific spot-check sampling rate/cadence for `CLEAR` verdicts (§7) — an operational parameter, set once real content volume exists, not an architecture-level constant.
- Which specific `LLMProvider` is pinned for compliance reasoning, and whether a secondary/adversarial second-opinion pass is warranted given the stakes — ADR-level decision.
- Formal legal review of the jurisdictional risk-calibration approach in §3.1 by qualified counsel — this document establishes the *architectural mechanism* (subject classification, jurisdiction-aware thresholds, audit trail), but the actual legal standards it should encode are a legal question, not an engineering one, and should not be finalized from this document alone.
- Whether named-entity extraction (§4) uses a dedicated model/provider or is handled within the same LLM call as risk scoring — an implementation-level decision deferred to when this stage is actually built.

---

*This document, together with `PROVIDER_ARCHITECTURE.md` and `MEMORY_ARCHITECTURE.md`, closes Gap §1.2 from `ARCHITECTURE_APPROVAL_REPORT.md`. One item remains open from that report: the YouTube quota strategy inside the Publishing `PlatformAdapter` (§1.4), plus reconciling Phase 0 status between `CURRENT_STATE.md` and `PROJECT_STATE.json` (§2.1).*
