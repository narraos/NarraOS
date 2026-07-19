"""Day 0 smoke tests.

These intentionally contain no business-logic assertions -- there is no
business logic yet. Their only job is to prove the package installs and
every top-level subpackage imports cleanly, and that the environment-loading
and logging configuration added on Day 0 actually work, satisfying the
"ensure the project builds successfully" objective.
"""

from __future__ import annotations

import narraos


def test_package_imports() -> None:
    assert narraos.__name__ == "narraos"


def test_core_subpackages_import() -> None:
    import narraos.compliance  # noqa: F401
    import narraos.core  # noqa: F401
    import narraos.core.agents  # noqa: F401
    import narraos.core.pipeline  # noqa: F401
    import narraos.core.schemas  # noqa: F401
    import narraos.core.stages  # noqa: F401
    import narraos.db  # noqa: F401
    import narraos.memory  # noqa: F401
    import narraos.observability  # noqa: F401
    import narraos.platforms  # noqa: F401
    import narraos.providers  # noqa: F401


def test_settings_load_with_defaults() -> None:
    from narraos.config.settings import Environment, Settings

    settings = Settings()
    assert settings.environment == Environment.LOCAL
    assert settings.log_level == "INFO"
    assert "narraos" in settings.database_url


def test_layered_config_loader_handles_missing_files(tmp_path: object) -> None:
    from pathlib import Path

    from narraos.config.loader import load_layered_config

    # No config files present at all -- loader must return an empty dict,
    # never raise, so an unconfigured environment fails at the point
    # something is actually resolved from it, not at load time.
    result = load_layered_config(Path(str(tmp_path)), "providers", "local")
    assert result == {}


def test_logging_configures_without_error() -> None:
    from narraos.observability.logging import configure_logging

    configure_logging(level="DEBUG")
