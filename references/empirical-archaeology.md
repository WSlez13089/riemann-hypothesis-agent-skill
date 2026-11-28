# Empirical Archaeology Report: Distilling Large-Scale Agent Architecture from Claude × Alpöge's Riemann Hypothesis Lean 4 Repository

**English** | [简体中文](empirical-archaeology.zh.md)

This report documents direct source sampling and configuration auditing performed on `2026-11-25` against a complete snapshot of `leanprover-community/riemann-hypothesis` (corresponding to the `2026-11-20` publication by Levent Alpöge and an internal frontier version of Claude formalizing RH and GRH).

---

## 1. Repository Scale & Baseline Facts

- **Pinned toolchain**: `leanprover/lean4:v4.33.1` + official Mathlib tag `v4.33.1` (`0df444a360ea`).
- **Repository totals** (from `verification/NOTES.md` and full-tree file inventory):
  - Submitted `.lean` files: **175,187** (**175,195** including verification wrappers)
  - Total source size: **982.83 MB** (`1,030,531,854` bytes)
  - Total lines: **17,374,215 lines** (`15,531,759` non-blank lines, **0 comments**)
  - Declarations: **818,755** `theorem`/`lemma` declarations + **242,067** `def`/`structure`/`class`/`instance`/`inductive` declarations
  - Build & verification footprint: ~7–10 hours on a 48-core / 503 GB RAM server; exported `solution.export` single file is `61.57 GB` (requiring `150–163 GB` RAM to replay/verify).

## 2. Stratified Random Sampling (`N = 2,578`, Fixed Seed `20261125`)

We drew a fixed-seed stratified random sample across all 10 top-level directories (capping at 400 files per directory, or taking all files when fewer than 400 exist):

| Top-Level Directory | Total Files | Sample P50 Lines | Sample P90 Lines | Sample Max Lines | Architectural Role |
| --- | ---: | ---: | ---: | ---: | --- |
| `Development` | 141,928 | **41** | 212 | 665 | Core atomic proofs & implementations (81% of all files) |
| `Formalism` | 18,254 | 115 | 368 | 6,929 | Core framework, Fourier/geometric formalisms, bridges |
| `GroundTheory` | 8,507 | 101 | 306 | 1,004 | Foundations (local/global fields, cohomology, etc.) |
| `ReciprocityTheory` | 3,845 | 128 | 287 | 707 | Reciprocity laws, reductive groups, abelian varieties |
| `CompanionTheory` | 2,027 | 64 | 242 | 565 | Companion theory & auxiliary bounds |
| `PositivityTheory` | 449 | 88 | 283 | 700 | Positivity theory |
| `Lemmata` | 167 | **40** | 92 | 364 | High-reuse short lemmata |
| `BuildAid` | 5 | **4** | 4 | 4 | **Retrieval / suggestion blacklist controller** |
| `Supplements` | 3 | **4** | 16 | 16 | **Thin aggregation glue** |
| Top-level root (`ROOT`) | 3 | 16 | 27 | 27 | `Challenge.lean` / `Statements.lean` / `Main.lean` |

### Key Quantile Findings
- **Sample file length**: `P10=13`, `P25=31`, **`P50=82`**, `P75=167`, `P90=274`, `P95=353`, `P99=608`.
- **Direct `import` count per file**: **`P50=3`**, `P90=7`, `P99=18`.
- **Most frequent filename suffixes**: `*Imports.lean` (**418 files** across the repo), followed by `Bound`, `St` (Statement), `Eq`, `Defs`, `Lift`, `Map`, `Bridge`, and `Iso`.
- **Scoping & local decomposition**: Custom notation across the repository uses `local` or `scoped` (`1,626` occurrences in the sample) with zero global symbol pollution; local intermediate steps (`have`) appear `41,459` times across the `2,578` sampled files.

---

## 3. Five Micro-Level Architectural Evidences

### Evidence A: Zero-Trust Target Isolation (`Challenge.lean` + `Main.lean` + `comparator.json`)
- `src/Challenge.lean` (27 lines) imports only `Mathlib` and declares the 5 target theorems independently (`by sorry` placeholders).
- `src/Main.lean` (12 lines) imports only `Statements` and `Supplements.Kernels.MainTheoremsAll`, wiring internal proofs line-by-line to the target signatures.
- `comparator.json` restricts allowed axioms to just 3 standard axioms (`propext`, `Quot.sound`, `Classical.choice`) and verifies inside a network-isolated, read-only container with independent kernels (`Lean 4.36` + `leanchecker-paranoid` + `nanoda`).
- **Transferable rule**: High-stakes AI coding workflows must separate acceptance contracts/tests from implementation and freeze them via SHA256 manifests so agents cannot silently weaken tests.

### Evidence B: Retrieval Noise Blacklists (`src/BuildAid/D1.lean` – `D5.lean`)
Five structurally identical 4-line files:
```lean
run_cmd Lean.modifyEnv fun env => Lean.LibrarySuggestions.nameDenyListExt.addEntry env "CompanionTheory"
```
Each removes a high-level namespace (`CompanionTheory`, `CrystallineSemistableComparison`, `GlobalTheory`, `PositivityTheory`, `UpperTheory`) from automatic library suggestion/retrieval.
- **Transferable rule**: Beyond tens of thousands of lines, retrieval noise causes agent hallucinations and reverse-layer imports. Maintain explicit `layers` and `deny_imports` in `.rh-arch.json`.

### Evidence C: 418 `*Imports.lean` Facades & Declaration / Impl Splits
For instance, under `CompanionTheory/AutomorphicTheory/PieriRules/PieriDegreeBounds/`, `*Statement.lean` (pure declarations), `Imports.lean` (dependency facade), `Definitions/`, and `Proofs/` are separated cleanly so leaf modules stay around 3–4 imports.
- **Transferable rule**: Separating type contracts, package re-export facades, and core implementations slashes both context window load per edit and incremental test/build blast radius.

### Evidence D: Metaprogramming Variant Derivation (`CutCptCopy.lean`, 91 lines)
When a dependency chain of declarations needed compactly supported (`Cpt`) variants, the authors wrote a 91-line deterministic metaprogram (`toCopy` / `subst` / `copyAll`) instead of having an LLM copy-paste dozens of files:
1. Traverse the constant dependency closure (`tainted`, `order`);
2. Rewrite expression trees via explicit `special` mappings + `suffixed` rules;
3. Inject via `addDecl` and verify every generated theorem in the kernel.
- **Transferable rule**: Replace `≥ 3` isomorphic boilerplate variants with a small deterministic generator validated by compiler/tests rather than manual agent copy-pasting.

### Evidence E: Strict Config Guardrails & Content-Addressed Caching (`lakefile.toml` + `verification/CACHE.md`)
- `lakefile.toml` enforces `autoImplicit = false` and `relaxedAutoImplicit = false` (eliminating typo-created implicit variables) and caps resource usage on heavy sub-libraries (e.g., `synthInstance.maxHeartbeats = 400000` on `GroundTheoryFields`).
- `CACHE.md` documents content-addressed artifact caching with per-file SHA256 verification before restoration, offline fallback compilation on mismatch, `-j1` determinism per sub-task (parallelism across independent modules only), and an explicit warning that community cache cannot replace independent verification.

---

## 4. Honest Limits (Avoiding Over-Optimistic Extrapolation)

1. **Missing search trajectory**: The final source snapshot does not show rejected proof branches from the 41-day run or human mathematical steering (such as switching to Stepanov's method + `sqrt(X)`-length Theta lift chains).
2. **Formal kernel advantage**: Lean 4 provides 100% logical soundness checking; general software engineering (Python/TS/Go) lacks an equivalent proof kernel and therefore relies on combining **type checking + contract/property tests + static security gates** to approximate deterministic adjudication.
3. **Compute feedback differences**: Hundreds of GBs of RAM enable rapid parallel proof-search backtracking; on a developer workstation, keeping modules small (`≤ 120` lines default, or project-tuned thresholds) + incremental unit tests gives a fast local feedback loop.
