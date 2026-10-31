# test-speedup-coverage-plan-c：补强覆盖缺口

**波次**：wave-2（与 plan-b 并行）

## 一、目标

将低于 90% 覆盖率的 yate 文件提升至 90%+，整体覆盖率维持 ≥ 92%。

## 二、非目标

- **不追 `yate/keyproto/driver_windows.py` 覆盖率**（26%）：真机键盘驱动需真实硬件钩子，
  投入产出比极低，显式排除；
- **不追架构守卫测试的覆盖率**（它们已 100% 覆盖自身逻辑）；
- **不为 100% 覆盖率而写无意义测试**（按 `python-coding-style.md` §4.7，
  测试必须验证真实行为）。

## 三、覆盖缺口清单

| 文件 | 当前覆盖率 | 缺失行 | 优先级 |
|---|---|---|---|
| `yate/flows/shell_flows.py` | 63% | 60-67, 73, 98, 127-128, 135-144 | P0 |
| `yate/editor_term/shells.py` | 78% | 49, 72-78 | P0 |
| `yate/flows/extension_flows.py` | 81% | 83-88, 91-93, 102 | P1 |
| `yate/services/user_setup.py` | 81% | 335-336, 365, 372, 375-376, 389-403, 422-439 | P1 |
| `yate/cli.py` | 82% | 269-272, 293-295, 346-353, 405-408, 448, 455, 499 | P1 |
| `yate/editor_view/explorer.py` | 81% | 多处 | P2 |
| `yate/flows/completion_flows.py` | 83% | - | P2 |
| `yate/flows/chunked_flows.py` | 84% | - | P2 |
| `yate/editor_view/terminal.py` | 84% | - | P2 |
| `yate/editor_syntax/engine.py` | 84% | 77-80, 92-93, 209-213 | P2 |
| `yate/editor_lsp/client.py` | 85% | - | P2 |

## 四、实施步骤

### 步骤 1：补强 `yate/flows/shell_flows.py` 覆盖（63% → 90%+）

**新增测试文件**：`tests/test_shell_flows.py`

**缺失行分析**（`yate/flows/shell_flows.py`）：

- L60-67：`run` 方法的 `show_output=False` 分支；
- L73：`run_later` 的空命令分支；
- L98：`run_async` 的空命令分支；
- L127-128, 135-144：`install_font` 与 `_font_async` 的成功/失败分支。

**新增测试用例**：

```python
def test_shell_flows_run_hides_output_when_show_output_false():
    """run(show_output=False) returns result without pushing overlay."""
    # Arrange: construct ShellFlows with mocked collaborators
    # Act: call run("echo hello", show_output=False)
    # Assert: result returned, _push_overlay not called

def test_shell_flows_run_later_rejects_empty_command():
    """run_later("") returns early without spawning worker."""
    # Arrange: construct ShellFlows with mocked spawn
    # Act: call run_later("")
    # Assert: spawn not called

def test_shell_flows_run_async_rejects_empty_command():
    """run_async("") returns None without running."""
    # Arrange: construct ShellFlows
    # Act: await run_async("")
    # Assert: returns None, no message shown

def test_shell_flows_install_font_success():
    """install_font spawns worker and reports success."""
    # Arrange: mock fonts.ensure_font to return success status
    # Act: call install_font(), await worker
    # Assert: _message called with "Nerd Font ready"

def test_shell_flows_install_font_failure():
    """install_font reports error when fonts.ensure_font raises."""
    # Arrange: mock fonts.ensure_font to raise Exception
    # Act: call install_font(), await worker
    # Assert: _message called with "font setup failed: ..."
```

### 步骤 2：补强 `yate/editor_term/shells.py` 覆盖（78% → 90%+）

**新增测试文件**：`tests/test_shells.py`（若不存在）或追加到现有文件

**缺失行分析**（`yate/editor_term/shells.py`）：

- L49：`resolve_shell` 的 Windows 默认路径（`_windows_default`）；
- L72-78：`_posix_default` 的 `$SHELL` / `bash` / `/bin/sh` 分支。

**新增测试用例**：

```python
def test_resolve_shell_windows_default_picks_pwsh():
    """resolve_shell("") on Windows picks pwsh.exe when on PATH."""
    # Arrange: mock sys.platform to "win32", mock shutil.which to return "pwsh"
    # Act: call resolve_shell("")
    # Assert: returns ["pwsh", "-NoLogo"]

def test_resolve_shell_posix_default_picks_shell_env():
    """resolve_shell("") on Unix picks $SHELL when set."""
    # Arrange: mock sys.platform to "linux", mock os.environ["SHELL"]
    # Act: call resolve_shell("")
    # Assert: returns ["/usr/bin/zsh"]

def test_resolve_shell_posix_default_falls_back_to_bash():
    """resolve_shell("") on Unix falls back to bash when $SHELL not set."""
    # Arrange: mock sys.platform to "linux", clear $SHELL, mock shutil.which("bash")
    # Act: call resolve_shell("")
    # Assert: returns ["/usr/bin/bash"]
```

### 步骤 3：补强 `yate/flows/extension_flows.py` 覆盖（81% → 90%+）

**新增测试文件**：`tests/test_extension_flows.py`（若不存在）或追加

**缺失行分析**（`yate/flows/extension_flows.py`）：

- L83-88：`trust_directory` 检测到 cwd 含 symlink 时拒绝并报错；
- L91-93：`trust_directory` 检测到 cwd 无 extensions 子目录时报 info；
- L102：`trust_directory` 报告单个扩展加载失败。

**新增测试用例**：

```python
def test_extension_flows_trust_directory_rejects_symlink():
    """trust_directory refuses cwd with symlink component."""
    # Arrange: construct ExtensionFlows with mocked extension_loader and _message
    # Act: call trust_directory(symlink_cwd) where symlink_cwd contains a symlink
    # Assert: _message called with "refused to trust" error, load_directory not called

def test_extension_flows_trust_directory_reports_missing_extensions_dir():
    """trust_directory reports info when cwd has no extensions/ subdir."""
    # Arrange: construct ExtensionFlows, cwd is a real dir without extensions/
    # Act: call trust_directory(cwd)
    # Assert: _message called with "no extensions directory to load" info

def test_extension_flows_trust_directory_reports_individual_extension_failure():
    """trust_directory reports each extension load failure."""
    # Arrange: mock extension_loader.load_directory to return records with errors
    # Act: call trust_directory(cwd)
    # Assert: _message called with "extension <name>: <error>" for each failure
```

### 步骤 4：补强 `yate/services/user_setup.py` 覆盖（81% → 90%+）

**新增测试文件**：`tests/test_user_setup.py`（若不存在）或追加

**缺失行分析**（`yate/services/user_setup.py`）：

- L335-336：`_interactive` 捕获 `AttributeError` / `OSError` 返回 False；
- L365：`_print_confirmation_prompt` 处理 symlink/other entry（非目录）；
- L372：`_print_confirmation_prompt` 处理 preserved 非 data 目录；
- L375-376：`_print_confirmation_prompt` 无 preserved 且 `include_data=False` 时提示；
- L389-403：`format_setup_report` 渲染 created_dirs / installed_rc / rc_backup /
  refreshed_templates / skipped_templates / errors；
- L422-439：`format_cleanup_report` 渲染 nothing_to_remove / removed_files /
  removed_dirs / preserved / base_removed / errors。

**新增测试用例**：

```python
def test_user_setup_interactive_returns_false_on_attribute_error():
    """_interactive returns False when stream lacks isatty."""
    # Arrange: mock stream_in without isatty method
    # Act: call _interactive(mock_in, mock_out)
    # Assert: returns False

def test_user_setup_interactive_returns_false_on_os_error():
    """_interactive returns False when isatty raises OSError."""
    # Arrange: mock stream_in.isatty to raise OSError
    # Act: call _interactive(mock_in, mock_out)
    # Assert: returns False

def test_user_setup_print_confirmation_prompt_handles_symlink():
    """_print_confirmation_prompt renders symlink entry correctly."""
    # Arrange: create a symlink in tmp_path
    # Act: call _print_confirmation_prompt with the symlink in remove_dirs
    # Assert: output contains "<name>" without file count

def test_user_setup_format_setup_report_renders_all_fields():
    """format_setup_report renders created_dirs, rc, templates, errors."""
    # Arrange: construct SetupReport with all fields populated
    # Act: call format_setup_report(report)
    # Assert: output contains "created", "installed", "refreshed", "skipped", "error"

def test_user_setup_format_cleanup_report_renders_nothing_to_remove():
    """format_cleanup_report renders nothing_to_remove message."""
    # Arrange: construct CleanupReport with nothing_to_remove=True
    # Act: call format_cleanup_report(report)
    # Assert: output contains "no yate-managed configuration"

def test_user_setup_format_cleanup_report_renders_removed_and_preserved():
    """format_cleanup_report renders removed_files, removed_dirs, preserved."""
    # Arrange: construct CleanupReport with removed_files, removed_dirs, preserved
    # Act: call format_cleanup_report(report)
    # Assert: output contains "removed:", "data/ preserved", "preserved (not created by yate)"
```

### 步骤 5：补强 `yate/cli.py` 覆盖（82% → 90%+）

**新增测试文件**：`tests/test_cli.py`（已存在）追加

**缺失行分析**（`yate/cli.py`）：

- L269-272：`_validate_hex_args` 拒绝 `--hex` 与 path / `--diff` 组合；
- L293-295：`_manage_extensions` 捕获 `yxp.YxpError` 并报告失败；
- L346-353：`main` 处理 `--install-font`（lazy import fonts，检查 status，返回 rc）；
- L405-408：`main` 处理 `--yaterc` 显式路径 vs 默认发现；
- L448：`main` 记录 config errors 到 log；
- L455：`main` 处理 `--keymap normal` 映射为 "vsc"；
- L499：`__main__` 入口（`raise SystemExit(main())`）。

**新增测试用例**：

```python
def test_cli_validate_hex_args_rejects_path_combination():
    """_validate_hex_args rejects --hex with startup path."""
    # Arrange: construct args with hex_file=True and path="file.txt"
    # Act: call _validate_hex_args(args, parser)
    # Assert: parser.error called with "--hex cannot be combined"

def test_cli_validate_hex_args_rejects_diff_combination():
    """_validate_hex_args rejects --hex with --diff."""
    # Arrange: construct args with hex_file=True and diff_files=True
    # Act: call _validate_hex_args(args, parser)
    # Assert: parser.error called with "--hex cannot be combined with --diff"

def test_cli_manage_extensions_reports_yxp_error():
    """_manage_extensions catches YxpError and reports failure."""
    # Arrange: mock yxp.uninstall_package to raise YxpError
    # Act: call _manage_extensions(args with uninstall_extensions)
    # Assert: returns 1, stderr contains "error:"

def test_cli_main_install_font_returns_success_when_nerd_font_available():
    """main --install-font returns 0 when Nerd Font already available."""
    # Arrange: mock fonts.font_status to return has_nerd_font=True
    # Act: call main(["--install-font"])
    # Assert: returns 0, stdout contains "Nerd Font already available"

def test_cli_main_handles_explicit_yaterc_path():
    """main --yaterc <path> uses explicit rc file."""
    # Arrange: create a temporary rc file
    # Act: call main(["--yaterc", str(rc_path), "--diag"])
    # Assert: config loaded from explicit path

def test_cli_main_logs_config_errors():
    """main logs config errors when present."""
    # Arrange: mock load_config to return config with errors
    # Act: call main(["--diag"])
    # Assert: log.warning called with "config errors:"

def test_cli_main_maps_normal_keymap_to_vsc():
    """main --keymap normal maps to 'vsc'."""
    # Arrange: construct args with keymap="normal"
    # Act: call main(["--keymap", "normal", "--diag"])
    # Assert: YateApp constructed with keymap="vsc"
```

### 步骤 6：补强其余文件覆盖（P2，视时间）

- `yate/editor_view/explorer.py`（81%）
- `yate/flows/completion_flows.py`（83%）
- `yate/flows/chunked_flows.py`（84%）
- `yate/editor_view/terminal.py`（84%）
- `yate/editor_syntax/engine.py`（84%）
- `yate/editor_lsp/client.py`（85%）

**策略**：P2 文件若时间允许则补强，否则登记为后续任务。

## 五、新增测试清单

| 测试文件 | 新增用例数 | 验证目标 |
|---|---|---|
| `tests/test_shell_flows.py` | 5 | shell flows 的空命令、隐藏输出、字体安装成功/失败 |
| `tests/test_shells.py` | 3 | shell 解析的 Windows/Unix 默认路径 |
| `tests/test_extension_flows.py` | 3 | extension flows 的 symlink 拒绝、无 extensions 目录、单扩展加载失败 |
| `tests/test_user_setup.py` | 6 | user setup 的 _interactive 异常、symlink 处理、report 渲染 |
| `tests/test_cli.py` | 7 | cli 的 --hex 校验、yxp 错误处理、--install-font、--yaterc、config errors、--keymap |

## 六、验证方案

### 验证目标

证明新增测试覆盖缺失行，且整体覆盖率提升。

### 验证命令

```powershell
# 1. 新增测试验证
.venv\Scripts\python.exe -m pytest tests/test_shell_flows.py tests/test_shells.py -v

# 2. 覆盖率验证（单文件）
.venv\Scripts\python.exe -m pytest tests/test_shell_flows.py --cov=yate/flows/shell_flows --cov-branch --cov-fail-under=0
.venv\Scripts\python.exe -m pytest tests/test_shells.py --cov=yate/editor_term/shells --cov-branch --cov-fail-under=0

# 3. 全量覆盖率验证
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto

# 4. 全量 pytest
.venv\Scripts\python.exe -m pytest tests/ -q -n auto

# 5. 架构守卫
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q

# 6. pyright
.venv\Scripts\python.exe -m pyright tests/
```

### 通过判定

- 新增测试全部通过（退出码 0）；
- `yate/flows/shell_flows.py` 覆盖率 ≥ 90%；
- `yate/editor_term/shells.py` 覆盖率 ≥ 90%；
- 整体覆盖率 ≥ 92%（不低于基线）；
- 全量 pytest 全绿；
- 架构守卫 37 项全绿；
- pyright 零诊断。

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 新增测试暴露隐藏 bug | 发现 bug 立即修复或登记 issue | 测试本身不回滚，bug 另案处理 |
| 覆盖率提升不明显 | 优先补 P0 文件 | 调整 P1/P2 优先级 |

## 八、独占文件清单

- `tests/test_shell_flows.py`（新增）
- `tests/test_shells.py`（新增或追加）
- `tests/test_extension_flows.py`（新增或追加）
- `tests/test_user_setup.py`（新增或追加）
- `tests/test_cli.py`（追加）

## 九、预计影响

- **覆盖率**：整体从 92.24% 提升至 ≥ 93%；
- **测试时长**：新增约 20-30 个测试，预计增加 5-10s；
- **可信度**：覆盖缺口补强后，回归检测能力增强。

## 十、修订记录（第 2 轮）

**修订日期**：2026-10-31

**修订内容**：

1. **§四 步骤 3**：消除"待调研"空泛表述。实测调研 `yate/flows/extension_flows.py`
   L83-88, 91-93, 102，明确缺失行为：symlink 拒绝、无 extensions 目录提示、
   单扩展加载失败报告。新增 3 个具体测试用例。

2. **§四 步骤 4**：消除"待调研"空泛表述。实测调研 `yate/services/user_setup.py`
   L335-336, 365, 372, 375-376, 389-403, 422-439，明确缺失行为：`_interactive`
   异常捕获、symlink 处理、report 渲染。新增 6 个具体测试用例。

3. **§四 步骤 5**：消除"待调研"空泛表述。实测调研 `yate/cli.py` L269-272, 293-295,
   346-353, 405-408, 448, 455, 499，明确缺失行为：--hex 校验、yxp 错误处理、
   --install-font、--yaterc、config errors、--keymap。新增 7 个具体测试用例。

4. **§五 新增测试清单**：更新用例数——extension_flows 3 个、user_setup 6 个、
   cli 7 个，总计 24 个新增测试用例（原为"待调研"）。
