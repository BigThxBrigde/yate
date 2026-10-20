# which-key 子计划总纲

issue IKLY1Y「Feature - 实现Keymap的visual反馈」（which-key 面板）的实施子计划索引。
主计划见 [../which-key-plan.md](../which-key-plan.md)：目标 / 非目标、备选方案与否决理由、
波次表、风险清单与回滚路径均在主计划维护；本文只做索引与调度视图。

## 子计划索引

| 子计划 | 波次 | 层 | 独占文件（源码） | 主题 |
|---|---|---|---|---|
| [which-key-keymap-observer-plan-a.md](which-key-keymap-observer-plan-a.md) | wave-1 | L1 | `yate/keymaps/base.py`、`yate/keymaps/vim.py`、`yate/keymaps/vsc.py` | 挂起 chord 观测 `pending_prefix()` + `RESERVED_KEYS` 常量 + F9 绑定 |
| [which-key-conflicts-plan-b.md](which-key-conflicts-plan-b.md) | wave-1 | L1 | `yate/keymaps/conflicts.py`(新) | 键位冲突扫描（duplicate / reserved）与报告格式化 |
| [which-key-panel-plan-c.md](which-key-panel-plan-c.md) | wave-1 | L2 | `yate/editor_view/whichkey.py`(新)、`yate/resources/which-key.tcss`(新) | which-key 面板组件（纯渲染、自持主题） |
| [which-key-flows-plan-d.md](which-key-flows-plan-d.md) | wave-2 | L3 | `yate/flows/whichkey_flows.py`(新) | 流程模块：候选计算 + 面板驱动 + 钉住态 + 冲突报告出口 |
| [which-key-wiring-plan-e.md](which-key-wiring-plan-e.md) | wave-3 | L3 | `yate/editor.py`、`yate/actions.py`、`yate/commands.py`、`tests/test_architecture.py` | Editor 组装 + 内置表 + R11 守卫登记 + 全量门禁 |
| [which-key-docs-plan-f.md](which-key-docs-plan-f.md) | wave-4 | 文档/规则 | `.trae/rules/architecture-boundaries.md`、`yate/docs/which-key.en.md`(新)、`yate/docs/which-key.zh.md`(新) | R9/R11/flows 清单回写 + 双语手册 |

测试文件（不计入判据，随各子计划列出）：`tests/test_keymaps_conflicts.py`、
`tests/test_whichkey_panel.py`、`tests/test_whichkey_flows.py`（均新建）；
`tests/test_vim_keymap.py` / `tests/test_vsc_keymap.py` 仅追加（归 plan-a）；
`tests/test_keymap_set.py` 不改（仅作 plan-a 回归范围）。

## 执行波次表

| 波次 | 子计划 | 并行性 | 进入条件 |
|---|---|---|---|
| wave-1 | plan-a ∥ plan-b ∥ plan-c | 文件互不重叠，可并行 | 无 |
| wave-2 | plan-d | 串行 | wave-1 全部验收命令退出码 0（plan-d 依赖 a 的 `pending_prefix`、b 的 `find_key_conflicts`、c 的 `WhichKeyPanel`） |
| wave-3 | plan-e | 串行 | wave-2 验收通过（依赖 d 的 `WhichKeyFlows`，登记 R11 白名单后全量门禁复绿） |
| wave-4 | plan-f | 串行 | wave-3 验收通过（规则文本需回写 wave-3 实测事实） |

## 依赖关系

```mermaid
flowchart LR
    A["plan-a (L1)<br/>pending_prefix + RESERVED_KEYS + F9"] --> D["plan-d (L3)<br/>WhichKeyFlows"]
    B["plan-b (L1)<br/>conflicts.py 冲突扫描"] --> D
    C["plan-c (L2)<br/>WhichKeyPanel + tcss"] --> D
    D --> E["plan-e (L3)<br/>Editor 接线 + 内置表 + 守卫登记"]
    E --> F["plan-f (docs/rules)<br/>R9/R11 回写 + 双语手册"]
```

波次一经批准不得在执行中临时重排；确需调整须回填本文与主计划并说明实测依据。
已知时序说明：plan-d 模块 import `yate.editor_view.whichkey`，R11 白名单键
随 plan-e 落地，故 plan-d 验收以 `-k` 排除耦合守卫用例（细则见 plan-d 验收节），
plan-e 以全量架构测试复绿。
