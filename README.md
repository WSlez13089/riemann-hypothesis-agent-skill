# `claude-rh-lean-architecture`

> 提炼自 **Anthropic 内部版 Claude × Levent Alpöge 黎曼猜想 / GRH 1737 万行 Lean 4 形式化证明仓库**（`leanprover-community/riemann-hypothesis`，2026-11-20 发布）的超大型 Agent 工程架构协议与静态门禁套件。

## 目录内容

- [`SKILL.md`](SKILL.md)：Agent 执行协议（七大工程铁律 `RH-01`~`RH-07`、四阶段闭环与门禁码表）
- [`references/empirical-archaeology.md`](references/empirical-archaeology.md)：针对 175,187 文件 / 17.37M 行源码的实证抽样与微观代码考古报告
- [`scripts/rh_arch_gate.py`](scripts/rh_arch_gate.py)：零第三方依赖 Python 3.12+ 静态架构门禁与零信任靶子验证器（支持 Python / Lean / TS / JS / Rust / Go）
- [`scripts/test_rh_arch_gate.py`](scripts/test_rh_arch_gate.py)：纯离线确定性 `unittest` 测试套件

## 快速上手

克隆本仓库后，无需任何第三方依赖（仅需 Python 3.12+）：

```bash
# 1. 初始化项目架构约束（分层 + BuildAid 风格检索/引用黑名单）
python scripts/rh_arch_gate.py init-config <repo_dir>

# 2. 冻结不可变契约/验收靶子（复刻 Challenge.lean + Comparator 模式）
python scripts/rh_arch_gate.py freeze-challenge <repo_dir> --files src/contracts.py tests/test_contract.py -o .rh-challenge.json --json

# 3. 执行静态架构门禁审计（检查 RH001~RH007）
python scripts/rh_arch_gate.py audit <repo_dir> --json

# 4. 零信任核验靶子未被篡改
python scripts/rh_arch_gate.py verify-challenge <repo_dir> --manifest .rh-challenge.json --json

# 5. 运行工具自测
python -W error -m unittest discover -s scripts -v
```

> 也可将 `.agents/skills/claude-rh-lean-architecture` 链接或复制到你的 Agent 技能目录中按标准 `SKILL.md` 加载使用。

## Authors

- **Exiled-by-Lady-Claude** ([@WSlez13089](https://github.com/WSlez13089)) — 发起构思、仓库考古提炼与工程化集成
- **Gemini (Antigravity)** — 实证抽样分析、协议梳理与静态门禁联合编写

## License

[MIT](LICENSE)
