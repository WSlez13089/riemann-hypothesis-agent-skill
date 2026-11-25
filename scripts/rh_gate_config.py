"""Configuration loader & starter template for .rh-arch.json (Layer 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rh_gate_contracts import (
    ArchConfig,
    DEFAULT_MAX_IMPORTS,
    DEFAULT_MAX_LINES,
    DEFAULT_SOFT_LINES,
    DenyRule,
    GateInputError,
    SCHEMA_VERSION,
)
from rh_gate_io import load_strict_json


def _expect_pos_int(val: Any, name: str) -> int:
    if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
        raise GateInputError(f"{name} must be a positive integer")
    return val


def load_arch_config(
    config_path: Path | None,
    cli_soft: int | None,
    cli_max: int | None,
    cli_imp: int | None,
    cli_excludes: list[str],
    cli_manifest: str | None,
) -> ArchConfig:
    soft, max_l, max_i = DEFAULT_SOFT_LINES, DEFAULT_MAX_LINES, DEFAULT_MAX_IMPORTS
    layers: list[str] = []
    deny_rules: list[DenyRule] = []
    excludes: list[str] = []
    manifest: str | None = None
    allow_todo_tests = False

    if config_path is not None:
        data = load_strict_json(config_path)
        if not isinstance(data, dict):
            raise GateInputError("Config root must be a JSON object")
        thresholds = data.get("thresholds", {})
        if thresholds is not None:
            if not isinstance(thresholds, dict):
                raise GateInputError("thresholds must be an object")
            if "soft_lines" in thresholds:
                soft = _expect_pos_int(thresholds["soft_lines"], "thresholds.soft_lines")
            if "max_lines" in thresholds:
                max_l = _expect_pos_int(thresholds["max_lines"], "thresholds.max_lines")
            if "max_imports" in thresholds:
                max_i = _expect_pos_int(thresholds["max_imports"], "thresholds.max_imports")
        raw_layers = data.get("layers", [])
        if not isinstance(raw_layers, list) or not all(isinstance(x, str) and x.strip() for x in raw_layers):
            raise GateInputError("layers must be a list of non-empty strings")
        layers = [x.strip().strip("./") for x in raw_layers]

        raw_deny = data.get("deny_imports", [])
        if not isinstance(raw_deny, list):
            raise GateInputError("deny_imports must be a list")
        for idx, item in enumerate(raw_deny):
            if not isinstance(item, dict):
                raise GateInputError(f"deny_imports[{idx}] must be an object")
            fp, fb, rs = item.get("from_prefix"), item.get("forbid_prefix"), item.get("reason", "")
            if not isinstance(fp, str) or not isinstance(fb, str) or not fp.strip() or not fb.strip():
                raise GateInputError(f"deny_imports[{idx}] requires non-empty from_prefix and forbid_prefix")
            if not isinstance(rs, str):
                raise GateInputError(f"deny_imports[{idx}].reason must be a string")
            deny_rules.append(DenyRule(fp.strip(), fb.strip(), rs.strip()))

        raw_ex = data.get("exclude", [])
        if not isinstance(raw_ex, list) or not all(isinstance(x, str) for x in raw_ex):
            raise GateInputError("exclude must be a list of glob strings")
        excludes.extend(raw_ex)

        raw_manifest = data.get("challenge_manifest")
        if raw_manifest is not None:
            if not isinstance(raw_manifest, str) or not raw_manifest.strip():
                raise GateInputError("challenge_manifest must be a non-empty string or null")
            manifest = raw_manifest.strip()

        raw_allow_todo = data.get("allow_todo_in_tests", False)
        if not isinstance(raw_allow_todo, bool):
            raise GateInputError("allow_todo_in_tests must be boolean")
        allow_todo_tests = raw_allow_todo

    if cli_soft is not None:
        soft = _expect_pos_int(cli_soft, "--soft-lines")
    if cli_max is not None:
        max_l = _expect_pos_int(cli_max, "--max-lines")
    if cli_imp is not None:
        max_i = _expect_pos_int(cli_imp, "--max-imports")
    if soft > max_l:
        raise GateInputError(f"soft_lines ({soft}) cannot exceed max_lines ({max_l})")
    excludes.extend(cli_excludes)
    if cli_manifest is not None:
        manifest = cli_manifest

    return ArchConfig(
        soft_lines=soft,
        max_lines=max_l,
        max_imports=max_i,
        layers=tuple(layers),
        deny_imports=tuple(deny_rules),
        exclude_globs=tuple(excludes),
        challenge_manifest=manifest,
        allow_todo_in_tests=allow_todo_tests,
    )


def default_config_template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "thresholds": {
            "soft_lines": DEFAULT_SOFT_LINES,
            "max_lines": DEFAULT_MAX_LINES,
            "max_imports": DEFAULT_MAX_IMPORTS,
        },
        "layers": ["contracts", "core", "services", "adapters", "entrypoints"],
        "deny_imports": [
            {
                "from_prefix": "core",
                "forbid_prefix": "services",
                "reason": "Lower core layer must not import upper service layer",
            }
        ],
        "exclude": ["tests/*", "**/__pycache__/*"],
        "challenge_manifest": None,
        "allow_todo_in_tests": False,
    }
