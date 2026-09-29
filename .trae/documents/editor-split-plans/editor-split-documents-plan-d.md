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

## 七、执行记录（wave-3，2026-09-29）

**实测数字**：editor.py 1196 → **989** 行（新 document_flows.py 309 行）；pyright 0 诊断；
pytest 全绿 cov **90.69%**；架构测试 **20/20**；探针 `git grep editor\.(open_path|…)`
退出码 1（零残留）；冒烟 **932/932（89 场景）**。提交：`refactor(editor): extract
document lifecycle flows`。

**偏离计划（均附实测依据）**：

1. **构造时序修正（§二装配点不成立）**：`_open_startup_target` 在 `_build_pane_stack`
   之前运行（PaneManager 以 `ed.session.doc` 播种首叶，editor.py:201-207），故
   DocumentFlows 改在 **`_build_widgets` 尾部**构造；`panes`/`completion` 经二段
   `attach_pane_stack(panes, completion)` 注入（`_build_pane_stack` 尾、CompletionFlows
   之后）。先例：`PaneManager.attach(host)`。
2. **§二签名补 `mounted`/`reveal_explorer` 两个 Callable**：原签名漏了
   `self.mounted`（5 处分支）与 `explorer_visible=True + sync_explorer_visibility()`
   （open_path 目录分支）；Editor 新增 2 行方法 `reveal_explorer`（自有侧栏状态，非委托）。
3. **ExplorerTree.open_path 晚挂**：explorer 先于 flows 构造，原「:141 直接改注入」
   不成立——参数改 `Callable[[Path], None] | None = None`，调用点 :348/:514 加 None
   守卫，`_build_widgets` 内 `ed.explorer_tree.open_path = ed.document_flows.open_path_later`
   （与 plan-e 的 window_prefix 晚挂同型）。
4. **TabBar 构造后移**：`on_activate` 绑 `document_flows.activate_doc`，故 TabBar 在
   flows 之后构造（compose 顺序不受影响，R9 id 不变）。
5. **extension_context 前向 lambda**：`open_path`/`save` 在 `_build_models` 期消费，
   flows 尚未存在——`lambda path: self.document_flows.open_path_later(path)` /
   `lambda: self.document_flows.save_document()`，与既有 `run_shell` 前向引用同型。
6. **`Editor._report` 改公开 `report`**：迁移后 editor.py 内无剩余调用者，唯一消费点
   是工厂注入（`report=ed._report` 触发 pyright reportPrivateUsage）；语义逐字保留。
7. **message 回调对齐模块约定**：`Callable[[str, str], None]`（prompt_flows/overlays/
   lsp_sync/shell_flows 同型），原 1 参调用补 `"info"` 位置实参，语义不变。
8. **调用方清单补遗**（§三 grep 清单漏 `open_path_later`）：commands.py:102（`:e FILE`）、
   test_app_textual.py:4449（OverlayFlows 桩注入）、tools/smoke_test/scenarios 7 处
   （files×2 / explorer / stress×2 / regression×2）；test_action_table.py 的 recorder
   桩：`FORWARDED_HOOKS` 5 个钩子转 `document_flows.*` 点路径、`_FLOW_NAMESPACES`
   增 `document_flows`（断言语义不变）。
