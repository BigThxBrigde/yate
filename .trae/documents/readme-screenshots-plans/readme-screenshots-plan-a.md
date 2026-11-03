# readme-screenshots plan-a：截图工具实现（wave-1）

> 总纲：`readme-screenshots-plans/overview.md`（唯一规范来源）。

## 目标

实现 `python -m tools.screenshots`：以 Textual pilot 驱动 `YateApp` 到各功能状态，
`save_screenshot()` 导出 SVG 到 `<repo-root>/screenshots/`；工具/测试报告类截图走
子进程真实命令 + Rich 重渲染；由场景注册表生成 `screenshots/README.md` 画廊。

## 独占文件清单（只改这些）

- 新增 `tools/screenshots/__init__.py`（包 docstring，惰性）
- 新增 `tools/screenshots/__main__.py`（CLI 入口：`--out/--only/--list/--skip-cli`）
- 新增 `tools/screenshots/scenarios.py`（场景注册表：名称、EN/ZH 标题与说明、
  驱动协程、尺寸；全英文注释）
- 新增 `tools/screenshots/driver.py`（pilot 驱动助手 + App 工厂 + 固定夹具文件）
- 新增 `tools/screenshots/cli_reports.py`（子进程捕获 → `Text.from_ansi` →
  录制型 Console → `export_svg`）
- 新增 `tools/screenshots/gallery.py`（由注册表生成 `screenshots/README.md`）
- 新增 `tests/test_screenshots_tool.py`

## 设计要点

1. **场景注册表**（scenarios.py）：`@dataclass(frozen=True)` 场景项
   `name / title_en / title_zh / desc_en / desc_zh / size / driver`；
   `SCENARIOS: tuple[Scenario, ...]` 按总纲 25 项排序；`name` kebab-case。
2. **驱动**（driver.py）：
   - 构造 `YateApp(...)` 直接用公开旋钮（`yate/app.py:85-98`），**不经**
     `harness.new_app`（避免 invariant sweep 注册）；
   - 复用 `tools.smoke_test.scenarios._base` 的 `run_command / type_text /
     wait_until`（同 tools 树内正当复用；其 `harness._speed_up_pilot` 加速
     经由该模块 import 链生效）；
   - 每个场景自备 `tmp_path` 夹具（预置 .py/.bin/diff 对等），按键序列照
     总纲调研 4 的证据行；
   - 屏保场景用 `YateConfig(screen_saver=ScreenSaverConfig(characters=["snake"]))`
     固定角色保证确定性；
   - 终端场景 `wait_until` 等面板出现（PTY 进程异步）。
3. **CLI 报告**（cli_reports.py）：`subprocess.run` 真实命令（smoke `--tag view`、
   `pytest tests/ -q -n auto --color=yes`、`pyright`），env `FORCE_COLOR=1`，
   `encoding="utf-8", errors="replace"`；捕获文本 → `Text.from_ansi` → 录制型
   `Console(width=100, record=True)` → `export_svg(title=...)`；pytest/pyright
   分两帧（两个 SVG）或同帧双面板（实现自选，注册表登记实际形态）。
4. **画廊**（gallery.py）：按注册表渲染 `screenshots/README.md`——
   标题 + 生成命令 + 字体限制说明 + 每场景一节（`### <name>` +
   `<img src="./x.svg" width="720">` + EN 一行 + ZH 一行）。
5. **CLI**（`__main__.py`）：默认生成全部到 `<repo>/screenshots/`；
   `--only <name>`（可重复）单跑调试；`--list` 打印注册表；`--skip-cli` 跳过
   三个慢速子进程场景；输出统计（生成数 / 跳过 / 失败，exit code）。
6. **合规**：全模块 `from __future__ import annotations`、pyright strict 零诊断、
   注释全英文 ASCII、单文件 ≤800 行、绝对导入。

## 新增测试（tests/test_screenshots_tool.py）

| 用例 | 三要素 |
|---|---|
| `test_registry_names_are_kebab_and_unique` | 前置：import SCENARIOS；操作：遍历；断言：全部匹配 `^[a-z0-9-]+$` 且无重名，EN/ZH 字段非空 |
| `test_gallery_renders_registry_to_markdown` | 前置：tmp 目录；操作：对 2 个 stub 场景调 gallery 渲染；断言：md 存在、含两个 `### ` 节、含 Nerd Font 限制说明行、含 ZH 说明行 |
| `test_welcome_screenshot_end_to_end` | 前置：tmp out 目录；操作：`--only welcome-screen --out <tmp>` 跑 CLI（asyncio.run 包裹）；断言：SVG 生成、`rich-terminal` 出现在内容里、画廊 md 同步生成 |

## 验收命令（PowerShell，worktree 根）

```powershell
.venv\Scripts\python.exe -m pyright tools/screenshots tests/test_screenshots_tool.py
.venv\Scripts\python.exe -m pytest tests/test_screenshots_tool.py -q -n 1
.venv\Scripts\python.exe -m tools.screenshots --list
```

通过判定：三条退出码均 0；`--list` 打印 25 个场景名。

## 风险与回滚

- 新文件仅 tools/tests，不触 yate/；回滚 = 删除目录与测试文件。
- pyright strict 对 subprocess/rich API 的类型缺口：用 `cast`/显式注解，禁止
  `# type: ignore`（§4.2）。
