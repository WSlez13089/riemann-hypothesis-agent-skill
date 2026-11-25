"""Data contracts and shared constants for rh-arch-gate (Layer 0: zero internal deps)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
MAX_FILE_BYTES = 2 * 1024 * 1024  # 2 MiB hard cap per scanned source/config file
MAX_HASH_BYTES = 32 * 1024 * 1024  # 32 MiB cap for challenge contract hashing
MAX_JSON_DEPTH = 16
DEFAULT_SOFT_LINES = 120
DEFAULT_MAX_LINES = 300
DEFAULT_MAX_IMPORTS = 8

SUPPORTED_EXTS: dict[str, str] = {
    ".py": "python",
    ".lean": "lean",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "js",
    ".jsx": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".rs": "rust",
    ".go": "go",
}

DEFAULT_EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".lake",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        "dist",
        "build",
        "target",
        ".idea",
        ".vscode",
    }
)

WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


class GateInputError(Exception):
    """Raised on invalid CLI arguments, unsafe paths, or malformed JSON config."""


@dataclass(frozen=True)
class DenyRule:
    from_prefix: str
    forbid_prefix: str
    reason: str = ""


@dataclass(frozen=True)
class ArchConfig:
    soft_lines: int = DEFAULT_SOFT_LINES
    max_lines: int = DEFAULT_MAX_LINES
    max_imports: int = DEFAULT_MAX_IMPORTS
    layers: tuple[str, ...] = ()
    deny_imports: tuple[DenyRule, ...] = ()
    exclude_globs: tuple[str, ...] = ()
    challenge_manifest: str | None = None
    allow_todo_in_tests: bool = False


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # "HIGH" | "WARN" | "ERROR"
    file: str
    line: int
    message: str
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule": self.rule,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
        }
        if self.evidence:
            payload["evidence"] = self.evidence
        return payload


@dataclass
class FileScanSummary:
    rel_path: str
    language: str
    module_name: str
    total_lines: int
    non_blank_lines: int
    import_count: int
    is_facade: bool = False
    imports: list[tuple[int, str]] = field(default_factory=list)
