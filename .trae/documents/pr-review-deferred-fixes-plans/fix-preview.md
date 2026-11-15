# 子计划 fix-preview — m5 预览装配去重 + m9 空操作守卫替换

**Worktree 根**：`../yate-file-manager`（分支 `feat/file-manager`，下述路径以此为根）。
**评审依据**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 m5 / m9（先读全文）。

## 独占文件

- `yate/editor_view/preview.py`
- `yate/editor_view/palette.py`
- `yate/editor_view/filemgr.py`
- `tests/test_palette_preview.py`

## m5 — 抽取共享装配函数

现状两段逐字重复的方法体（行号为当前实测）：

- `filemgr.py:463-482`（`FileManagerScreen._preview_text`，单行 docstring）
- `palette.py:399-423`（`PaletteScreen._preview_text`，多行 docstring 含
  「Token columns are clamped…」说明）

### 1. `preview.py` 新增模块级纯函数（放在 `load_preview_worker` 之后、`PreviewCache` 之前）

```python
def preview_text(data: PreviewData, t: Theme, max_lines: int) -> Text:
    """Assemble the syntax-highlighted preview text (pure, UI-thread side).

    Token columns are clamped to the line length (backends may lag the
    source after the truncation cut); token-free spans render with the
    plain foreground.
    """
```

函数体 = 现方法体原样平移，仅两处参数化：
`self.preview.max_lines` → `max_lines`；`t` 由参数传入（不再调 `theme.active()`）。
保留 `… truncated at {max_lines} lines` 字面量（字符串字面量不受 ASCII 注释纪律约束）。

导入补充：`from rich.text import Text`；`Theme` 类型的导入方式先 grep 既有
`-> Theme` / `: Theme` 签名的写法对齐（`yate/editor_view/theme.py` 是登记的门面
再导出例外，architecture-boundaries §三.5）。

同步修正 `preview.py:126-128` 注释里对 `_preview_text's` 的引用为新函数名。

### 2. 两屏改为调用共享函数

- `filemgr.py:461` → `pane.write(preview_text(data, theme.active(), self.preview.max_lines))`，
  删除 `_preview_text` 方法（463-482）；
- `palette.py:397` 同改，删除 `_preview_text` 方法（399-423）。

`_render_preview` 的 note 分支仍用 `Text`，两文件的 `rich.text` 导入保留；
删除方法后若出现其它未用导入一并清理。`preview_text` 从 `yate.editor_view.preview`
导入（两屏已有该模块导入，追加名字即可）。

### 3. 测试平移

`tests/test_palette_preview.py:282` 的 `screen._preview_text(data)` 改为
`preview_text(data, theme.active(), screen.preview.max_lines)`（导入对齐）。
若该文件还有其它 `_preview_text` 调用一并平移；装配断言保持等价，不新加行为。

## m9 — `is_mounted` 空操作守卫替换（三处同形）

Textual 8.2.8 的 `is_mounted` 只置 `True` 永不复位（评审已实证）；真实保护来自
`Widget._on_unmount → workers.cancel_node`。守卫统一换成 `is_attached`
（`filemgr.py` `_wire_mount` docstring 219-224 已论证该判据）：

- `filemgr.py:445`（`_load_preview_worker` 内 `if not self.is_mounted:`）；
- `palette.py:227`（entries 收集 worker 后）；
- `palette.py:382`（预览 worker 后）。

每文件在第一处替换旁加一行英文注释说明理由（`is_mounted` never resets on
unmount; `is_attached` mirrors Textual's own mount check），同文件后续替换不再重复。
其余文件的 `is_mounted`（commandline / manual / highlighting / find_replace / panes）
**一律不动**——不在本波评审范围。

## 自测

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/        # 0 诊断
.venv\Scripts\python.exe -m pytest tests/test_palette_preview.py tests/test_filemgr.py -q -n auto
```

全绿按退出码判定。允许**运行** `tests/test_filemgr.py`（只读），**禁止修改**它
（归 fix-navtest 批独占）。

## 执行纪律

- 禁触碰其它文件；`yate/editor.py`（fix-editor 批）、`tests/test_filemgr.py`
  （fix-navtest 批）由并行批次负责，不为图省事去改。
- 完成后**不提交**，汇报：改动文件、diff 要点、自测命令与退出码、未解决项。
