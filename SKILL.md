---
name: claude-rh-lean-architecture
description: 提炼自 Anthropic 内部版 Claude 与 Levent Alpöge 2026-11-20 公布的黎曼猜想/GRH 1737 万行 Lean 4 形式化证明仓库（leanprover-community/riemann-hypothesis）的超大型 Agent 工程架构协议与静态门禁（RH001~RH007）。用于拆解超大型仓库、冻结不可变验收靶子、配置分层依赖与检索黑名单、拦截逃生舱与循环依赖，以及构建编译器/门禁驱动的高可靠 AI 编程流水线。
---

# Claude × RH 黎曼级超大型 Agent 工程协议 (`claude-rh-lean-architecture`)

> **溯源声明**：本技能的所有定量基线与工程铁律均直接反推自本地源码仓库 `leanprover-community/riemann-hypothesis`（2026-11-20 Levent Alpöge × Anthropic 内部版 Claude 公布的 RH/GRH Lean 4 形式化工程：175,187 个 `.lean` 文件、17,374,215 行无注释源码、818,755 条定理）。详细抽样实证与边界分析见 [实证考古报告](references/empirical-archaeology.md)。

- **零依赖门禁工具**：[rh_arch_gate.py](scripts/rh_arch_gate.py)（纯 Python 3.12+ 标准库，不导入、不执行目标代码）
- **运行方式**：`python scripts/rh_arch_gate.py <subcommand>`（若已加入 PATH，也可直接调用 `rh-arch-gate`）

## 诚实边界（先厘清能偷师什么、不能偷师什么）

- **能复现的（工程骨架）**：极端微模块粒度、零信任靶子隔离（Comparator 模式）、声明/门面/实现三层分离、检索与引用黑名单（`BuildAid` 模式）、零逃生舱门禁、确定性代码生成替代人工复制、内容寻址增量验证。
- **不可仅靠 Prompt 复现的（能力底座）**：前沿模型本身的数学直觉、人类专家方向纠偏、以及数百 GB 内存下由编译器内核驱动的高并发试错搜索树。本技能通过**把架构纪律与确定性门禁前置**，探索现有 Agent 在大型工程中的稳定性提升。尚未通过对照实验验证能力增益。

> 规则阈值是可调初始策略。哈希清单、配置和验证器需要受保护的可信基线；本地哈希不是访问控制。轻量扫描不能替代编译、测试及人工验收。

---

## 七大工程铁律（RH-01 ~ RH-07）

| 编号 | 铁律名称 | 黎曼仓库实证来源 | 强制落地要求 |
| --- | --- | --- | --- |
| **RH-01** | 极端微模块与低直接导入数 | `Development` 14.19 万文件 P50 仅 **41 行**（合并分层样本 P50=82 行）；单文件 `import` P50 仅 **3 个**（P90=7） | 单文件软上限 **120 行**、硬上限 **300 行**；单文件直接导入 **≤ 8**。禁止让 Agent 持续膨胀千行巨型文件 |
| **RH-02** | 零信任靶子隔离 | `Challenge.lean` 仅依赖标准库锁死 5 个契约；`Main.lean` 仅 12 行薄胶水对接；`comparator.json` 独立内核裁决 | 编码前先冻结只读接口/验收靶子并落盘 SHA256 清单；实现期间禁止修改靶子，交付前独立验真 |
| **RH-03** | 声明 / 门面 / 实现分离 | 全库 418 个 `*Imports.lean` 门面 + `Definitions`/`Statement` 与 `Proofs` 分离，将样本直接导入数中位数为 3 | 公共类型/协议单独成文件；子包对外只暴露薄门面（facade/barrel），实现文件不得跨包直插私有细节 |
| **RH-04** | 分层边界与检索黑名单 | `BuildAid/D1..D5.lean` 主动把无关高层命名空间写入 `nameDenyListExt`，防止自动检索污染上下文 | 在 `.rh-arch.json` 显式声明层序 `layers`（上层仅可依赖下层）及 `deny_imports` 黑名单，阻断跨层幻觉引用 |
| **RH-05** | 零隐式魔法与零逃生舱 | `lakefile.toml` 禁用 `autoImplicit`、`local/scoped` 隔离符号、静态扫描 0 `sorry/admit/axiom/unsafe` | 禁用通配符导入（`import *`）、动态 `eval/exec`、无证据跳过测试或占位桩（`NotImplementedError`/`TODO`/`sorry`） |
| **RH-06** | 规律变体改用生成器 | `CutCptCopy.lean`（91 行）遍历依赖闭包自动派生变体声明并交内核验真，拒绝手工复制粘贴 | 超过 3 处结构同构的样板/变体代码，禁止 Agent 逐份手抄；改为确定性生成脚本 + 编译器/测试全量校验 |
| **RH-07** | 确定性单任务与内容寻址 | `CACHE.md` 按源码+依赖哈希缓存、SHA256 逐件验真、子作业强制 `-j1` 确定性并发 | 模块级并行、单任务确定性执行；不信任过期/外部未验真缓存作为最终放行依据，未实测项必须标注 `UNVERIFIED` |

---

## 标准四阶段执行流

### Stage 0：冻结不可变验收靶子（编码前）
先把目标契约（接口定义、核心测试或验收规范）写入独立文件，并用门禁工具计算 SHA256 锁死，在可信基线不变的前提下检测 Agent 在迭代中“偷偷改测试/降标准”：

```powershell
rh-arch-gate freeze-challenge <repo_dir> --files tests/test_contract.py src/contracts.py -o .rh-challenge.json --json
```

### Stage 1：声明分层与屏蔽区（建仓或重构前）
生成 `.rh-arch.json`，明确自底向上的层序（列表靠后层可引用靠前层，反之违规）和检索/依赖黑名单：

```powershell
rh-arch-gate init-config <repo_dir> -o <repo_dir>\.rh-arch.json
```

配置示例（`.rh-arch.json`）：
```json
{
  "schema_version": 1,
  "thresholds": { "soft_lines": 120, "max_lines": 300, "max_imports": 8 },
  "layers": ["contracts", "core", "services", "adapters", "entrypoints"],
  "deny_imports": [
    { "from_prefix": "core", "forbid_prefix": "services", "reason": "底层核心禁止反向依赖业务层" },
    { "from_prefix": "services", "forbid_prefix": "experimental", "reason": "复刻 BuildAid 检索黑名单，屏蔽实验命名空间" }
  ],
  "challenge_manifest": ".rh-challenge.json"
}
```

### Stage 2：微模块迭代与静态门禁自检（每次改动后）
每完成一个微模块，先跑静态门禁检查体积、直接导入数、逃生舱、隐式污染、跨层依赖与循环依赖（SCC）：

```powershell
rh-arch-gate audit <repo_dir> --config <repo_dir>\.rh-arch.json --json
# 严格模式（警告也升级阻断，排除测试与构建目录）
rh-arch-gate audit <repo_dir> --config <repo_dir>\.rh-arch.json --strict --exclude "tests/*" --json
```

### Stage 3：零信任独立裁决（交付前）
交付前必须同时确认：（1）冻结靶子哈希一字未改；（2）架构门禁无高危项；（3）关联单测/类型检查独立实测通过。

```powershell
rh-arch-gate verify-challenge <repo_dir> --manifest <repo_dir>\.rh-challenge.json --json
rh-arch-gate audit <repo_dir> --config <repo_dir>\.rh-arch.json --manifest <repo_dir>\.rh-challenge.json --json
```

---

## 规则代码与退出码速查

| 规则码 | 严重度 | 检测内容 | 修复方向 |
| --- | --- | --- | --- |
| `RH001` | WARN / HIGH | 单文件非空行数超过 `soft_lines`(120) 或 `max_lines`(300) | 按单一职责拆分为 `statement/types` + 细粒度实现子模块 |
| `RH002` | WARN / HIGH | 单文件直接导入数超过 `max_imports`(8) | 引入子包门面（`facade`/`imports`）或削减跨模块耦合 |
| `RH003` | HIGH | 逃生舱与未完成桩：`NotImplementedError`、`TODO`/`FIXME`、`pytest.skip`、`sorry`/`admit`/`axiom`/`unsafe` | 补全真实实现与证明；确需例外须在评审记录中单独登记 |
| `RH004` | HIGH / WARN | 隐式魔法与全局污染：`import *`、`eval`/`exec`、裸 `global`、无理由 `# type: ignore` | 改为显式具名导入、局部作用域与完整类型标注 |
| `RH005` | HIGH | 分层越界或命中 `deny_imports` 黑名单（`BuildAid` 隔离失效） | 移除反向/跨界依赖，通过底层 `contracts` 契约倒置依赖 |
| `RH006` | HIGH | 模块间存在强连通循环依赖（Tarjan SCC，节点数 ≥ 2） | 抽出共享契约层打断环路，恢复严格 DAG |
| `RH007` | HIGH | 冻结靶子契约文件缺失、被篡改或被替换为符号链接 | 恢复受信任靶子基线；若确需变更契约，须人工批准后重新 `freeze-challenge` |
| `PARSE001` | ERROR | 读取/编码/超字节(2 MiB)/符号链接/语法解析错误 | 修复源文件编码、路径或语法问题 |

- **退出码**：`0` 全部通过（无 HIGH 与 ERROR）；`1` 存在 HIGH 违规、靶子验真失败或 `--strict` 下存在 WARN；`2` CLI 参数、配置文件或源文件解析错误（优先于 `1`）。
- **协同建议**：可与五维边界契约测试、仓库拓扑定位、安全静态审计等工程技能互补使用；本技能专攻**超大规模代码库的架构防塌方与零信任靶子验证**。
