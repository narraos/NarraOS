"""Generic YAML configuration file loading.

This module only reads YAML files into plain dictionaries and performs simple
layered merging (base file, then an environment-specific override file merged
on top), matching the layering described in PROVIDER_ARCHITECTURE.md §15.

It deliberately knows nothing about providers, plugins, or agents
specifically. Turning a merged dict into a validated, typed configuration
object (and persisting a Configuration_v1 snapshot per SCHEMA_REFERENCE.md §7)
is Core Infrastructure work, not part of this loader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file into a dict. Returns {} if the file doesn't exist."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    return loaded or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` on top of `base`, without mutating either input."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_layered_config(config_dir: Path, base_name: str, environment: str) -> dict[str, Any]:
    """Load `<base_name>.base.yaml`, then merge `<base_name>.<environment>.yaml` on top.

    Example: `load_layered_config(Path("config"), "providers", "local")` reads
    `config/providers.base.yaml`, then merges `config/providers.local.yaml`
    over it -- matching PROVIDER_ARCHITECTURE.md §15's layering exactly.
    """
    base = load_yaml(config_dir / f"{base_name}.base.yaml")
    overrides = load_yaml(config_dir / f"{base_name}.{environment}.yaml")
    return _deep_merge(base, overrides)
