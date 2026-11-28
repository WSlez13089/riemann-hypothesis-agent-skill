#!/usr/bin/env python3
"""Reproducible end-to-end CLI demo for rh-arch-gate.

Creates an isolated temporary repository and demonstrates:
1. Clean layered micro-modules + frozen SHA256 challenge pass (exit 0).
2. Injecting RH005 (layer breach), RH006 (cycle), and RH007 (tampered test)
   is deterministically blocked (exit 1).
3. Restoring the clean baseline passes again (exit 0).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "rh_arch_gate.py"


def run_gate(*args: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(GATE), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    payload = json.loads(proc.stdout)
    return proc.returncode, payload


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="rh_gate_demo_") as td:
        repo = Path(td)
        (repo / "contracts.py").write_text("VALUE = 1\n", encoding="utf-8")
        (repo / "service.py").write_text("from contracts import VALUE\n\ndef get() -> int:\n    return VALUE\n", encoding="utf-8")
        (repo / "test_contract.py").write_text("from service import get\nassert get() == 1\n", encoding="utf-8")
        (repo / ".rh-arch.json").write_text(json.dumps({
            "schema_version": 1,
            "thresholds": {"soft_lines": 120, "max_lines": 300, "max_imports": 8},
            "layers": ["contracts", "service"],
            "exclude": ["test_*.py"],
            "challenge_manifest": ".rh-challenge.json",
        }, indent=2), encoding="utf-8")

        manifest = repo / ".rh-challenge.json"
        code, frozen = run_gate(
            "freeze-challenge", str(repo),
            "--files", "contracts.py", "test_contract.py",
            "-o", str(manifest), "--json",
        )
        assert code == 0, f"freeze failed: {frozen}"

        code, clean = run_gate(
            "audit", str(repo),
            "--config", str(repo / ".rh-arch.json"),
            "--manifest", str(manifest),
            "--strict", "--json",
        )
        print("1. Clean baseline:", clean["status"], clean["counts"])
        assert code == 0 and clean["status"] == "PASS"

        # Inject RH005 (upward import) + RH006 (cycle) + RH007 (tampered test)
        (repo / "contracts.py").write_text("from service import get\nVALUE = get()\n", encoding="utf-8")
        (repo / "test_contract.py").write_text("assert True\n", encoding="utf-8")

        code, blocked = run_gate(
            "audit", str(repo),
            "--config", str(repo / ".rh-arch.json"),
            "--manifest", str(manifest),
            "--strict", "--json",
        )
        rules = sorted({f["rule"] for f in blocked["findings"]})
        print("2. Violations injected -> exit:", code, "rules caught:", rules)
        assert code == 1 and {"RH005", "RH006", "RH007"}.issubset(set(rules))

        # Restore clean baseline
        (repo / "contracts.py").write_text("VALUE = 1\n", encoding="utf-8")
        (repo / "test_contract.py").write_text("from service import get\nassert get() == 1\n", encoding="utf-8")

        code, recovered = run_gate(
            "audit", str(repo),
            "--config", str(repo / ".rh-arch.json"),
            "--manifest", str(manifest),
            "--strict", "--json",
        )
        print("3. Baseline restored:", recovered["status"], recovered["counts"])
        assert code == 0 and recovered["status"] == "PASS"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
