# 子计划 a —— 规则层秩登记（Fix-A / Fix-B / Fix-C2 / Fix-C3 规则侧 / Fix-C4 规则侧）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)（v3）
- 来源：[`../../reviews/2026-10-17-repo-structure-layering-audit.md`](../../reviews/2026-10-17-repo-structure-layering-audit.md)（S-1 / S-2 / S-4 / S-7 / S-8）
- 波次：wave-1｜独占文件：`.trae/rules/architecture-boundaries.md`（**只改这一个文件**）
- 前置依赖：无（与 plan-f 并行；层秩定稿见总纲 §三.1，白名单契约见 §三.2）

## 一、目标

把 v3 的干净切分写进规则：

1. `keymaps/keys.py` = **L0**（键位记法，零上层依赖）；`keymaps/` 其余 = **L1**；
   切分后**全仓零 L0→L1 例外**；
2. 登记切分后**唯一**的向上连线：`editor_view/statusbar.py`（L2）→ `yate.services.extensions`（L3）；
3. 登记 `editor_view/theme.py` 门面再导出例外（S-7）、`dist_meta.py` 层级（S-8）、
   `services/yxp.py` 归属（S-4）；
4. 用例计数 31 → **32**（配合 plan-b）。

## 二、逐处改动（锚点为现状文本；**逐字替换，不得改写措辞**）

> 执行纪律：先定位"现状文本"，任何一处匹配不上即停止回报，不得猜测近似改法。
> 中文文档编辑，保持既有排版与行宽风格；不得引入绝对路径（doc-conventions §五）。

### 改动 1 —— §一 L1 文本（约 `:24-26`）

现状：
```
         registries.py（依赖 keymaps.base 的 ActionContext，层级位于 keymaps 之上、
         actions/commands/editor 之下）/ keymaps/registry.py（KeymapSet）
```
目标：
```
         registries.py（依赖 keymaps.base 的 ActionContext，层级位于 keymaps 之上、
         actions/commands/editor 之下）/
         keymaps/（2026-10-17 层秩切分：`keys.py` 属 **L0**（键位记法，零上层依赖）；
         `base.py` / `vim.py` / `vsc.py` / `registry.py` / `__init__.py` 属 **L1** ——
         `base.py` 持有 `ActionContext`（内含 `EditorSession`）与 `ActionFunc`，
         `registry.py` 持有 `KeymapSet`）
```

### 改动 2 —— §一 L0 文本（约 `:27-33`）

现状（两处，分别替换）：
```
L0 叶子：editor_core / editor_lsp / editor_syntax / editor_term / keyproto /
        editor_sprites / logs / paths / config / services/* / keymaps/base|vim|vsc
```
目标：
```
L0 叶子：editor_core / editor_lsp / editor_syntax / editor_term / keyproto /
        editor_sprites / logs / paths / config / services/* / keymaps/keys.py
```
并把既有注记尾句：
```
        `yate.logs` 为 R12 统一 tracing 的豁免依赖）
```
替换为：
```
        `yate.logs` 为 R12 统一 tracing 的豁免依赖；
        2026-10-17 层秩切分（S-1）：键位记法下沉为 L0 单文件 `keymaps/keys.py`，
        `keymaps/` 其余收敛为 L1 —— 切分后 **L0 无任何向上连线**（`keyproto/legacy.py`
        作为 L0 消费者改从 `keymaps/keys.py` 取记法），故本行不再登记 L0 例外；
        补入 `dist_meta.py`（stdlib-only：运行期供 `diagnostics.py`、构建期供 `pack/_common.py`））
```

### 改动 3 —— §一 依赖图 Mermaid（两处节点）

现状（L1 节点）：
```
        SES["session.py（EditorSession + 窗格树）/ registries.py / keymaps/registry.py"]
```
目标：
```
        SES["session.py（EditorSession + 窗格树）/ registries.py /
        keymaps/（base · vim · vsc · registry · __init__；keys.py 为 L0，见下）"]
```
现状（L0 节点）：
```
        LEAVES["editor_core / editor_lsp / editor_syntax / editor_term / keyproto /
        editor_sprites / keymaps.base|vim|vsc / services/* / config / yaterc* / logs / paths"]
```
目标：
```
        LEAVES["editor_core / editor_lsp / editor_syntax / editor_term / keyproto /
        editor_sprites / keymaps.keys / services/* / config / yaterc* / logs / paths /
        dist_meta"]
```

### 改动 4 —— §二 层职责表（L1 行与 L0 行）

现状（L1 行）：
```
| `EditorSession` / `KeymapSet` / 注册表（L1） | 文档、标签、搜索、键映射集合、动作与命令容器、**窗格状态模型**（`Leaf` / `Split` / `ViewState` + 树纯操作，无 UI） | 不 import `editor_view`、不碰 Textual |
```
目标（仅"可以做什么"列补一层秩切分说明）：
```
| `EditorSession` / `KeymapSet` / 注册表（L1） | 文档、标签、搜索、键映射集合（`keymaps/` 除 L0 记法 `keys.py` 外整体在本层）、动作与命令容器、**窗格状态模型**（`Leaf` / `Split` / `ViewState` + 树纯操作，无 UI） | 不 import `editor_view`、不碰 Textual |
```
现状（L0 行，行尾）：
```
… 字体、空闲跟踪 `services/idle_tracker.py`） | 不 import 上层 |
```
目标：
```
… 字体、空闲跟踪 `services/idle_tracker.py`、dist 元数据 `dist_meta.py`、键位记法 `keymaps/keys.py`） | 不 import 上层（2026-10-17 切分后：零例外） |
```

### 改动 5 —— §三.5③（约 `:225-230`，叶包清单与 keymaps 归属）

现状：
```
  ③ 纯 L0 叶包（`editor_core` / `editor_lsp` / `editor_syntax` / `editor_term` /
  `keymaps`）允许**有限** re-export 作为插件公共 API 面（插件手册明文示例
  `from yate.editor_syntax import LangSpec`），且**重量级实现模块**（如
  `editor_lsp.manager`）不得进包根；例外须在各包 `__init__.py` docstring 注明
  （守卫：`test_leaf_package_reexports_carry_exception_note`、
  `test_editor_lsp_package_root_is_light`）。
```
目标：
```
  ③ 纯 L0 叶包（`editor_core` / `editor_lsp` / `editor_syntax` / `editor_term`）
  允许**有限** re-export 作为插件公共 API 面（插件手册明文示例
  `from yate.editor_syntax import LangSpec`），且**重量级实现模块**（如
  `editor_lsp.manager`）不得进包根；例外须在各包 `__init__.py` docstring 注明
  （守卫：`test_leaf_package_reexports_carry_exception_note`、
  `test_editor_lsp_package_root_is_light`）。`keymaps` 自 2026-10-17 起整体属 **L1**
  （`keys.py` 除外），其包根 re-export 仍按本款登记并受同一守卫检查。
```

### 改动 6 —— §三.5②（约 `:222-224`，`editor_view/theme.py` 例外）

现状：
```
  ② UI / 服务包（`editor_view` / `services`）**禁止** re-export（现状惯例成文化，
  `editor_view/__init__.py` 与 `services/__init__.py` 的"deliberately not re-exported"
  声明为范本）；
```
目标：
```
  ② UI / 服务包（`editor_view` / `services`）**禁止** re-export（现状惯例成文化，
  `editor_view/__init__.py` 与 `services/__init__.py` 的"deliberately not re-exported"
  声明为范本）；**唯一例外**：`editor_view/theme.py` 作为主题广播枢纽与门面再导出
  （big-module-split d 波产物，2026-10-17 审计登记，模块 docstring 已自述），不视为本款禁止项；
```

### 改动 7 —— R14 条目末尾（在 `**守卫**：§六「R14」条目（…）` 之前插入）

插入内容（其后的"**守卫**"句保持不变）：
```
  **L2→L3 已登记例外**（2026-10-17 审计）：`editor_view/statusbar.py` 取本门面公共名
  （`ExtensionLoader`）与冻结的 `.bridges`（`UiExtensionBridge`，见 §六
  `EXTENSION_SUBMODULE_FROZEN`）以渲染扩展状态段，`statusbar.py:83-84` 为构造参数注入；
  这是 2026-10-17 层秩切分后全仓**唯一**的向上连线，由 §六 的层秩守卫冻结；
  L2 新增到 L3 的连线必须先在本条登记。
  `yate/services/yxp.py`（`.yxp` 包装卸逻辑）**不随迁**本子包：它不含扩展运行时耦合，
  归属仍为 `services/`（与 `events.py` / `user_setup.py` 同理）。
```

### 改动 8 —— §六 R4 条目（约 `:348`）与 UI-free 表述

现状（`- **R4** …` 行）：
```
- **R4** `keymaps/*`、`services/*`、`keyproto/*`、`editor_sprites/*`、`session.py`、
```
目标：
```
- **R4** `keymaps/*`、`services/*`、`keyproto/*`、`editor_sprites/*`、`dist_meta.py`、`session.py`、
```
并在同条目末尾补一句：
```
  （R4 是 **UI 耦合**约束，与层秩无关：`keymaps/*` 同时是 UI-free 面与该包按文件切分的
  L0/L1 混合面，见 §一。）
```

### 改动 9 —— §六 用例数与对照表

现状：
```
`tests/test_architecture.py` 已落地 **31 个用例**（2026-10-13 实测复核：
`python -m pytest tests/test_architecture.py -q` → `31 passed`；用例清单见文末对照）：
```
目标（数字以 plan-b 完成后的实测为准；预期 32）：
```
`tests/test_architecture.py` 已落地 **32 个用例**（2026-10-17 实测复核：
`python -m pytest tests/test_architecture.py -q` → `32 passed`；用例清单见文末对照）：
```
文末对照表追加一行（现有末行为 `| 31 | test_extension_facade_exports_the_frozen_plugin_names | … |`）：
```
| 32 | `test_no_unregistered_upward_imports` | 层秩向上连线（2026-10-17：切分后白名单仅 statusbar 2 条，`extensions/` 跳过） |
```

## 三、验收命令

```powershell
git --no-pager diff --stat .trae/rules/architecture-boundaries.md
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern 'keymaps/base\|vim\|vsc'   # 期望 0 命中
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern 'keymaps/keys\.py'          # 期望 ≥2 命中
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern '已落地 \*\*32 个用例\*\*'  # 期望 1 命中
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern 'L0 例外|零例外'            # 期望命中新增句
```

- 判定：9 处逐处替换完成、`keymaps/base|vim|vsc` 旧表述归零、仓库内引用均为相对路径；
- 纯文档文件，但整批含代码/测试改动 → 门禁并入总纲 §四（不单独豁免）。

## 四、风险与回滚

- 四处互引（§一 文本 / §一 Mermaid / §二 表 / §六 计数）必须同步，否则规则自相矛盾 → 逐处验收；
- 锚点不匹配 = 停止回报；
- 回滚：`git revert <本步提交 sha>`。
