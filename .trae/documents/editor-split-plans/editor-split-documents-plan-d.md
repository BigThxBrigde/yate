# plan-d：抽取 DocumentFlows（document_flows.py）

> 所属总纲：[overview.md](overview.md) · wave-3（串行，改 editor.py）
> 模式：既有 L3 流程模块形态——构造注入具体协作者、不向上依赖。
> 行号锚点：wave-2（删薄委托）后 editor.py 1425→1196 行，2026-09-29 实测 grep
> 复核并更新；成员集、调用点、装配点与原方案一致，仅行号偏移。

## 一、职责与迁移清单

**文档生命周期**（editor.py:473-721 + 提示项两方法），19 个成员整体迁移：

| 成员 | 行号（wave-2 后实测） |
|---|---|
| open_target / _apply_session_readonly | 473-483 / 485-498 |
| activate_doc / _open_document / _open_document_async / open_document | 500-541 |
| open_path / open_path_async / open_path_later | 543-591 |
| new_buffer / show_welcome / close_tab / cycle_tab | 593-652 |
| save_document / prompt_save_as / save_as / _submit_save_as | 654-721 |
| prompt_open / _submit_open（`:e` 路径提示，属打开流程） | 1050-1061 |

## 二、构造签名与装配

```python
DocumentFlows(
    app, session, workspace, panes, lsp,
    explorer_tree,        # editor_view.explorer.ExplorerTree（刷新树）
    prompt_bar,           # editor_view.commandline.PromptBar（save/open 提示）
    completion,           # CompletionFlows（open/close 后收起弹窗）
    message, report,      # Callable（report = Editor._report 缓冲版）
    refresh_ui,           # Callable
    startup_readonly,     # bool（--readonly 旗标，构造期快照）
)
```

装配点：`_build_pane_stack` 尾部（completion 之后）
`ed.document_flows = DocumentFlows(...)`；类注解区加 `document_flows: DocumentFlows`。

**规则同步**（总纲 §六矩阵）：document_flows.py import `yate.editor_view.panes` /
`explorer` / `commandline` → `tests/test_architecture.py` UI_FROZEN_FILES 增条目
（同 lsp_sync/prompt_flows 先例）；architecture-boundaries.md §一 L3 清单补
`document_flows.py`、R11 白名单文本同步。

## 三、调用方改直调（grep 驱动，断言语义不变）

- **editor.py**：装配 `_open_startup_target`（:155-166，:158 取 `ed.open_target`）→
  `ed.document_flows.open_target`；
  :141（explorer_tree open_path 注入）、:213（OverlayFlows open_path 注入）、
  :341（extension_context open_path）→ `ed.document_flows.open_path_later`；
  :898/:916（split 流程内 open_path/open_path_async）→ `self.document_flows.*`
  （plan-e 收口为注入对象，回填记录）。
- **actions.py / commands.py**：grep
  `editor\.(open_path|open_document|new_buffer|show_welcome|close_tab|cycle_tab|save_document|save_as|prompt_open|activate_doc|open_target)`
  逐处 → `editor.document_flows.<同名>`。
- **tests/**：同 grep 清单逐处改（test_app_textual 为主）。
- Editor 上旧方法随迁**删除**（不留转发）。

## 四、验收命令（退出码 0；探针退出码 1 = 通过）

```powershell
d:\Programming\yate-editor-refactoring\.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
d:\Programming\yate-editor-refactoring\.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
d:\Programming\yate-editor-refactoring\.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
git grep -n -I "editor\.\(open_path\|open_document\|new_buffer\|show_welcome\|close_tab\|cycle_tab\|save_document\|save_as\|prompt_open\|activate_doc\|open_target\)" -- yate tests
```

另跑 textual-pilot-smoke 全量（打开/保存/关闭/换页场景覆盖）。

## 五、提交

单笔：`refactor(editor): extract document lifecycle flows`。

## 六、风险与回滚

| 风险 | 缓解 |
|---|---|
| 依赖环 DocumentFlows↔WindowFlows | 单向：WindowFlows 注入 DocumentFlows 具体对象；split 路径本波经 editor 转接、plan-e 收口并回填 |
| `_report` 缓冲语义丢失 | 注入 `report=ed._report`，语义逐字保留 |
| startup_readonly 快照时机 | 构造期传值（`--readonly` 仅启动期生效） |
| 回滚 | 单笔提交 `git revert` |
