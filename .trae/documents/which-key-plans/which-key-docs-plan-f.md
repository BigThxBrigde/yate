# which-key 子计划 f：规则文档回写 + 双语手册

wave-4（串行，在 plan-e 验收后执行——回写内容以 wave-3 实测事实为准）。纯文档。

## 输入

- plan-e 落地后的实测事实：面板 id、组合位置、`<f9>` / `:check-keys` 行为、
  `UI_FROZEN_FILES` 新键、`flows/whichkey_flows.py` 的 R11 冻结耦合。
- 规则文档现行条款：[architecture-boundaries.md](../../rules/architecture-boundaries.md)
  R9（id 冻结清单）、§一 L3 flows 清单、R11（冻结白名单说明）、§三.8
  （flows 接入清单）。
- 手册同步义务（doc-conventions §三）：`yate/docs/` 双语成对，同时新增。

## 目标

1. 架构边界规则与实现对齐（R9 新 id、§一 L3 清单、R11 白名单注记）。
2. 新增 which-key 用户手册（英 / 中成对）：功能、`<f9>`、`:check-keys`、
   vim 与 vsc 的行为差异。

## 非目标

- 不做存量文档的历史路径清扫（doc-conventions §五末条：随下次修改迁移）；
- 不动 CHANGELOG / README（发布流程另行处理）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `.trae/rules/architecture-boundaries.md` | 修改（3 处） |
| `yate/docs/which-key.en.md` | 新建 |
| `yate/docs/which-key.zh.md` | 新建 |

## 具体修改

### 1. architecture-boundaries.md

1a. **R9**：id 冻结清单追加 `#which-key`，并按 `#statusbar` 的先例标注
「widget id、样式由组件自持（`yate/resources/which-key.tcss`），
不被外壳 CSS 引用」；同步硬性依赖连线图无变化（L3→L2 实线已覆盖）。

1b. **§一 L3 清单**：`flows/` 子包列表追加 `whichkey_flows.py`（括号内
`overlay_flows.py` 旁）。

1c. **R11**：flows 冻结说明处补一句——`whichkey_flows.py` 于 which-key
任务（本文档）登记 `editor_view` / `editor_view.whichkey`，键见
`UI_FROZEN_FILES`。

### 2. which-key.en.md / which-key.zh.md（成对，结构一致）

章节：Overview（auto popup on pending chords, pinned sheet via F9）、
Keymap differences（vim: auto popup for operators/prefixes/registers/counts
and the ctrl+w chord; vsc: pinned sheet only）、Conflict checking
（`:check-keys`, duplicate + reserved classes）、Limitations
（F9 terminal availability, no yaterc persistence yet）。
两份同时新增，中文为英文的忠实翻译（不增删章节）。

### 3. 验收（misc-rules §三：纯文档变更豁免测试）

```text
git diff --stat .trae/rules/architecture-boundaries.md
```

人工核对：R9 清单含 `#which-key`；§一 L3 清单与
`tests/test_architecture.py::UI_FROZEN_FILES` 键集合一致（十个 flows 键）；
两份手册章节数一致。无测试门禁（纯文档）。

## 风险与回滚

- 规则文本与实现漂移：本计划在 wave-3 之后执行，回写以实测为准；
  守卫面（`UI_FROZEN_FILES`）本身在 plan-e 已落，规则文字仅描述事实。
- 回滚：`git checkout -- .trae/rules/` + 删除两份手册，无连锁影响。
