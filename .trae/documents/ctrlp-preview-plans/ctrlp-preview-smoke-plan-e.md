# plan-e：冒烟场景（tools/smoke_test）

> 总纲见 `overview.md`。前置依赖：plan-b（预览 UI）与 plan-c（接线）。
> 项目冒烟的正式形态是 `tools/smoke_test` 场景注册表（`python -m tools.smoke_test`
> 运行），不是临时脚本——本波把 preview 端到端行为注册为永久场景。

## 一、目标

以真实 `YateApp` + pilot 驱动 Ctrl+P → 预览渲染 → 确认打开的全链路，
覆盖「预览渲染 / 大文件截断 / enable=False 关闭」三条路径，
并通过 `tests/test_smoke_harness.py` 的注册表守卫（唯一名、tags 合法、
docstring 存在）。

## 二、独占文件清单

- `tools/smoke_test/scenarios/palette_preview.py`（新建）
- `tools/smoke_test/scenarios/__init__.py`（改：登记新模块）

## 三、逐文件改动明细

### `tools/smoke_test/scenarios/palette_preview.py`（新建）

形态照 `scenarios/core.py::_file_palette`（45-62 行）与 `scenarios/files.py`：
`from ..harness import Check, Scenario, ScenarioResult, new_app, snapshot_svg`、
`from ._base import type_text, wait_until`、`__all__ = ["SCENARIOS"]`、
每个场景 async def 签名 `(tmp: Path) -> ScenarioResult` + docstring。

场景 1：`palette_preview_renders`（tags `("files",)`）

- 夹具：`tmp / "alpha.py"`（内容含 `def greet():\n    return "hi"\n`）、
  `tmp / "notes.txt"`；
- `app = new_app(target=tmp)`；`run_test(size=(110, 32))`（同 file_palette）；
- `ctrl+p` → `Check("palette_open", 2, len(app.screen_stack))`；
- `type_text(pilot, "alpha")` 过滤；
- `wait_until(pilot, <预览就绪谓词>)`——谓词从 PaletteScreen 探针：
  `screen = app.screen`；`screen.query("#palette-preview")` 非空且
  `screen._preview_cache` 含 `alpha.py` 的 Path（worker 完成的可靠信号；
  场景模块允许探内部，test_smoke_harness 先例即如此）；
- checks：preview widget 存在、缓存条目 `note is None` 且 `lines` 首行含
  `def greet`、`tokens` 非空（语法高亮生效）；
- `enter` 打开 → `Check("doc.name", "alpha.py", ...)` +
  `Check("palette_closed", 1, len(app.screen_stack))`；
- `rows = snapshot_svg(app, tmp)` 收档。

场景 2：`palette_preview_truncates`（tags `("files",)`）

- 夹具：`tmp / "big.py"` 写 3000 行（`"x = 1"` 循环）；
- ctrl+p → 过滤 "big" → wait_until 缓存就绪；
- checks：缓存条目 `truncated is True`、`len(lines) == 2000`（默认 max_lines）、
  widget 渲染文本含 "truncated"（从 RichLog 的 renderable/内部 lines 探针，
  实施时以实际可断言形态为准）。

场景 3：`palette_preview_disabled`（tags `("files",)`）

- 夹具：`tmp / "project"` 子目录 + `yaterc`
  （`file_preview = {"enable": False}\n`）+ `plain.txt`；
  `os.chdir(project)` + `finally` 还原 cwd（`files.py::_workspace_trust` 先例）；
- `new_app(target=...)` 启动（项目 yaterc 经 `find_project_config` 生效）；
- ctrl+p → checks：`query("#palette-preview")` 为空、PaletteScreen 无
  `with-preview` class、结果区仍渲染（`filtered_count >= 1`）、
  `enter` 打开 `plain.txt` 正常（回归保护：关闭态与旧行为一致）。

### `tools/smoke_test/scenarios/__init__.py`

- import 区加 `from .palette_preview import SCENARIOS as _PALETTE_PREVIEW`；
- `SCENARIOS` 拼接列表中放 `*_FILES` 之后（功能分组就近）；
- `__all__` 与 re-export 助手不动。

## 四、注册表守卫自检（test_smoke_harness 将校验）

- 场景名唯一（`palette_preview_*` 前缀无冲突）；
- tags ∈ `harness.TAGS`——全部复用 `("files",)`（files.py 全组同款），不改 TAGS；
- 每个场景协程有 docstring；
- 场景不落盘到仓库、不改全局状态（chdir 场景 finally 还原）。

## 五、验收命令（worktree 内）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_smoke_harness.py -q
.venv\Scripts\python.exe -m tools.smoke_test
```

预期：harness 守卫全绿；smoke 全量运行新场景 3 条 pass、既有场景不回归。
（若 smoke CLI 支持按名过滤，先单跑 3 条新场景再全量；实施时以
`python -m tools.smoke_test --help` 确认参数。基线文件非必需——diff 机制
按已存在基线比对，新场景无基线不阻塞；若流程要求补齐，用 smoke CLI 的
写基线入口生成后一并提交。）

## 六、回滚

场景文件 + `__init__.py` 两行登记，revert 干净；不影响既有场景与基线。
