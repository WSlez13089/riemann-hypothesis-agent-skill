# 实证考古报告：从 Claude × Alpöge 黎曼猜想 Lean 4 仓库反推超大型 Agent 工程范式

[English](empirical-archaeology.md) | **简体中文**

本报告基于 2026-11-25 对开源仓库 `leanprover-community/riemann-hypothesis` 完整快照（对应 2026-11-20 Levent Alpöge 与 Anthropic 内部前沿版 Claude 公布的 RH/GRH 形式化证明）的直接源码抽样与配置审计。

---

## 1. 仓库客观体量与基线数据

- **工具链锁定**：`leanprover/lean4:v4.33.1` + 官方 Mathlib tag `v4.33.1`（`0df444a360ea`）。
- **总规模**（来自 `verification/NOTES.md` 及本地全量统计）：
  - 原提交 `.lean` 文件数：**175,187**（含验证封装后共 **175,195**）
  - 源码总大小：**982.83 MB**（1,030,531,854 bytes）
  - 总行数：**17,374,215 行**（非空行 15,531,759 行，**0 行注释**）
  - 声明数量：**818,755** 个 `theorem`/`lemma` + **242,067** 个 `def`/`structure`/`class`/`instance`/`inductive`
  - 完整构建与验证开销：48 核 / 503 GB 内存服务器构建约 7–10 小时；导出 `solution.export` 单文件 61.57 GB（需 150–163 GB RAM 验真）。

## 2. 分层抽样实证（N = 2,578，固定随机种子 20261125）

我们对全部 10 个顶层目录执行分层随机抽样（每层至多 400 个文件，不足全采），实测统计如下：

| 顶层模块 | 总文件数 | 样本 P50 行数 | 样本 P90 行数 | 样本最大行数 | 架构角色 |
| --- | ---: | ---: | ---: | ---: | --- |
| `Development` | 141,928 | **41** | 212 | 665 | 主体原子证明与实现（占全库 81% 文件） |
| `Formalism` | 18,254 | 115 | 368 | 6,929 | 核心框架、傅里叶/几何形式化与关键桥接 |
| `GroundTheory` | 8,507 | 101 | 306 | 1,004 | 底层数学地基（局部/全局域、上同调等） |
| `ReciprocityTheory` | 3,845 | 128 | 287 | 707 | 互反律与约化群/阿贝尔簇基础 |
| `CompanionTheory` | 2,027 | 64 | 242 | 565 | 伴随理论与辅助界估计 |
| `PositivityTheory` | 449 | 88 | 283 | 700 | 正定性理论 |
| `Lemmata` | 167 | **40** | 92 | 364 | 高复用短引理集合 |
| `BuildAid` | 5 | **4** | 4 | 4 | **检索/建议黑名单控制器** |
| `Supplements` | 3 | **4** | 16 | 16 | **薄聚合胶水层** |
| 顶层入口 (`ROOT`) | 3 | 16 | 27 | 27 | `Challenge.lean` / `Statements.lean` / `Main.lean` |

### 关键分位数发现
- **全样本文件行数**：`P10=13`, `P25=31`, **`P50=82`**, `P75=167`, `P90=274`, `P95=353`, `P99=608`。
- **单文件直接 `import` 数**：**`P50=3`**, `P90=7`, `P99=18`。
- **最频繁的文件命名后缀**：`*Imports.lean`（全库共 **418 个**），其次为 `Bound`、`St`（Statement）、`Eq`、`Defs`、`Lift`、`Map`、`Bridge`、`Iso`。
- **声明与局部作用域特征**：全库所有自定义记号均为 `local` 或 `scoped`（样本出现 1,626 次），0 全局符号污染；局部中间步骤（`have`）在 2,578 个文件中出现 41,459 次（高度线性化的局部步骤分解）。

---

## 3. 五大关键微观代码证据

### 证据 A：零信任靶子隔离（`Challenge.lean` + `Main.lean` + `comparator.json`）
- `src/Challenge.lean`（27 行）仅 `import Mathlib`，独立定义 5 个目标命题（以 `by sorry` 占位）。
- `src/Main.lean`（12 行）仅导入 `Statements` 和 `Supplements.Kernels.MainTheoremsAll`，把内部证明一行一行对接到目标签名。
- `comparator.json` 锁定仅允许 3 条标准公理（`propext`、`Quot.sound`、`Classical.choice`），并在无网络只读容器里用独立内核（Lean 4.36 + `leanchecker-paranoid` + `nanoda`）重放比对。
- **工程映射**：任何高风险 AI 编程任务都应把“验收契约/核心测试”与“代码实现”分离并做 SHA256 冻结，防止 Agent 偷改测试来通过门禁。

### 证据 B：检索降噪黑名单（`src/BuildAid/D1.lean` ~ `D5.lean`）
5 个文件结构完全一致，每个仅 4 行：
```lean
run_cmd Lean.modifyEnv fun env => Lean.LibrarySuggestions.nameDenyListExt.addEntry env "CompanionTheory"
```
分别将 `CompanionTheory`、`CrystallineSemistableComparison`、`GlobalTheory`、`PositivityTheory`、`UpperTheory` 移出自动库检索建议范围。
- **工程映射**：当代码库超过数万行时，检索/补全噪声会直接引发 Agent 幻觉和错层引用。必须显式维护分层依赖边界与排除黑名单（`.rh-arch.json` 的 `layers` + `deny_imports`）。

### 证据 C：418 个 `*Imports.lean` 聚合门面与声明/实现分离
例如 `CompanionTheory/AutomorphicTheory/PieriRules/PieriDegreeBounds/` 中，将 `*Statement.lean`（纯声明）、`Imports.lean`（依赖门面）、`Definitions/`（定义）与 `Proofs/`（实现）严格拆开，保证叶节点文件的 `import` 数量停留在 3–4 行。
- **工程映射**：把“类型契约”、“子包重导出门面”与“核心逻辑实现”拆成小文件，既能显著降低 Agent 每次编辑需要读入的上下文，又能大幅减少增量编译/单测波及范围。

### 证据 D：元编程自动变体派生（`CutCptCopy.lean`，91 行）
当需要将一整条依赖链上的声明批量改写成紧支集（`Cpt`）变体时，作者没有让 LLM 手工复制粘贴几十个文件，而是编写 91 行确定性元程序 `toCopy` / `subst` / `copyAll`：
1. 沿常量依赖图遍历出受影响闭包（`tainted`, `order`）；
2. 按显式映射表 `special` + 后缀规则 `suffixed` 重写表达式树；
3. 逐条通过 `addDecl` 注入并由内核完整校验。
- **工程映射**：面对 ≥ 3 处结构同构的样板或跨类型变体，优先写小而确定的代码生成脚本并交由编译器/测试门禁验真，严禁让 Agent 人工复制改变量名。

### 证据 E：显式配置约束与内容寻址缓存（`lakefile.toml` + `verification/CACHE.md`）
- `lakefile.toml` 强制 `autoImplicit = false`、`relaxedAutoImplicit = false`（杜绝隐式拼写幻觉），并为高负载子库 `GroundTheoryFields` 单独设置 `synthInstance.maxHeartbeats = 400000` 资源上限。
- `CACHE.md` 展示了一套严格的离线缓存治理：每个产物按输入指纹内容寻址、恢复前逐文件校 SHA256、不匹配即离线沙盒编译回退、且子任务显式传 `-j1`（单任务确定性，仅在独立模块间并行）。同时明确警告“社区缓存不能替代独立验真”。

---

## 4. 不可偷师的真实边界（防过度乐观）

1. **过程轨迹缺失**：最终源码不包含 41 天里失败的证明分支、人类数学家对关键思路（如转向 Stepanov 方法 + `sqrt(X)` 长度 Theta lifts 链）的直觉引导。
2. **形式化内核红利**：Lean 4 内核提供 100% 逻辑保真裁判，而通用软件工程（Python/TS/Go）没有等价的完备数学内核，因此必须用**强类型检查 + 契约测试 + 属性测试 + 静态安全审计**组合逼近确定性裁判。
3. **算力反馈闭环差异**：百核大内存机器支持极高频率的“生成-编译-回溯”搜索；个人开发机上应通过**缩小模块粒度（≤120行）+ 增量单测**来模拟低延迟反馈闭环。
