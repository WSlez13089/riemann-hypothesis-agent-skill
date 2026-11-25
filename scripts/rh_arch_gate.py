#!/usr/bin/env python3
"""CLI entrypoint & thin public facade for rh-arch-gate (Layer 4)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rh_gate_challenge import freeze_challenge, verify_challenge_manifest
from rh_gate_config import default_config_template, load_arch_config
from rh_gate_contracts import (
    ArchConfig,
    DEFAULT_MAX_IMPORTS,
    DEFAULT_MAX_LINES,
    DEFAULT_SOFT_LINES,
    DenyRule,
    Finding,
    GateInputError,
    SCHEMA_VERSION,
)
from rh_gate_engine import audit_repository
from rh_gate_io import atomic_write_json, load_strict_json, parse_strict_json_text, resolve_cli_path

__all__ = [
    "ArchConfig",
    "DenyRule",
    "Finding",
    "GateInputError",
    "audit_repository",
    "freeze_challenge",
    "verify_challenge_manifest",
    "load_strict_json",
    "parse_strict_json_text",
    "main",
]


def _format_human_audit(report: dict[str, Any]) -> str:
    m = report["metrics"]
    c = report["counts"]
    lines = [
        f"[rh-arch-gate] status={report['status']} files={m['scanned_files']} "
        f"lines(P50={m['lines_p50']}, P90={m['lines_p90']}, max={m['lines_max']}) "
        f"imports(P50={m['imports_p50']}, P90={m['imports_p90']}) cycles={m['cycles_count']}",
        f"counts: ERROR={c['ERROR']} HIGH={c['HIGH']} WARN={c['WARN']}",
    ]
    for f in report["findings"][:50]:
        ev = f" | {f['evidence']}" if f.get("evidence") else ""
        lines.append(f"  {f['severity']:5s} {f['rule']} {f['file']}:{f['line']} - {f['message']}{ev}")
    extra = len(report["findings"]) - 50
    if extra > 0:
        lines.append(f"  ... ({extra} more findings; pass --json for full output)")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rh-arch-gate",
        description="Architectural gate & zero-trust challenge verifier distilled from Claude x RH Lean 4 architecture.",
        exit_on_error=False,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="Audit repository against RH001-RH007 architectural gates.")
    p_audit.add_argument("target", help="Repository or source root directory")
    p_audit.add_argument("--config", help="Path to .rh-arch.json config file")
    p_audit.add_argument("--manifest", help="Optional challenge manifest JSON to verify as RH007")
    p_audit.add_argument("--soft-lines", type=int, help=f"Soft non-blank line limit (default {DEFAULT_SOFT_LINES})")
    p_audit.add_argument("--max-lines", type=int, help=f"Hard non-blank line limit (default {DEFAULT_MAX_LINES})")
    p_audit.add_argument("--max-imports", type=int, help=f"Direct import limit per file (default {DEFAULT_MAX_IMPORTS})")
    p_audit.add_argument("--exclude", action="append", default=[], help="Glob pattern to exclude (repeatable)")
    p_audit.add_argument("--strict", action="store_true", help="Treat WARN findings as exit code 1")
    p_audit.add_argument("--json", action="store_true", help="Emit JSON output")

    p_freeze = sub.add_parser("freeze-challenge", help="Freeze contract/test files into a SHA256 manifest.")
    p_freeze.add_argument("repo", help="Repository root directory")
    p_freeze.add_argument("--files", nargs="+", required=True, help="Relative paths to freeze")
    p_freeze.add_argument("-o", "--output", required=True, help="Output manifest JSON path")
    p_freeze.add_argument("--json", action="store_true", help="Emit JSON output")

    p_verify = sub.add_parser("verify-challenge", help="Verify frozen challenge manifest SHA256 integrity.")
    p_verify.add_argument("repo", help="Repository root directory")
    p_verify.add_argument("--manifest", required=True, help="Path to frozen challenge manifest JSON")
    p_verify.add_argument("--json", action="store_true", help="Emit JSON output")

    p_init = sub.add_parser("init-config", help="Write starter .rh-arch.json template.")
    p_init.add_argument("repo", help="Repository root directory")
    p_init.add_argument("-o", "--output", default=".rh-arch.json", help="Output path (relative to repo or absolute)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing config file")
    p_init.add_argument("--json", action="store_true", help="Emit JSON output")

    return parser


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init-config":
        repo = Path(args.repo).resolve()
        out_path = resolve_cli_path(repo, args.output)
        if out_path.exists() and not args.force:
            raise GateInputError(f"Config already exists (pass --force to overwrite): {out_path}")
        atomic_write_json(out_path, default_config_template())
        if args.json:
            print(json.dumps({"status": "OK", "output": str(out_path)}, ensure_ascii=False))
        else:
            print(f"Wrote starter config to {out_path}")
        return 0

    if args.command == "freeze-challenge":
        repo = Path(args.repo).resolve()
        out_path = resolve_cli_path(repo, args.output)
        manifest = freeze_challenge(repo, args.files, out_path)
        if args.json:
            print(json.dumps({"status": "FROZEN", "output": str(out_path), "manifest": manifest}, ensure_ascii=False))
        else:
            print(f"Froze {len(manifest['files'])} challenge files to {out_path}")
        return 0

    if args.command == "verify-challenge":
        repo = Path(args.repo).resolve()
        m_path = resolve_cli_path(repo, args.manifest)
        ok, ch_findings, details = verify_challenge_manifest(repo, m_path)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "PASS" if ok else "FAIL",
            **details,
            "findings": [f.to_dict() for f in ch_findings],
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"[verify-challenge] status={payload['status']} checked={details['checked_files']} mismatched={details['mismatched_files']}")
            for f in ch_findings:
                print(f"  HIGH {f.rule} {f.file} - {f.message}")
        return 0 if ok else 1

    if args.command == "audit":
        target = Path(args.target).resolve()
        cfg_path: Path | None = None
        if args.config:
            cfg_path = resolve_cli_path(target, args.config)
        elif (target / ".rh-arch.json").is_file():
            cfg_path = target / ".rh-arch.json"

        cfg = load_arch_config(cfg_path, args.soft_lines, args.max_lines, args.max_imports, args.exclude, args.manifest)
        m_override = resolve_cli_path(target, args.manifest) if args.manifest else None
        report = audit_repository(target, cfg, manifest_override=m_override)
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(_format_human_audit(report))
        if report["counts"]["ERROR"] > 0:
            return 2
        if report["counts"]["HIGH"] > 0:
            return 1
        if args.strict and report["counts"]["WARN"] > 0:
            return 1
        return 0

    raise GateInputError(f"Unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except argparse.ArgumentError as exc:
        print(f"[rh-arch-gate] ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        return _dispatch(args)
    except GateInputError as exc:
        err_payload = {"schema_version": SCHEMA_VERSION, "status": "ERROR", "error": str(exc)}
        if getattr(args, "json", False):
            print(json.dumps(err_payload, ensure_ascii=False))
        else:
            print(f"[rh-arch-gate] ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
