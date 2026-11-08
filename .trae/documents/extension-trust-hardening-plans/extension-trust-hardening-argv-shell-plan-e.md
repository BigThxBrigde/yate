# 子计划 e — S-03 `shell=False` argv 变体与 Lua 面同步（wave-2）

> 唯一规范来源：[overview.md](overview.md) + [主计划](../extension-trust-hardening-plan.md)
> + 本文件。输入素材：[inventory](../extension-trust-hardening-inventory.md) §S-03。
> **硬约束**：`yate/editor.py` 实测 800 行（守卫阈值），本子计划不得修改它；
> 不得新增门面导出名（R14 14 名冻结）；不得改 `run_shell(command: str)` 语义。

## 一、目标与非目标

- 目标：向扩展提供不经 shell 解释的 argv 形态执行能力
  （`services.shell.run_argv` / `ExtensionAPI.shell_argv` / `yate.shell_argv`），
  与既有 `shell=True` 接口并存；`:!` / `api.shell` 保持原样，仅在文档中标注
  为完全权限接口。
- 非目标：不改 `ExtensionContext`（避免 `editor.py` 接线超 800 行）、不新增
  `ShellFlows.run_argv` 死方法、不给 `api.shell` 增加交互确认、不引入
  `Protocol` / 新类型层、不改 `tools/pack/wiki` 的 shell 用法。

## 二、独占文件清单

1. `yate/services/shell.py`
2. `yate/flows/shell_flows.py`
3. `yate/services/extensions/api.py`
4. `yate/extensions/_yate.lua`
5. `yate/extensions/_yate.d.lua`
6. `tests/test_shell.py`
7. `tests/test_shell_flows.py`
8. `tests/test_extension_api.py`
9. `tests/test_lua_defs.py`

## 三、具体改动

### 3.1 `yate/services/shell.py:1-122`

- `from collections.abc import Sequence` 加入标准库导入组（字母序）。
- 新增 L0 纯函数（cwd 语义单一事实来源）：
  ```python
  def shell_cwd(workspace_root: Path | None, document_dir: Path | None) -> Path:
      """Pick the command working directory: workspace / document / process."""
      return workspace_root or document_dir or Path.cwd()
  ```
- 把 `run_shell()` 中 `:87-117` 的 communicate / 超时 / `_kill_tree` / 有界
  排水 / `ShellResult` 组装**原样**抽为私有函数：
  ```python
  def _capture(
      proc: subprocess.Popen[str], label: str, workdir: Path, timeout: float
  ) -> ShellResult: ...
  ```
  行为、消息（`"command timed out after {timeout}s"`）、返回码 124、日志点
  一个字不改；`ShellResult.command` 改由 `label` 传入。
- 抽出 `_popen(command: str | list[str], *, shell: bool, workdir: Path) -> subprocess.Popen[str]`：
  搬运现有 9 个 Popen 关键字参数（`cwd=str(workdir)`、`stdout/stderr=PIPE`、
  `text=True`、`encoding="utf-8"`、`errors="replace"`、
  `start_new_session=not sys.platform.startswith("win")`）。若 pyright strict
  对 `str | list[str]` 联合的 `Popen` 重载报诊断，用 `cast()` 按
  `python-coding-style.md` §4.4 显式窄化，不得写 `# type: ignore`。
- `run_shell()` 保持签名与 docstring 语义：`workdir = Path(cwd) if ...`；
  `try: proc = _popen(command, shell=True, workdir=workdir) except OSError`
  仍返回 `ShellResult(command, 1, f"[yate] failed to run shell: {exc}", workdir)`；
  否则 `return _capture(proc, command, workdir, timeout)`。
- 新增：
  ```python
  def run_argv(
      argv: Sequence[str], cwd: Path | None = None, timeout: float = 60.0
  ) -> ShellResult:
      """Run *argv* as a program vector (``shell=False``), capturing output."""
  ```
  - `args = list(argv)`；空向量 `raise ValueError("argv must contain at least one element")`；
  - `workdir = Path(cwd) if cwd is not None else Path.cwd()`；
  - `label = " ".join(args)`（`ShellResult.command` 为展示用标签，不是可执行串）；
  - `_popen(args, shell=False, workdir=workdir)`；`OSError` →
    `ShellResult(label, 1, f"[yate] failed to run command: {exc}", workdir)`；
  - 其余交给 `_capture(...)`，因此超时杀进程树行为与 `run_shell` 完全一致；
  - docstring 明确：这是**避免 shell 元字符解释**的变体，不是降权沙箱，
    进程仍以当前用户权限运行。
- 文件行数预计 ~175 行，远低于 800；不改 `PRINT_EXEMPT_SITES`（无 `print()`）。

### 3.2 `yate/flows/shell_flows.py:13-22, 109-116`

- `from collections.abc import Callable, Sequence`? 本模块不需要 `Sequence`
  （不新增流方法），保持 `Callable` 即可。
- 导入行 `:22` 改为
  `from yate.services.shell import ShellResult, run_shell, shell_cwd, shell_name`。
- `_cwd()` 改为调用 L0 单一来源，行为等价：
  ```python
      def _cwd(self) -> Path:
          """The working directory for shell commands (workspace / file / cwd)."""
          doc = self.session.doc
          return shell_cwd(
              self.workspace.root,
              doc.path.parent if doc.path is not None else None,
          )
  ```
- **不新增** `run_argv` 方法（无调用方，会是死代码）；不触碰 `run_async` /
  `_show_result` / 字体安装。

### 3.3 `yate/services/extensions/api.py:14, 49, 614-622`

- `from collections.abc import Callable, Sequence`。
- `from yate.services.shell import ShellResult, run_argv, shell_cwd`。
- 在 `# ---- services` 区 `shell()` 之后新增方法：
  ```python
      def shell_argv(self, argv: Sequence[str]) -> ShellResult | None:
          """Run *argv* without a shell; no metacharacter interpretation."""
          doc = self._ctx.session.doc
          cwd = shell_cwd(
              self._ctx.workspace.root,
              doc.path.parent if doc.path is not None else None,
          )
          return run_argv(argv, cwd=cwd)
  ```
  docstring 说明：与 :meth:`shell` 一样是同步、静默、完全权限接口；差别仅在
  不经过系统 shell；失败时 `run_argv` 返回带非零码的 `ShellResult`，
  空向量按 `ValueError` 显式报错。
- 不改 `ExtensionContext`、不改 `services/extensions/__init__.py` 的
  `__all__`（R14 冻结）、不改任何 bridge。

### 3.4 Lua 面（三文件同步）

- `yate/extensions/_yate.lua`：
  - 顶部 "Exported functions" 列表（`:64-86`）在 `shell(cmd)` 行后加
    `shell_argv(argv)    run an argv vector without shell interpretation`；
  - 在 `yate.shell` 定义（`:145-152`）之后新增：
    ```lua
    -- Run a program vector synchronously (shell=False, no metacharacter
    -- interpretation). Still runs with the full permissions of the host.
    ---@param argv string[]
    ---@return any result
    function yate.shell_argv(argv)
      return api.shell_argv(argv)
    end
    ```
    注释全英文 ASCII；`---@param` / `---@return` 与既有风格一致。
- `yate/extensions/_yate.d.lua`：在 `yate.shell` 声明（`:52-57`）之后镜像
  同样的注释与 `function yate.shell_argv(argv) end`。
- `tests/test_lua_defs.py`：`LUA_SURFACE`（`:33-63`）与 `PYTHON_SURFACE`
  （`:68-93`）各加入 `"shell_argv"`；三条既有静态守护用例不改。

### 3.5 测试

**`tests/test_shell.py`**（先读 `:1-330` 既有夹具与 `_WINDOWS` 形态）：

- `test_run_argv_captures_stdout_and_success(tmp_path)`：
  `run_argv([sys.executable, "-c", "print('argv-ok')"], cwd=tmp_path)` →
  `ok is True`、`"argv-ok" in output`、`cwd == tmp_path`、
  `command == " ".join([...])`。
- `test_run_argv_does_not_interpret_shell_metacharacters(tmp_path)`：
  `payload = "a & echo INJECTED"`；
  `run_argv([sys.executable, "-c", "import sys; print(sys.argv[1])", payload], cwd=tmp_path)`；
  断言输出中 `payload` 作为完整一行出现、`INJECTED` 没有被 shell 当作新命令
  （可用 `result.returncode == 0` + `payload in result.output.splitlines()` +
  `"is not recognized" not in result.output` 组合）。
- `test_run_argv_rejects_empty_argv()`：`pytest.raises(ValueError, match="at least one")`。
- `test_run_argv_reports_missing_executable(monkeypatch)`：monkeypatch
  `yate.services.shell.subprocess.Popen` 抛 `OSError("nope")` → 返回
  `ShellResult` rc 1、output 含 `failed to run command`；用后自动还原。
- `test_shell_cwd_prefers_workspace_root(tmp_path)`：`shell_cwd(tmp_path, other) == tmp_path`；
  `shell_cwd(None, other) == other`；`shell_cwd(None, None) == Path.cwd()`。
- 既有 `run_shell` 全套用例（含 timeout / taskkill / 20s grandchild 探针）
  **一条不改**，作为 `_capture` 行为等价的回归锚点。

**`tests/test_shell_flows.py`**：

- 新增 `test_cwd_uses_the_shared_shell_cwd_helper()`：构造既有 fixture 形的
  `ShellFlows`（参考 `:103 test_run_gates_output_overlay_on_show_output_and_mounted`），
  设置 `workspace.set_root(tmp_path)` 与带路径的 doc，断言 `_cwd()` 等于
  workspace root；再断言 `shell_flows.shell_cwd(...)` 同值（本文件已有
  `from yate.flows import shell_flows` 模块引用）。
- 不 stub 新的 `run_argv`：既有 `run_shell` stub 形态保持不变。

**`tests/test_extension_api.py`**：

- 新增 `test_shell_argv_runs_without_shell_metacharacter_interpretation()`：
  用本文件 `_extension_api()` 构造真实 `ExtensionAPI`；
  `api.shell_argv([sys.executable, "-c", "import sys; print(sys.argv[1])", "a & echo INJECTED"])`；
  断言返回非 None、`returncode == 0`、输出含完整 payload、`ok is True`。
- 新增 `test_shell_argv_rejects_empty_vector()`：`pytest.raises(ValueError)`；
  `ValueError` 必须在任何 `Popen` 之前抛出（可 monkeypatch `_popen` 计数断言 0 次）。
- 不修改 `_extension_api()` 夹具（`ExtensionContext` 未变，无需新回调）。

## 四、验收命令（可复制执行，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright yate/services/shell.py yate/flows/shell_flows.py yate/services/extensions/api.py tests/test_shell.py tests/test_shell_flows.py tests/test_extension_api.py tests/test_lua_defs.py
.venv\Scripts\python.exe -m pytest tests/test_shell.py tests/test_shell_flows.py tests/test_extension_api.py tests/test_lua_defs.py tests/test_lua_layout.py tests/test_lua_lint.py -q
.venv\Scripts\python.exe -m pytest tests/test_shell.py tests/test_extension_api.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

不跑 `tests/test_lua_engine.py` / `tests/test_lua_extensions.py`（wave-2 由
plan_d 并行修改前者，避免竞态）。通过判定：三条退出码全 0；Lua 三面静态
守护全绿；既有 `run_shell` 超时 / kill-tree 用例无回归。

## 五、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `_capture` 抽取改变超时返回消息 / 有界排水 | 逐行搬运，`test_shell.py` 全量回归 | `git checkout -- <9 个独占文件>` |
| `Popen` 联合类型在 pyright strict 报错 | 用 `cast()` 窄化，禁 `# type: ignore` | 拆成两个 `_popen` 分支（需上报主代理） |
| `api.shell_argv` 直接调 L0 被视为绕过 flow 层 | L3→L0 是允许方向；cwd 语义由 L0 `shell_cwd` 与 `ShellFlows._cwd()` 共用，无 UI 行为可绕过 | 恢复 `api.shell_argv` 但保留服务层（需重新设计） |
| Lua 面新增函数触发 `test_lua_defs.py` 三守护 | 三文件同批加名 | 同上 |
| `_yate.lua` 注释非 ASCII / lint 失败 | 全英文 ASCII，`test_lua_lint.py` 回归 | 改注释 |

## 六、报告格式

改动清单、实跑命令与退出码、pyright 诊断数、未解决项与原因；计划外情况停下上报。
