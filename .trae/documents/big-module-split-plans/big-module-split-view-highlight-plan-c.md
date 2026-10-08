# 波次 c：editor_view/editor → highlighting + welcome（issue IKK5F7）

## 目标

`yate/editor_view/editor.py`（1007 行）拆为：

- 新增 `yate/editor_view/highlighting.py`（~300 行）：
  - `_tokenize_with_states`（原 72–86）、`HighlightProbe`（89–109）；
  - `HighlightMixin` 类：`_init_highlight_state()`（由 `EditorView.__init__`
    的 `_hl_*`/`_match_buckets` 初始化块改造）、`_HIGHLIGHT_DEBOUNCE_S`、
    `_tokens_for`（417–453）、`_rebuild_tokens_on_edit`（455–557）、
    `tokens_for`（559–567）、`highlight_probe`（569–578）、
    `_schedule_highlight`（580–602）、`_launch_highlight`（604–624）、
    `_highlight_later`（626–661）。
  - imports：`asyncio`、`Document`、`Token`、两个 tokenize 函数、`tracing`；
    不 import 本包其他模块。
- 新增 `yate/editor_view/welcome.py`（~115 行）：`_WELCOME_BANNER`（59–66）、
  `_WelcomeRow`（69）；`_welcome_lines`（806–863）函数化为
  `welcome_rows(t, vim_keys, cache)`（cache 由调用方传 `self._welcome_cache`）；
  `_render_welcome`（865–888）函数化为 `render_welcome_row(...)`。
  imports：rich + `.theme` + `yate.__version__`。
- `editor.py` 瘦身（~680 行）：`EditorView(ScrollView, HighlightMixin)`；
  保留 PaneRegistry（冻结白名单 Protocol，原位不动）、`LEFT_BUTTON`、`S_*`
  常量、全部消息处理、鼠标几何、`render_line` 渲染管线、
  `_welcome_active`（耦合 session，留 widget）。

## 不可拆部分理由（A11 判据）

`render_line` + `_row_style_ranges`/`_matches_for_row`/`_cell_style`/
`_diagnostic_underlines` 是共享单次查找的渲染管线（拆分需改长参数列表并割裂
`_row_style_ranges` 对 `_match_buckets` 的就地写回）；4 个 `on_mouse_*` 与
Textual 鼠标捕获契约强耦合。

## 唯一测试破坏面（必须同步改）

`tests/test_app_render.py:143–157` monkeypatch
`yate.editor_view.editor._tokenize_with_states` → 改 patch
`yate.editor_view.highlighting._tokenize_with_states`。
`UI_FROZEN_FILES` 不动（flows 仍从 `yate.editor_view.editor` import）。

## 架构守卫

行数守卫豁免集合移除 `editor_view/editor.py`。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pyright yate/editor_view/
.venv\Scripts\python.exe -m pytest tests/test_app_render.py tests/test_support_mouse.py tests/test_dispatch_guards.py tests/test_architecture.py -q
```

## 预估

`highlighting.py` ~300；`welcome.py` ~115；`editor.py` ~680。
