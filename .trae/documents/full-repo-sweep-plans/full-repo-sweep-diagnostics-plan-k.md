# R3：移除 diagnostics 对 Editor 的反向依赖（计划 k）

> **实施状态**：✅ 已实施 —— 2026-11-20（`dd61c63f` + `8a247d98`，headless import 无 editor）

父计划：[../full-repo-sweep-plan.md](../full-repo-sweep-plan.md)。

## 输入

`../../../yate/diagnostics.py:25` 从 `yate.editor` 导入 `Editor`；六个签名（`:82,131,268,298,355,399`）和八处属性读取（`:271,299,368,371,375,382,400,401`）依赖它。`../../../yate/cli.py:31-32,507-525` 先构建 app，再调用 `diagnostics.print_report(app.editor)`。架构图只画了 `ED -> DIAG`。`tests/test_diagnostics.py` 有 53+ 个调用点使用 `format_report(app.editor)` / `print_report(app.editor)`。

## 独占文件

- `../../../yate/diagnostics.py`
- `../../../yate/cli.py`
- `../../../tests/test_diagnostics.py`

## 设计

1. 在 `diagnostics.py` 中定义一个冻结的 `DiagnosticsInput` dataclass，其显式字段从八处读取收集而来：`config: YateConfig`、`ext_dirs: tuple[Path, ...]`、`ext_files: tuple[Path, ...]`、`loaded_extensions: tuple[<registered record type>, ...]`、`lsp_configs: tuple[<LSP config type>, ...]`、`lsp_states: dict[str, <LSP state type>]`。导入这些具体的叶子类型（不用 `Protocol`、不用 `TYPE_CHECKING`、不用 `Any`）；仅当顶层导入会产生循环时才使用局部导入，并在 docstring 中说明原因。
2. 修改 `format_report`、`print_report`、`_section_yaterc`、`_section_config`、`_section_extensions`、`_section_lsp` 使其接受 `DiagnosticsInput`。保持所有报告文本、章节顺序、着色和错误降级行为逐字节不变。
3. 在 `cli.py` 的 L4 调用点、`load_extensions()` / `register_configured_servers()` 之后构建快照：一个小型私有助手 `_diagnostics_input(editor)` 从活动 editor 构造 `DiagnosticsInput`。本波次之后 `diagnostics.py` 中不得再有 `from yate.editor import Editor`。
4. 通过一个测试侧助手 `_snapshot(editor: Editor) -> diagnostics.DiagnosticsInput` 更新 `tests/test_diagnostics.py` 中的所有调用点；将 `format_report(app.editor)` 替换为 `format_report(_snapshot(app.editor))`，`print_report` 同理。不改动任何断言字符串。
5. **仅当**计划 g 已添加说明时，才更新 `../../rules/architecture-boundaries.md` 中的架构依赖图；否则将所需的那一行图修改上报给主代理，而不要在此编辑规则文件（文件归属属于计划 g）。

## 测试

- 现有 50+ 个报告测试必须在预期文本不变的情况下通过（页眉、十二个章节、彩色/纯文本输出、探针失败降级）。
- `test_diagnostics_input_snapshot_is_read_only`：构造一个 `DiagnosticsInput`，尝试修改 tuple 字段（断言 `AttributeError`/不可变性），并确认在修改来源 editor 的无关状态前后 `format_report` 输出相同。
- `test_diagnostics_module_does_not_import_editor`：`../../../tests/test_architecture.py` 中的 AST/文本断言归计划 g 所有；若本波次在该守卫之前落地，则在 `tests/test_diagnostics.py` 内以模块级源码扫描的形式添加该断言，使这条新边不会在此回退。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest tests/test_diagnostics.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/diagnostics.py yate/cli.py tests/test_diagnostics.py
.venv\Scripts\python.exe -c "import sys, yate.diagnostics; assert 'yate.editor' not in sys.modules"
```

最后一条命令必须 exit 0（证明 headless 导入不再拖入 TUI 栈）。

## 风险 / 回滚

风险：50+ 个测试调用点以及细微的报告文本漂移。回滚：恢复 `Editor` 签名和旧的测试调用点；如有需要，快照 dataclass 可以保留但不用。
