# 2026-10-16 全仓结构审计（Gitee IKMCZW）

- 来源：[Gitee IKMCZW](https://gitee.com/jermaine/yate/issues/IKMCZW)（ENHANCE - 大模块、项目结构以及层次的审核，文档更新）
- 修复方案：[`.trae/documents/repo-structure-audit-plan.md`](../documents/repo-structure-audit-plan.md)
- 分支：`enh/repo-structure-audit`；本文为**只读事实文档**，只记录发现与核对结论。

## 基线门禁（实测）

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 |
| `pytest tests/ -q` | 全绿，exit 0 |
| `pytest tests/test_architecture.py -q` | 31 passed |

## 发现（按 issue 四项任务）

### 1. 大模块拆分审核

- `yate/` + `tools/` 内 **>800 行文件全部登记在 `SIZE_EXEMPT_FILES`，无遗漏**。
- 守卫口径（`splitlines()`）实测：`editor.py` 1024、`vim.py` 1184、`buffer.py` 1069、
  `wiki.py` 1495、`langdefs.py` 813、`logs.py` 690（负面清单）。五处与规则登记数漂移，
  已随 [`.trae/rules/architecture-boundaries.md`](../rules/architecture-boundaries.md) §三.7 同步。
- **拆分候选登记**：`yate/editor.py`（1024 行，docstring 自述约 9 类操作职责，构成
  工厂 + 命令分发 + explorer 分节）为下一个 big-module-split 候选——本轮不改代码，
  拆分另行立项；豁免维持，行数注记已更新。
- **观察项**：`yate/services/yxp.py` 705 行、`yate/editor_view/panes.py` 694 行逼近阈值，
  下次改动时留意。
- 单一职责豁免均复核成立：`vim.py`（单一键映射域）、`buffer.py`（文本模型/撤销/多点
  原语）、`wiki.py`（pack 生成器）、`langdefs.py`（声明式注册表）、`logs.py`（三服务
  内聚，负面清单已论证）。

### 2. 模块 / 包结构审核

- 命名守卫：无 `*Feature` / `*Host` / `*Ops` / `*Delegate` / `*Controller` 违规
  （白名单 `PaneHost` / `PaneManager` / `LspManager` 合法在册）。
- 相对导入：全仓 `from .X` 0 处。
- 错位模块：未发现；`flows/extension_flows.py` 实测不 import `editor_view`
  （extension_flows.py:20-27），合规且无需登记 `UI_FROZEN_FILES`。
- 近空模块：仅 `__main__.py`（8 行）等常规样板。
- `editor_sprites/chars/` 27 个角色模块 + `_shared.py`，单文件 30–69 行，无膨胀。

### 3. 项目层次审核（R1–R14 违规信号，yate/ + tools/）

| 信号 | 命中 |
|---|---|
| `import yate.app` 出界（cli.py 之外） | 0 |
| `TYPE_CHECKING` | 0 |
| `Optional[` / `Union[` | 0 |
| `self.log` / `self.app.log` | 0（2 处为注释） |
| 类级 `ScrollBar.renderer =` | 0 |
| 模块/类级 `X = Callable[` 赋值 | 0 |
| 架构测试 | 31 passed |

分层边界全部成立；31 个守卫用例数与规则 §六登记一致。

### 4. 文档出入（已修复项）

1. `architecture-boundaries.md` §三.7 五处豁免/负面清单行数过期 → 已同步（本分支）。
2. R11 flows 枚举漏 `mouse_flows.py` / `extension_flows.py`（与 §一 L3 依赖图、实际
   目录 10 模块不一致）→ 已补齐（本分支）。
3. `tests/test_architecture.py` 的 `UI_FROZEN_FILES` 块注释误引 "(R4)"、守卫 docstring
   只概括 2 个 flows 文件（实际 9 键）→ 已修正（本分支，注释级改动）。
4. README 数字声明实测全部吻合：内置语言 30（`_LANGUAGES` 按语言对象去重）、
   tree-sitter 25（`BUILTIN_PACKS`）、主题 8（`THEMES`）、屏保角色 27
   （`character_names()` 运行时）——**零出入**。
5. 扩展门面 `__all__` 恰为 14 名，与 `EXTENSION_FACADE_NAMES` 逐名一致；双语插件手册
   引用的导入路径与实现一致——**零出入**。
6. CHANGELOG 顶部 [Unreleased] 条目与代码现状吻合——**零出入**。

## 结论

代码侧（结构、层次、体量豁免、边界信号）全部合规；本轮全部产出为文档与注释级修正。
迭代后续：pr-review 技能对分支全部改动复审，直至无 BLOCKER / MAJOR 产出（结论见计划
文档回填）。
