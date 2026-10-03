# dap-support plan-i：TUI 视图层（W4：DebugPanel / gutter / 状态栏）

主计划依据：§5.2 gutter、§5.3 面板、§5.4 状态栏。

## 目标

视图三件套独立可测：`DebugPanel` widget（自持 toggle/open/close）、gutter
调试列（●/▶）、状态栏 debug 段。本计划**不改 `yate/editor.py`**——挂载与
按键路由归 plan-j；本计划用注入协作者/假 manager 完成 pilot 测试。

## 非目标

不接真实 DapManager 生命周期（plan-j 接线）；不动 terminal.py（互斥在
Editor 路由侧，plan-j）；不做 ANSI 解析/watch/setVariable。

## 独占文件清单（只改这些）

- `yate/editor_view/debug_panel.py`（新增）— `DebugPanel(Vertical)` 对照
  `TerminalPanel`（[editor_view/terminal.py:377](../../yate/editor_view/terminal.py#L377)）
  包可聚焦 `DebugView(Widget, can_focus=True)`（对照 :73）；**toggle/open/
  close/apply_height 方法自持**（对照 :453/:460/:474/:485）；只渲染与按键，
  不持有调试状态；依赖经构造注入具体协作者或 `Callable`（R3：禁 import
  `yate.editor`；不引入 editor_term）；out/info 双模式 + evaluate 输入
  （主计划 §5.3）；主题自持（R13：`theme.subscribe` / `theme.active()`）；
- `yate/editor_view/editor.py` — `gutter_width()` :344-346 公式 `+3` 改
  `+4`；gutter 拼接 :666-687 增调试点列（执行行 ▶ t.yellow+bold 优先、
  断点 ● t.red、否则空格）；执行行整行复用 :664 `line_bg = t.surface`
  （行号 bold + 底色），零 Theme 变更；执行行数据源经注入的查询回调
  （Editor 接线在 plan-j 提供实现）；welcome 页 `_welcome_lines` :736
  仅核对居中不错位，不改文案；
- `yate/editor_view/statusbar.py` — 新增 `_debug_segment()`（仿
  `_lsp_segment` :161-185），插入右段拼装链 :149-158（lsp 段 :155-157 后）；
  仅会话非 CONFIGURED/TERMINATED 显示，无会话零占位；
- `tests/test_dap_tui.py`（新增）— pilot headless（范式
  [test_app_textual.py:109-117](../../tests/test_app_textual.py#L109-L117)，
  `wait_until` :39-47）：gutter 字符串断言（●/▶/叠加优先/宽度恒定 +1/
  welcome 不错位/补全弹层边界随 gutter——复用
  [completion.py:283](../../yate/completion.py#L283)）；状态栏无会话零段、
  PAUSED 段含 `paused at`；DebugPanel out 追加（stdout/stderr 区分）、
  stopped 切 info、变量 `+` 展开触发注入回调、evaluate 回显
  （本计划用假 manager/假回调用例；真接线用例归 plan-j 追加同文件）。

## 实施要点

1. gutter 宽度恒定 +1 与会话有无无关（防文本抖动）；诊断列 :666-687 逻辑
   一律不动。
2. R9：DebugPanel 的 widget id 由 plan-j 构造时传入（本期类型只定义，
   不写死外壳 CSS；若外壳 CSS 需引用则同步 `yate/resources/app.tcss`——
   默认不加）。
3. R13 红黄均为既有 theme 字段（t.red/t.yellow），不加新颜色。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dap_tui.py tests/test_completion_popup.py tests/test_editor_view.py -q
.venv\Scripts\python.exe -m pyright yate/editor_view
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/ -q
```

（若 `tests/test_editor_view.py` 不存在则以实际文件名为准——验收命令以
pyright + 全量 pytest 为准绳。）

## 风险与回滚

- gutter +1 影响全部视图：恒定宽度 + welcome/补全回归用例兜底。
- 面板按键吞键（历史缺陷）：按键分支只消费自己处理的键，未识别 fall-through
  （R10 与架构自检清单）。
- 回滚：gutter/statusbar 改动各自单 commit；debug_panel.py 整文件删除即可。
