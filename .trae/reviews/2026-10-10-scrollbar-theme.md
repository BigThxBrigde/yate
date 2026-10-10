# 2026-10-10 scrollbar-theme 合并分支评审

- 评审对象：`enh/preview-scrollbar-slim` 合并 `enh/manual-scrollbar-theme`
  之后的全部分支改动（`master..HEAD`，合并提交 `62e0324`，评审时分支头
  `2345100`）。
- 评审范围：preview 修复（`8c23a58`/`f4ec992`/`dd6ae92`，PreviewLog 自持
  滚动条）+ manual 修复（`4d1622e`，新增 DocScroll 组件）+ 二者合并态。
- 评审执行：code-review-expert 子代理（一轮），主代理复核。

## 一、验证结果（评审实跑）

| 命令 | 结果 |
|---|---|
| `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings（exit 0） |
| 目标测试集（palette_preview / app_render / app_manual / changelog_view / scrollbars / theme_subscribe / architecture） | 93 passed（含 28 条架构测试，exit 0） |

- 架构边界核对：R13（组件自持主题着色、无类级 `ScrollBar.renderer` patch、
  无 L3 着色）合规；R9/R10 未受影响；无新增 `Protocol` / `TYPE_CHECKING` /
  `Any`；文件体量守卫通过。
- 生命周期取证（针对 Textual 8.2.8 运行时探针）：
  `VerticalScroll → ScrollableContainer → Widget` 的 MRO 无 `on_mount`，
  `DocScroll` 不写 `super().on_mount()`/`@override` 是正确且必要的；
  `PreviewLog`（`RichLog → ScrollView`）保留 `super().on_mount()` 与
  explorer/editor 既有惯例一致。`Widget._on_mount`（滚动条可见性刷新）经
  Textual 消息机制独立分发，两处实现均不遗漏。
- attach/detach 无泄漏：两组件均单一构造点、modal 生命周期成对、
  `detach` 幂等；两条测试都覆盖了卸载后广播不再触达的负向断言。

## 二、发现与处置

| # | 严重度 | 位置 | 发现 | 处置 |
|---|---|---|---|---|
| 1 | suggestion | `../../yate/editor_view/manual.py`（DocScroll.on_mount） | 与 PreviewLog 的不对称（无 `super()`/`@override`）只记录在计划文档与提交信息里，代码内无解释；后续读者 diff 两个实现会产生疑问，且是 Textual 升级的 coupling 提示点 | 已修复：commit `2345100` 补三行注释（MRO 依据 + 升级时复查提示）；pyright 0 诊断、相关测试 49 passed 复验通过 |
| 2 | nit | `../../yate/editor_view/palette.py`（PreviewLog.on_mount） | `super().on_mount()` 在 8.2.8 分发机制下会令 `ScrollView.on_mount` 执行两次（探针实证；幂等无副作用） | 不改：与 explorer/editor 既有惯例逐字一致，一致性优先；已记录 |
| 3 | nit | `../../tests/test_palette_preview.py` / `../../tests/test_app_render.py`（卸载断言） | 卸载后负向断言在「默认主题恰为 latte」时是空断言；实际不可达（DEFAULT_THEME 为 mocha，且所有改主题的测试都在 finally 还原） | 不改：不可达路径，评审标注知悉即可；已记录 |

## 三、结论

- 无 blocker / major；1 条 suggestion 已修复复验，2 条 nit 核实为无需行动。
- 迭代第 1 轮收敛：无未决 issue，评审闭环。

## 四、第二轮：TRAE-code-review（2026-10-10，同日）

- 评审执行：TRAE-code-review skill（意图推断 + 主代理扫描 + 2 个并行验证
  子代理交叉确认，2 条发现均为 2/2 高置信；范围同上，分支头 `7783c14`）。

| # | 严重度 | 位置 | 发现 | 处置 |
|---|---|---|---|---|
| 1 | nit | `../../tests/test_palette_preview.py`（132-162）/ `../../tests/test_app_render.py`（340-388）（卸载负向断言） | §二#3 的同源问题精确化：`theme.set_theme` 无同名短路、每次都广播——latte 起始分支切到 `"mocha"` 后再以 `"mocha"` 还原，广播携带与窗格已绘一致的调色板，负向断言即使监听未解除也恒真；且 finally 硬编码 `"mocha"` 在 latte 起始时并未还原全局主题 | 已修复（用户选定「修复全部问题」，上轮「不改」登记就此翻转）：测试起始捕获 `original = theme.active().name`，切换目标与还原值均由其推导（`original` 与 `other` 构造上必异，负向断言在任意分支恢复判别力，finally 恢复真实原值）；复验 pyright 全仓 0 诊断 + 两文件 24 passed |
| 2 | nit | `../../tests/test_app_render.py`（8-23）（导入块） | 导入无分组空行（stdlib / 第三方 / yate / 本地连排），与 `test_palette_preview.py` 的分组风格不一致 | 已修复（同上）：加三处空行对齐既有分组风格 |

- 迭代第 2 轮收敛：2 条 nit 全部修复并复验，无未决 issue。
