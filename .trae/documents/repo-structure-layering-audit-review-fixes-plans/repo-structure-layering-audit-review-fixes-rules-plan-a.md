# 子计划 a —— 规则文档对齐（Fix-A / Fix-B / Fix-C2 / Fix-C3 规则侧 / Fix-C4 规则侧）

- 总纲：[`overview.md`](overview.md)｜主计划：[`../repo-structure-layering-audit-review-fixes-plan.md`](../repo-structure-layering-audit-review-fixes-plan.md)
- 来源：[`../../reviews/2026-10-17-repo-structure-layering-audit.md`](../../reviews/2026-10-17-repo-structure-layering-audit.md)（S-1 / S-2 / S-4 / S-7 / S-8）
- 波次：wave-1｜独占文件：`.trae/rules/architecture-boundaries.md`（**只改这一个文件**）
- 前置依赖：无（与 plan-b 并行；白名单契约见总纲 §三.1）

## 一、目标

把审计确证的 5 处"规则文本与实现/守卫不一致"落成规则文本：

1. **S-1**：`keymaps/base.py`（L0）运行期 import `yate.session`（L1）—— 保留既有层秩切分，**登记该例外**
   （不重排层秩；重排的理由已否决，见主计划 §四 方案 B）；
2. **S-2**：`editor_view/statusbar.py`（L2）读 L3 扩展门面 —— 登记 L2→L3 例外；
3. **S-7**：`editor_view/theme.py` 门面再导出 —— 登记 §三.5② 例外；
4. **S-8**：`dist_meta.py` 层级归 L0 并纳入 UI-free 守卫面；
5. **S-4**：`services/yxp.py` 归属登记（留在 `services/`，不随迁 `services/extensions/`）；
6. 用例计数 31 → **32**（配合 plan-b）。

## 二、逐处改动（锚点为现状文本；**逐字替换，不得改写措辞**）

> 执行纪律：每处先定位下列**现状文本**（若不匹配，停止并回报，不得猜测）；替换为对应**目标文本**。
> 全部为中文文档编辑，行宽与既有排版风格保持一致；不得引入绝对路径（doc-conventions §五）。

### 改动 1 —— §一 依赖图 Mermaid L0 节点（约 `:64-65`）

现状：
```
        LEAVES["editor_core / editor_lsp / editor_syntax / editor_term / keyproto /
        editor_sprites / keymaps.base|vim|vsc / services/* / config / yaterc* / logs / paths"]
```
目标：
```
        LEAVES["editor_core / editor_lsp / editor_syntax / editor_term / keyproto /
        editor_sprites / keymaps.base|vim|vsc / services/* / config / yaterc* / logs / paths /
        dist_meta"]
```

### 改动 2 —— §一 L1 文本（约 `:24-26`）

现状：
```
         registries.py（依赖 keymaps.base 的 ActionContext，层级位于 keymaps 之上、
         actions/commands/editor 之下）/ keymaps/registry.py（KeymapSet）
```
目标：
```
         registries.py（依赖 keymaps.base 的 ActionContext，层级位于 keymaps 之上、
         actions/commands/editor 之下）/ keymaps/registry.py（KeymapSet）
         （2026-10-17 审计定案：`keymaps/` 的层秩按文件切分——`base|vim|vsc` 属 L0（键映射契约，
         `keyproto/legacy.py` 依赖其 `SPECIAL_KEYS`）；`registry.py` 与包根 `__init__.py`
         （re-export `KeymapSet`）属 L1）
```

### 改动 3 —— §一 L0 文本（约 `:27-33`，在既有注记后追加）

现状：
```
        `yate.logs` 为 R12 统一 tracing 的豁免依赖）
```
目标：
```
        `yate.logs` 为 R12 统一 tracing 的豁免依赖；
        2026-10-17 审计定案：补入 `dist_meta.py`（stdlib-only，运行期供 `diagnostics.py`、
        构建期供 `pack/_common.py`），并登记**唯一 L0→L1 例外**——
        `keymaps/base.py` 运行期 `import yate.session`（`ActionContext(session, ui)` 持有会话，
        且 `KeyBinding.action` 引用 `ActionFunc`，无法迁出而不损失类型约束）；
        该例外由 §六 的层秩守卫冻结，新增 L0→L1 连线须先在本行登记）
```

### 改动 4 —— §二 层职责表 L0 行（约 `:211`）

现状（行尾）：
```
… 字体、空闲跟踪 `services/idle_tracker.py`） | 不 import 上层 |
```
目标：
```
… 字体、空闲跟踪 `services/idle_tracker.py`、dist 元数据 `dist_meta.py`） | 不 import 上层（唯一登记例外：`keymaps/base.py` → `yate.session`，见 §一） |
```

### 改动 5 —— §三.5②（约 `:222-224`）

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
  （big-module-split d 波产物，2026-10-17 审计登记，模块 docstring 已自述），不视为本款禁止项）；
```

### 改动 6 —— R14 条目末尾（在 `**守卫**：§六「R14」条目（…）` 之前插入两句）

插入内容（保留其后原有"**守卫**"句不变）：
```
  **L2→L3 已登记例外**（2026-10-17 审计）：`editor_view/statusbar.py` 取本门面公共名
  （`ExtensionLoader`）与冻结的 `.bridges`（`UiExtensionBridge`，见 §六
  `EXTENSION_SUBMODULE_FROZEN`）以渲染扩展状态段，`statusbar.py:83-84` 为构造参数注入；
  L2 新增到 L3 的连线必须先在本条登记，并由 §六 的层秩守卫冻结。
  `yate/services/yxp.py`（`.yxp` 包装卸逻辑）**不随迁**本子包：它不含扩展运行时耦合，
  归属仍为 `services/`（与 `events.py` / `user_setup.py` 同理）。
```

### 改动 7 —— §六 R4 条目（约 `:348`）与 UI-free 说明（约 `:370`）

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
  （R4 是 **UI 耦合**约束，与层秩无关：`keymaps/*` 同为 UI-free 面与 L0/L1 混合包，见 §一。）
```

### 改动 8 —— §六 用例数与对照表（约 `:292` 与文末表）

现状（§六 开头）：
```
`tests/test_architecture.py` 已落地 **31 个用例**（2026-10-13 实测复核：
`python -m pytest tests/test_architecture.py -q` → `31 passed`；用例清单见文末对照）：
```
目标（数字以 plan-b 完成后实测回填；预期 32）：
```
`tests/test_architecture.py` 已落地 **32 个用例**（2026-10-17 实测复核：
`python -m pytest tests/test_architecture.py -q` → `32 passed`；用例清单见文末对照）：
```
文末对照表追加一行（现有末行为 `| 31 | test_extension_facade_exports_the_frozen_plugin_names | … |`）：
```
| 32 | `test_no_unregistered_upward_imports` | 层秩向上连线（2026-10-17：白名单 3 条冻结，`extensions/` 跳过） |
```

## 三、验收命令

```powershell
git --no-pager diff --stat .trae/rules/architecture-boundaries.md
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern 'keymaps/base\|vim\|vsc'   # 仍应为 1 命中（L0 行保留）
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern 'dist_meta'                 # 应 ≥3 命中（§一/§二/§六 R4）
Select-String -Path .trae/rules/architecture-boundaries.md -Pattern '已落地 \*\*32 个用例\*\*'  # 应 1 命中
```

- 判定：全部逐处替换成功、无残留旧表述、仓库内引用均为相对路径；
- 本文件为纯文档 → 测试门禁并入总纲 §四（与 plan-b 同批跑全量，不单独豁免）；
- 输出：改动清单 + 上述命令输出 + 未解决项。

## 四、风险与回滚

- 四处互引（§一 L1 文本 / §一 L0 文本 / §二 表 / §六 计数）必须同步，否则规则自相矛盾 → 逐处验收；
- 任何一处现状文本不匹配 = 停止回报（不得近似改写）；
- 回滚：`git revert <本步提交 sha>`。
