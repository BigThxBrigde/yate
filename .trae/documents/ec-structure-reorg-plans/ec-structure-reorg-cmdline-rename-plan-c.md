# Plan C: flows/cmdline_completions.py 改名（wave-3）

## 输入

- `yate/flows/prompt_completion.py`（52 行）
- 函数 `prompt_completions()`

## 输出

- `yate/flows/cmdline_completions.py`（52 行，函数改名为 `cmdline_completions()`）
- 旧文件删除（`git mv` 保 rename）

## 独占文件清单

| 操作 | 文件 |
|---|---|
| git mv | `yate/flows/prompt_completion.py` -> `yate/flows/cmdline_completions.py` |
| 编辑 | `yate/flows/cmdline_completions.py`（函数改名） |
| 编辑 | `yate/editor.py`（import + 接线 ×2） |
| 编辑 | `tests/test_prompt_completion.py`（import + 调用 ×4） |
| 编辑 | `tests/test_app_find.py`（import + 调用 ×2） |
| 编辑 | `tests/test_set_options.py`（函数名含 prompt_completion） |
| 编辑 | `tests/test_workspace_filter.py:723`（注释） |
| 编辑 | `tools/smoke_test/scenarios/guards.py:200`（docstring） |
| 编辑 | `yate/config.py`（docstring + 注释 ×2） |
| 编辑 | `yate/services/extensions/api.py:411`（docstring） |
| 编辑 | `README.md:264` / `README.zh.md:282`（目录树表述） |
| 编辑 | `.trae/wikis/yate-architecture.md`（行 23/151/159） |
| 编辑 | `tests/test_architecture.py:25`（头注） |
| 编辑 | `.trae/rules/architecture-boundaries.md`（行 21/129/135/259/288/467） |

## 具体修改

### 步骤 c.1 — git mv + 函数改名

```powershell
cd D:\Programming\yate-ec-structure-reorg
git mv yate/flows/prompt_completion.py yate/flows/cmdline_completions.py
```

[yate/flows/cmdline_completions.py](file:///D:/Programming/yate-ec-structure-reorg/yate/flows/cmdline_completions.py)：

- 行 1 docstring：`prompt_completions` -> `cmdline_completions`
- 行 17：`def prompt_completions(` -> `def cmdline_completions(`
- 行 31：`return _command_completions(text, commands=commands)` （不变）

### 步骤 c.2 — 更新 editor.py

[yate/editor.py](file:///D:/Programming/yate-ec-structure-reorg/yate/editor.py)：

- 行 59：`from yate.flows.prompt_completion import prompt_completions`
  -> `from yate.flows.cmdline_completions import cmdline_completions`
- 行 153：`prompt_completions,` -> `cmdline_completions,`

### 步骤 c.3 — 更新测试

| 文件 | 行 | 旧 | 新 |
|---|---|---|---|
| `tests/test_prompt_completion.py` | 1 | docstring `prompt_completions` | `cmdline_completions` |
| `tests/test_prompt_completion.py` | 28 | `from yate.flows.prompt_completion import prompt_completions` | `from yate.flows.cmdline_completions import cmdline_completions` |
| `tests/test_prompt_completion.py` | 72 | `prompt_completions(` | `cmdline_completions(` |
| `tests/test_prompt_completion.py` | 142 | `prompt_completions(` | `cmdline_completions(` |
| `tests/test_prompt_completion.py` | 153 | `prompt_completions(` | `cmdline_completions(` |
| `tests/test_app_find.py` | 18 | `from yate.flows.prompt_completion import prompt_completions` | `from yate.flows.cmdline_completions import cmdline_completions` |
| `tests/test_app_find.py` | 337 | `prompt_completions(` | `cmdline_completions(` |
| `tests/test_app_find.py` | 479 | `prompt_completions(` | `cmdline_completions(` |
| `tests/test_set_options.py` | 45 | `test_set_option_names_feed_prompt_completion` | `test_set_option_names_feed_cmdline_completions` |
| `tests/test_workspace_filter.py` | 723 | `# --- path_matches (migrated from flows/prompt_completion, 2026-10-30) ---` | `# --- path_matches (migrated from flows/cmdline_completions, 2026-10-30) ---` |

### 步骤 c.4 — 更新表述面

| 文件 | 行 | 旧 | 新 |
|---|---|---|---|
| `yate/config.py` | 12 | `(:mod:`yate.flows.prompt_completion`)` | `(:mod:`yate.flows.cmdline_completions`)` |
| `yate/config.py` | 290 | `flows/prompt_completion` | `flows/cmdline_completions` |
| `yate/services/extensions/api.py` | 411 | `flows/prompt_completion.py` | `flows/cmdline_completions.py` |
| `tools/smoke_test/scenarios/guards.py` | 200 | `prompt_completions`` (yate/flows/prompt_completion.py) | `cmdline_completions`` (yate/flows/cmdline_completions.py) |
| `README.md` | 264 | `prompt_completion.py  # Tab-completion...` | `cmdline_completions.py  # Tab-completion...` |
| `README.zh.md` | 282 | `prompt_completion.py  # 底部命令行...` | `cmdline_completions.py  # 底部命令行...` |

### 步骤 c.5 — 更新规则文档

[.trae/rules/architecture-boundaries.md](file:///D:/Programming/yate-ec-structure-reorg/.trae/rules/architecture-boundaries.md)

- 行 21：`prompt_completion.py` -> `cmdline_completions.py`
- 行 129：`prompt_completion.py` -> `cmdline_completions.py`
- 行 135：`prompt_completion.py` 自 2026-10-30... -> `cmdline_completions.py` 自 2026-10-30...
- 行 259：`flows/prompt_completion.py` -> `flows/cmdline_completions.py`
- 行 288：`prompt_completions` -> `cmdline_completions`
- 行 467：`flows/prompt_completion.py` -> `flows/cmdline_completions.py`

[tests/test_architecture.py](file:///D:/Programming/yate-ec-structure-reorg/tests/test_architecture.py)
行 25：`flows/prompt_completion.py` -> `flows/cmdline_completions.py`

[.trae/wikis/yate-architecture.md](file:///D:/Programming/yate-ec-structure-reorg/.trae/wikis/yate-architecture.md)

- 行 23：`prompt_completion` -> `cmdline_completions`
- 行 151：`flows/prompt_completion.py` -> `flows/cmdline_completions.py`
- 行 159：`prompt_completion.py::prompt_completions` -> `cmdline_completions.py::cmdline_completions`

### 步骤 c.6 — 验收门禁

```powershell
cd D:\Programming\yate-ec-structure-reorg
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate -q
.venv\Scripts\python.exe -m tools.smoke_test
```

残留 grep（期望 0 命中）：

```powershell
.venv\Scripts\python.exe -c "import subprocess; r = subprocess.run(['rg', 'prompt_completion', 'yate/', 'tests/', 'tools/', '.trae/rules/'], capture_output=True, text=True); print(r.stdout); exit(1 if r.stdout.strip() else 0)"
```

### 步骤 c.7 — 独立提交

```powershell
git add -A
git commit -m "refactor(flows): rename prompt_completion to cmdline_completions"
```

## 风险与回滚

| 风险 | 缓解 |
|---|---|
| 函数改名破坏插件 | `prompt_completions` 是内部函数，不暴露给插件 API |
| 测试文件名 `test_prompt_completion.py` 不改 | issue 未要求改测试文件名；改名即可，内容已同步 |
| 回滚 | `git revert <commit>` 单提交回滚 |

## 备注

测试文件 `tests/test_prompt_completion.py` 保持原名（issue 未要求改测试文件名），
仅更新内部 import 与调用。如未来需统一命名，另行立项。
