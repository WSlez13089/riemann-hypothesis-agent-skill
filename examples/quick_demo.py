#!/usr/bin/env python3
"""Reproduce a clean audit, deliberate violations and recovery in a temporary repo."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile


CLI = Path(__file__).resolve().parents[1] / "scripts" / "rh_arch_gate.py"


def call(root: Path, *args: str, expected: int) -> dict:
    result = subprocess.run(
        [sys.executable, str(CLI), *args, "--json"],
        cwd=root, capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    if result.returncode != expected:
        raise RuntimeError(f"Expected exit {expected}, got {result.returncode}: {result.stdout} {result.stderr}")
    return json.loads(result.stdout)


def write(root: Path, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rh-gate-demo-") as directory:
        root = Path(directory)
        spec = "EXPECTED = 42\n"
        clean_core = "from contracts.spec import EXPECTED\n\ndef run():\n    return EXPECTED\n"
        write(root, "contracts/spec.py", spec)
        write(root, "core/engine.py", clean_core)
        write(root, "services/api.py", "from core.engine import run\n")
        call(root, "init-config", ".", expected=0)
        call(root, "freeze-challenge", ".", "--files", "contracts/spec.py",
             "-o", ".rh-challenge.json", expected=0)

        print("$ rh-arch-gate audit . --manifest .rh-challenge.json")
        clean = call(root, "audit", ".", "--manifest", ".rh-challenge.json", expected=0)
        print(f"PASS  |  {clean['metrics']['scanned_files']} files  |  {clean['counts']['HIGH']} high findings")

        print("\n# Simulate a bad Agent edit: reverse import, cycle, altered contract")
        write(root, "core/engine.py", "import services.api\n")
        write(root, "contracts/spec.py", "EXPECTED = 999\n")
        print("$ rh-arch-gate audit . --manifest .rh-challenge.json")
        blocked = call(root, "audit", ".", "--manifest", ".rh-challenge.json", expected=1)
        for rule, description in (
            ("RH005", "Reverse layer dependency"),
            ("RH006", "Circular dependency"),
            ("RH007", "Frozen contract changed"),
        ):
            findings = [f for f in blocked["findings"] if f["rule"] == rule and f["severity"] == "HIGH"]
            if not findings:
                raise RuntimeError(f"Expected {rule} to be detected: {blocked}")
            print(f"BLOCK | {rule} | {description}")
        print("FAIL  |  exit 1")

        print("\n# Restore the contract and correct the implementation")
        write(root, "contracts/spec.py", spec)
        write(root, "core/engine.py", clean_core)
        restored = call(root, "audit", ".", "--manifest", ".rh-challenge.json", expected=0)
        print("$ rh-arch-gate audit . --manifest .rh-challenge.json")
        print(f"PASS  |  {restored['counts']['HIGH']} high findings  |  exit 0")


if __name__ == "__main__":
    main()
