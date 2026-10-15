# plan-d：接线（wave-3）

> 总纲见 [overview.md](overview.md)。波次：wave-3；依赖 plan-c 的
> FindReplaceScreen 构造签名（plan-b 的确认循环与本波无文件交集）。

## 一、输入

- 总纲 D5、F8-F13、F20-F22；
- plan-c 定稿的 `FindReplaceScreen(workspace, session, *, open_path,
  reveal, message, readonly_notice, refresh)` 签名。

## 二、独占改动文件清单

| 文件 | 动作 |
|---|---|
| `yate/flows/overlay_flows.py` | 修改（`__init__` 加 `session`；`open_project_replace()` 新方法；import 2 行） |
| `yate/editor.py` | 修改（`_build_pane_stack` 构造处补 2 参；新增 `reveal_match` 方法，≤25 行） |
| `yate/actions.py` | 修改（search 组 +1 条 reg） |
| `yate/commands.py` | 修改（+1 条 reg） |
| `yate/keymaps/vsc.py` | 修改（search 组 +1 行） |
| `yate/keymaps/vim.py` | 修改（CMD 组 +1 行） |
| `tests/test_architecture.py` | 修改（`UI_FROZEN_FILES["flows/overlay_flows.py"]` 集合追加 `"yate.editor_view.find_replace"`——F13 精确集合） |

> editor.py 已是 §三.7 豁免名单成员（983 行），本波增量 ~25 行，豁免
> 状态不变（名单行数由守卫 `SIZE_EXEMPT_FILES` 口径复核）。

## 三、具体修改

### 3.1 `yate/flows/overlay_flows.py`

1. import 段（L19-32）追加：

```python
from yate.editor_view.find_replace import FindReplaceScreen
from yate.session import EditorSession
```

2. `__init__`（L38-74）参数表在 `workspace: Workspace,`（L47）前插
   `session: EditorSession,`；函数体在 `self.workspace = workspace` 旁加
   `self.session = session`。
3. 新增方法（置于 `open_diff` 与 `_palette` 之间，动词方法对齐既有形态）：

```python
def open_project_replace(self) -> None:
    """Open the project-wide find & replace overlay (ctrl+h)."""
    if not self._mounted():
        return
    if self.workspace.root is None:
        self._message("no workspace folder open", "warn")
        return
    self.push(FindReplaceScreen(
        workspace=self.workspace,
        session=self.session,
        open_path=self._open_path,
        reveal=self._reveal_match,
        message=self._message,
        readonly_notice=self._readonly_notice,
        refresh=self._refresh,
    ))
```

   `_reveal_match` / `_readonly_notice` 为构造器新注入的两个回调
   （见 3.2）；`self.push` 自动获得 stale message 清理语义（F12 L76-89）。

### 3.2 `yate/editor.py`

1. `_build_pane_stack` 的 `OverlayFlows(...)` 构造（L239-256）在
   `workspace=ed.workspace,`（L247）前补：

```python
session=ed.session,
reveal_match=ed.reveal_match,
readonly_notice=ed.readonly_notice,
```

2. `Editor` 类新增方法（`readonly_notice` L750 附近，组合点归 L3）：

```python
def reveal_match(self, path: Path, row: int, col: int) -> None:
    """Open *path* if needed and put the cursor on a project-search hit.

    ``open_path_later`` loads asynchronously; the cursor is applied to the
    active document when it is already the right one, and otherwise the
    deferred open lands on the file with the cursor clamped to the match
    start by the regular view pipeline.
    """
    doc = self.session.is_open(path)
    if doc is not self.session.doc:
        self.document_flows.open_path_later(path)
        doc = self.session.is_open(path)
    if doc is not None:
        buf = doc.buffer
        buf.anchor = None
        buf.set_cursor((row, min(col, len(buf.lines[row]))))
        view = self.panes.view_for(doc)
        if view is not None:
            view.reveal_cursor()
    self.refresh_ui()
```

   实现注记：`view_for` / `reveal_cursor` 以 editor.py / panes.py 现有
   API 为准（prompt_flows.goto_line L140-143 的
   `panes.active_view` + `view.reveal_cursor()` 是最近参照；若 panes 无
   per-doc 查询则用 `active_view`——open_path_later 激活该文档后
   active_view 即目标视图）。执行者实现时以实际 API 微调，行为契约：
   enter 后目标文档聚焦、光标落在匹配起点、视图滚动可见。

### 3.3 `yate/actions.py`

search 组（L203-204 `reg("replace", ...)` 之后）追加：

```python
reg("project_replace",
    lambda ctx: editor.overlays.open_project_replace(),
    "Find & replace in project (ctrl+h)")
```

### 3.4 `yate/commands.py`

既有 reg 形态处追加 `reg("project-replace", ...)`，委托
`editor.overlays.open_project_replace()`（命令面板 / `:project-replace`
可达）。

### 3.5 `yate/keymaps/vsc.py`

search 组（L100 `_k("<f4>", "replace", ...)` 之后）追加：

```python
_k("<ctrl-h>", "project_replace", "Find & replace in project (ctrl+h)", SRCH),
```

### 3.6 `yate/keymaps/vim.py`

CMD 组（L186 `KeyBinding(parse_key("<f4>"), "replace", ...)` 之后）追加：

```python
KeyBinding(parse_key("<ctrl-h>"), "project_replace",
    "Find & replace in project (ctrl+h)", CMD),
```

**生效路径（F11 静态论证）**：`"\x08"` 不属于 `\x1f` 分支与
`_FUNCTION_KEYS`（L71，仅 F1-F12）→ `_handle_normal`（L452）→ 内置
normal 分支均不匹配 → 落 `_extension_binding`（L693）→ 查全量 `_index`
且只排除字面 `category != "general"`（L231-244）→ `CMD = "Vim: command"`
命中 dispatch。pilot 用例为回归锚点而非验证赌注。

### 3.7 `tests/test_architecture.py`

`UI_FROZEN_FILES["flows/overlay_flows.py"]` 的模块集合追加
`"yate.editor_view.find_replace",`（F13：精确集合，不追加即架构测试红）。

## 四、输出

- ctrl+h 在 vsc 全模式与 vim normal 模式打开 FindReplaceScreen；
- `:project-replace` 命令可达；冻结面登记完整。

## 五、测试用例（追加 `tests/test_app_find_replace.py`；接线类，本波先行落地，plan-e 全量回归）

| 用例 | 前置与操作 | 断言 |
|---|---|---|
| `test_ctrl_h_opens_project_replace_vsc` | tmp_path workspace；`YateApp()`；`press ctrl+h` | `type(app.screen).__name__ == "FindReplaceScreen"` |
| `test_ctrl_h_opens_project_replace_vim` | `YateApp(keymap="vim")`；同上 | 同上（F11 运行时锚点） |
| `test_ctrl_h_without_workspace_warns` | 无 target 启动；`ctrl+h` | screen 仍为编辑器；消息含 `no workspace` |
| `test_project_replace_action_registered` | 构造 app | `app.editor.actions.get("project_replace") is not None`（F22：API 是 `get` 非 `lookup`） |
| `test_overlay_push_clears_stale_message` | 先制造 stale 消息再 `ctrl+h` | 打开 overlay 时消息行被 `prompt.idle()` 重置（F12 push 语义） |

## 六、验收命令（该波结束应全绿）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_app_find_replace.py tests/test_app_find.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe -m pytest tests/ -q
```

通过判定：四条退出码 0（全量回归无新红）。

## 七、风险与回滚

- R1 终端歧义：F10 两侧一致 + `test_ctrl_h_opens_project_replace_*` 锚定；
- R7 漏登记：3.7 显式步骤，架构测试兜底；
- 构造顺序风险：`session` 在 `_build_pane_stack` 时已就绪（Editor
  组装顺序：session 先于 pane stack），pyright strict 在接线处推导；
- 回滚：键位两行 + action 一条独立 revert；`open_project_replace` 留守
  不影响既有 overlay 行为。
