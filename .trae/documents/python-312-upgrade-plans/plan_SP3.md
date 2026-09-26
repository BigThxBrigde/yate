# plan SP3 — PEP 604 存量迁移：`Optional[X]`/`Union[X, Y]` → `X | Y`（313 处 / 53 文件）

> 从属于[总纲](README.md)；前置：SP2（pyupgrade 就位）。
> 308 处 `Optional[` + 5 处 `Union[`（F10/F11）；按架构层切 3 个子批，**批间为验证检查点**（最终单提交）；
> 批内失败按文件级回退（`git checkout -- <file>`）复跑。

## 1. 工具与统一命令

```powershell
.venv\Scripts\pyupgrade.exe --py312-plus --keep-percent-format <files...>
```

pyupgrade 顺带清空被掏空的 `typing` 导入（`Optional`/`Union` 不再使用时）。
**禁止裸跑**（不带 `--keep-percent-format` 会改写日志 `%` 格式，见总纲）。

## 2. 子批次与独占文件清单

数字 = `Optional[` 命中数；**★ = 该文件另含 `Union[` 落点**（pyupgrade 一并重写）。

### 3a · yate 叶子层 + L1（23 文件 / 155 处 Optional + 4 处 Union）

| 文件 | Optional | Union |
|---|---|---|
| `yate/editor_core/buffer.py` | 7 | |
| `yate/editor_core/document.py` | 6 | |
| `yate/editor_core/search.py` | 4 | |
| `yate/editor_lsp/client.py` | 13 | |
| `yate/editor_lsp/manager.py` | 16 | |
| `yate/editor_lsp/protocol.py` | 4 | |
| `yate/editor_syntax/regex_backend.py` | 11 | |
| `yate/editor_syntax/ts_backend/backend.py` | 1 | |
| `yate/editor_syntax/ts_backend/languages.py` | 5 | |
| `yate/editor_term/emulator.py` | 7 | |
| `yate/editor_term/pty_proc.py` | 16 | ★ L31（`ExitState = int \| Literal[...]`） |
| `yate/logs.py` | 24 | |
| `yate/config.py` | 7 | |
| `yate/services/extensions.py` | 11 | |
| `yate/services/workspace.py` | 3 | |
| `yate/services/trust.py` | 3 | |
| `yate/services/fonts.py` | 1 | |
| `yate/services/shell.py` | 1 | |
| `yate/extensions/python_lsp.py` | 2 | |
| `yate/session.py` | 9 | ★ L267（`Node = Leaf \| Split`） |
| `yate/registries.py` | 2 | |
| `yate/keymaps/base.py` | 1 | ★ L168 / L232（`str \| ActionFunc`） |
| `yate/keymaps/registry.py` | 1 | |

批级验证：pyright 全仓 0 + `pytest tests/ -q` 一次全绿。

### 3b · yate L2–L4（14 文件 / 93 处）

| 文件 | Optional |
|---|---|
| `yate/editor_view/editor.py` | 20 |
| `yate/editor_view/commandline.py` | 8 |
| `yate/editor_view/explorer.py` | 9 |
| `yate/editor_view/terminal.py` | 8 |
| `yate/editor_view/panes.py` | 7 |
| `yate/editor_view/completion.py` | 5 |
| `yate/editor_view/keys.py` | 3 |
| `yate/editor_view/theme.py` | 3 |
| `yate/editor_view/palette.py` | 2 |
| `yate/editor_view/manual.py` | 2 |
| `yate/editor.py` | 15 |
| `yate/completion.py` | 4 |
| `yate/app.py` | 6 |
| `yate/cli.py` | 1 |

批级验证同 3a。

### 3c · tests + tools（16 文件 / 60 处 Optional + 1 处 Union）

| 文件 | Optional | Union |
|---|---|---|
| `tests/test_pty_proc.py` | 13 | |
| `tests/test_lsp.py` | 8 | |
| `tests/test_release_tool.py` | 4 | |
| `tests/test_fonts.py` | 3 | |
| `tests/test_panes.py` | 3 | |
| `tests/test_changelog_tool.py` | 3 | |
| `tests/test_terminal.py` | 2 | |
| `tests/test_app_textual.py` | 1 | |
| `tests/test_key_notation.py` | 1 | ★ L440 |
| `tools/smoke_test/harness.py` | 8 | |
| `tools/smoke_test/report.py` | 4 | |
| `tools/smoke_test/scenarios/integration.py` | 4 | |
| `tools/release/cli.py` | 2 | |
| `tools/changelog/cli.py` | 2 | |
| `tools/smoke_test/cli.py` | 1 | |
| `tools/smoke_test/scenarios/_base.py` | 1 | |

批级验证同 3a。

## 3. 边界与风险

- 纯注解改写，零行为变更；`from __future__ import annotations` 全仓在位（规则 §4.1），
  注解全惰性求值；三处运行时类型别名（`Node = Leaf | Split`、`ExitState = int | Literal[...]`、
  `str | ActionFunc`）在 3.12 运行时与 `Union[...]` 等价（pytest 导入路径即覆盖）。
- 全仓无引号形态 `Optional["..."]`（F11），重写面均匀无特例。
- `git diff` 复核：仅允许注解行与 typing 导入行变化；任何方法体/字符串/日志语句变化
  即单独回退该文件复跑。

## 4. 验证命令

- **批级**（每子批收尾）：
  ```powershell
  .venv\Scripts\python.exe -m pyright yate tests tools   # 0
  .venv\Scripts\python.exe -m pytest tests/ -q           # 一次全绿
  ```
- **波次收尾**（标准门禁）：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/ -q                # 连续两次全绿
  .venv\Scripts\python.exe -m tools.smoke_test run --fail-only # exit 0
  git grep -n -E "Optional\[|Union\[" -- yate tests tools      # 归零
  ```

## 5. 提交

- 单提交：`refactor(types): adopt PEP 604 unions across the codebase`
- 信息体要点：313 annotation sites across 53 files rewritten via
  `pyupgrade --py312-plus --keep-percent-format`; zero behavior change
  (PEP 604 unions are runtime-equivalent; annotations are lazy via
  `from __future__ import annotations`).
