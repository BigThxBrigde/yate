# diff-tool-integration-plan-c（wave-3：L3/L4 集成 + 架构守卫登记）

主计划：[../diff-tool-plan.md](../diff-tool-plan.md) · 总纲：[overview.md](overview.md)
前置：wave-1、wave-2 验收通过（`DiffScreen` 可独立构造运行）。

## 输入

- 设计决策 D7/D8（落位表、启动时序）；事实 F1/F2/F9/F10。
- 触碰的边界条款：**R11**（overlays.py 新增 `editor_view` 导入须登记）、R5/R7（commands 单向 import editor；装表仍只在 app.py）、R1（cli 改动不新增 app importer）、R12（新代码走 tracing 惰性 %）。

## 独占文件清单

| 文件 | 动作 |
|---|---|
| `yate/overlays.py` | 修改（新增 `open_diff`） |
| `yate/commands.py` | 修改（新增 `:diff`） |
| `yate/cli.py` | 修改（新增 `--diff` / `--3way` / `--2way`） |
| `yate/app.py` | 修改（CLI 请求转交 + on_mount 触发） |
| `tests/test_architecture.py` | 修改（R11 登记 + R4 守卫面扩大） |
| `tests/test_cli.py` | 修改（CLI 校验用例） |
| `tests/test_diff_integration.py` | 新增（pilot 集成冒烟） |

## 具体修改

### 1. [overlays.py](../../yate/overlays.py) — `OverlayFlows.open_diff`

- 导入区（:11-28）新增：`from yate.editor_view.diffview import DiffScreen` 与 `from yate.editor_core.document import Document`。前者触发 **R11 登记**（见第 5 步）；`Workspace.is_text_file` 已可用（`Workspace` 已导入于 :28）。
- 新方法置于 `open_command_palette`（:111-114）与 `_palette` 之间：

```python
def open_diff(self, paths: list[Path]) -> None:
    """Open the two- or three-way diff overlay for *paths*.

    Mode is derived from the count (2 -> 2way, 3 -> 3way with the
    base/local/remote order).  Missing, non-text or oversized files are
    refused on the message line; the screen never opens half-configured.
    """
```

行为（顺序固定）：
1. `if not self._mounted(): return`；`if isinstance(self._current_screen(), DiffScreen): return`（复用 `_open_doc` :102 的防重入模式）。
2. 数量校验：`len(paths)` 不为 2/3 → `self._message("usage: :diff [--3way] FILE1 FILE2 [FILE3]", "warn")` 并返回。
3. 逐路径：不存在 → message `"no such file: <p>"` 返回；`Workspace.is_text_file(p)` 为假 → `"not a text file: <name>"` 返回。
4. `docs = [Document.open(p) for p in paths]`（同步读盘，risk R-2 由下一行兜底）；任一 `doc.buffer.line_count > MAX_DIFF_LINES`（plan-b 导出常量）→ message `"file too large for diff view: <name> (>20000 lines)"` 返回。
5. `self.push(DiffScreen(docs, mode="3way" if len(docs) == 3 else "2way", keymaps=self.keymaps, labels=[...角色标签 base/local/remote 或 left/right]))`。
- 不新增注入依赖：push_screen/prompt/message/mounted/current_screen/keymaps 均为既有构造参数（:34-70）——能力注入条款（IKJB0Q）无需新边。

### 2. [commands.py](../../yate/commands.py) — `:diff`

- 在 "explorer / terminal / diagnostics" 段（:272-295）后新增 "diff" 小节：

```python
def _diff(args: str) -> None:
    tokens = args.split()
    three = False
    names: list[str] = []
    for token in tokens:
        if token in ("-3", "--3way"):
            three = True
        else:
            names.append(token)
    if len(names) == 2 and three:
        editor.message("--3way needs three files", kind="warn")
        return
    if len(names) not in (2, 3):
        editor.message("usage: :diff [--3way] FILE1 FILE2 [FILE3]", kind="warn")
        return
    editor.overlays.open_diff([Path(p) for p in names])

reg("diff", _diff, "compare files in a diff view (:diff [--3way] F1 F2 [F3])")
```

- R5/R7 不受影响：仍只 import editor（:13），app.py 仍是唯一装表者（守卫 `test_shell_loads_the_builtin_tables` 的 importer 断言不涉 commands 内部）。

### 3. [cli.py](../../yate/cli.py) — `--diff`

- `build_parser()`（:38-174）在 `--diag`（:168-173）后追加：

```python
diff_group = parser.add_mutually_exclusive_group()
diff_group.add_argument("--2way", dest="two_way", action="store_true",
    help="with --diff: force two-way compare (default)")
diff_group.add_argument("--3way", dest="three_way", action="store_true",
    help="with --diff: three-way compare (base local remote)")
parser.add_argument("--diff", dest="diff_files", nargs="+", metavar="FILE",
    help="open the diff view instead of the editor: 2 files = two-way, "
         "3 files = three-way (base local remote)")
```

- epilog（:44-63）追加示例行：`yate --diff old.py new.py    compare two files in the diff view`。
- `main()` 在 `args = parser.parse_args(argv)`（:194）后追加校验（沿用 parser.error → 退出码 2）：

```python
if args.diff_files:
    if args.path:
        parser.error("--diff cannot be combined with a startup path argument")
    if len(args.diff_files) not in (2, 3):
        parser.error("--diff expects 2 or 3 files")
    if len(args.diff_files) == 2 and args.three_way:
        parser.error("--3way requires three files")
    if len(args.diff_files) == 3 and args.two_way:
        parser.error("--2way requires exactly two files")
```

- `YateApp(...)` 两处构造（--diag 分支 :326-334 与正常分支 :340-348）均增 keyword：`diff_files=[Path(p) for p in args.diff_files] if args.diff_files else None`（--diag 分支同样传入以保持构造路径一致，但 diag 不进入 TUI、不触发推送）。
- R1 不变：仍只有 cli.py import yate.app。

### 4. [app.py](../../yate/app.py) — 转交与触发

- `__init__`（:85-95）签名追加 `diff_files: list[Path] | None = None`（`--3way` 语义已由文件数承载，不再传布尔）；存 `self._diff_files = diff_files`。
- `on_mount`（:180-200）在 `await self.editor.on_mount()`（:200）之后追加：

```python
if self._diff_files:
    self.call_after_refresh(
        self.editor.overlays.open_diff, self._diff_files
    )
```

`call_after_refresh` 保证基屏已完成首轮布局后再 push（与 poll_idle 的 screen 类型判断同层安全）。

### 5. [test_architecture.py](../../tests/test_architecture.py) — 守卫登记

- `UI_FROZEN_FILES["overlays.py"]`（:141-148）集合内新增 `"yate.editor_view.diffview"`（R11：先登记后使用，`test_collaborators_keep_widget_coupling_frozen` 自动生效）。
- `UI_FREE_PACKAGES`（:98）追加 `"editor_core"`（R4 守卫面扩大：`editor_core/diff.py` 与整个包从此被"不 import editor_view / 不 import textual.app"两条守卫扫描）。执行顺序：先跑一遍架构测试确认存量 `editor_core` 干净，再落表（回滚 = 删该项）。
- 模块 docstring 的 R4 行（:16-17、:93-97）补一句 `editor_core` 纳管的说明（文档同步义务）。

### 6. `tests/test_cli.py` 追加用例（沿用该文件既有 parser 测试形态）

| 用例 | act | assert |
|---|---|---|
| `test_cli_diff_two_files_defaults_two_way` | `build_parser().parse_args(["--diff", "a", "b"])` | `args.diff_files == ["a", "b"]`；`args.three_way is False` |
| `test_cli_diff_three_files_with_flag_parses` | `parse_args(["--diff", "a", "b", "c", "--3way"])` | `args.diff_files == ["a", "b", "c"]`；`args.three_way is True` |
| `test_cli_diff_rejects_positional_conflict` | `pytest.raises(SystemExit)` 包裹 `parse_args(["f", "--diff", "a", "b"])` | `exc.value.code == 2` |
| `test_cli_diff_rejects_wrong_file_count` | `parse_args(["--diff", "a"])` 于 raises 内 | 退出码 2 |
| `test_cli_three_way_requires_three_files` | `parse_args(["--diff", "a", "b", "--3way"])` | 退出码 2 |
| `test_cli_two_way_rejects_three_files` | `parse_args(["--diff", "a", "b", "c", "--2way"])` | 退出码 2 |
| `test_cli_two_and_three_way_mutually_exclusive` | `parse_args(["--diff", "a", "b", "--2way", "--3way"])` | 退出码 2 |

### 7. `tests/test_diff_integration.py`（新增，pilot 端到端）

宿主：`YateApp(target=tmp_path)` + `app.run_test(size=(100, 30))`（参照 tests/test_app_textual.py 的 YateApp 驱动形态）；临时文件 fixture 与 plan-b 同款。

| 用例 | act | assert |
|---|---|---|
| `test_command_diff_opens_two_way_screen` | `app.editor.run_command(f"diff {f1} {f2}")`；`pilot.pause()` | `isinstance(app.screen, DiffScreen)`；`len(app.screen.query(DiffPane)) == 2` |
| `test_command_diff_three_files_open_three_panes` | `run_command(f"diff {f_base} {f_local} {f_remote}")` | 3 个 DiffPane；regions 含 conflict |
| `test_command_diff_bad_arg_count_stays_on_base` | `run_command("diff onlyone")` | `len(app.screen_stack) == 1`；prompt 行文本含 "usage" |
| `test_command_diff_missing_file_reports_and_stays` | `run_command(f"diff {f1} {nope}")` | screen 栈不变；prompt 行含 "no such file" |
| `test_cli_boot_diff_flag_opens_screen_after_mount` | `YateApp(diff_files=[f1, f2])` run_test；`pilot.pause()` | `isinstance(app.screen, DiffScreen)` |
| `test_diff_close_returns_keys_to_editor` | 打开 diff → `press("escape")` ×2 → `press("x")` | screen 栈回到 1；主 buffer 光标行含 `"x"`（证明 modal 关闭后无按键残留/二次派发，F4+R10） |
| `test_copy_persisted_via_command_flow` | `run_command` 打开后 `press("alt+right")` → `press("ctrl+s")` | 磁盘上 f2 内容 == f1（复制+保存全链路） |

## 验证方案（本计划 + 全量门禁）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_diff_integration.py tests/test_cli.py -q
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
python -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q
```

- 通过判定：全部退出码 0；架构测试含新增守卫面后仍 22 用例全绿（用例数不变，守卫面扩大）。
- 手工验证（真终端）：`yate --diff a.txt b.txt` 目视双栏底色/导航/复制/编辑/Ctrl+S；`yate --diff base local remote --3way` 三栏与 conflict 徽标；`:diff` 无参提示 usage；Esc 二次确认文案。

## 风险与回滚

- R-6 CLI 解析歧义：位置参数冲突即 error（用例锁定）；`nargs="+"` 吞掉后续所有位置参数属预期行为。
- R-7 守卫面扩大误伤：`editor_core` 现状已 UI-free（buffer/document/search/textobjects 均不 import textual/editor_view），落表前先全量跑架构测试确认。
- R-4/R-5 同主计划风险表；集成用例覆盖关闭后按键回落。
- 回滚：本计划单提交（`feat(diff): wire diff view into commands, overlays and cli`），revert 即整体退出集成；plan-a/b 产物无破坏（守卫登记回退一行）。
