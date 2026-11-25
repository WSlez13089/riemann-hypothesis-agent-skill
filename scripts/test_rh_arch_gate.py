#!/usr/bin/env python3
"""Deterministic unit tests for rh_arch_gate (zero external deps, strict JSON)."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import rh_arch_gate as gate


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", errors="strict")


class TestRhArchGate(unittest.TestCase):
    def test_clean_layered_repo_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_text(root / "contracts" / "spec.py", "def ok(x: int) -> int:\n    return x + 1\n")
            _write_text(
                root / "core" / "engine.py",
                "from contracts.spec import ok\n\ndef run(x: int) -> int:\n    return ok(x)\n",
            )
            _write_text(
                root / "services" / "api.py",
                "from core.engine import run\n\ndef handle(x: int) -> int:\n    return run(x)\n",
            )
            cfg = gate.ArchConfig(
                layers=("contracts", "core", "services"),
                deny_imports=(gate.DenyRule("core", "services", "no upward import"),),
            )
            report = gate.audit_repository(root, cfg)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["counts"], {"ERROR": 0, "HIGH": 0, "WARN": 0})
            self.assertEqual(report["metrics"]["scanned_files"], 3)

    def test_rh001_line_limits_warn_and_high(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_text(root / "warn_mod.py", "\n".join(f"x_{i} = {i}" for i in range(15)) + "\n")
            _write_text(root / "high_mod.py", "\n".join(f"y_{i} = {i}" for i in range(35)) + "\n")
            cfg = gate.ArchConfig(soft_lines=10, max_lines=25, max_imports=8)
            report = gate.audit_repository(root, cfg)
            rules = {(f["file"], f["rule"], f["severity"]) for f in report["findings"]}
            self.assertIn(("warn_mod.py", "RH001", "WARN"), rules)
            self.assertIn(("high_mod.py", "RH001", "HIGH"), rules)
            self.assertEqual(report["status"], "FAIL")

    def test_rh002_high_fan_in_and_facade_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            imps = "\n".join(f"import m{i}" for i in range(10)) + "\n"
            _write_text(root / "leaf.py", imps)
            _write_text(root / "pkg" / "Imports.lean", "\n".join(f"import Mod.A{i}" for i in range(12)) + "\n")
            cfg = gate.ArchConfig(max_imports=4)
            report = gate.audit_repository(root, cfg)
            rh002_files = {f["file"] for f in report["findings"] if f["rule"] == "RH002"}
            self.assertIn("leaf.py", rh002_files)
            self.assertNotIn("pkg/Imports.lean", rh002_files)

    def test_rh003_and_rh004_escape_hatches_and_wildcards(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_text(
                root / "bad.py",
                "from math import *\n"
                "def stub():\n"
                "    # TODO: finish later\n"
                "    raise NotImplementedError('later')\n"
                "def dyn(s):\n"
                "    return eval(s)  # type: ignore\n",
            )
            _write_text(root / "bad_proof.lean", "import Mathlib\ntheorem fake : True := by sorry\n")
            report = gate.audit_repository(root, gate.ArchConfig())
            by_rule = {f["rule"] for f in report["findings"]}
            self.assertIn("RH003", by_rule)
            self.assertIn("RH004", by_rule)
            self.assertTrue(
                any(f["file"] == "bad_proof.lean" and f["rule"] == "RH003" for f in report["findings"])
            )

    def test_rh005_layer_and_deny_rules_and_rh006_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_text(root / "core" / "a.py", "import services.b\n")
            _write_text(root / "services" / "b.py", "import core.a\n")
            cfg = gate.ArchConfig(
                layers=("core", "services"),
                deny_imports=(gate.DenyRule("core", "services", "BuildAid deny"),),
            )
            report = gate.audit_repository(root, cfg)
            rules = {f["rule"] for f in report["findings"]}
            self.assertIn("RH005", rules)
            self.assertIn("RH006", rules)
            self.assertEqual(report["metrics"]["cycles_count"], 1)

    def test_rh007_freeze_and_verify_challenge_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            contract = root / "contracts" / "challenge.py"
            _write_text(contract, "EXPECTED = 42\n")
            manifest = root / ".rh-challenge.json"

            buf_f = io.StringIO()
            with redirect_stdout(buf_f):
                rc_freeze = gate.main(
                    ["freeze-challenge", str(root), "--files", "contracts/challenge.py", "-o", str(manifest), "--json"]
                )
            self.assertEqual(rc_freeze, 0)

            buf_ok = io.StringIO()
            with redirect_stdout(buf_ok):
                rc_ok = gate.main(["verify-challenge", str(root), "--manifest", str(manifest), "--json"])
            self.assertEqual(rc_ok, 0)

            _write_text(contract, "EXPECTED = 999\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc_tamper = gate.main(["verify-challenge", str(root), "--manifest", str(manifest), "--json"])
            self.assertEqual(rc_tamper, 1)
            payload = gate.parse_strict_json_text(buf.getvalue())
            self.assertEqual(payload["status"], "FAIL")
            self.assertEqual(payload["mismatched_files"], 1)

    def test_strict_json_rejects_duplicate_keys_and_nan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dup = root / "dup.json"
            _write_text(dup, '{"a": 1, "a": 2}')
            with self.assertRaises(gate.GateInputError):
                gate.load_strict_json(dup)

            nan_f = root / "nan.json"
            _write_text(nan_f, '{"x": NaN}')
            with self.assertRaises(gate.GateInputError):
                gate.load_strict_json(nan_f)

    def test_path_escape_and_windows_reserved_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(gate.GateInputError):
                gate.freeze_challenge(root, ["../outside.py"], root / "m.json")
            with self.assertRaises(gate.GateInputError):
                gate.freeze_challenge(root, ["CON.py"], root / "m.json")

    def test_cli_init_config_and_audit_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_text(root / "core" / "ok.py", "def f(x: int) -> int:\n    return x\n")
            buf_init = io.StringIO()
            with redirect_stdout(buf_init):
                rc_init = gate.main(["init-config", str(root), "--json"])
            self.assertEqual(rc_init, 0)
            self.assertTrue((root / ".rh-arch.json").is_file())

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc_audit = gate.main(["audit", str(root), "--json"])
            self.assertEqual(rc_audit, 0)
            rep = gate.parse_strict_json_text(buf.getvalue())
            self.assertEqual(rep["status"], "PASS")

    def test_syntax_error_exits_with_code_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_text(root / "broken.py", "def bad(:\n    pass\n")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = gate.main(["audit", str(root), "--json"])
            self.assertEqual(rc, 2)
            rep = gate.parse_strict_json_text(buf.getvalue())
            self.assertEqual(rep["counts"]["ERROR"], 1)


if __name__ == "__main__":
    unittest.main()
