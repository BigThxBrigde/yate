# arch-sec-audit plan-a：工作区主题目录信任门控（S1 高危）+ 主题手册信任段落

## 输入与依据

- 取证：`yate/cli.py:410-416` 无条件把 `Path.cwd() / "themes"` 交给
  `theme_mod.load_theme_paths`；`yate/editor_view/theme_files.py:69-76` 对 `*.py`
  主题文件 `compile` + `exec`（任意 Python）。
- 既有范式：`yate/services/extensions/loader.py:291-309` 对 `./extensions` 的信任门控
  （resolved cwd → `is_trusted(cwd)` → 不信任则跳过并向 messages 追加
  `"... skipped untrusted <path> (run :trust to load them)"`）。
- 威胁模型声明：`yate/services/trust.py:1-19`（打开仓库绝不执行仓库自身代码）。
  用户级 `~/.yate/themes` 是用户自己投放的目录，保持无条件加载（与 `~/.yate/extensions` 同理）。

## 独占文件清单（只改这些文件，不动其它任何文件）

1. `yate/cli.py`
2. `yate/docs/themes.en.md`
3. `yate/docs/themes.zh.md`
4. `tests/test_theme_trust.py`（新建）

## 具体修改

### 1. `yate/cli.py`（约 410-424 行区域）

- 新增模块级或 main 内辅助函数（推荐模块级私有函数，便于测试）：

```python
def _default_theme_dirs(errors: list[str]) -> list[Path]:
    """Resolve the built-in theme directories, gating workspace themes on trust.

    The user-level ``~/.yate/themes`` is the user's own data and loads
    unconditionally; ``./themes`` inside the opened workspace executes
    workspace-authored Python and therefore auto-loads only in workspaces
    trusted via :command:`:trust` (mirroring ``./extensions``).
    """
    theme_dirs: list[Path] = []
    cwd_themes = Path.cwd() / "themes"
    if cwd_themes.is_dir():
        if is_trusted(Path.cwd().resolve()):
            theme_dirs.append(cwd_themes)
        else:
            errors.append(
                f"themes: skipped untrusted {cwd_themes} (run :trust to load them)"
            )
    theme_dirs.append(Path.home() / ".yate" / "themes")
    return theme_dirs
```

- import：`from yate.services.trust import is_trusted`（cli 为 L4，trust 为 L0，向下合法；
  loader.py 已有同向先例）。按 cli.py 现有 import 分组放置。
- 原 `main()` 内调用改为：

```python
theme_mod.load_theme_paths(_default_theme_dirs(default_errors), default_errors)
```

  保持原语义：`load_theme_paths` 后加载者胜（home 仍最后加载）；`config.errors` 通道
  沿用 `default_errors`（与 rc_notes 同类，用户可见）。
- 纪律：注释/docstring 一律英文；日志走 tracing（本改动无新增日志）；不新增 Protocol/Any。

### 2. `yate/docs/themes.en.md` / `themes.zh.md`（双语同步，两文件同时改）

- 新增小节 "Workspace themes and trust"（中文对应 "工作区主题与信任"），要点：
  - 打开的工作区内的 `./themes/*.py` 属工作区作者代码，仅在 `:trust` 信任该工作区后加载；
  - 未信任时启动会收到一条 skip 提示（`themes: skipped untrusted ... (run :trust to load them)`）；
  - 用户级 `~/.yate/themes` 与 yaterc `theme_dirs`、`--theme-dir` 不受门控（刻意用户动作）。
- 措辞风格对齐 `yate/docs/extensions.en.md` 中对 workspace trust 的既有描述（先读后写）。

### 3. `tests/test_theme_trust.py`（新建）

前置：conftest 的 autouse `isolated_home` 已把 `Path.home()` 指到临时目录；
`trust.TRUST_FILE` 是 import 期绑定，测试须 `monkeypatch.setattr(trust, "TRUST_FILE", <tmp>/"trusted_workspaces")`
（先读 `tests/` 里既有 trust 用例的写法并对齐）。`monkeypatch.chdir` 切到临时工作区。

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_workspace_themes_skipped_when_untrusted` | tmp 工作区含 `themes/probe.py`（调用 register_theme 注册 "trust-probe"）；不写信任 | `monkeypatch.chdir(ws)` 后调 `cli._default_theme_dirs(errors=[])` | 返回列表**不含** `ws/themes`；errors 含 `"themes: skipped untrusted"` 且含 `":trust"` |
| `test_workspace_themes_loaded_when_trusted` | 同上 + `trust.trust_workspace(ws.resolve())`（写 patched TRUST_FILE） | 同上 | 列表首项为 `ws/themes`；errors 为空 |
| `test_home_themes_always_loaded_without_trust` | 无工作区 themes 目录 | 同上 | 列表恰为 `[Path.home()/".yate"/"themes"]`；errors 为空 |
| `test_no_themes_directory_appends_no_note` | 工作区无 `themes/` | 同上 | 列表为 home 一项；errors 为空 |

- 另加 1 条集成向用例（可选，若 cli 测试基建允许）：`test_cli_loads_trusted_workspace_themes_only`
  ——直接以 `load_theme_paths(_default_theme_dirs(errs), errs)` 后查
  `yate.editor_view.themes` 注册表断言主题注册/未注册。基建不足就放弃该条，不强凑。

## 验收命令（在 worktree 根，PowerShell）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_theme_trust.py -q
.venv\Scripts\python.exe -m pytest tests/test_theme_files.py tests/test_cli.py -q   # 文件名以 ls tests/test_theme* test_cli* 实际为准
.venv\Scripts\python.exe -m pyright yate/cli.py tests/test_theme_trust.py
```

通过判定：全部 exit 0；pyright 对所改文件零诊断。

## 风险与回滚

- cli.py 启动路径回归 → 冒烟（117 场景）+ 上述用例兜底；回滚 = revert 本子计划提交。
- 禁止事项：不改 `theme_files.py`（exec 本身是设计内行为，门控加在 cli 侧）；不动 `.trae/` 规则。
