# plan-c：删除全部薄委托/薄壳（delegates）

> **实施状态**：✅ 已实施 —— 2026-10-05 全量核对：文档自述与代码产物一致。
> `ShellFlows`/`OverlayFlows`/`CompletionFlows` 命名。行号基于 `07004a0`，改名波
> 不改行号结构，执行时以实测为准）
> 机制依据：architecture-boundaries §四第 1 行「1:1 直调具体协作者的方法」。
> **行为零变更，不新增测试用例**。

## 一、输入（HEAD `07004a0` 实测）

| 项 | 证据 |
|---|---|
| prompt_flows 6 委托 | editor.py:1064-1086 |
| `shell_prompt` 流程入口（唯一外部调用 actions.py:147） | editor.py:1056-1062 |
| shell 2 委托（run_shell_command_later 全仓零调用方） | editor.py:1209-1213、1215-1217 |
| `install_font` 委托（外部 commands.py:287） | editor.py:1242-1244 |
| completion 3 委托（全部仅 editor 内部调用：close ×6 于 :546/566/588/615/635/1025、request :746、accept :760） | editor.py:1258-1274 |
| lsp 1 委托（commands.py:284） | editor.py:1278-1280 |
| overlays 7 委托（push_overlay 零调用方；外部 actions.py:141/142/146/150/154、commands.py:122/125/255/258/261、内部 :780/:802） | editor.py:1284-1314 |
| `refresh_explorer` 委托（唯一调用方 set_show_hidden:1325） | editor.py:1318-1320 |
| `prompt_completions` 组装壳（PromptBar 接线 :132；tests 5 处） | editor.py:1100-1108；test_app_textual.py:2295/2427/2432/2435/2438 |
| actions.py 12 处 / commands.py 8 处 | actions.py:132-135/140/141/142/146/147/150/154；commands.py:122/125/255/258/261/284/287 |
| 时序约束：extension_context 早于 shell 构造 | editor.py:117-118、307-310、324（总纲 §四） |
| `Screen` / `ShellResult` 删后零残留 | editor.py:30+1286、64+1211 |
| KeyUi 2 字段引用委托（早于 prompt_flows 构造） | editor.py:119-126 |
| ShellFlows 已持有 `prompt`；`run_later(str)` 与 PromptBar `on_submit(str)` 直配 | shell_flows.py:37/47/70 |

## 二、独占文件清单（只改这些）

`yate/editor.py`、`yate/shell_flows.py`、`yate/completion.py`、`yate/actions.py`、
`yate/commands.py`、`tests/test_app_textual.py`、`tests/test_changelog_view.py`、
`tests/test_action_table.py`、`.trae/rules/architecture-boundaries.md`（仅 :149）。

## 三、步骤

1. **editor.py 删 23 个薄委托/薄壳**（§一行号）：prompt_flows 6、shell_prompt、
   shell 2、install_font、completion 3、show_diagnostics、overlays 7、
   refresh_explorer、prompt_completions 方法体。删孤儿节头 `# === lsp` /
   `# === overlays`；`_build_pane_stack` docstring 去 "thin delegating methods"。
2. **ShellFlows.open_prompt()**（`run_later` 后新增，`on_submit=self.run_later`
   直绑零 lambda；动作名 `shell_prompt` 不改）：
   ```python
   def open_prompt(self) -> None:
       """Open the shell prompt (``:!`` / F2)."""
       self.prompt.activate(
           "shell", placeholder="shell command", on_submit=self.run_later,
       )
   ```
3. **completion 只读兜底内聚**：CompletionFlows 接住 `BufferReadOnlyError`
   （构造补 `readonly_notice: Callable[[], None]` 注入，refresh 已有）——accept
   路径自行 notice+refresh，Editor 的 accept_completion 壳随之消失。
4. **prompt_completions 直绑**：`_build_widgets` :132 改
   `partial(prompt_completions, commands=ed.commands, session=ed.session,
   workspace=ed.workspace)`（零 lambda；partial 已 import）。
5. **KeyUi 后置工厂**：删 `_build_models` :119-126；`__init__` :310 后调
   `_build_key_ui(self)`，`find_prompt=ed.prompt_flows.find_prompt`、
   `goto_prompt=ed.prompt_flows.goto_prompt` 直绑。
6. **editor 内部调用点**：:746 → `self.completion.request(manual=True)`；
   :760 → `self.completion.accept()`；:780/:802 → `self.overlays.open_command_palette()`
   / `open_file_palette()`；:1230 → `self.prompt_flows.goto_line_command(text)`；
   :1325 → `self.explorer_tree.refresh_tree()`；:324 → 总纲 §四 lambda；
   :546/566/588/615/635/1025 → `self.completion.close()`。
7. **actions.py 12 处 / commands.py 8 处**：prompt_flows 5 处（actions :132-135/140）
   → `editor.prompt_flows.<同名>`；overlays 10 处（actions :141/142/146/150/154、
   commands :122/125/255/258/261）→ `editor.overlays.<同名>`；shell 2 处
   （actions :147 → `editor.shell.open_prompt()`、commands :287 →
   `editor.shell.install_font()`）；lsp 1 处（commands :284 →
   `editor.lsp_sync.show_diagnostics()`）。
8. **tests**：test_app_textual :630/794 → `overlays.open_file_palette`、
   :707/742/767 → `overlays.open_command_palette`、:2557 → `prompt_flows.goto_prompt`、
   :2682 → `prompt_flows.find_next`、:2295/2427-2438 → 直调模块函数
   `prompt_completions(..., commands=app.editor.commands, session=…, workspace=…)`；
   test_changelog_view :152/168/178/187 → `editor.overlays.*`；test_action_table
   recorder 最小适配（子记录器，断言集合不变）。
9. **规则同步**：architecture-boundaries.md:149 删 `run_shell_command_later`
   示例字样（§四异步任务行）。
10. 删 import：editor.py:30 `Screen`、:64 `ShellResult`。

## 四、验收命令（全部退出码 0；探针退出码 1 = 通过）

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
git grep -n -I "editor\.find_prompt\|editor\.find_next\|editor\.replace_prompt\|editor\.goto_prompt\|editor\.goto_line\|editor\.show_\|editor\.push_overlay\|editor\.open_file_palette\|editor\.open_command_palette\|editor\.toggle_screensaver\|editor\.run_shell_command\|editor\.shell_prompt()\|editor\.install_font\|editor\.close_completion\|editor\.request_completion\|editor\.accept_completion\|editor\.refresh_explorer" -- yate tests
```

另按 `textual-pilot-smoke` skill 跑冒烟（基线 932 通过，预期全绿）。

## 五、提交

单笔：`refactor(editor): drop thin delegates and shells, call owners directly`。

## 六、风险与回滚

| 风险 | 缓解 |
|---|---|
| KeyUi 构造顺序 | `_build_key_ui` 置于 `_build_pane_stack` 之后；pyright 兜底 |
| extension_context 早于 shell | 总纲 §四：惯例内 lambda 延迟解析 |
| completion 兜底内聚改变行为 | try/except 语义逐字搬运（notice 文本与 refresh 时机不变）；smoke 覆盖 |
| recorder 适配超预期 | 最小子记录器；断言集合不变 |
| 回滚 | 单笔提交 `git revert` |
