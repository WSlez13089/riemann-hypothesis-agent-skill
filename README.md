**简体中文** | [English](README_EN.md)

# `riemann-hypothesis-agent-skill`
### 黎曼猜想 1737 万行 Lean 4 仓库蒸馏 · AI Agent 工程架构 Skill 与零依赖静态门禁

> **把 1737 万行黎曼猜想 Lean 4 证明仓库的“不塌方工程骨架”，蒸馏成任何 AI Coding Agent 都能直接挂载的 `SKILL.md` + 零依赖静态门禁。**
> *Distilled from the 17.37M-line Riemann Hypothesis Lean 4 repository into a plug-and-play Agent Skill & zero-dependency static architecture gate.*

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](#快速开始)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20(stdlib%20only)-brightgreen.svg)](#快速开始)
[![Agent Skill](https://img.shields.io/badge/Agent-Skill%20%2B%20CLI%20Gate-orange.svg)](#作为-agent-skill-使用)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 为什么做这个项目？

2026 年 11 月 20 日，Anthropic 数学家 Levent Alpöge 与内部版 Claude 公开了黎曼猜想 / GRH 的 Lean 4 形式化证明仓库（`leanprover-community/riemann-hypothesis`）：
**`175,187` 个源文件、`17,374,215` 行代码、0 行注释、`818,755` 条定理**。

大多数人看到这个新闻只会感叹“AI 数学好强”，但如果你把仓库拉下来做微观代码考古，会发现它能写到 1700 万行还不散架，靠的不是玄学，而是一套极其冷酷的**工程防塌方纪律**：
- 主体 14 万个文件里，**中位数（P50）只有 41 行**，单文件 `import` **P50 只有 3 个**；
- 验收靶子（`Challenge.lean` + `comparator.json`）与实现彻底物理隔离，**绝不允许在迭代中偷偷降标准**；
- 主动用 `BuildAid` 黑名单屏蔽无关高层命名空间，**防止上下文检索污染引发 Agent 幻觉引用**；
- 静态门禁把隐式魔法与逃生舱（`sorry`/`admit`、`import *`、占位桩）**全部归零**。

我们以固定随机种子对全库 10 个顶层目录做了分层抽样（`N = 2,578`），把这套可迁移的工程骨架蒸馏成了两样东西：
1. **一本给 AI 看的行动铁律**（[`SKILL.md`](SKILL.md)）：让 Claude Code / Cursor / Codex / Antigravity 在写大型项目时先锁靶子、再分层、只写微模块；
2. **一把人类也能直接跑的静态门禁**（[`scripts/rh_arch_gate.py`](scripts/rh_arch_gate.py)）：纯 Python 标准库、零第三方依赖，支持 Python / Lean / TS / JS / Rust / Go。

---

## 快速开始

### 方式一：作为 Agent Skill 使用（推荐）

把本仓库放进你的 Agent 技能目录即可按标准 `SKILL.md` 自动发现与按需加载：

```bash
# 使用 skills CLI 一键安装
npx skills add WSlez13089/riemann-hypothesis-agent-skill

# 或手动克隆到项目本地 .agents/skills/
git clone https://github.com/WSlez13089/riemann-hypothesis-agent-skill.git .agents/skills/claude-rh-lean-architecture
```

> 适用于支持 `SKILL.md` 规范的 AI 编程助手（Claude Code、Antigravity、Codex、Cursor 等）。加载后，Agent 在动工前会自动引导你：**冻结不可变验收契约 → 声明分层与黑名单 → 按微模块迭代并自检**。

### 方式二：作为独立静态门禁 CLI 使用

无需 `pip install`，只要本机有 **Python 3.12+** 就能直接跑：

```bash
git clone https://github.com/WSlez13089/riemann-hypothesis-agent-skill.git
cd riemann-hypothesis-agent-skill

# 1. 在你的目标项目里生成 .rh-arch.json（分层规则 + 屏蔽黑名单）
python scripts/rh_arch_gate.py init-config /path/to/your-repo

# 2. 编码前先冻结“不可变验收靶子”（把核心契约/测试锁进 SHA256 清单）
python scripts/rh_arch_gate.py freeze-challenge /path/to/your-repo \
  --files src/contracts.py tests/test_contract.py \
  -o .rh-challenge.json --json

# 3. 每次改完代码跑一次架构门禁（检查体积、扇入、逃生舱、越界、循环依赖）
python scripts/rh_arch_gate.py audit /path/to/your-repo --json

# 4. 交付前做零信任验真（确认 AI 没有在迭代中偷偷篡改验收测试或契约）
python scripts/rh_arch_gate.py verify-challenge /path/to/your-repo --manifest .rh-challenge.json --json
```

运行门禁自身单元测试：

```bash
python -W error -m unittest discover -s scripts -v
```

---

## 核心内容：从 1737 万行仓库提炼的七大铁律

| 编号 | 铁律 | 黎曼仓库里的实证数据 | 落地到你的项目里是什么 |
| :--- | :--- | :--- | :--- |
| **RH-01** | **极端微模块与低扇入** | `Development` 14.19 万文件 P50 仅 **41 行**；单文件 `import` P50 仅 **3 个** | 单文件软上限 **120 行**、硬上限 **300 行**；直接导入 **≤ 8**，禁止千行巨石文件 |
| **RH-02** | **零信任靶子隔离** | `Challenge.lean` 仅依赖标准库锁死契约，`comparator.json` 独立裁决 | 编码前冻结只读接口/测试并生成 SHA256 清单，交付前独立验真 |
| **RH-03** | **声明 / 门面 / 实现分离** | 全库 418 个 `*Imports.lean` 门面，`Statement` 与 `Proofs` 分离 | 公共类型单独成文件，子包只暴露薄门面，禁止跨包直插私有细节 |
| **RH-04** | **分层边界与检索黑名单** | `BuildAid/D1..D5.lean` 主动把无关高层命名空间写入 `nameDenyListExt` | 在 `.rh-arch.json` 显式声明层序 `layers` 与 `deny_imports` 黑名单 |
| **RH-05** | **零隐式魔法与零逃生舱** | 禁用 `autoImplicit`，全库静态扫描 0 `sorry/admit/axiom/unsafe` | 禁用 `import *`、`eval/exec`、占位桩（`NotImplementedError`/`TODO`/`pytest.skip`） |
| **RH-06** | **规律变体改用生成器** | `CutCptCopy.lean`（91 行）自动派生变体声明，拒绝手工复制粘贴 | 超过 3 处同构样板代码改用确定性生成脚本 + 全量校验 |
| **RH-07** | **确定性单任务与内容寻址** | `CACHE.md` 按源码+依赖哈希缓存、SHA256 逐件验真、子作业 `-j1` | 模块级并行、单任务确定性执行，不轻信过期缓存 |

---

## 门禁规则速查与输出示例

`rh_arch_gate.py` 会静态扫描代码库并输出结构化 JSON（不导入、不执行目标代码）：

| 规则码 | 级别 | 拦什么问题 |
| :--- | :--- | :--- |
| `RH001` | WARN / HIGH | 单文件非空行数超过 `120`（警告）或 `300`（阻断） |
| `RH002` | WARN / HIGH | 单文件直接导入超过 `8` 个（门面文件按配置豁免） |
| `RH003` | HIGH | 逃生舱与未完成桩：`NotImplementedError`、`TODO`/`FIXME`、`pytest.skip`、`sorry`/`admit`/`unsafe` |
| `RH004` | HIGH / WARN | 隐式魔法：`import *`、`eval`/`exec`、裸 `global`、无理由 `# type: ignore` |
| `RH005` | HIGH | 逆向跨层依赖或命中 `deny_imports` 黑名单 |
| `RH006` | HIGH | 模块间存在强连通循环依赖（Tarjan SCC 检测） |
| `RH007` | HIGH | 冻结靶子缺失、哈希被篡改或被替换为符号链接 |

对本项目自身 `scripts/` 目录执行自检的真实输出：

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

## 仓库结构

```text
riemann-hypothesis-agent-skill/
├── SKILL.md                          # Agent 行为协议（RH-01 ~ RH-07 四阶段工作流）
├── references/
│   └── empirical-archaeology.md      # N=2,578 分层抽样实证与微观代码考古报告
├── scripts/
│   ├── .rh-arch.json                 # 本工具自身使用的分层架构配置（DOGFOODING）
│   ├── rh_arch_gate.py               # CLI 入口（Layer 4）
│   ├── rh_gate_engine.py             # 审计与 Tarjan SCC 环路检测引擎（Layer 3）
│   ├── rh_gate_challenge.py          # 零信任靶子冻结与 SHA256 验真（Layer 2）
│   ├── rh_gate_config.py             # 配置加载与默认模板（Layer 2）
│   ├── rh_gate_scanners.py           # 多语言轻量静态扫描器（Layer 1）
│   ├── rh_gate_io.py                 # 跨平台安全路径与严格 JSON I/O（Layer 1）
│   ├── rh_gate_contracts.py          # 共享数据契约与常量（Layer 0，零内部依赖）
│   └── test_rh_arch_gate.py          # 离线确定性单元测试（10 项全覆盖）
├── LICENSE
└── README.md
```

---

## 诚实边界

- **能复现的**：微模块粒度纪律、零信任靶子隔离、分层与屏蔽边界、零逃生舱门禁、确定性验证闭环。
- **无法仅靠 Skill 复现的**：前沿基座模型本身的数学直觉、人类专家的方向纠偏，以及数百 GB 内存下由编译器内核驱动的高并发试错搜索算力。

---

## Authors

- **Exiled-by-Lady-Claude** ([@WSlez13089](https://github.com/WSlez13089)) — 发起构思、仓库考古提炼与工程化集成
- **Gemini (Antigravity)** — 实证抽样分析、协议梳理与静态门禁联合编写

## License

[MIT](LICENSE)
