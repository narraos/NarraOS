#!/usr/bin/env python3
"""scripts/bootstrap.py

Scaffolds the NarraOS repository layout defined in `REPOSITORY_STRUCTURE.md`.

This script creates directories, Python packages (directory + `__init__.py`), and
non-code infrastructure folders (directory + `.gitkeep`, only when the folder would
otherwise be empty). It never writes documentation, never overwrites an existing
file, and is safe to re-run at any time — every existing directory or file is left
untouched and reported as skipped rather than recreated.

Scope, deliberately:
    - Directories, Python packages, and infrastructure folders only.
    - No business logic. No stub implementations of agents, stages, providers,
      or plugins are created here — those are written when that work actually
      begins, per DAILY_DEVELOPMENT_PLAN.md's "no business logic on Day 0" rule.
    - No `pyproject.toml`, Dockerfiles, or CI workflow content — those are
      separate, explicit deliverables, not folder scaffolding.

Usage:
    python scripts/bootstrap.py                # create what's missing
    python scripts/bootstrap.py --dry-run       # preview only, writes nothing
    python scripts/bootstrap.py --verbose       # also list skipped items

Reference: REPOSITORY_STRUCTURE.md §2 (layout), §9 (superseded directories excluded).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository root
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# Extensions this script must never create or touch, under any circumstance.
# This is a defensive guarantee, not just a consequence of what's listed below:
# even if a future edit to this file accidentally added a doc-like path to one
# of the specs, the write helpers refuse rather than silently doing it.
_PROTECTED_DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}


# ---------------------------------------------------------------------------
# Specification: what gets created
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageSpec:
    """A directory that must exist as an importable Python package."""

    path: str  # POSIX-style, relative to repo root
    purpose: str  # one-line description, written into the package's __init__.py docstring


@dataclass(frozen=True)
class FolderSpec:
    """A directory that must exist but is not a Python package."""

    path: str  # POSIX-style, relative to repo root
    purpose: str  # one-line description, written into .gitkeep's comment if the folder is empty


# Python packages under src/narraos/, per REPOSITORY_STRUCTURE.md §2.
# Excludes the superseded top-level `media/` and `core/feedback/` directories (§9) —
# image/video/voice generation logic now lives under core/stages/, and Feedback Loop
# is core/agents/feedback_loop/.
PYTHON_PACKAGES: tuple[PackageSpec, ...] = (
    PackageSpec("src/narraos", "NarraOS — Autonomous AI Media Operating System."),
    # --- core -----------------------------------------------------------
    PackageSpec("src/narraos/core", "Platform-agnostic pipeline core: agents, stages, schemas, orchestration."),
    PackageSpec("src/narraos/core/pipeline", "LangGraph graph assembly, checkpointing, human-checkpoint gating."),
    PackageSpec("src/narraos/core/agents", "The 9 Agents — judgment-exercising pipeline steps. See AGENT_SPECIFICATIONS.md §1.1."),
    PackageSpec("src/narraos/core/agents/trend_discovery", "Trend Discovery agent — AGENT_SPECIFICATIONS.md §3.1."),
    PackageSpec("src/narraos/core/agents/competitor_analysis", "Competitor Analysis agent — AGENT_SPECIFICATIONS.md §3.2."),
    PackageSpec("src/narraos/core/agents/virality_prediction", "Virality Prediction agent — AGENT_SPECIFICATIONS.md §3.3."),
    PackageSpec("src/narraos/core/agents/topic_research", "Topic Research agent — AGENT_SPECIFICATIONS.md §3.4."),
    PackageSpec("src/narraos/core/agents/fact_verification", "Fact Verification agent — AGENT_SPECIFICATIONS.md §3.5."),
    PackageSpec("src/narraos/core/agents/compliance_review", "Compliance & Risk Review agent — see COMPLIANCE_ARCHITECTURE.md (authoritative)."),
    PackageSpec("src/narraos/core/agents/story_generation", "Story Generation agent — AGENT_SPECIFICATIONS.md §3.7."),
    PackageSpec("src/narraos/core/agents/retention_optimization", "Retention Optimization agent — AGENT_SPECIFICATIONS.md §3.8."),
    PackageSpec("src/narraos/core/agents/feedback_loop", "Feedback Loop agent — sole writer to procedural-feedback memory. AGENT_SPECIFICATIONS.md §3.9."),
    PackageSpec("src/narraos/core/stages", "The 10 Stages — deterministic pipeline steps. See AGENT_SPECIFICATIONS.md §1.1."),
    PackageSpec("src/narraos/core/stages/script_writing", "Script Writing stage."),
    PackageSpec("src/narraos/core/stages/storyboard_generation", "Storyboard Generation stage."),
    PackageSpec("src/narraos/core/stages/image_generation", "Image Generation stage — calls ImageProvider."),
    PackageSpec("src/narraos/core/stages/animation_generation", "Animation Generation stage — calls VideoProvider."),
    PackageSpec("src/narraos/core/stages/voice_synthesis", "Voice Synthesis stage — calls TTSProvider."),
    PackageSpec("src/narraos/core/stages/video_editing", "Video Editing stage — local ffmpeg/MoviePy/OpenCV assembly, not provider-backed."),
    PackageSpec("src/narraos/core/stages/thumbnail_generation", "Thumbnail Generation stage — calls ImageProvider."),
    PackageSpec("src/narraos/core/stages/seo_generation", "SEO Generation stage."),
    PackageSpec("src/narraos/core/stages/asset_packaging", "Asset Packaging stage."),
    PackageSpec("src/narraos/core/stages/upload_preparation", "Upload Preparation stage — validates against PlatformAdapter.constraints()."),
    PackageSpec("src/narraos/core/stages/publish", "Publish stage — queue-mediated for YouTube. YOUTUBE_ADAPTER_ARCHITECTURE.md §6."),
    PackageSpec("src/narraos/core/stages/analytics_collection", "Analytics Collection stage — calls AnalyticsProvider."),
    PackageSpec("src/narraos/core/schemas", "Versioned Pydantic contracts between stages/agents. DEVELOPER_HANDBOOK.md §7."),
    PackageSpec("src/narraos/core/schemas/v1", "Current schema version. common.py holds Task/Result/Error/Metadata/Configuration/AgentMessage."),
    # --- providers --------------------------------------------------------
    PackageSpec("src/narraos/providers", "Provider interfaces, registry, and error taxonomy. PROVIDER_ARCHITECTURE.md."),
    PackageSpec("src/narraos/providers/llm", "LLMProvider interface and implementations."),
    PackageSpec("src/narraos/providers/llm/implementations", "Vendor-specific LLMProvider implementations. Never imported outside providers/registry.py."),
    PackageSpec("src/narraos/providers/image", "ImageProvider interface and implementations."),
    PackageSpec("src/narraos/providers/image/implementations", "Vendor-specific ImageProvider implementations."),
    PackageSpec("src/narraos/providers/video", "VideoProvider interface and implementations."),
    PackageSpec("src/narraos/providers/video/implementations", "Vendor-specific VideoProvider implementations."),
    PackageSpec("src/narraos/providers/tts", "TTSProvider interface and implementations."),
    PackageSpec("src/narraos/providers/tts/implementations", "Vendor-specific TTSProvider implementations."),
    PackageSpec("src/narraos/providers/stt", "STTProvider interface and implementations."),
    PackageSpec("src/narraos/providers/stt/implementations", "Vendor-specific STTProvider implementations."),
    PackageSpec("src/narraos/providers/storage", "StorageProvider interface and implementations."),
    PackageSpec("src/narraos/providers/storage/implementations", "Vendor-specific StorageProvider implementations."),
    PackageSpec("src/narraos/providers/embedding", "EmbeddingProvider interface and implementations."),
    PackageSpec("src/narraos/providers/embedding/implementations", "Vendor-specific EmbeddingProvider implementations."),
    PackageSpec("src/narraos/providers/vector_store", "VectorStoreProvider interface and implementations. MEMORY_ARCHITECTURE.md §5."),
    PackageSpec("src/narraos/providers/vector_store/implementations", "FAISS/Qdrant VectorStoreProvider implementations."),
    PackageSpec("src/narraos/providers/analytics", "AnalyticsProvider interface and implementations."),
    PackageSpec("src/narraos/providers/analytics/implementations", "Vendor-specific AnalyticsProvider implementations."),
    PackageSpec("src/narraos/providers/publishing", "PublishingProvider interface and implementations."),
    PackageSpec("src/narraos/providers/publishing/implementations", "Vendor-specific PublishingProvider implementations."),
    # --- memory, compliance -------------------------------------------------
    PackageSpec("src/narraos/memory", "MemoryStore facade, namespaces, redaction. MEMORY_ARCHITECTURE.md §6, §8."),
    PackageSpec("src/narraos/compliance", "Risk taxonomy, jurisdiction rules, audit trail helpers. COMPLIANCE_ARCHITECTURE.md."),
    # --- platforms ----------------------------------------------------------
    PackageSpec("src/narraos/platforms", "PlatformAdapter interface and per-platform plugins. PLUGIN_ARCHITECTURE.md."),
    PackageSpec("src/narraos/platforms/youtube", "YouTube plugin — only platform implemented in Phase 1. YOUTUBE_ADAPTER_ARCHITECTURE.md."),
    PackageSpec("src/narraos/platforms/tiktok", "TikTok plugin — stub only, Phase 4."),
    PackageSpec("src/narraos/platforms/instagram", "Instagram plugin — stub only, Phase 4."),
    PackageSpec("src/narraos/platforms/x", "X plugin — stub only, Phase 4."),
    PackageSpec("src/narraos/platforms/facebook", "Facebook plugin — stub only, Phase 4."),
    # --- api, config, db, observability, common ------------------------------
    PackageSpec("src/narraos/api", "FastAPI application. Phase 2+ — do not build early."),
    PackageSpec("src/narraos/api/routes", "API route modules: runs, approvals, state."),
    PackageSpec("src/narraos/config", "Configuration loading — settings, provider/plugin config, config schema."),
    PackageSpec("src/narraos/db", "Database Layer (PostgreSQL) — the canonical store. MEMORY_ARCHITECTURE.md §2."),
    PackageSpec("src/narraos/db/models", "SQL models: runs, content, compliance_records, analytics."),
    PackageSpec("src/narraos/observability", "Structured logging, run tracing, cost tracking. DEVELOPER_HANDBOOK.md §8."),
    PackageSpec("src/narraos/common", "Genuinely cross-cutting utilities only. REPOSITORY_STRUCTURE.md §5."),
)

# Non-package infrastructure/docs/config/test folders, per REPOSITORY_STRUCTURE.md §2
# and DOCUMENTATION_STRUCTURE.md §2/§6.
PLAIN_FOLDERS: tuple[FolderSpec, ...] = (
    FolderSpec("dashboard", "Phase 2+ TypeScript/React control panel. Do not build early."),
    FolderSpec("infra/docker", "Dockerfiles for the API and worker images."),
    FolderSpec("infra/local", "Local docker-compose overrides."),
    FolderSpec("src/narraos/db/migrations", "Alembic migrations, timestamp-prefixed. Not a Python package."),
    FolderSpec("tests/unit", "Unit tests, mirrors src/narraos/ path-for-path as source files are added."),
    FolderSpec("tests/integration", "Integration tests, organized by pipeline flow rather than path mirroring."),
    FolderSpec("tests/fixtures", "Shared test fixtures."),
    FolderSpec("tests/fixtures/golden_run", "The fixed golden-run fixture for the CI full-pipeline integration test."),
    FolderSpec("docs/architecture", "Subsystem deep-dive docs. DOCUMENTATION_STRUCTURE.md §2."),
    FolderSpec("docs/api", "API reference, once core/api exists."),
    FolderSpec("docs/agents", "Per-agent design docs — prompts, evaluation criteria."),
    FolderSpec("docs/platforms/youtube", "YouTube integration notes — API quirks, auth setup."),
    FolderSpec("docs/platforms/tiktok", "Stub — populated at Phase 4."),
    FolderSpec("docs/platforms/instagram", "Stub — populated at Phase 4."),
    FolderSpec("docs/platforms/x", "Stub — populated at Phase 4."),
    FolderSpec("docs/platforms/facebook", "Stub — populated at Phase 4."),
    FolderSpec("docs/runbooks", "Operational procedures — incident response, manual overrides."),
    FolderSpec("docs/decisions", "Architecture Decision Records (ADRs), numbered sequentially."),
    FolderSpec("docs/onboarding", "Setup guides for new contributors, human or agent."),
    FolderSpec("config", "Environment-layered provider/plugin config (providers.*.yaml). PROVIDER_ARCHITECTURE.md §15."),
    FolderSpec("config/plugins", "Per-plugin config files (youtube.yaml, etc). PLUGIN_ARCHITECTURE.md §7."),
    FolderSpec(".github/workflows", "CI workflows — lint/typecheck/test, dependency-boundary enforcement."),
    FolderSpec("scripts", "One-off dev/ops scripts, including this one."),
)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass
class BootstrapReport:
    dirs_created: list[str] = field(default_factory=list)
    dirs_skipped: list[str] = field(default_factory=list)
    init_files_created: list[str] = field(default_factory=list)
    init_files_skipped: list[str] = field(default_factory=list)
    gitkeep_created: list[str] = field(default_factory=list)
    gitkeep_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def total_created(self) -> int:
        return len(self.dirs_created) + len(self.init_files_created) + len(self.gitkeep_created)

    def total_skipped(self) -> int:
        return len(self.dirs_skipped) + len(self.init_files_skipped) + len(self.gitkeep_skipped)

    def print_summary(self, *, dry_run: bool, verbose: bool) -> None:
        header = "Would create" if dry_run else "Created"
        print()
        print("=" * 72)
        print(f"NarraOS bootstrap summary — {header.lower()} {self.total_created()} item(s), "
              f"skipped {self.total_skipped()} existing item(s)")
        print("=" * 72)

        def _section(title: str, created: list[str], skipped: list[str]) -> None:
            print(f"\n{title}: {len(created)} {header.lower()}, {len(skipped)} skipped")
            for item in created:
                print(f"  + {item}")
            if verbose:
                for item in skipped:
                    print(f"  = {item} (already existed)")

        _section("Directories", self.dirs_created, self.dirs_skipped)
        _section("Package __init__.py files", self.init_files_created, self.init_files_skipped)
        _section(".gitkeep placeholders", self.gitkeep_created, self.gitkeep_skipped)

        if self.errors:
            print(f"\nErrors: {len(self.errors)}")
            for err in self.errors:
                print(f"  ! {err}")

        print()
        if dry_run:
            print("Dry run only — nothing was written. Re-run without --dry-run to apply.")
        elif self.errors:
            print("Completed with errors — review above before proceeding.")
        else:
            print("Repository scaffold is up to date with REPOSITORY_STRUCTURE.md.")
        print()


# ---------------------------------------------------------------------------
# Core scaffolding logic
# ---------------------------------------------------------------------------


def _assert_not_documentation(target: Path) -> None:
    """Refuse to touch anything that looks like a documentation file.

    This is a hard invariant of this script, not just a consequence of what's
    listed in PYTHON_PACKAGES/PLAIN_FOLDERS above: bootstrap.py must never
    create or overwrite documentation, per its own specification.
    """
    if target.suffix.lower() in _PROTECTED_DOC_EXTENSIONS:
        raise RuntimeError(
            f"Refusing to write '{target}': bootstrap.py must never create or modify "
            f"documentation files ({', '.join(sorted(_PROTECTED_DOC_EXTENSIONS))})."
        )


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _ensure_directory(path: Path, *, dry_run: bool, report: BootstrapReport) -> None:
    """Create `path` if missing. Never touches an existing directory or file."""
    if path.exists():
        if not path.is_dir():
            report.errors.append(f"Expected a directory but found a file at: {_relative(path)}")
            return
        report.dirs_skipped.append(_relative(path))
        return
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)
    report.dirs_created.append(_relative(path))


def _ensure_init_file(package_dir: Path, purpose: str, *, dry_run: bool, report: BootstrapReport) -> None:
    """Create `package_dir/__init__.py` if missing. Never overwrites an existing one."""
    init_path = package_dir / "__init__.py"
    _assert_not_documentation(init_path)
    if init_path.exists():
        report.init_files_skipped.append(_relative(init_path))
        return
    content = f'"""{purpose}"""\n'
    if not dry_run:
        init_path.write_text(content, encoding="utf-8")
    report.init_files_created.append(_relative(init_path))


def _ensure_gitkeep(folder_dir: Path, purpose: str, *, dry_run: bool, report: BootstrapReport) -> None:
    """Create `folder_dir/.gitkeep` only if the directory would otherwise be empty.

    A folder that already has real content (e.g. a docs/ subfolder that already
    holds hand-written .md files) is left completely alone — no .gitkeep is added
    and nothing in it is touched.
    """
    keep_path = folder_dir / ".gitkeep"
    _assert_not_documentation(keep_path)

    if keep_path.exists():
        report.gitkeep_skipped.append(_relative(keep_path))
        return

    if folder_dir.exists() and any(folder_dir.iterdir()):
        report.gitkeep_skipped.append(f"{_relative(keep_path)} (folder already has content)")
        return

    content = (
        f"# {purpose}\n"
        f"# This file exists only to keep this otherwise-empty directory tracked in git.\n"
        f"# Safe to delete once real content is added to this folder.\n"
    )
    if not dry_run:
        keep_path.write_text(content, encoding="utf-8")
    report.gitkeep_created.append(_relative(keep_path))


def scaffold(*, dry_run: bool) -> BootstrapReport:
    """Create every directory/package/folder defined above that doesn't already exist."""
    report = BootstrapReport()

    for spec in PYTHON_PACKAGES:
        pkg_dir = REPO_ROOT / spec.path
        _ensure_directory(pkg_dir, dry_run=dry_run, report=report)
        _ensure_init_file(pkg_dir, spec.purpose, dry_run=dry_run, report=report)

    for spec in PLAIN_FOLDERS:
        folder_dir = REPO_ROOT / spec.path
        _ensure_directory(folder_dir, dry_run=dry_run, report=report)
        _ensure_gitkeep(folder_dir, spec.purpose, dry_run=dry_run, report=report)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold the NarraOS repository layout defined in REPOSITORY_STRUCTURE.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without writing anything to disk.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Also list every skipped (already-existing) item in the summary.",
    )
    args = parser.parse_args(argv)

    print(f"NarraOS bootstrap — {'DRY RUN' if args.dry_run else 'applying changes'}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Repository root: {REPO_ROOT}")

    try:
        report = scaffold(dry_run=args.dry_run)
    except RuntimeError as exc:
        print(f"\nABORTED: {exc}", file=sys.stderr)
        return 1

    report.print_summary(dry_run=args.dry_run, verbose=args.verbose)

    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())