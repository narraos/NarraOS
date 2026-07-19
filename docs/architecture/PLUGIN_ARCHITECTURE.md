# NarraOS — Plugin Architecture

**Version:** 0.1.0
**Status:** Specification — minimal, generic plugin system definition
**Last Updated:** 2026-07-18
**Scope note:** Defines the plugin *mechanism* only. Individual platform plugins (YouTube, TikTok, Instagram, Podcast, Blog) are not designed here — see `PROJECT_ARCHITECTURE.md` §4 for the `PlatformAdapter` contract each plugin must satisfy, and `REPOSITORY_STRUCTURE.md` §2 for where plugin code lives (`platforms/`).

---

## 1. What a Plugin Is (and Isn't)

A **Plugin** is a self-contained, independently loadable unit that extends NarraOS to support one external platform, without requiring any change to `core/`. This is the mechanism that fulfills `CURRENT_STATE.md`'s mandatory rule: *"Future plugins should integrate without changing the core architecture."*

**A Plugin is not a Provider.** `PROVIDER_ARCHITECTURE.md` defines abstractions over generic external *capabilities* (an LLM, a TTS engine). A Plugin is a complete platform integration — it typically *uses* one or more Providers internally (a `PublishingProvider` and an `AnalyticsProvider`, per `PROVIDER_ARCHITECTURE.md` §10, §12) but also owns platform-specific business rules (validation, constraints, quota behavior) that a Provider deliberately does not. Every Plugin satisfies the `PlatformAdapter` interface already defined in `PROJECT_ARCHITECTURE.md` §4; this document defines the system that loads, manages, and governs Plugins — not a new adapter contract.

---

## 2. Plugin Manifest

Every plugin declares itself via a manifest — static metadata read at discovery time, before the plugin is initialized:

```
PluginManifest:
  plugin_id: str                     # unique, stable — e.g. "youtube", "tiktok"
  display_name: str
  plugin_interface_version: str        # semver — which version of the PlatformAdapter contract this plugin targets (§6)
  implementation_version: str            # semver — this plugin's own version, independent of the interface version
  capabilities: PluginCapabilities         # see §5
  entry_point: str                          # module path NarraOS loads to obtain the plugin's PlatformAdapter implementation
  requires_config: List[str]                  # named config keys this plugin needs present to initialize (§7)
```

The manifest is intentionally the *only* thing read during discovery (§4). NarraOS must never need to import or execute a plugin's actual implementation code just to know it exists.

---

## 3. Plugin Lifecycle

```
DISCOVERED → REGISTERED → INITIALIZED → ENABLED ⇄ DISABLED → UNLOADED
```

1. **Discovered** — manifest found (§4), not yet loaded.
2. **Registered** — manifest validated (interface version compatibility, §6; required config keys present, §7); the plugin's entry point is known but not yet imported/instantiated.
3. **Initialized** — entry point loaded, `PlatformAdapter` instance constructed, its own dependent Providers resolved via `ProviderRegistry` (`PROVIDER_ARCHITECTURE.md` §14).
4. **Enabled / Disabled** — an initialized plugin can be toggled without unloading it. A disabled plugin is skipped by orchestration (no publish/analytics calls routed to it) but retains its state — this is the mechanism for pausing a platform (e.g., a temporary account issue) without a restart.
5. **Unloaded** — graceful teardown, typically only at process shutdown or explicit removal.

**Rule:** a plugin failing to initialize must never prevent other plugins, or the core pipeline, from operating. Plugin initialization failures are isolated and logged per-plugin (§8) — one broken platform integration cannot take down the whole system.

---

## 4. Discovery

Plugins are discovered at startup by scanning `platforms/` (per `REPOSITORY_STRUCTURE.md` §2) for manifests — no plugin is loaded by being manually imported elsewhere in the codebase. This keeps adding a plugin a purely additive act: drop a new directory under `platforms/` with a valid manifest, and it's discovered on the next startup without touching any existing file.

- Discovery reads manifests only (§2) — cheap, safe, side-effect-free.
- A manifest that fails validation (missing required fields, unsupported `plugin_interface_version`) is logged and skipped, not treated as a startup failure for the whole system.
- Stub plugin directories (`tiktok/`, `instagram/`, `x/`, `facebook/` per `REPOSITORY_STRUCTURE.md` §2, unimplemented until Phase 4) either carry no manifest yet or a manifest with no valid `entry_point` — either is a normal, expected discovery-time state, not an error.

---

## 5. Capability Declaration

Plugins declare what they support so the core pipeline can make platform-aware decisions without hardcoding platform names anywhere:

```
PluginCapabilities:
  content_types: List[ContentType]        # e.g. VIDEO, SHORT_FORM_VIDEO, IMAGE_POST, TEXT_POST
  supports_analytics: bool
  supports_scheduling: bool                  # can the plugin schedule a future publish, or only publish immediately
  max_asset_duration: Duration | null
  aspect_ratios: List[AspectRatio]
  rate_limit_model: RateLimitModel             # ties to PublishingProvider.rate_limit_status(), PROVIDER_ARCHITECTURE.md §10
```

This is what lets Retention Optimization, Asset Packaging, and Upload Preparation (`core/stages/`, per `REPOSITORY_STRUCTURE.md` §2) branch on *what a platform supports* rather than on *which platform it is* — the core pipeline queries capabilities, never plugin identity, to decide how to shape output. This is the concrete mechanism that keeps the core platform-agnostic per `PROJECT_ARCHITECTURE.md` §7.

---

## 6. Versioning and Compatibility

Two independent version numbers exist per plugin (§2), and they must not be conflated:

- **`plugin_interface_version`** — which version of the `PlatformAdapter` contract (`PROJECT_ARCHITECTURE.md` §4) the plugin was built against. NarraOS checks this at registration time (§3) against the interface version(s) it currently supports. An incompatible interface version blocks registration with a clear error — it never attempts a best-effort load against a contract the plugin wasn't built for.
- **`implementation_version`** — the plugin's own release version (e.g., a YouTube plugin update to handle a new API field). This can increment freely without any interface version change, as long as the `PlatformAdapter` contract itself hasn't changed.

**Rule:** a breaking change to the `PlatformAdapter` interface itself is a `plugin_interface_version` bump, handled with the same discipline as schema versioning in `DEVELOPER_HANDBOOK.md` §7 — old and new interface versions may need to coexist temporarily while plugins migrate, rather than every plugin being forced to update in lockstep with core.

---

## 7. Configuration

Each plugin's configuration is isolated from every other plugin's, and from core configuration generally:

```
config/
└── plugins/
    ├── youtube.yaml         # enabled: true/false, credentials refs, plugin-specific settings
    ├── tiktok.yaml            # (Phase 4)
    └── ...
```

- Credentials are referenced by environment variable name, never embedded as literal values — same rule as `PROVIDER_ARCHITECTURE.md` §15, applied here at the plugin level.
- `enabled: false` in config is a valid, first-class state distinct from the plugin not existing at all — it's how a platform integration gets paused operationally (§3) without removing or reinstalling it.
- A plugin's `requires_config` (§2) is checked against the actual config file present at registration time (§3); missing required keys block registration with a specific, named error, not a generic startup failure.

---

## 8. Isolation and Error Handling

- Every plugin lifecycle transition (§3) is wrapped so a plugin-level exception is caught, logged with the plugin's `plugin_id`, and results in that plugin remaining in (or reverting to) `DISABLED` — it never propagates to crash orchestration or another plugin.
- Runtime errors during actual use (publish, fetch analytics) flow through the same error taxonomy already defined in `PROVIDER_ARCHITECTURE.md` §16, since a plugin's underlying calls go through `PublishingProvider`/`AnalyticsProvider` implementations — this document does not define a second, parallel error taxonomy.
- A plugin that repeatedly fails at runtime (not just at init) should be automatically transitioned to `DISABLED` after a configurable failure threshold, with an explicit log entry — this is a targeted extension of `DEVELOPER_HANDBOOK.md` §2's "fail loud, fail safe" principle to the plugin boundary specifically.

---

## 9. Extension Mechanism: Adding a New Plugin

1. Create a new directory under `platforms/` (`REPOSITORY_STRUCTURE.md` §2) with a valid `PluginManifest` (§2).
2. Implement the `PlatformAdapter` interface (`PROJECT_ARCHITECTURE.md` §4) at the manifest's declared `entry_point`.
3. Declare accurate `PluginCapabilities` (§5) — an overstated capability set (e.g., claiming scheduling support that isn't really implemented) will cause the core pipeline to make incorrect platform-aware decisions upstream; this is a correctness requirement, not documentation.
4. Add the plugin's config file under `config/plugins/` (§7), `enabled: false` by default until verified.
5. Register any new `PublishingProvider`/`AnalyticsProvider` implementations the plugin depends on through `providers/registry.py` (`PROVIDER_ARCHITECTURE.md` §14, `REPOSITORY_STRUCTURE.md` §6.2) — the plugin itself never constructs these directly.
6. No change to `core/` is required or permitted as part of adding a plugin. If one seems necessary, that's a signal the `PlatformAdapter` or `PluginCapabilities` contract itself is insufficiently general and needs a deliberate, documented extension — not a one-off exception for this plugin.

---

## 10. Open Items Not Resolved by This Document

- Concrete list of supported `plugin_interface_version`s and the deprecation policy once a second version exists — not needed until a breaking `PlatformAdapter` change actually occurs.
- Automated failure-threshold value for §8's auto-disable behavior — an operational tuning parameter, not architecture.
- Individual plugin designs (YouTube fully, TikTok/Instagram/X/Facebook/Podcast/Blog) — explicitly out of scope per this document's stated scope note.

---

*This document, together with `PROJECT_ARCHITECTURE.md` §4 (`PlatformAdapter` contract) and `PROVIDER_ARCHITECTURE.md` §10 (`PublishingProvider`/`AnalyticsProvider`), fully specifies how platform extensibility works without redesigning core — the guarantee `ROADMAP.md` Phase 4 depends on.*
