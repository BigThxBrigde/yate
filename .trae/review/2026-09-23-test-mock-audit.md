# yate Code Review — 测试 mock 目标核对 — 2026-09-23

## 测试 mock 目标核对 — 2026-09-23

> 来源：分层重构后的大规模机械改路径（`app.doc` → `app.editor.session.doc`）可能造成 mock 目标漏改而**静默失效**
> （patch 目标仍可解析，但被测代码已不从那里查找）。核对判据因此不是"目标是否存在"，而是"**使用点是否经该模块查找**"。

- [x] **22 处 mock 目标（15 个不同目标）全部核对，无静默失效** — `tests/`
  - `yate.app.YateApp` / `yate.config.load_config` / `yate.editor_view.manual.load_changelog_markdown`：
    使用方 `yate/cli.py` 全是**函数内 lazy import**（[`cli.py:155`](../../yate/cli.py) / `:178` / `:229` / `:279`），
    绑定发生在 patch 生效期间 ✓；
  - `yate.logs.crash.install` / `.uninstall`：patch 的是 `CrashService` **实例属性**，cli 经同一实例调用
    （[`cli.py:157`](../../yate/cli.py) / `:216`）✓；
  - `yate.editor.run_shell`：`editor.py` 以模块全局调用（[`editor.py:1081`](../../yate/editor.py) / `:1112`）✓
    —— 即本次评审建议的 `yate.app.run_shell` → `yate.editor.run_shell` 的正确形态，已迁移到位；
  - `yate.diagnostics._section_fonts` / `format_report`：`sections` 列表是 `format_report` 的**函数内局部变量**
    （[`diagnostics.py:84-97`](../../yate/diagnostics.py)），运行时按模块全局解析；`print_report` 同理（`:126`）✓；
  - `yate.editor_syntax.ts_backend.ts_available` / `yate.editor_syntax.resolve_filetype` / `available_filetypes`：
    被测方 [`diagnostics.py:313-316`](../../yate/diagnostics.py) 为**函数内 import** ✓；
  - `yate.editor_lsp.manager.CHANGE_DEBOUNCE_S`：同模块全局使用（[`manager.py:330`](../../yate/editor_lsp/manager.py)）✓；
  - `yate.editor_view.manual.files`：`manual.py` 内 `files(...)` 模块全局 ✓；
  - `yate.editor_term.shells.shutil.which` / `yate.extensions.python_lsp.sys.executable`：
    属"patch 打到真实模块对象"（`shutil` / `sys`），生效但影响面是**全局**，依赖 mock 的自动恢复兜底 ✓；
  - 另有 12 处 `patch.object(<运行期对象>, ...)`（`ts_langs._LANGS`、`app.editor.lsp`、`Workspace.walk_files` 等），
    不依赖字符串路径，天然无重构漂移风险 ✓。
  - 证据：`pytest tests/test_cli.py tests/test_diagnostics.py tests/test_shell.py tests/test_changelog_view.py
    tests/test_lsp.py tests/test_python_lsp_ext.py tests/test_ts_backend.py -q` → **exit 0 全绿**。
  - 结论：`tests/` **无需改动**；核对脚本为临时文件、已删除。
