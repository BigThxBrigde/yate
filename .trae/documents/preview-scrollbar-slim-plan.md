# preview-scrollbar-slim 方案

来源 issue：gitee IKJUU2「文件 preview pane 的滚动条外观与 explorer 保持一致」。
分支：`enh/preview-scrollbar-slim`（worktree `../yate-preview-scrollbar-slim`）。

## 一、目标与非目标

**目标**

1. Ctrl+P 文件预览窗格（`PreviewLog`）的滚动条视觉与 explorer 完全一致：
   透明轨道 + 主题色细条拇指（水平方向不再是整行实心粗条）。
2. 按 R13 让 `PreviewLog` 成为自持主题的组件：挂载时自行注入 slim 渲染器与
   主题调色板，并订阅主题广播。

**非目标**

- 不改动 `manual.py` 文档查看器的滚动条（同样缺主题着色，但不在本 issue
  范围；列为后续候补）。
- 不改动 `SlimScrollBarRender` 渲染算法本身（粗细字形 `▂`/`▐` 保持）。
- 不改预览窗格几何（宽度百分比、边框、padding 均不动）。

## 二、调研事实清单

1. slim 渲染器只改拇指字形，不改几何：`yate/editor_view/scrollbars.py:29-91`
   （水平拇指 `▂` 为 1/4 行高字形）；`apply_slim_scrollbars` 逐 widget 注入
   （同文件 94-111 行）。
2. `apply_scrollbar_theme` 把轨道设为全透明、拇指用 `theme.active()` 的
   `border`/`fg_dim`/`accent`（scrollbars.py:114-130）——explorer 的"细"观感
   来自这层着色，缺了它整条 1 行高轨道不透明可见，即"太粗"的来源。
3. explorer 的完整做法（对照组）：`yate/editor_view/explorer.py:242-253`
   —— `apply_slim_scrollbars(self)` + `self._apply_theme()`（内部调
   `apply_scrollbar_theme`）+ `theme.attach(self, self._apply_theme)`，
   `on_unmount` 时 `theme.detach(self)`。
4. 预览窗格现状（缺陷侧）：`yate/editor_view/palette.py:518-530` ——
   `PaletteScreen.on_mount` 只对 `#palette-preview` 调了
   `apply_slim_scrollbars`，**没有** `apply_scrollbar_theme`，也没订阅主题。
5. `palette-screen.tcss` 的 `#palette-preview` 无任何 scrollbar 样式
   （`yate/resources/palette-screen.tcss:36-40`），Textual 默认调色板生效：
   不透明轨道 + 默认拇指色。
6. `PreviewLog` 是 `RichLog` 子类，当前无任何方法体（palette.py:102-109）；
   Textual 的 `RichLog` 未定义 `on_mount`/`on_unmount`，子类自定义安全。
7. R13（架构规则 §一）：组件自持主题——组件挂载或收到主题广播时自行读
   `theme.active()` 上色；禁止 L3 直改 `.styles.*`。新增主题感知组件应订阅
   `theme.subscribe`。
8. `theme.attach`/`detach` 是 `theme.subscribe` 的 widget 包装
   （`yate/editor_view/theme.py:163-182`）；`ThemeListener = Callable[[], None]`
   （theme.py:113）。`palette.py` 已有 `from . import theme`（palette.py:40）。
9. 现有测试面：`tests/test_palette_preview.py`（pilot 驱动，`_Host` 宿主 +
   `_palette()` 工厂）、`tests/test_scrollbars.py:77-92`（renderer 注入断言
   写法参照）。

## 三、备选方案与否决理由

| 方案 | 内容 | 裁决 |
|---|---|---|
| A（采纳） | `PreviewLog` 组件自持：自身 `on_mount` 注入 slim 渲染器 + `apply_scrollbar_theme`，订阅主题广播；删除 screen 级调用 | 与 explorer 同构，R13 合规，主题切换实时生效 |
| B | screen 级一行补丁：在 `PaletteScreen.on_mount` 现有调用旁补 `apply_scrollbar_theme` | 否决——维持"屏幕替子组件上色"的反模式，主题广播不生效，正是本次缺陷的成因 |
| C | 纯 CSS：`palette-screen.tcss` 给 `#palette-preview` 写 `scrollbar-background: transparent` 等 | 否决——`apply_scrollbar_theme` 的颜色来自 yate 主题系统（`t.border`/`t.accent`），CSS 设计令牌无 1:1 映射，hover/drag 语义分散在两套机制里，无法真正"与 explorer 保持一致" |

## 四、分步实施计划

### 步骤 1：`PreviewLog` 组件自持滚动条

- 输入：调研清单 §二 3/4/6/7/8。
- 改动文件：`yate/editor_view/palette.py`
  - 导入 `apply_scrollbar_theme`（第 42 行 import 扩展）；
  - `PreviewLog` 增加：
    - `on_mount`：`apply_slim_scrollbars(self)` + `self._apply_theme()` +
      `theme.attach(self, self._apply_theme)`；
    - `on_unmount`：`theme.detach(self)`；
    - `_apply_theme`：`apply_scrollbar_theme(self)`（docstring 注明对齐
      issue IKJUU2 与 explorer/IKEINF3 模式）；
  - `PaletteScreen.on_mount`：删除 screen 级
    `apply_slim_scrollbars(self.query_one("#palette-preview", PreviewLog))`
    （组件已自持；保留 `self._update_preview()`）。
- 输出：预览窗格滚动条 = slim 字形 + 透明轨道 + 主题色，且随主题广播刷新。
- 验收命令：`python -m pyright yate/editor_view/palette.py`；先写步骤 2 测试后
  合并验收 `python -m pytest tests/test_palette_preview.py tests/test_scrollbars.py -q`。

### 步骤 2：运行时回归测试

- 输入：步骤 1 产物；`tests/test_palette_preview.py` 现有 `_Host`/`_palette`
  设施；`tests/test_scrollbars.py:77-92` 断言写法。
- 改动文件：`tests/test_palette_preview.py`
  - 新增 1 条 pilot 用例（preview 启用的 files 模式）断言：
    1. `#palette-preview` 的横/纵 scrollbar `renderer is SlimScrollBarRender`；
    2. `pane.styles.scrollbar_background` 为全透明（`Color(0, 0, 0, 0)`）；
    3. `pane.styles.scrollbar_color == theme.active().border`。
- 输出：回归守卫（防止再次退回"只注入渲染器、不上色"）。
- 验收命令：`python -m pytest tests/test_palette_preview.py -q`。

### 步骤 3：全量门禁 + 冒烟

- 输入：步骤 1、2 完成。
- 改动文件：无（验证步骤）。
- 验收命令（worktree 内，`.venv\Scripts\python.exe`）：
  1. `python -m pyright yate/ tests/ tools/` → 0 diagnostics；
  2. `python -m pytest tests/ -q` → 全绿；
  3. `python -m pytest tests/test_architecture.py -q` → 28 passed；
  4. `python -m pytest tests/ -q --cov=yate --cov-fail-under=75` → 覆盖率门槛；
  5. 冒烟（可选，视觉确认）：pilot 打开 Ctrl+P files 模式、导出 SVG 截图，
     核对预览窗格水平滚动条为细条字形（`▂`），轨道无实心底色。
- 输出：门禁实测数字回填本计划 §六。

## 五、风险清单与回滚路径

| 风险 | 评估 | 缓解 |
|---|---|---|
| `PreviewLog.on_mount` 早于主题就绪 | 低——`theme.active()` 在 app 启动即有默认值，explorer 同路径已验证 | 测试断言读取 `theme.active()` 实际值比对 |
| 每次开 palette 都 attach/detach | 低——modal screen 生命周期成对，`attach` 对重复 listener 去重（theme.py:126-131） | `on_unmount` 幂等 detach |
| 删除 screen 级调用导致旧测试失败 | 低——现有用例不断言 renderer/着色 | 步骤 3 全量 pytest 兜底 |
| `RichLog` 上游未来新增 `on_mount` 被覆盖 | 低——Textual 消息处理器本就允许子类覆盖 | 挂载链无上游 handler 需求（调研 §二 6） |

回滚：改动集中在 2 个文件 + 1 个提交序列，`git revert` 单笔即可完整回退；
无数据/配置迁移。

## 六、执行记录（收尾回填）

- 步骤 1：palette.py 改动完成（PreviewLog 自持 + 删除 screen 级调用）；
  pyright yate/ tests/ tools/ 全量 0 诊断（exit 0）。
- 步骤 2：新增 2 条用例 `test_preview_pane_scrollbar_palette` /
  `test_preview_pane_scrollbar_follows_theme_change`（评审补强后）；
  `pytest tests/test_palette_preview.py -q` → 17 passed。
- 步骤 3：全量 `pytest tests/ -q --cov=yate --cov-fail-under=75` → 全绿
  （9 skipped，其余全 passed），TOTAL 覆盖率 91.44%（≥75 达标，exit 0）；
  架构测试 28 passed；冒烟 `python -m tools.smoke_test run` →
  107/107 场景、1286/1286 checks 通过（含 `palette_preview_renders` 等直接
  相关场景）。
- 评审（code-review-expert）：结论可合并，无 blocker / major；2 条 SUGGESTION
  （主题广播路径未钉、五字段只钉两个）与 1 条 nit（测试名）已随手补强
  （commit `dd6ae92`），1 条 nit（本记录占位）随本次回填消除。
- 偏离记录：`PreviewLog.on_mount` 在计划清单之外补了 `super().on_mount()`——
  Textual `ScrollView.on_mount` 会 `_refresh_scrollbars()`，不能静默丢弃；
  属对 §五风险表第 4 行的正确回应，评审确认为完善而非偏离。
