# NarraOS — Provider Architecture

**Version:** 0.1.0
**Status:** Specification — required reading before Core Infrastructure implementation
**Last Updated:** 2026-07-18
**Resolves:** Gap §1.3 in `ARCHITECTURE_APPROVAL_REPORT.md` (Provider Abstraction named but unspecified)

> This document specifies contracts, not implementations. No provider-specific code (OpenAI, ElevenLabs, YouTube, etc.) is written here — only the interfaces every provider implementation must satisfy, and the rules governing how they're configured, injected, monitored, and swapped.

---

## 1. Purpose and Principle

`CURRENT_STATE.md` mandates Provider Abstraction as a non-negotiable architecture rule: **changing a provider must never require changing business logic.** This document is what makes that rule enforceable rather than aspirational.

A **Provider** is the sole integration point between NarraOS and one external capability (an LLM API, an image generation API, a publishing platform, etc.). Pipeline stages and agents never call an external SDK directly — they depend only on a provider **interface**, never a concrete implementation. Concrete implementations (`OpenAILLMProvider`, `YouTubePublishingProvider`, etc.) are swappable behind that interface without touching stage logic, schemas, or tests that use a mock provider.

This is distinct from, and sits underneath, the **Model Gateway** described in `PROJECT_ARCHITECTURE.md` §6: the Model Gateway is the internal routing/facade layer that stages call; providers are what the Model Gateway routes *to*. The Model Gateway handles cross-cutting concerns (cost tracking, provider selection policy); providers handle the actual external call contract defined here.

---

## 2. Provider Categories in Scope

| Provider Type | Responsibility |
|---|---|
| `LLMProvider` | Text generation/completion (research synthesis, story generation, scripts, SEO copy) |
| `ImageProvider` | Static image generation (storyboard frames, thumbnail source images) |
| `VideoProvider` | Video/animation generation (motion from static assets, AI video clips) |
| `TTSProvider` | Text-to-speech / voice synthesis (narration) |
| `STTProvider` | Speech-to-text (transcription — competitor content analysis, QA-checking narration against script) |
| `StorageProvider` | Object storage read/write (video, image, audio assets) |
| `EmbeddingProvider` | Vector embedding generation (feeds the Memory Layer / vector store — see §11) |
| `AnalyticsProvider` | Post-publish performance data retrieval |
| `PublishingProvider` | Platform upload/publish transport (see §10 for its relationship to Platform Adapters) |

Each is specified below with: responsibility, interface contract, lifecycle behavior, error taxonomy mapping, and retry policy.

---

## 3. Common Provider Contract (applies to all types)

Every provider, regardless of category, implements a shared base contract so the Model Gateway and orchestration engine can manage all providers uniformly:

```
BaseProvider (interface, all provider types extend this):
  provider_id: str                      # unique, stable identifier, e.g. "openai-gpt", "elevenlabs-tts"
  provider_type: ProviderType            # enum: LLM | IMAGE | VIDEO | TTS | STT | STORAGE | EMBEDDING | ANALYTICS | PUBLISHING

  initialize(config: ProviderConfig) -> None
  health_check() -> HealthStatus         # returns HEALTHY | DEGRADED | UNAVAILABLE, called before use and periodically
  shutdown() -> None                     # graceful cleanup (close connections, flush buffers)
  capabilities() -> ProviderCapabilities # declares what this provider instance supports (e.g. max tokens, supported languages, formats)
  cost_estimate(request: Any) -> CostEstimate  # pre-call estimate, used by Model Gateway for budget checks
```

**Rule:** no provider type-specific interface below may omit or override this base contract. Type-specific interfaces *extend* it with capability-specific methods.

---

## 4. LLMProvider

**Responsibility:** All text generation — research synthesis, story generation, script writing, SEO copy, and any agent reasoning that requires LLM calls.

```
LLMProvider extends BaseProvider:
  complete(prompt: PromptPayload, params: GenerationParams) -> LLMResponse
  stream(prompt: PromptPayload, params: GenerationParams) -> Stream[LLMResponseChunk]
  supports_tool_use() -> bool
  supports_structured_output() -> bool
  token_count(text: str) -> int          # for pre-flight budget/context checks
```

- `PromptPayload` is versioned per `DEVELOPER_HANDBOOK.md` §7 schema rules — a provider must never require stage code to format prompts differently per vendor. Vendor-specific prompt formatting is the provider's internal responsibility.
- `GenerationParams` includes temperature, max_tokens, stop sequences — normalized fields, not vendor-native parameter names.
- Structured output (JSON mode / function-calling-style constrained generation) is declared via `supports_structured_output()` so calling stages can degrade gracefully (e.g., fall back to prompt-based JSON + parsing) if a configured provider lacks it.

---

## 5. ImageProvider

**Responsibility:** Static image generation for storyboards and thumbnail source material.

```
ImageProvider extends BaseProvider:
  generate(prompt: ImagePromptPayload, params: ImageGenParams) -> ImageResult
  variations(source: ImageAsset, params: ImageGenParams) -> List[ImageResult]
  supports_style_reference() -> bool
  supported_resolutions() -> List[Resolution]
```

- `ImageResult` references a `StorageProvider`-backed asset ID, never raw bytes passed through pipeline state (per Handbook §7 — storage is referenced, not embedded).
- Providers declare `supported_resolutions()` so Storyboard/Thumbnail stages can request platform-appropriate dimensions without hardcoding a specific vendor's output constraints.

---

## 6. VideoProvider

**Responsibility:** AI-driven video/animation generation — animating static images, generating short AI video clips used in editing.

```
VideoProvider extends BaseProvider:
  animate(source: ImageAsset, motion: MotionSpec) -> VideoResult
  generate_clip(prompt: VideoPromptPayload, params: VideoGenParams) -> VideoResult
  max_clip_duration() -> Duration
  supported_formats() -> List[VideoFormat]
```

- This is distinct from `VideoEditor` (a core pipeline stage, not a provider) — `VideoProvider` generates raw clips/animation; the Video Editing *stage* assembles them using ffmpeg/MoviePy/OpenCV per `CURRENT_STATE.md`'s approved stack. Video editing/assembly itself is not provider-abstracted because it's not an external service — it's local processing logic. Only externally-sourced generation is behind a provider.

---

## 7. TTSProvider

**Responsibility:** Narration voice synthesis from finalized script text.

```
TTSProvider extends BaseProvider:
  synthesize(text: str, voice: VoiceProfile, params: TTSParams) -> AudioResult
  list_voices() -> List[VoiceProfile]
  clone_voice(sample: AudioAsset) -> VoiceProfile          # optional capability, guarded by capabilities()
  max_input_length() -> int
```

- `VoiceProfile` is a normalized identifier, not a vendor-specific voice ID — the mapping from a NarraOS voice profile to a vendor's actual voice catalog lives inside the provider implementation.
- Voice cloning is explicitly marked optional since not all providers support it; calling code must check `capabilities()` before relying on it.

---

## 8. STTProvider

**Responsibility:** Speech-to-text — used for (a) transcribing competitor content during Competitor Analysis, and (b) QA-verifying that synthesized narration audio actually matches the approved script before assembly.

```
STTProvider extends BaseProvider:
  transcribe(audio: AudioAsset, params: STTParams) -> TranscriptResult
  supports_diarization() -> bool
  supports_timestamps() -> bool
  supported_languages() -> List[LanguageCode]
```

- `TranscriptResult` includes confidence scoring — this feeds directly into the QA gate that checks narration-vs-script fidelity before a run proceeds past Voice Synthesis.
- `Whisper` (the approved STT stack per `CURRENT_STATE.md`) is one possible implementation; this interface must not assume Whisper-specific output structure (e.g., its native segment format) leaks into stage code.

---

## 9. StorageProvider

**Responsibility:** All object storage read/write — video, image, audio, and packaged asset persistence.

```
StorageProvider extends BaseProvider:
  put(asset: bytes | Stream, metadata: AssetMetadata) -> AssetReference
  get(reference: AssetReference) -> bytes | Stream
  get_url(reference: AssetReference, expiry: Duration) -> str    # signed/temporary URL for external handoff (e.g. publish)
  delete(reference: AssetReference) -> None
  exists(reference: AssetReference) -> bool
  list(prefix: str) -> List[AssetReference]
```

- `AssetReference` is the only thing that ever travels through pipeline state (per Handbook §7) — never raw asset bytes.
- `get_url` exists specifically because `PublishingProvider` implementations typically need a fetchable URL rather than raw bytes to hand to a platform's upload API.

---

## 10. PublishingProvider (and its relationship to Platform Adapters)

**Responsibility:** The transport-level mechanics of authenticating with and uploading to a platform — nothing more.

```
PublishingProvider extends BaseProvider:
  authenticate(credentials: PlatformCredentials) -> AuthSession
  upload(package: AssetPackage, session: AuthSession) -> UploadResult
  update_metadata(content_id: str, metadata: ContentMetadata, session: AuthSession) -> None
  delete_content(content_id: str, session: AuthSession) -> None
  rate_limit_status(session: AuthSession) -> RateLimitStatus
```

**Critical distinction — read carefully:**

- `PublishingProvider` (this document, Layer 1 concern) = the raw transport contract: auth, upload call, rate-limit reporting. It knows nothing about content strategy or validation rules.
- `PlatformAdapter` (`PROJECT_ARCHITECTURE.md` §4, Layer 4 concern) = platform-specific business logic: `validate()` against platform constraints, `constraints()` (title length, aspect ratio, **quota limits** — resolving Gap §1.4 from the approval report), and orchestrating the publish sequence. A `PlatformAdapter` **uses** a `PublishingProvider` internally; it is not replaced by one.

This split exists so that, for example, a future second YouTube-uploading integration (should one ever be needed) is a new `PublishingProvider` implementation without touching `PlatformAdapter` validation logic, while a genuinely new platform (TikTok) requires a new `PlatformAdapter` *and* typically a new `PublishingProvider`, since both the business rules and the transport differ.

- `rate_limit_status()` is mandatory, not optional, on this interface specifically because of the YouTube quota gap flagged in the approval report — every publishing provider must be able to report remaining quota so the `PlatformAdapter`'s `constraints()` check and the orchestration engine's scheduling can react to it *before* attempting an upload that will fail.

---

## 11. EmbeddingProvider

**Responsibility:** Generates vector embeddings from text/content for use by the (separately architected) Memory Layer and vector store.

```
EmbeddingProvider extends BaseProvider:
  embed(text: str) -> EmbeddingVector
  embed_batch(texts: List[str]) -> List[EmbeddingVector]
  dimensions() -> int
  model_identifier() -> str          # so stored vectors can be tied to the model version that produced them
```

**Explicit scope boundary:** This interface covers embedding *generation* only. The vector store itself (FAISS today, Qdrant later, per `CURRENT_STATE.md`) and the broader Memory Layer concept (short-term run context vs. long-term cross-run memory) are **not** specified here — that boundary is still open per Gap §1.1 of `ARCHITECTURE_APPROVAL_REPORT.md`. `EmbeddingProvider` is deliberately scoped narrowly so this document doesn't silently pre-decide that unresolved architectural question. `model_identifier()` exists so that whenever the Memory Layer design lands, it can detect and handle embedding-model version changes (e.g., re-embedding requirements) correctly.

---

## 12. AnalyticsProvider

**Responsibility:** Retrieves post-publish performance data from a platform, feeding the Feedback Loop stage.

```
AnalyticsProvider extends BaseProvider:
  fetch_metrics(content_id: str, window: TimeWindow) -> MetricsSnapshot
  fetch_audience_data(content_id: str) -> AudienceSnapshot
  supported_metrics() -> List[MetricType]
  polling_interval_recommendation() -> Duration
```

- Distinct from `PublishingProvider` because analytics and publishing frequently have different auth scopes, different rate limit pools, and are called on entirely different schedules (publish once; poll analytics repeatedly over the content's lifetime).
- `polling_interval_recommendation()` exists so the Feedback Loop stage doesn't hardcode a polling cadence that happens to suit one platform's API design but wastes quota on another.

---

## 13. Provider Lifecycle

All providers, regardless of type, move through the same lifecycle, managed by the Model Gateway:

```
REGISTERED → INITIALIZED → HEALTHY ⇄ DEGRADED → UNAVAILABLE → SHUTDOWN
```

1. **Registered** — provider implementation is known to the system (via the registry, §14) but not yet configured or connected.
2. **Initialized** — `initialize(config)` has run successfully; credentials validated, connections/clients prepared.
3. **Healthy / Degraded** — `health_check()` is polled periodically (interval configurable per provider type). `Degraded` means the provider is usable but exhibiting elevated latency/errors — the Model Gateway may deprioritize it in favor of a fallback without fully removing it from rotation.
4. **Unavailable** — health checks failing consistently; Model Gateway routes around it entirely and raises alerts (does not silently degrade output quality by continuing to attempt calls against a dead provider).
5. **Shutdown** — graceful teardown, typically only at process shutdown, not a normal operational state.

**Rule:** No stage or agent may call a provider directly without going through the Model Gateway's lifecycle-aware routing. This is what allows automatic fallback (§15) and prevents a pipeline run from hanging against a provider that health checks have already marked unavailable.

---

## 14. Dependency Injection Strategy

Providers are never instantiated directly inside stage or agent code. NarraOS uses **configuration-driven provider resolution** via a central Provider Registry:

```
ProviderRegistry:
  register(provider_type: ProviderType, provider_id: str, factory: Callable[[ProviderConfig], BaseProvider]) -> None
  resolve(provider_type: ProviderType, provider_id: str | None = None) -> BaseProvider
    # provider_id=None resolves the configured default for that provider_type
```

**Principles:**

1. **Stages and agents declare a dependency on a provider *type*, never a concrete class.** A Script Writing stage depends on "an `LLMProvider`," never on "the OpenAI provider." The concrete instance is resolved at runtime from configuration.
2. **Registration happens once at startup**, scanning known provider implementations and registering their factories against the registry. Adding a new provider implementation means writing the implementation and registering it — it does not mean editing any stage code.
3. **Resolution is configuration-driven, not code-driven.** Which concrete provider backs `LLMProvider` for a given stage is a config value (§15), not a hardcoded import.
4. **No global singletons reached via ambient import.** Stages/agents receive their resolved provider through explicit construction (constructor or factory parameter) at the point the orchestration engine builds the stage for a run — never via a module-level global that hides the dependency.
5. **Test doubles use the same registry mechanism.** A test registers a `FakeLLMProvider` factory against the same registry interface real code uses — there is no separate "test mode" branching inside stage logic.

This satisfies `CURRENT_STATE.md`'s mandatory Provider Abstraction rule directly: swapping a provider is a configuration and registration change, never a business-logic change.

---

## 15. Configuration Strategy

Provider configuration is layered and environment-aware, never hardcoded:

```
config/
├── providers.base.yaml        # provider type → default provider_id mapping, shared across environments
├── providers.local.yaml        # local/dev overrides (e.g. cheaper/faster models for iteration)
├── providers.production.yaml    # production overrides
└── .env                          # secrets referenced by key only, never committed (per Handbook §6)
```

Example shape (illustrative structure, not implementation):

```
llm:
  default: "openai-gpt"
  fallback: "anthropic-claude"
  per_stage_overrides:
    fact_verification: "anthropic-claude"   # a stage may pin a specific provider when justified
tts:
  default: "elevenlabs"
publishing:
  youtube: "youtube-data-api-v3"
```

**Rules:**

1. Every provider's credentials are referenced by environment variable name in config, resolved at `initialize()` time — never embedded as literal values anywhere in version control (per Handbook §6, no exceptions for providers).
2. `per_stage_overrides` exists because not every stage should use the same default provider (e.g., Fact Verification may deliberately pin a different/more conservative model than Story Generation) — but overrides must be explicit and visible in config, never silently hardcoded inside the stage.
3. Config changes that alter which provider handles a given stage are logged as part of that run's audit trail (ties into Handbook §8 observability) so a quality regression can be traced back to a provider change.

---

## 16. Error Handling Taxonomy

Every provider implementation must map its vendor-specific errors into this shared taxonomy so stage/orchestration logic never branches on vendor-specific exception types:

| NarraOS Error Type | Meaning | Typical Origin |
|---|---|---|
| `TransientError` | Likely to succeed on retry (network blip, momentary 5xx) | Any provider |
| `RateLimitError` | Provider-side throttling; includes `retry_after` if known | LLM, Image, Video, TTS, STT, Publishing |
| `QuotaExceededError` | Hard ceiling reached (daily/monthly quota, not just rate limit) | Publishing (YouTube quota — §10), LLM/Image usage caps |
| `AuthError` | Credentials invalid/expired | All providers |
| `ContentPolicyError` | Provider rejected the request on content-policy grounds | LLM, Image, Video, Publishing |
| `ValidationError` | Malformed request per the provider's own constraints (not a NarraOS schema issue — those are caught before reaching the provider) | All providers |
| `PermanentError` | Will not succeed on retry, not policy/auth/quota related (e.g. unsupported input) | All providers |
| `ProviderUnavailableError` | Provider is down/unreachable (distinct from a single failed call — tied to health check state, §13) | All providers |

**Rule:** stage and orchestration code catches only these taxonomy types, never vendor-native exception classes. A provider implementation that leaks a vendor-specific exception type past its own boundary is a bug in that provider, not something calling code should need to defend against.

`ContentPolicyError` deserves specific attention given the approved content niche (per `ARCHITECTURE_APPROVAL_REPORT.md` §1.2): a `ContentPolicyError` from an `LLMProvider` or `PublishingProvider` must route to human review, never to a silent retry with reworded input aimed at circumventing the rejection.

---

## 17. Retry Policy

Retry behavior is defined per error type, not per provider — every provider inherits the same policy for a given error classification, keeping behavior predictable regardless of which vendor is configured:

| Error Type | Retry? | Strategy |
|---|---|---|
| `TransientError` | Yes | Exponential backoff, base delay configurable per provider type, max 3 attempts by default |
| `RateLimitError` | Yes | Honor `retry_after` if provided; otherwise exponential backoff, higher max attempts than generic transient (rate limits are expected, not exceptional) |
| `QuotaExceededError` | No | Do not retry within the run. Surface immediately to orchestration for scheduling/human decision (e.g., wait for quota reset, or halt the Publish stage for the day) |
| `AuthError` | No | Do not retry with the same credentials. Surface immediately — this requires human intervention, not automated recovery |
| `ContentPolicyError` | No | Never retried automatically (see §16). Routes to human review. |
| `ValidationError` | No | Indicates a bug in the calling stage's request construction, not a transient condition. Retrying won't help — surface as a defect. |
| `PermanentError` | No | Surface immediately |
| `ProviderUnavailableError` | No (at the provider) | Model Gateway attempts fallback to a secondary provider if one is configured (§18 below), rather than retrying the same unavailable provider |

**Idempotency requirement (ties to Handbook §2 principle 3):** every retryable call must be safe to repeat. Providers with side effects that are not naturally idempotent (e.g., `PublishingProvider.upload`) must accept and honor an idempotency key so a retried call after a partial failure does not create a duplicate publish.

---

## 18. Fallback and Degradation Strategy

- Each provider type may have a configured **fallback provider** (see `providers.base.yaml` example, §15). Fallback triggers on `ProviderUnavailableError` or sustained `Degraded` health status — not on every individual transient error, which should retry against the primary first.
- Fallback is **not silent** — a run that falls back to a secondary provider logs this explicitly (Handbook §8), because output quality/characteristics can differ meaningfully between providers (a different LLM's writing voice, a different TTS voice), which matters for a media product where consistency is part of the value.
- Not every provider type should have fallback enabled by default. `PublishingProvider` in particular should generally **not** silently fall back to an alternate transport for the *same* platform without explicit configuration — publishing is exactly the kind of side-effecting operation where an unexpected fallback path is more dangerous than a clear failure.

---

## 19. Extension Guidelines

### 19.1 Adding a new implementation of an existing provider type
(e.g., adding a second `LLMProvider` implementation for a new vendor)

1. Implement the full interface for that provider type (§4–§12), including the common `BaseProvider` contract (§3).
2. Map all vendor-specific errors into the shared taxonomy (§16) — no leakage of vendor exception types.
3. Register the implementation's factory with the `ProviderRegistry` (§14) at startup.
4. Add it as a selectable option in `providers.*.yaml` (§15) — do not hardcode it as a default without an explicit config change and, if it affects a stage already in production use, an ADR recording why.
5. Add contract tests (Handbook §10) verifying the new implementation satisfies the interface's behavioral guarantees, not just its method signatures — particularly around error mapping and idempotency.

### 19.2 Adding an entirely new provider type
(e.g., a future provider category not listed in §2)

1. Confirm it genuinely represents a new *category* of external capability, not a new implementation of an existing one — check §2 carefully first.
2. Define its interface here, in this document, following the same structure as §4–§12 (responsibility, interface contract, any category-specific notes).
3. Extend the `ProviderType` enum and the error taxonomy (§16) only if the new category has genuinely distinct failure modes.
4. Update `PROJECT_ARCHITECTURE.md`'s Foundation Services layer description to reference it, in the same change — per the documentation-drift rule in `DEVELOPER_HANDBOOK.md` §11 and `DOCUMENTATION_STRUCTURE.md` §5.

### 19.3 What must never happen during extension
- A stage or agent gaining a direct, provider-specific import (defeats the entire abstraction).
- A new provider implementation being added without registering it through the `ProviderRegistry` "for now, just to test quickly."
- Vendor-specific configuration values appearing outside `config/providers.*.yaml` and `.env`.

---

## 20. Open Items Not Resolved by This Document

For traceability, explicitly noting what this document does **not** settle, so it isn't mistaken for having done so:

- The Memory Layer / vector store architecture (Gap §1.1 in `ARCHITECTURE_APPROVAL_REPORT.md`) — `EmbeddingProvider` (§11) is scoped narrowly on purpose and does not pre-decide this.
- The Compliance/Risk Review stage design (Gap §1.2) — `ContentPolicyError` handling (§16) provides a hook for it, but the stage itself is a separate design task.
- Which specific vendors back each provider type initially (this is an ADR-level decision, not an architecture-level one — see `DOCUMENTATION_STRUCTURE.md` §4 for the ADR template).
- YouTube-specific quota numbers and scheduling behavior — `rate_limit_status()` (§10) provides the interface hook; the actual `PlatformAdapter` logic that consumes it is specified in `PROJECT_ARCHITECTURE.md` §4, not here.

---

*This document must be read before any Core Infrastructure code (Database Layer, Memory Layer, Provider Interfaces) is implemented, per `ARCHITECTURE_APPROVAL_REPORT.md` §5, item 3.*
