**English** | [简体中文](README.md)

# `riemann-hypothesis-agent-skill`
### Distilled Engineering Rules & Zero-Dependency Static Gate from the 17.37M-Line Riemann Hypothesis Lean 4 Repo

> **We sampled 2,578 files from the 17.37M-line Claude × Levent Alpöge Riemann Hypothesis Lean 4 repository (`leanprover-community/riemann-hypothesis`) and distilled its anti-collapse engineering skeleton into a plug-and-play `SKILL.md` + zero-dependency static architecture gate.**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](#quick-start)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(stdlib%20only)-brightgreen.svg)](#quick-start)
[![Agent Skill](https://img.shields.io/badge/Agent-Skill%20%2B%20CLI%20Gate-orange.svg)](#option-1-use-as-an-agent-skill-recommended)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why This Exists

On November 20, 2026, Anthropic mathematician Levent Alpöge and an internal frontier version of Claude published a formal Lean 4 proof of the Riemann Hypothesis & GRH (`leanprover-community/riemann-hypothesis`):
**175,187 source files, 17,374,215 lines of code, 0 comments, and 818,755 theorems.**

Most commentary stops at *"AI is great at math."* But if you inspect the codebase itself, it didn't survive 17 million lines by magic—it survived because of ruthless **anti-collapse engineering discipline**:
- Across the 141,928 core proof files (`Development/`), the **median file length (P50) is just 41 lines**, with a **median of 3 imports per file**;
- Acceptance targets (`Challenge.lean` + `comparator.json`) are strictly isolated from implementation so **criteria can never be silently weakened during iteration**;
- `BuildAid` explicitly blocks unrelated high-level namespaces (`nameDenyListExt`) to **prevent context retrieval noise and hallucinated cross-layer imports**;
- Static checks enforce **zero implicit magic and zero escape hatches** (no `sorry`/`admit`/`axiom`/`unsafe`, no wildcard imports).

Using a fixed-seed stratified sample (`N = 2,578`) across all 10 top-level directories, we distilled the transferable engineering skeleton into two artifacts:
1. **An Agent Protocol ([`SKILL.md`](SKILL.md))**: Guides Claude Code / Cursor / Codex / Antigravity to lock acceptance targets first, declare strict layers + deny-lists, and iterate in micro-modules.
2. **A Standalone Static Gate ([`scripts/rh_arch_gate.py`](scripts/rh_arch_gate.py))**: Pure Python 3.12+ stdlib, zero external dependencies, supporting Python / Lean / TS / JS / Rust / Go.

---

## Quick Start

### Option 1: Use as an Agent Skill (Recommended)

Install via [`skills.sh`](https://skills.sh) / Vercel Skills CLI, or clone directly into your agent skills directory:

```bash
# Install with skills CLI
npx skills add WSlez13089/riemann-hypothesis-agent-skill

# Or clone into your project's .agents/skills/
git clone https://github.com/WSlez13089/riemann-hypothesis-agent-skill.git .agents/skills/claude-rh-lean-architecture
```

Once loaded, your AI coding agent follows a strict 4-stage loop: **Freeze immutable challenge targets → Declare layers & deny-lists → Iterate in micro-modules → Independent zero-trust verification**.

### Option 2: Use as a Standalone Static Gate CLI

No `pip install` needed—just **Python 3.12+**:

```bash
git clone https://github.com/WSlez13089/riemann-hypothesis-agent-skill.git
cd riemann-hypothesis-agent-skill

# 1. Initialize .rh-arch.json (layer order + BuildAid-style deny_imports)
python scripts/rh_arch_gate.py init-config /path/to/your-repo

# 2. Freeze immutable acceptance targets (SHA256 manifest, Challenge.lean style)
python scripts/rh_arch_gate.py freeze-challenge /path/to/your-repo \
  --files src/contracts.py tests/test_contract.py \
  -o .rh-challenge.json --json

# 3. Audit architecture after changes (file size, fan-in, escape hatches, cycles)
python scripts/rh_arch_gate.py audit /path/to/your-repo --json

# 4. Zero-trust verification before delivery (ensure targets were never tampered with)
python scripts/rh_arch_gate.py verify-challenge /path/to/your-repo --manifest .rh-challenge.json --json
```

Run the self-test suite:

```bash
python -W error -m unittest discover -s scripts -v
```

---

## The 7 Iron Laws (`RH-01` ~ `RH-07`)

| ID | Law | Empirical Finding in the RH Repo | Practical Rule in Your Repo |
| :--- | :--- | :--- | :--- |
| **RH-01** | **Extreme Micro-Modules & Low Fan-In** | `Development/` (141.9k files) P50 = **41 lines**; imports P50 = **3** | Soft cap **120 lines**, hard cap **300 lines**; direct imports **≤ 8** |
| **RH-02** | **Zero-Trust Target Isolation** | `Challenge.lean` imports only stdlib; `comparator.json` adjudicates independently | Freeze read-only contracts/tests into a SHA256 manifest before coding; verify before delivery |
| **RH-03** | **Declaration / Facade / Impl Split** | 418 `*Imports.lean` facades; `Statement` separated from `Proofs` | Keep shared types separate; expose thin package facades; forbid reaching into private internals |
| **RH-04** | **Layer Boundaries & Retrieval Blacklists** | `BuildAid/D1..D5.lean` adds unrelated namespaces to `nameDenyListExt` | Declare bottom-up `layers` and `deny_imports` in `.rh-arch.json` |
| **RH-05** | **Zero Implicit Magic & Escape Hatches** | `autoImplicit` disabled; 0 `sorry/admit/axiom/unsafe` across 17.37M lines | Ban `import *`, `eval/exec`, and stubs (`NotImplementedError`, `TODO`, `pytest.skip`) |
| **RH-06** | **Generate Regular Variants** | `CutCptCopy.lean` (91 lines) derives variants deterministically | Replace >3 isomorphic copy-pasted blocks with a deterministic generator + full verification |
| **RH-07** | **Deterministic Tasks & Content Addressing** | `CACHE.md` hashes source + deps; SHA256 verified; `-j1` determinism | Module-level parallelism, deterministic runs, never trust unverified stale caches |

---

## Gate Rule Codes & Sample Output

`rh_arch_gate.py` statically inspects source files without importing or executing target code:

| Code | Severity | What It Catches |
| :--- | :--- | :--- |
| `RH001` | WARN / HIGH | Non-empty lines exceed `120` (warn) or `300` (block) |
| `RH002` | WARN / HIGH | Direct imports exceed `8` (facade files configurable) |
| `RH003` | HIGH | Escape hatches & stubs: `NotImplementedError`, `TODO`/`FIXME`, `pytest.skip`, `sorry`/`admit`/`unsafe` |
| `RH004` | HIGH / WARN | Implicit magic: `import *`, `eval`/`exec`, bare `global`, unjustified `# type: ignore` |
| `RH005` | HIGH | Upward/reverse layer import or `deny_imports` hit |
| `RH006` | HIGH | Strongly connected dependency cycle (Tarjan SCC) |
| `RH007` | HIGH | Frozen challenge file missing, modified, or replaced by a symlink |

Real self-audit output on this repo's `scripts/` directory:

```json
{
  "schema_version": 1,
  "tool": "rh-arch-gate",
  "status": "PASS",
  "metrics": {
    "scanned_files": 7,
    "lines_p50": 160,
    "lines_max": 249,
    "imports_p50": 4,
    "cycles_count": 0
  },
  "counts": { "ERROR": 0, "HIGH": 0, "WARN": 0 }
}
```

---

## Honest Boundaries

- **What transfers cleanly:** Micro-module discipline, zero-trust target isolation, explicit layer/deny-list boundaries, zero escape hatches, and deterministic verification loops.
- **What cannot be distilled into a skill alone:** Frontier base-model mathematical intuition, human expert steering, and hundreds of GBs of Lean kernel proof-search compute.

---

## Authors

- **Exiled-by-Lady-Claude** ([@WSlez13089](https://github.com/WSlez13089)) — Concept, repository archaeology, and engineering integration
- **Gemini (Antigravity)** — Stratified empirical analysis, protocol distillation, and static gate co-authoring

## License

[MIT](LICENSE)
