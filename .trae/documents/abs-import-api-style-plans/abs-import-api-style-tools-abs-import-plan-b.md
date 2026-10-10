# plan-b：tools/ 包相对导入转绝对导入（wave-1）

> 隶属 [主计划](../abs-import-api-style-plan.md) 议题 1。独占文件域：`tools/**`（与 plan-a 的 `yate/**` 零重叠，可并行）。

## 一、输入

- 主计划 §二 议题 1 的事实清单：`tools/` 94 处相对导入、37 个文件。
- 运行形态证据：tools 一律 `python -m tools.<pkg>` 从仓库根执行（`.workflow/test.yml:65`、`README.md:361-404`、`CHANGELOG.md:3`），tests 已按 `from tools.xxx import` 绝对消费（`tests/test_changelog_tool.py:19` 等）——绝对导入可行。

## 二、改写规则

与 plan-a 相同的映射（见 plan-a §二）；tools 侧根包名为 `tools`：

| 相对形态（所在包） | 绝对形态 |
|---|---|
| `from .cli import main`（`tools/<pkg>/__main__.py`） | `from tools.<pkg>.cli import main` |
| `from .._util import repo_root`（`tools/<pkg>/*.py`） | `from tools._util import repo_root` |
| `from ..harness import ...`（`tools/smoke_test/scenarios/*.py`） | `from tools.smoke_test.harness import ...` |
| `from ._base import run_command`（scenarios 内） | `from tools.smoke_test.scenarios._base import ...` |
| `from . import gitee, gitdata, ...` | `from tools.<pkg> import gitee, gitdata, ...` |

## 三、改动文件清单（37 个）

### tools/release（2 文件）

| 文件 | 行号与改写 |
|---|---|
| [__main__.py](../../../tools/release/__main__.py) | 5 → `from tools.release.cli import main` |
| [cli.py](../../../tools/release/cli.py) | 33-35：`.._util` → `from tools._util import repo_root`；`..changelog` → `from tools.changelog import gitdata`；`..changelog.cli` → `from tools.changelog.cli import check, generate` |

### tools/pack（5 文件）

| 文件 | 行号与改写 |
|---|---|
| [__main__.py](../../../tools/pack/__main__.py) | 5 → `from tools.pack.cli import main` |
| [cli.py](../../../tools/pack/cli.py) | 36 `.. import _util` → `from tools import _util`；37 `. import errors, icon, rosters, wiki` → `from tools.pack import ...`；38 `.errors` → `from tools.pack.errors import Code` |
| [icon.py](../../../tools/pack/icon.py) | 23 → `from tools._util import repo_root` |
| [rosters.py](../../../tools/pack/rosters.py) | 21 `.icon` → `from tools.pack.icon import repo_root`（18-19 行的 yate 导入已是绝对形态，不动） |
| [wiki.py](../../../tools/pack/wiki.py) | 74 `.. import _util` → `from tools import _util`；75 `. import errors` → `from tools.pack import errors`；76 `.errors` → `from tools.pack.errors import Code, PackError` |

### tools/changelog（6 文件）

| 文件 | 行号与改写 |
|---|---|
| [__main__.py](../../../tools/changelog/__main__.py) | 5 → `from tools.changelog.cli import main` |
| [cli.py](../../../tools/changelog/cli.py) | 31 `.._util` → `from tools._util import repo_root`；32 `. import gitee, gitdata, render, segments, translations` → `from tools.changelog import ...`；33-35 `.classify`/`.model`/`.translations` 同法 |
| [classify.py](../../../tools/changelog/classify.py) | 7 `.model` → `from tools.changelog.model import ...` |
| [gitdata.py](../../../tools/changelog/gitdata.py) | 15 `.model` 同法 |
| [segments.py](../../../tools/changelog/segments.py) | 23 `.model` 同法 |
| [render.py](../../../tools/changelog/render.py) | 14 `. import gitee` → `from tools.changelog import gitee`；15-16 `.model`/`.translations` 同法 |

### tools/smoke_test（5 文件）

| 文件 | 行号与改写 |
|---|---|
| [__main__.py](../../../tools/smoke_test/__main__.py) | 5 → `from tools.smoke_test.testsuite import main` |
| [testsuite.py](../../../tools/smoke_test/testsuite.py) | 76 `.baselines`；77 `.cli`；78 多行 `.harness`；92 `.report`；93 `.scenarios` → 全部 `from tools.smoke_test.X import ...` |
| [cli.py](../../../tools/smoke_test/cli.py) | 17 `. import baselines`；18 多行 `.harness`；29 `.report`；30 `.scenarios` 同法 |
| [baselines.py](../../../tools/smoke_test/baselines.py) | 16 `.._util` → `from tools._util import repo_root`；17 `.harness` → `from tools.smoke_test.harness import ...` |
| [report.py](../../../tools/smoke_test/report.py) | 27 `.harness` → `from tools.smoke_test.harness import ...` |

### tools/smoke_test/scenarios（19 文件）

- [__init__.py](../../../tools/smoke_test/scenarios/__init__.py) | 11-12（`..harness` / `._base`）+ 13-30（18 行 `from .aliases import SCENARIOS as _ALIASES` 等）→ `from tools.smoke_test.harness import ...`、`from tools.smoke_test.scenarios._base import ...`、`from tools.smoke_test.scenarios.aliases import SCENARIOS as _ALIASES` 等。
- 18 个场景文件（aliases, core, diffview, edit, explorer, files, guards, integration, multi_cursor, palette_preview, panes, regression, screensaver, search, stress, vim_advanced, view, workspace_nav）各 2 处：`from ..harness import ...` → `from tools.smoke_test.harness import ...`（各文件 :7-:37 区间的第 1 处导入）、`from ._base import ...` → `from tools.smoke_test.scenarios._base import ...`（第 2 处；`_base` 是包内私有共享模块，非开放 API，模块名保持不变）。
- 场景文件内已有的 `from yate.xxx import` 绝对导入不动。

### 不触碰

- `tools/probes/**`：pyright exclude 区，无相对导入命中（主计划 §二），保持原样。
- `tools/_util.py`、`tools/__init__.py`、`tools/translate/**`：无相对导入命中，不动。

## 四、输出

- `tools/` 全部 94 处相对导入变为绝对形态；`from .` / `from ..` 在 `tools/` 下归零。
- 零行为变化；`python -m tools.<pkg>` 与 tests 的 `from tools.xxx import` 消费方式均不变。

## 五、验收命令（worktree 根执行）

```powershell
# 1. 相对导入归零（应无输出，退出码 1 = 无匹配）
rg -n "^\s*from\s+\.+" tools/ ; if ($LASTEXITCODE -eq 1) { "CLEAN" } else { "FAIL" }

# 2. 类型门禁零诊断
.venv\Scripts\python.exe -m pyright tools/

# 3. -m 入口冒烟（绝对导入在真实运行形态下成立）
.venv\Scripts\python.exe -m tools.changelog check
.venv\Scripts\python.exe -m tools.pack icon --help

# 4. 全量测试回归（test_changelog_tool / test_pack_wiki* / test_release_tool /
#    test_smoke_* 直接消费 tools 包）
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 六、风险与回滚

- 风险：仅当 tools 被以 `python tools/<pkg>/cli.py` 直跑时绝对导入会失败——全仓文档与 CI 无此形态（§一 证据）；`tools/smoke_test/harness.py:32-37` 的 env 注入先于导入 + `# noqa: E402` 是既有惯例，本计划不触碰其行序。
- 回滚：本计划单独 commit；异常时 `git revert` 该 commit，不影响 plan-a。
