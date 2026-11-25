"""Cross-file DAG/layer auditor engine (Layer 3)."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from rh_gate_challenge import verify_challenge_manifest
from rh_gate_contracts import (
    ArchConfig,
    DEFAULT_EXCLUDED_DIRS,
    FileScanSummary,
    Finding,
    GateInputError,
    MAX_FILE_BYTES,
    SCHEMA_VERSION,
    SUPPORTED_EXTS,
)
from rh_gate_io import is_reparse_or_symlink, read_bounded_bytes, resolve_cli_path
from rh_gate_scanners import rel_to_module_name, scan_generic_file, scan_python_file


def _matches_exclude(rel_posix: str, exclude_globs: tuple[str, ...]) -> bool:
    for pat in exclude_globs:
        norm = pat.replace("\\", "/")
        if fnmatch.fnmatch(rel_posix, norm) or fnmatch.fnmatch(rel_posix.split("/")[-1], norm):
            return True
    return False


def _prefix_matches(name: str, prefix: str) -> bool:
    norm_name = name.replace("/", ".").strip(".")
    norm_pref = prefix.replace("/", ".").strip(".")
    return norm_name == norm_pref or norm_name.startswith(norm_pref + ".")


def _layer_index(name: str, layers: tuple[str, ...]) -> int | None:
    if not layers:
        return None
    norm = name.replace("/", ".").strip(".")
    parts = norm.split(".")
    for idx, layer in enumerate(layers):
        l_norm = layer.replace("/", ".").strip(".")
        if norm == l_norm or norm.startswith(l_norm + "."):
            return idx
        if len(parts) > 1 and parts[0] in ("src", "lib"):
            rest = ".".join(parts[1:])
            if rest == l_norm or rest.startswith(l_norm + "."):
                return idx
    return None


def _match_internal_module(imp: str, known_modules: set[str]) -> str | None:
    if imp in known_modules:
        return imp
    parts = imp.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        cand = ".".join(parts[:cut])
        if cand in known_modules:
            return cand
    return None


def tarjan_sccs(graph: dict[str, set[str]]) -> list[list[str]]:
    index_counter = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []

    for root_node in sorted(graph.keys()):
        if root_node in indices:
            continue
        call_stack: list[tuple[str, list[str], int]] = []
        indices[root_node] = lowlink[root_node] = index_counter
        index_counter += 1
        stack.append(root_node)
        on_stack.add(root_node)
        call_stack.append((root_node, sorted(graph.get(root_node, ())), 0))

        while call_stack:
            v, neighbors, n_idx = call_stack[-1]
            if n_idx < len(neighbors):
                call_stack[-1] = (v, neighbors, n_idx + 1)
                w = neighbors[n_idx]
                if w not in indices:
                    indices[w] = lowlink[w] = index_counter
                    index_counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    call_stack.append((w, sorted(graph.get(w, ())), 0))
                elif w in on_stack and indices[w] < lowlink[v]:
                    lowlink[v] = indices[w]
            else:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    if lowlink[v] < lowlink[parent]:
                        lowlink[parent] = lowlink[v]
                if lowlink[v] == indices[v]:
                    comp: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack.remove(w)
                        comp.append(w)
                        if w == v:
                            break
                    if len(comp) >= 2:
                        sccs.append(sorted(comp))
    return sorted(sccs)


def _iter_safe_source_files(resolved_root: Path) -> list[tuple[Path, str]]:
    """Bounded iterative directory walk refusing symlinks/Windows junctions via lstat."""
    results: list[tuple[Path, str]] = []
    pending: list[Path] = [resolved_root]
    while pending:
        cur_dir = pending.pop()
        try:
            entries = sorted(os.scandir(cur_dir), key=lambda e: e.name)
        except OSError:
            continue
        subdirs: list[Path] = []
        for entry in entries:
            child = Path(entry.path)
            if is_reparse_or_symlink(child):
                if child.suffix.lower() in SUPPORTED_EXTS:
                    rel = child.relative_to(resolved_root).as_posix()
                    results.append((child, rel))
                continue
            resolved_child = child.resolve()
            if not resolved_child.is_relative_to(resolved_root):
                continue
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in DEFAULT_EXCLUDED_DIRS:
                    subdirs.append(resolved_child)
            elif entry.is_file(follow_symlinks=False):
                rel = resolved_child.relative_to(resolved_root).as_posix()
                results.append((resolved_child, rel))
        pending.extend(reversed(subdirs))
    return results


def _check_cross_file_rules(summaries: list[FileScanSummary], cfg: ArchConfig) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    known = {s.module_name for s in summaries if s.module_name}
    mod_to_file = {s.module_name: s.rel_path for s in summaries if s.module_name}
    dep_graph: dict[str, set[str]] = {m: set() for m in known}

    for s in summaries:
        src_layer = _layer_index(s.module_name, cfg.layers)
        for lineno, imp in s.imports:
            for rule in cfg.deny_imports:
                if _prefix_matches(s.module_name, rule.from_prefix) and _prefix_matches(imp, rule.forbid_prefix):
                    detail = f" ({rule.reason})" if rule.reason else ""
                    findings.append(
                        Finding(
                            "RH005",
                            "HIGH",
                            s.rel_path,
                            lineno,
                            f"Forbidden import '{imp}' violates deny_imports {rule.from_prefix} -/-> {rule.forbid_prefix}{detail}",
                        )
                    )
            if src_layer is not None:
                dst_layer = _layer_index(imp, cfg.layers)
                if dst_layer is not None and dst_layer > src_layer:
                    findings.append(
                        Finding(
                            "RH005",
                            "HIGH",
                            s.rel_path,
                            lineno,
                            f"Upward layer violation: '{cfg.layers[src_layer]}' (L{src_layer}) cannot import '{cfg.layers[dst_layer]}' (L{dst_layer}) via '{imp}'",
                        )
                    )
            matched = _match_internal_module(imp, known)
            if matched is not None and matched != s.module_name:
                dep_graph[s.module_name].add(matched)

    sccs = tarjan_sccs(dep_graph)
    for comp in sccs:
        anchor = mod_to_file.get(comp[0], comp[0])
        evidence = " -> ".join(comp[:6]) + (" -> ..." if len(comp) > 6 else "")
        findings.append(
            Finding(
                "RH006",
                "HIGH",
                anchor,
                1,
                f"Circular module dependency cycle ({len(comp)} modules); extract shared contracts",
                evidence,
            )
        )
    return findings, len(sccs)


def audit_repository(repo_root: Path, cfg: ArchConfig, manifest_override: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root.resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise GateInputError(f"Target directory does not exist: {repo_root}")

    summaries: list[FileScanSummary] = []
    findings: list[Finding] = []
    skipped = 0

    for full, rel_posix in _iter_safe_source_files(resolved_root):
        if _matches_exclude(rel_posix, cfg.exclude_globs):
            skipped += 1
            continue
        lang = SUPPORTED_EXTS.get(full.suffix.lower())
        if lang is None:
            continue
        if is_reparse_or_symlink(full):
            findings.append(Finding("PARSE001", "ERROR", rel_posix, 1, "Symlink/reparse source file rejected"))
            continue
        try:
            text = read_bounded_bytes(full, max_bytes=MAX_FILE_BYTES).decode("utf-8", errors="strict")
        except (GateInputError, OSError, UnicodeDecodeError) as exc:
            findings.append(Finding("PARSE001", "ERROR", rel_posix, 1, f"Failed reading UTF-8 source: {exc}"))
            continue

        mod_name = rel_to_module_name(rel_posix, lang)
        summary, f_findings = (
            scan_python_file(rel_posix, mod_name, text, cfg)
            if lang == "python"
            else scan_generic_file(rel_posix, lang, mod_name, text, cfg)
        )
        summaries.append(summary)
        findings.extend(f_findings)

        if summary.non_blank_lines > cfg.max_lines:
            findings.append(Finding("RH001", "HIGH", rel_posix, 1, f"{summary.non_blank_lines} non-blank lines exceeds hard limit {cfg.max_lines}"))
        elif summary.non_blank_lines > cfg.soft_lines:
            findings.append(Finding("RH001", "WARN", rel_posix, 1, f"{summary.non_blank_lines} non-blank lines exceeds soft target {cfg.soft_lines} (RH P50=82)"))

        imp_limit = cfg.max_imports * 4 if summary.is_facade else cfg.max_imports
        if summary.import_count > imp_limit:
            sev = "HIGH" if summary.import_count > imp_limit * 2 else "WARN"
            findings.append(Finding("RH002", sev, rel_posix, 1, f"High fan-in: {summary.import_count} unique imported modules (limit {imp_limit})"))

    cross_findings, cycles_count = _check_cross_file_rules(summaries, cfg)
    findings.extend(cross_findings)

    challenge_result: dict[str, Any] | None = None
    manifest_path = manifest_override
    if manifest_path is None and cfg.challenge_manifest:
        manifest_path = resolve_cli_path(resolved_root, cfg.challenge_manifest)
    if manifest_path is not None:
        ok, ch_findings, ch_details = verify_challenge_manifest(resolved_root, manifest_path)
        findings.extend(ch_findings)
        challenge_result = {"passed": ok, **ch_details}

    line_vals = sorted(s.non_blank_lines for s in summaries)
    imp_vals = sorted(s.import_count for s in summaries)
    pct = lambda vals, q: vals[min(len(vals) - 1, int(len(vals) * q))] if vals else 0
    counts = {lvl: sum(1 for f in findings if f.severity == lvl) for lvl in ("ERROR", "HIGH", "WARN")}
    status = "ERROR" if counts["ERROR"] else ("FAIL" if counts["HIGH"] else ("WARN" if counts["WARN"] else "PASS"))

    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "rh-arch-gate",
        "root": str(resolved_root),
        "status": status,
        "metrics": {
            "scanned_files": len(summaries),
            "skipped_files": skipped,
            "lines_p50": pct(line_vals, 0.5),
            "lines_p90": pct(line_vals, 0.9),
            "lines_max": line_vals[-1] if line_vals else 0,
            "imports_p50": pct(imp_vals, 0.5),
            "imports_p90": pct(imp_vals, 0.9),
            "cycles_count": cycles_count,
        },
        "counts": counts,
        "challenge_verification": challenge_result,
        "findings": [f.to_dict() for f in sorted(findings, key=lambda x: (x.severity, x.rule, x.file, x.line))],
    }
