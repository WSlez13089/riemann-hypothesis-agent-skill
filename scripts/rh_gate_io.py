"""Bounded I/O, cross-platform path safety, strict JSON, and atomic writes (Layer 1)."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from rh_gate_contracts import (
    GateInputError,
    MAX_FILE_BYTES,
    MAX_HASH_BYTES,
    MAX_JSON_DEPTH,
    WINDOWS_RESERVED_NAMES,
)

_REPARSE_ATTR = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)


def utc_now_iso() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def is_reparse_or_symlink(path: Path) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    if _REPARSE_ATTR and (getattr(st, "st_file_attributes", 0) & _REPARSE_ATTR):
        return True
    return False


def validate_path_segments(path_obj: Path) -> None:
    for part in path_obj.parts:
        if (
            part in ("", "/", "\\")
            or (len(part) == 2 and part[1] == ":")
            or (len(part) == 3 and part[1:] in (":\\", ":/"))
        ):
            continue
        if part != part.rstrip(" ."):
            raise GateInputError(f"Unsafe path segment with trailing space/dot: {part!r}")
        stem = part.split(".", 1)[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            raise GateInputError(f"Unsafe Windows reserved path segment: {part!r}")


def resolve_under_root(root: Path, raw_path: str) -> tuple[Path, str]:
    if not raw_path or "\x00" in raw_path:
        raise GateInputError(f"Invalid path: {raw_path!r}")
    resolved_root = root.resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        validate_path_segments(candidate)
        joined = resolved_root.joinpath(candidate)
    else:
        joined = candidate
    resolved_target = joined.resolve()
    if not resolved_target.is_relative_to(resolved_root):
        raise GateInputError(f"Path escapes repository root: {raw_path}")
    cur = resolved_root
    for part in resolved_target.relative_to(resolved_root).parts:
        cur = cur.joinpath(part)
        if not cur.resolve().is_relative_to(resolved_root):
            raise GateInputError(f"Path escapes repository root: {raw_path}")
        if is_reparse_or_symlink(cur):
            raise GateInputError(f"Symlink/reparse point refused: {cur}")
    rel_posix = resolved_target.relative_to(resolved_root).as_posix()
    return resolved_target, rel_posix


def resolve_cli_path(base: Path, raw_path: str) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise GateInputError(f"Invalid path: {raw_path!r}")
    cand = Path(raw_path)
    if cand.is_absolute():
        validate_path_segments(cand)
        return cand.resolve()
    resolved, _ = resolve_under_root(base, raw_path)
    return resolved


def _check_json_depth(obj: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise GateInputError(f"JSON nesting depth exceeds limit ({MAX_JSON_DEPTH})")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_json_depth(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _check_json_depth(v, depth + 1)


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise GateInputError(f"Duplicate JSON key rejected: {k!r}")
        out[k] = v
    return out


def _reject_nonfinite(token: str) -> Any:
    raise GateInputError(f"Non-standard JSON numeric constant rejected: {token!r}")


def parse_strict_json_text(raw: str, max_bytes: int = MAX_FILE_BYTES, label: str = "<string>") -> Any:
    if len(raw) > max_bytes:
        raise GateInputError(f"JSON payload exceeds {max_bytes} char limit: {label}")
    if len(raw.encode("utf-8", errors="replace")) > max_bytes:
        raise GateInputError(f"JSON payload exceeds {max_bytes} byte limit: {label}")
    try:
        parsed = json.loads(
            raw,
            object_pairs_hook=_strict_pairs_hook,
            parse_constant=_reject_nonfinite,
        )
    except json.JSONDecodeError as exc:
        raise GateInputError(f"Invalid JSON in {label}: {exc}") from exc
    _check_json_depth(parsed)
    return parsed


def read_bounded_bytes(path: Path, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    if is_reparse_or_symlink(path):
        raise GateInputError(f"Symlink/reparse file refused: {path}")
    try:
        st = path.stat()
    except OSError as exc:
        raise GateInputError(f"Cannot stat file {path}: {exc}") from exc
    if st.st_size > max_bytes:
        raise GateInputError(f"File exceeds {max_bytes} byte limit ({st.st_size} bytes): {path}")
    with path.open("rb") as fh:
        data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise GateInputError(f"File grew beyond {max_bytes} byte limit during read: {path}")
    return data


def load_strict_json(path: Path, max_bytes: int = MAX_FILE_BYTES) -> Any:
    raw_bytes = read_bounded_bytes(path, max_bytes=max_bytes)
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GateInputError(f"Non-UTF-8 JSON file {path}: {exc}") from exc
    return parse_strict_json_text(text, max_bytes=max_bytes, label=str(path))


def sha256_file(path: Path, max_bytes: int = MAX_HASH_BYTES) -> tuple[str, int]:
    data = read_bounded_bytes(path, max_bytes=max_bytes)
    return hashlib.sha256(data).hexdigest(), len(data)


def atomic_write_json(target: Path, payload: dict[str, Any]) -> None:
    validate_path_segments(target)
    if target.exists() and is_reparse_or_symlink(target):
        raise GateInputError(f"Refusing to overwrite symlink/reparse point: {target}")
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    tmp_path: Path | None = None
    fd_obj = None
    committed = False
    try:
        fd_obj = tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        )
        tmp_path = Path(fd_obj.name)
        fd_obj.write(encoded)
        fd_obj.flush()
        os.fsync(fd_obj.fileno())
        fd_obj.close()
        fd_obj = None
        os.replace(str(tmp_path), str(target))
        committed = True
    finally:
        if fd_obj is not None:
            try:
                fd_obj.close()
            except OSError:
                pass
        if not committed and tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
