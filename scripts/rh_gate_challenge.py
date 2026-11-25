"""Zero-trust challenge manifest freeze & SHA256 verifier (Layer 2, RH-02/RH007)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rh_gate_contracts import Finding, GateInputError, SCHEMA_VERSION
from rh_gate_io import (
    atomic_write_json,
    load_strict_json,
    resolve_under_root,
    sha256_file,
    utc_now_iso,
)


def freeze_challenge(repo_root: Path, rel_files: list[str], output_path: Path) -> dict[str, Any]:
    if not rel_files:
        raise GateInputError("At least one --files target is required for freeze-challenge")
    resolved_root = repo_root.resolve()
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rel_files:
        target, norm_rel = resolve_under_root(resolved_root, raw)
        if norm_rel in seen:
            continue
        if not target.exists() or not target.is_file():
            raise GateInputError(f"Challenge file does not exist or is not a regular file: {raw}")
        digest, nbytes = sha256_file(target)
        entries.append({"path": norm_rel, "sha256": digest, "bytes": nbytes})
        seen.add(norm_rel)
    entries.sort(key=lambda x: x["path"])
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "rh_challenge_manifest",
        "created_utc": utc_now_iso(),
        "files": entries,
    }
    atomic_write_json(output_path, manifest)
    return manifest


def verify_challenge_manifest(repo_root: Path, manifest_path: Path) -> tuple[bool, list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    data = load_strict_json(manifest_path)
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise GateInputError(f"Unsupported or invalid challenge manifest schema in {manifest_path}")
    entries = data.get("files")
    if not isinstance(entries, list) or not entries:
        raise GateInputError("Challenge manifest must contain a non-empty 'files' list")

    checked = 0
    mismatched = 0
    for idx, item in enumerate(entries):
        if not isinstance(item, dict):
            raise GateInputError(f"Manifest entry {idx} must be an object")
        rel, exp_sha, exp_bytes = item.get("path"), item.get("sha256"), item.get("bytes")
        if not isinstance(rel, str) or not isinstance(exp_sha, str) or not isinstance(exp_bytes, int):
            raise GateInputError(f"Manifest entry {idx} missing valid path/sha256/bytes")
        checked += 1
        try:
            resolved, norm_rel = resolve_under_root(repo_root, rel)
        except GateInputError as exc:
            mismatched += 1
            findings.append(Finding("RH007", "HIGH", rel, 1, f"Challenge path violation: {exc}"))
            continue
        if not resolved.exists() or not resolved.is_file():
            mismatched += 1
            findings.append(Finding("RH007", "HIGH", norm_rel, 1, "Frozen challenge contract file is missing"))
            continue
        try:
            actual_sha, actual_bytes = sha256_file(resolved)
        except (GateInputError, OSError) as exc:
            mismatched += 1
            findings.append(Finding("RH007", "HIGH", norm_rel, 1, f"Failed hashing challenge file: {exc}"))
            continue
        if actual_sha != exp_sha or actual_bytes != exp_bytes:
            mismatched += 1
            findings.append(
                Finding(
                    "RH007",
                    "HIGH",
                    norm_rel,
                    1,
                    "Frozen challenge contract file was modified (SHA256 mismatch)",
                    f"expected={exp_sha[:12]}.. actual={actual_sha[:12]}..",
                )
            )
    details = {"manifest": str(manifest_path), "checked_files": checked, "mismatched_files": mismatched}
    return mismatched == 0, findings, details
