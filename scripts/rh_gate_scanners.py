"""Static AST (Python) & lexical (Lean/TS/JS/Rust/Go) file scanners (Layer 2)."""

from __future__ import annotations

import ast
import re

from rh_gate_contracts import ArchConfig, FileScanSummary, Finding, SUPPORTED_EXTS

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")
TYPE_IGNORE_RE = re.compile(r"#\s*(type:\s*ignore|noqa)\b")
LEAN_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.']+)")
LEAN_ESCAPE_RE = re.compile(
    r"\b(sorry|admit|axiom|native_decide|unsafe|skipKernelTC|implemented_by)\b"
)
JS_IMPORT_RE = re.compile(
    r"""^\s*(?:import\s+(?:.+?\s+from\s+)?|export\s+.+?\s+from\s+)['"]([^'"]+)['"]"""
)
JS_REQUIRE_RE = re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""")
JS_WILDCARD_RE = re.compile(r"^\s*export\s+\*\s+from\s+")
JS_SKIP_RE = re.compile(r"\b(?:it|test|describe)\.skip\s*\(")
JS_EVAL_RE = re.compile(r"\b(?:eval|Function)\s*\(")
RUST_USE_RE = re.compile(r"^\s*(?:pub\s+)?use\s+([^;]+);")
RUST_ESCAPE_RE = re.compile(r"\b(todo!|unimplemented!|unsafe\s*\{)")
GO_IMPORT_SINGLE_RE = re.compile(r'^\s*import\s+(?:[A-Za-z0-9_.]+\s+)?"([^"]+)"')
GO_IMPORT_LINE_RE = re.compile(r'^\s*(?:[A-Za-z0-9_.]+\s+)?"([^"]+)"')


def rel_to_module_name(rel_posix: str, lang: str) -> str:
    p = rel_posix
    for ext in SUPPORTED_EXTS:
        if p.endswith(ext):
            p = p[: -len(ext)]
            break
    if lang == "python" and p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    elif lang in ("ts", "js") and p.endswith("/index"):
        p = p[: -len("/index")]
    if p.startswith("src/"):
        p = p[4:]
    return p.replace("/", ".")


def is_test_path(rel_posix: str) -> bool:
    parts = rel_posix.lower().split("/")
    name = parts[-1]
    return (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    )


def is_barrel_or_facade(rel_posix: str) -> bool:
    """Detect dedicated Import-Hub / facade files (RH-03 Imports.lean pattern)."""
    name = rel_posix.split("/")[-1]
    lower = name.lower()
    if lower in ("__init__.py", "index.ts", "index.tsx", "index.js", "index.mjs", "mod.rs", "facade.py"):
        return True
    if name == "Imports.lean" or name.endswith("Imports.lean"):
        return True
    return False


def _extract_python_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and (in_single or in_double):
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[idx:]
    return ""


def _resolve_py_rel_import(current_mod: str, is_init: bool, level: int, module: str | None) -> str:
    parts = current_mod.split(".") if current_mod else []
    if not is_init and parts:
        parts = parts[:-1]
    up = max(0, level - 1)
    base = [] if up >= len(parts) else (parts[: len(parts) - up] if up > 0 else parts)
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def _is_not_implemented_raise(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
        return True
    return isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError"


def _is_skip_decorator_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Attribute) and node.func.attr == "skip":
        val = node.func.value
        if isinstance(val, ast.Name) and val.id in ("unittest", "pytest"):
            return True
        if isinstance(val, ast.Attribute) and val.attr == "mark":
            return True
    return False


def _is_stub_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if len(body) != 1:
        return False
    only = body[0]
    if isinstance(only, ast.Pass):
        return True
    return isinstance(only, ast.Expr) and isinstance(only.value, ast.Constant) and only.value.value is Ellipsis


def _is_abstract_or_overload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id in ("abstractmethod", "overload"):
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in ("abstractmethod", "overload"):
            return True
    return False


def scan_python_file(rel_posix: str, mod_name: str, text: str, cfg: ArchConfig) -> tuple[FileScanSummary, list[Finding]]:
    findings: list[Finding] = []
    lines = text.splitlines()
    non_blank = sum(1 for ln in lines if ln.strip())
    imports: list[tuple[int, str]] = []
    facade = is_barrel_or_facade(rel_posix)
    is_test = is_test_path(rel_posix)

    try:
        tree = ast.parse(text, filename=rel_posix)
    except SyntaxError as exc:
        findings.append(Finding("PARSE001", "ERROR", rel_posix, exc.lineno or 1, f"Python syntax error: {exc.msg}"))
        return FileScanSummary(rel_posix, "python", mod_name, len(lines), non_blank, 0, facade, []), findings

    is_init = rel_posix.endswith("/__init__.py") or rel_posix == "__init__.py"
    unique_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
                unique_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_py_rel_import(mod_name, is_init, node.level, node.module) if node.level > 0 else (node.module or "")
            if base == "__future__":
                continue
            if base:
                unique_modules.add(base)
            for alias in node.names:
                if alias.name == "*":
                    findings.append(Finding("RH004", "HIGH", rel_posix, node.lineno, "Wildcard import leaks namespace", f"from {base} import *"))
                    if base:
                        imports.append((node.lineno, base))
                else:
                    full_target = f"{base}.{alias.name}" if base else alias.name
                    imports.append((node.lineno, full_target))
                    if not base:
                        unique_modules.add(alias.name)
        elif isinstance(node, ast.Global):
            findings.append(Finding("RH004", "WARN", rel_posix, node.lineno, "Mutable 'global' binding introduces hidden coupling", ", ".join(node.names)))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                findings.append(Finding("RH004", "HIGH", rel_posix, node.lineno, f"Dynamic execution '{node.func.id}()' breaks static contract"))
            elif _is_skip_decorator_call(node):
                findings.append(Finding("RH003", "HIGH", rel_posix, node.lineno, "Unconditional test skip violates zero-trust gate"))
        elif isinstance(node, ast.Raise) and _is_not_implemented_raise(node):
            findings.append(Finding("RH003", "HIGH", rel_posix, node.lineno, "Unimplemented stub ('raise NotImplementedError') detected"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_stub_body(node) and not _is_abstract_or_overload(node):
            findings.append(Finding("RH003", "WARN", rel_posix, node.lineno, f"Empty placeholder body in '{node.name}'"))

    for lineno, raw_line in enumerate(lines, start=1):
        comment = _extract_python_comment(raw_line)
        if not comment:
            continue
        if TODO_RE.search(comment) and not (is_test and cfg.allow_todo_in_tests):
            findings.append(Finding("RH003", "HIGH", rel_posix, lineno, "Unresolved TODO/FIXME/HACK marker", comment.strip()[:80]))
        if TYPE_IGNORE_RE.search(comment) and "[" not in comment:
            findings.append(Finding("RH004", "WARN", rel_posix, lineno, "Blanket '# type: ignore' or '# noqa' without code", comment.strip()[:80]))

    return FileScanSummary(rel_posix, "python", mod_name, len(lines), non_blank, len(unique_modules), facade, imports), findings


def scan_generic_file(rel_posix: str, lang: str, mod_name: str, text: str, cfg: ArchConfig) -> tuple[FileScanSummary, list[Finding]]:
    findings: list[Finding] = []
    lines = text.splitlines()
    non_blank = sum(1 for ln in lines if ln.strip())
    imports: list[tuple[int, str]] = []
    facade = is_barrel_or_facade(rel_posix)
    is_test = is_test_path(rel_posix)
    in_go_block = False

    for lineno, raw_line in enumerate(lines, start=1):
        s = raw_line.strip()
        if not s:
            continue
        if lang == "lean":
            if s.startswith("--"):
                if TODO_RE.search(s) and not (is_test and cfg.allow_todo_in_tests):
                    findings.append(Finding("RH003", "HIGH", rel_posix, lineno, "Unresolved TODO/FIXME marker", s[:80]))
                continue
            code = s.split("--", 1)[0]
            if m_imp := LEAN_IMPORT_RE.match(code):
                imports.append((lineno, m_imp.group(1)))
            if m_esc := LEAN_ESCAPE_RE.search(code):
                findings.append(Finding("RH003", "HIGH", rel_posix, lineno, f"Lean escape hatch '{m_esc.group(1)}' detected", code[:80]))
        elif lang in ("ts", "js"):
            if s.startswith("//"):
                if TODO_RE.search(s) and not (is_test and cfg.allow_todo_in_tests):
                    findings.append(Finding("RH003", "HIGH", rel_posix, lineno, "Unresolved TODO/FIXME marker", s[:80]))
                continue
            if m_imp := JS_IMPORT_RE.match(s):
                imports.append((lineno, m_imp.group(1)))
            for m_req in JS_REQUIRE_RE.finditer(s):
                imports.append((lineno, m_req.group(1)))
            if JS_WILDCARD_RE.match(s):
                findings.append(Finding("RH004", "WARN", rel_posix, lineno, "Wildcard re-export ('export *')", s[:80]))
            if JS_SKIP_RE.search(s):
                findings.append(Finding("RH003", "HIGH", rel_posix, lineno, "Skipped test case detected", s[:80]))
            if JS_EVAL_RE.search(s):
                findings.append(Finding("RH004", "HIGH", rel_posix, lineno, "Dynamic JS eval/Function detected", s[:80]))
        elif lang == "rust":
            if s.startswith("//"):
                if TODO_RE.search(s) and not (is_test and cfg.allow_todo_in_tests):
                    findings.append(Finding("RH003", "HIGH", rel_posix, lineno, "Unresolved TODO/FIXME marker", s[:80]))
                continue
            if m_use := RUST_USE_RE.match(s):
                imports.append((lineno, m_use.group(1).replace("::", ".")))
            if m_esc := RUST_ESCAPE_RE.search(s):
                findings.append(Finding("RH003", "HIGH", rel_posix, lineno, f"Rust escape hatch '{m_esc.group(1)}' detected", s[:80]))
        elif lang == "go":
            if s.startswith("//"):
                if TODO_RE.search(s) and not (is_test and cfg.allow_todo_in_tests):
                    findings.append(Finding("RH003", "HIGH", rel_posix, lineno, "Unresolved TODO/FIXME marker", s[:80]))
                continue
            if s.startswith("import ("):
                in_go_block = True
                continue
            if in_go_block:
                if s == ")":
                    in_go_block = False
                elif m_go := GO_IMPORT_LINE_RE.match(s):
                    imports.append((lineno, m_go.group(1).replace("/", ".")))
                continue
            if m_go_s := GO_IMPORT_SINGLE_RE.match(s):
                imports.append((lineno, m_go_s.group(1).replace("/", ".")))

    return FileScanSummary(rel_posix, lang, mod_name, len(lines), non_blank, len(imports), facade, imports), findings
