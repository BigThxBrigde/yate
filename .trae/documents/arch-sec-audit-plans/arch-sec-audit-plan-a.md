# arch-sec-audit plan-a：工作区主题目录信任门控（S1 高危）+ 主题手册信任段落

> **修订 v2（2026-10-29，用户裁决）**：门控逻辑**不得放在 cli.py**——cli.py 不新增
> 任何 yate 模块导入（现状 module-level 仅 yate.logs，main() 内既有懒加载保持不变，
> **禁止**新增 `yate.services.trust` 直连导入）。门控下沉到主题模块：
> `editor_view/theme_files.py` 实现助手，`editor_view/theme.py` 门面再导出（该文件是
> §三.5 已登记的主题门面例外），cli 仅改调用行。层级合法性：L2 `editor_view/*` →
> L0 `services/trust.py` 是依赖图已画出的 EV → LEAVES 向下边（trust 仅依赖 yate.logs，
> 无环）。

## 输入与依据

- 取证：`yate/cli.py:410-416` 无条件把 `Path.cwd() / "themes"` 交给
  `theme_mod.load_theme_paths`；`yate/editor_view/theme_files.py:69-76` 对 `*.py`
  主题文件 `compile` + `exec`（任意 Python）。
- 既有范式：`yate/services/extensions/loader.py:291-309` 对 `./extensions` 的信任门控
  （resolved cwd → `is_trusted(cwd)` → 不信任则跳过并向 messages 追加
  `"... skipped untrusted <path> (run :trust to load them)"`）。
- 威胁模型声明：`yate/services/trust.py:1-19`（打开仓库绝不执行仓库自身代码）。
  用户级 `~/.yate/themes` 是用户自己投放的目录，保持无条件加载（与 `~/.yate/extensions` 同理）。
- 用户裁决（2026-10-29）：cli 除 yate.logs 外不新增导入；主题门控放 theme 模块处理。

## 独占文件清单（只改这些文件，不动其它任何文件）

1. `yate/editor_view/theme_files.py`（新增助手 + import + `__all__`）
2. `yate/editor_view/theme.py`（门面再导出新助手；该文件为 §三.5 登记的主题门面例外）
3. `yate/cli.py`（**仅 410-416 调用行改为经 theme_mod 调用助手；import 面零新增**）
4. `yate/docs/themes.en.md`
5. `yate/docs/themes.zh.md`
6. `tests/test_theme_trust.py`（新建）

## 具体修改

### 1. `yate/editor_view/theme_files.py`

- 新增 import（按既有分组）：`from yate.services.trust import is_trusted`。
- 新增公共函数（放在 `load_theme_file` 之前）：

```python
def default_theme_dirs(errors: list[str]) -> list[Path]:
    """Resolve the built-in theme directories, gating workspace themes on trust.

    The user-level ``~/.yate/themes`` is the user's own data and loads
    unconditionally.  ``./themes`` inside the opened workspace executes
    workspace-authored Python, so it auto-loads only in workspaces trusted
    via :command:`:trust` -- mirroring the ``./extensions`` gate in
    :mod:`yate.services.extensions.loader`.  A skipped workspace directory
    appends a ``"themes: skipped untrusted ..."`` note to *errors*, the
    same user-visible channel as rc discovery notes.
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

- `__all__` 追加 `"default_theme_dirs"`。
- 语义保持：返回顺序 = 原加载顺序（cwd 在前、home 在后，后者同名覆盖前者）；
  **不改动** `load_theme_paths` 的通用语义（rc `theme_dirs` / `--theme-dir` 仍无条件，
  门控只作用于本助手的默认目录解析）。

### 2. `yate/editor_view/theme.py`

- 在既有对 theme_files 的再导出块（`load_theme_file` / `load_theme_paths` 所在）按同样
  方式再导出 `default_theme_dirs`，同步其 `__all__`（如有）。先读文件再改，跟随既有形态。

### 3. `yate/cli.py`（仅调用行，import 面零新增）

- 原 `main()` 内（约 410-416）：

```python
theme_mod.load_theme_paths(
    [Path.cwd() / "themes", Path.home() / ".yate" / "themes"],
    default_errors,
)
```

  改为：

```python
theme_mod.load_theme_paths(theme_mod.default_theme_dirs(default_errors), default_errors)
```

- **自证纪律**：完成后 `git diff yate/cli.py` 必须只有该调用块变化，无任何新增 import。

### 4. `yate/docs/themes.en.md` / `themes.zh.md`（双语同步，两文件同时改）

- 新增小节 "Workspace themes and trust"（中文对应 "工作区主题与信任"），要点：
  - 打开的工作区内的 `./themes/*.py` 属工作区作者代码，仅在 `:trust` 信任该工作区后加载；
  - 未信任时启动会收到一条 skip 提示（`themes: skipped untrusted ... (run :trust to load them)`）；
  - 用户级 `~/.yate/themes` 与 yaterc `theme_dirs`、`--theme-dir` 不受门控（刻意用户动作）。
- 措辞风格对齐 `yate/docs/extensions.en.md` 中对 workspace trust 的既有描述（先读后写）。

### 5. `tests/test_theme_trust.py`（新建）

前置：conftest 的 autouse `isolated_home` 已把 `Path.home()` 指到临时目录；
`trust.TRUST_FILE` 是 import 期绑定，测试须 `monkeypatch.setattr(trust, "TRUST_FILE", <tmp>/"trusted_workspaces")`
（先读 `tests/` 里既有 trust 用例的写法并对齐）。`monkeypatch.chdir` 切到临时工作区。
被测对象：`from yate.editor_view.theme_files import default_theme_dirs`（tests 直测内部
机件不在拦截面，参照既有测试对 theme_files 的引用方式）。

| 用例 | 前置 | 操作 | 断言 |
|---|---|---|---|
| `test_workspace_themes_skipped_when_untrusted` | tmp 工作区含 `themes/probe.py`（调用 register_theme 注册 "trust-probe"）；不写信任 | `monkeypatch.chdir(ws)` 后调 `default_theme_dirs(errors=[])` | 返回列表**不含** `ws/themes`；errors 含 `"themes: skipped untrusted"` 且含 `":trust"` |
| `test_workspace_themes_loaded_when_trusted` | 同上 + `trust.trust_workspace(ws.resolve())`（写 patched TRUST_FILE） | 同上 | 列表首项为 `ws/themes`；errors 为空 |
| `test_home_themes_always_loaded_without_trust` | 无工作区 themes 目录 | 同上 | 列表恰为 `[Path.home()/".yate"/"themes"]`；errors 为空 |
| `test_no_themes_directory_appends_no_note` | 工作区无 `themes/` | 同上 | 列表为 home 一项；errors 为空 |

- 另加 1 条加载向用例（若基建允许）：`test_default_theme_dirs_feed_load_theme_paths`
  ——trusted 工作区下 `load_theme_paths(default_theme_dirs(errs), errs)` 后断言
  "trust-probe" 已注册。基建不足就放弃该条，不强凑。

## 验收命令（在 worktree 根，PowerShell）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_theme_trust.py -q
.venv\Scripts\python.exe -m pytest tests/test_theme_files.py tests/test_cli.py -q   # 文件名以 ls tests/test_theme* test_cli* 实际为准
.venv\Scripts\python.exe -m pyright yate/editor_view/theme_files.py yate/editor_view/theme.py yate/cli.py tests/test_theme_trust.py
git diff --stat yate/cli.py   # 必须仅调用行变化
```

通过判定：全部 exit 0；pyright 对所改文件零诊断；cli.py 无新增 import。

## 风险与回滚

- cli.py 启动路径回归 → 冒烟（117 场景）+ 上述用例兜底；回滚 = revert 本子计划提交。
- 禁止事项：不在 cli.py 新增任何 import（含懒加载）；不改 `yate/services/trust.py` 与
  `theme_files.load_theme_paths` 的通用语义；不动 `.trae/` 其它文件。
