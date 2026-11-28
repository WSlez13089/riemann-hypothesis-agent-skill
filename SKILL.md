---
name: claude-rh-lean-architecture
description: Large-scale AI coding agent architecture protocol and zero-dependency static gate (RH001-RH007) distilled from the 17.37M-line Claude x Levent Alpoge Riemann Hypothesis Lean 4 repository (leanprover-community/riemann-hypothesis). Use to enforce micro-module boundaries, freeze immutable SHA256 acceptance contracts, declare bottom-up dependency layers and BuildAid-style deny-lists, block escape hatches and dependency cycles, and run deterministic pre-delivery verification.
---

**English** | [简体中文](SKILL_ZH.md)

# Claude × RH Large-Scale Agent Engineering Protocol (`claude-rh-lean-architecture`)

> **Provenance**: Quantitative baselines and engineering laws in this skill are distilled directly from a local snapshot of `leanprover-community/riemann-hypothesis` (published Nov 20, 2026 by Levent Alpöge × an internal frontier version of Claude: `175,187` `.lean` files, `17,374,215` comment-free lines of code, and `818,755` theorems). See the [Empirical Archaeology Report](references/empirical-archaeology.md) for full stratified sampling methodology and boundaries.

- **Zero-dependency static gate**: [`scripts/rh_arch_gate.py`](scripts/rh_arch_gate.py) (pure Python 3.12+ standard library; never imports or executes target code)
- **Invocation**: `python scripts/rh_arch_gate.py <subcommand>` (or `rh-arch-gate <subcommand>` when installed via `uv` / `pipx` / `pip`)

## Honest Boundaries (What Transfers vs. What Does Not)

- **Transferable structural skeleton**: Extreme micro-module granularity, zero-trust target isolation (`Challenge.lean` + `comparator.json`), declaration/facade/implementation splits (`*Imports.lean`), retrieval and import deny-lists (`BuildAid`), zero escape hatches, deterministic generators instead of manual copy-paste, and content-addressed verification.
- **Not reproducible by prompts alone**: Frontier base-model mathematical intuition, human expert steering, and hundreds of GBs of RAM driving concurrent compiler-kernel proof search. This skill pushes existing coding agents as close to that ceiling as possible by **front-loading deterministic structural gates**.

---

## The 7 Iron Laws (`RH-01` – `RH-07`)

| ID | Law | RH Repository Evidence | Mandatory Engineering Rule |
| --- | --- | --- | --- |
| **RH-01** | **Extreme Micro-Modules & Low Fan-In** | `Development/` (141,928 files) median is **41 lines** (repo sample P50 = 82); direct imports P50 = **3** (P90 = 7) | Default soft cap **120 non-blank lines**, hard cap **300 lines**; direct imports **≤ 8** (tune via `.rh-arch.json` or CLI flags for legacy repos). Never let agents grow 1,000-line monoliths |
| **RH-02** | **Zero-Trust Target Isolation** | `Challenge.lean` imports only stdlib to lock 5 contracts; `Main.lean` is a 12-line glue file; `comparator.json` adjudicates independently | Freeze read-only interfaces/acceptance tests into a SHA256 manifest before coding; forbid modifying frozen targets during implementation; verify independently before delivery |
| **RH-03** | **Declaration / Facade / Impl Split** | `418` `*Imports.lean` facades + `Definitions`/`Statement` separated from `Proofs`, holding leaf fan-in near 3 | Keep public types/contracts in standalone files; expose thin package facades (`facade`/`barrel`); forbid reaching across packages into private internals |
| **RH-04** | **Layer Boundaries & Retrieval Blacklists** | `BuildAid/D1..D5.lean` adds unrelated high-level namespaces to `nameDenyListExt` to curb retrieval noise | Declare bottom-up `layers` and `deny_imports` in `.rh-arch.json` to block reverse imports and hallucinated cross-layer references |
| **RH-05** | **Zero Implicit Magic & Escape Hatches** | `lakefile.toml` disables `autoImplicit`; `local`/`scoped` isolate notation; `0` `sorry/admit/axiom/unsafe` | Ban `import *`, dynamic `eval`/`exec`, unjustified `# type: ignore`, skipped tests, and placeholder stubs (`NotImplementedError`, `TODO`, `sorry`) |
| **RH-06** | **Generate Regular Variants** | `CutCptCopy.lean` (91 lines) traverses the dependency closure to derive variants and passes them through the kernel | When `> 3` structurally isomorphic blocks appear, forbid manual agent copy-pasting; write a deterministic generator validated by compiler + tests |
| **RH-07** | **Deterministic Single Tasks & Content Addressing** | `CACHE.md` hashes source + deps, checks SHA256 per artifact, and passes `-j1` for sub-task determinism | Use module-level parallelism with deterministic single tasks; never accept stale or unverified caches as proof of completion (`UNVERIFIED` until re-run) |

---

## Standard 4-Stage Workflow

### Stage 0: Freeze Immutable Acceptance Targets (Before Coding)
Write your target contracts (interfaces, invariants, or acceptance tests) first and lock their SHA256 hashes before implementation begins so an agent cannot silently weaken assertions to pass checks:

```bash
rh-arch-gate freeze-challenge <repo_dir> --files tests/test_contract.py src/contracts.py -o .rh-challenge.json --json
```

### Stage 1: Declare Layers & Deny-Lists (Before New Work or Refactoring)
Generate `.rh-arch.json` to define bottom-up `layers` (later layers may depend on earlier ones, never the reverse) and `BuildAid`-style `deny_imports`:

```bash
rh-arch-gate init-config <repo_dir> -o <repo_dir>/.rh-arch.json
```

Example `.rh-arch.json`:
```json
{
  "schema_version": 1,
  "thresholds": { "soft_lines": 120, "max_lines": 300, "max_imports": 8 },
  "layers": ["contracts", "core", "services", "adapters", "entrypoints"],
  "deny_imports": [
    { "from_prefix": "core", "forbid_prefix": "services", "reason": "Core must not depend upward on services" },
    { "from_prefix": "services", "forbid_prefix": "experimental", "reason": "BuildAid-style retrieval/dependency isolation" }
  ],
  "challenge_manifest": ".rh-challenge.json"
}
```

> **Tip for existing repositories**: Start without fighting existing file sizes by tuning `thresholds` in `.rh-arch.json` (for example `soft_lines: 250, max_lines: 300, max_imports: 10`, as used in this repo's own [`scripts/.rh-arch.json`](scripts/.rh-arch.json)) or passing `--soft-lines` / `--max-lines` / `--max-imports`, while keeping `RH003`–`RH007` strict from day one.

### Stage 2: Micro-Module Iteration & Gate Checks (After Every Change)
Run the static gate after each small module edit to inspect size, fan-in, escape hatches, implicit magic, layer violations, and Tarjan SCC dependency cycles:

```bash
rh-arch-gate audit <repo_dir> --config <repo_dir>/.rh-arch.json --json
# Strict mode (fail on WARN too, excluding test/build directories as needed)
rh-arch-gate audit <repo_dir> --config <repo_dir>/.rh-arch.json --strict --exclude "tests/*" --json
```

### Stage 3: Zero-Trust Adjudication (Before Delivery / Merge)
Before finalizing, independently verify: (1) frozen challenge hashes are untouched; (2) architectural audit has zero blocking findings; (3) targeted tests/type-checks were actually executed and passed:

```bash
rh-arch-gate verify-challenge <repo_dir> --manifest <repo_dir>/.rh-challenge.json --json
rh-arch-gate audit <repo_dir> --config <repo_dir>/.rh-arch.json --manifest <repo_dir>/.rh-challenge.json --json
```

---

## Rule Codes, Scanner Scope & Exit Codes

| Code | Severity | What It Detects | Remediation |
| --- | --- | --- | --- |
| `RH001` | WARN / HIGH | Non-empty lines exceed `soft_lines` (default `120`) or `max_lines` (default `300`) | Split by responsibility into thin declarations (`contracts`/`types`) + focused sub-modules |
| `RH002` | WARN / HIGH | Direct imports exceed `max_imports` (default `8`; facade/barrel files allow higher fan-out) | Introduce a sub-package facade or trim cross-module coupling |
| `RH003` | HIGH | Escape hatches & stubs: `NotImplementedError`, `TODO`/`FIXME`, `pytest.skip`, `sorry`/`admit`/`axiom`/`unsafe` | Complete real implementation/proofs, or track explicit waivers outside the gate |
| `RH004` | HIGH / WARN | Implicit magic & global pollution: `import *`, `eval`/`exec`, bare `global`, unjustified `# type: ignore` | Replace with explicit named imports, local state, and proper types |
| `RH005` | HIGH | Reverse layer import or `deny_imports` violation (`BuildAid` isolation breach) | Remove upward dependency or invert through a shared lower `contracts` layer |
| `RH006` | HIGH | Strongly connected dependency cycle (Tarjan SCC, size `≥ 2`) | Extract shared contracts to break the cycle and restore a strict DAG |
| `RH007` | HIGH | Frozen challenge target file missing, modified, or replaced with a symlink | Restore the trusted challenge file, or intentionally re-run `freeze-challenge` with approval |
| `PARSE001` | ERROR | Unreadable file, encoding error, oversized file (`> 2 MiB`), symlink traversal, or syntax error | Fix source file encoding, path safety, or syntax |

- **Scanner precision**: Python files are parsed using Python's standard-library `ast`; Lean, TypeScript, JavaScript, Rust, and Go use lightweight zero-dependency lexical scanners so the gate remains self-contained and build-free.
- **Exit codes**: `0` = PASS (no `HIGH` or `ERROR`; and no `WARN` under `--strict`); `1` = `HIGH` findings, `RH007` mismatch, or `WARN` under `--strict`; `2` = CLI argument, config, or `PARSE001` input/parse error (takes precedence over `1`).
