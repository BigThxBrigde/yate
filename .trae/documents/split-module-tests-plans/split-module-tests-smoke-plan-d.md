# plan-d：新增冒烟 scenario（wave-2，串行）

## 输入

- harness：`tools/smoke_test/harness.py`（`new_app` / `Scenario` / `Check` /
  `snapshot_svg`；TAGS 不新增，用 `"integration"`）
- 助手：`tools/smoke_test/scenarios/_base.py`（`run_command` / `type_text` /
  `wait_until` / `message_text`）
- 接线点：`yate/editor.py:108-109`——`ed.extension_api = ExtensionAPI(...)`
  与 `ed.extension_loader = ExtensionLoader(ed.extension_api)`；`Editor` 同时
  暴露 `extension_loader` 属性（editor.py:330 类注解）。
- 装载入口：`yate/services/extension_loader.py:205`
  `load_startup_extensions(loader, config, *, ext_dirs=(), ext_files=())`
  返回 user-facing 消息列表。
- 主题模板：`yate/resources/theme_examples/ayu_theme.example`（合法主题文件
  形态，内含 `register_theme(Theme(...))` 调用）。
- scenario 形态范本：`tools/smoke_test/scenarios/view.py`（run_command /
  message_text / snapshot_svg 的组合方式）。

## 独占文件清单

**新建**：

- `tools/smoke_test/scenarios/modules.py`（2 个 scenario）
- `tools/smoke_test/smoke_baselines/integration_extension_roundtrip.json`
- `tools/smoke_test/smoke_baselines/integration_custom_theme_file.json`

**修改（唯一产品侧改动，共 3 行）**：

- `tools/smoke_test/scenarios/__init__.py`：新增
  `from tools.smoke_test.scenarios.modules import SCENARIOS as _MODULES`
  （import 块按字母序插入）+ `SCENARIOS` 列表在 `*_INTEGRATION` 之后追加
  `*_MODULES`。

## scenario 1：`integration_extension_roundtrip`

覆盖端到端链：`load_startup_extensions`（loader.py）→ `ExtensionAPI`
（extension_api.py rollback scope）→ 注册表 → `:命令` / action 派发 →
`teardown_all`。这是 issue IKKS9X 新拆分模块协同的主冒烟路径（现有
scenario 群无扩展装载场景）。

```python
async def _extension_roundtrip(tmp: Path) -> ScenarioResult:
    """A temp extension registers action+command, they dispatch, teardown runs."""
    ext = tmp / "ext_roundtrip.py"
    ext.write_text(
        "MARK = {'torn_down': False}\n"
        "def setup(api):\n"
        "    api.message('EXT-SETUP')\n"
        "    api.register_action('ext_rt_action',\n"
        "                        lambda: api.message('RT-ACTION-OK'))\n"
        "    def cmd(args):\n"
        "        api.message('RT-CMD-OK:' + args)\n"
        "    api.command('ext_rt_cmd')(cmd)\n"
        "def teardown(api):\n"
        "    MARK['torn_down'] = True\n",
        encoding="utf-8",
    )
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        messages = load_startup_extensions(
            app.editor.extension_loader, app.editor.config,
            ext_files=[ext],
        )
        checks.append(Check("setup_message", True,
                            any("EXT-SETUP" in m for m in messages) or "EXT-SETUP" in message_text(app)))
        checks.append(Check("no_load_errors", True,
                            not any("error" in m.lower() for m in messages)))
        await run_command(pilot, "ext_rt_cmd with args")
        checks.append(Check("command_dispatched", True,
                            "RT-CMD-OK:with args" in message_text(app)))
        app.editor.execute_action("ext_rt_action")
        await pilot.pause()
        checks.append(Check("action_dispatched", True,
                            "RT-ACTION-OK" in message_text(app)))
        app.editor.extension_loader.teardown_all()
        await pilot.pause()
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("integration_extension_roundtrip", checks, rows)
```

**执行者注意**：`teardown` 的 MARK 断言跨进程内模块状态（loader 经
importlib 装载该文件），scenario 内不易再 import 同一模块实例——断言收敛
在 `teardown_all()` 无异常 + `loader.loaded` 记录 `error is None`；MARK 翻转
验证由 `tests/test_extensions.py::test_teardown_hook_is_captured_and_called`
（既有）承担，不重复。若 `EXT-SETUP` 未上消息线（load_startup_extensions
只回错误消息），删去该 check 的 messages 分支、只断言
`not any("extension ext_roundtrip:" in m for m in messages)`（无错误即成功）。

## scenario 2：`integration_custom_theme_file`

覆盖链：`theme_files.load_theme_paths`（新拆分）→ `themes.register_theme`
→ `:theme <name>` 命令 → `theme.active()`。现有 scenario 群无自定义主题
文件场景。

```python
async def _custom_theme_file(tmp: Path) -> ScenarioResult:
    """A user theme file registers a theme that :theme can switch to."""
    template = Path(yate.__file__).parent / "resources/theme_examples/ayu_theme.example"
    body = template.read_text(encoding="utf-8").replace("ayu", "rt_custom")
    (tmp / "themes").mkdir()
    (tmp / "themes" / "rt_custom_theme.py").write_text(body, encoding="utf-8")
    app = new_app(target=tmp / "a.txt")
    checks: list[Check] = []
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        load_theme_paths([tmp / "themes"], [])
        checks.append(Check("theme_registered", True, "rt_custom" in available()))
        await run_command(pilot, "theme rt_custom")
        checks.append(Check("switched", "rt_custom", theme.active().name))
        await run_command(pilot, "theme mocha")
        checks.append(Check("restored", "mocha", theme.active().name))
        rows = snapshot_svg(app, tmp)
    return ScenarioResult("integration_custom_theme_file", checks, rows)
```

**执行者注意**：
1. `ayu_theme.example` 的实际内容先读一遍；若其内部注册名不是字面
   `ayu`（如带 `Ayu` 混合大小写），replace 目标以模板内
   `Theme(name=...)` 实参为准；若模板结构不适合 replace，改为在文件末尾
   追加一行 `register_theme(Theme(**{**t.__dict__, "name": "rt_custom"}))`
   形态（`t` 取模板已注册对象或 `THEMES` 内最近似者）——二选一，落定后
   记入执行记录。
2. `load_theme_paths` 的第二参 errors 列表在 scenario 内同步断言为空
   （可并入 `theme_registered` check 前置）。
3. 进程全局 `THEMES` 污染：scenario 结束时主题已切回 mocha；`rt_custom`
   注册项残留进程内——冒烟工具一次性进程（CLI 运行），可接受；若
   `run_scenarios` 同进程跑多场景，`rt_custom` 残留不影响其它断言
   （名称唯一）。在 docstring 中注明。

## 注册表接线（__init__.py 修改点）

`tools/smoke_test/scenarios/__init__.py`：

1. import 块按字母序在 `integration` 与 `multi_cursor` 之间插：
   `from tools.smoke_test.scenarios.modules import SCENARIOS as _MODULES`
2. `SCENARIOS` 列表在 `*_INTEGRATION,` 之后插入 `*_MODULES,`。

## 验收命令（顺序执行，全部退出码 0）

```text
.venv\Scripts\python.exe -m pytest tests/test_smoke_harness.py -q
.venv\Scripts\python.exe -m pyright tools/smoke_test/scenarios/modules.py tools/smoke_test/scenarios/__init__.py
.venv\Scripts\python.exe -m tools.smoke_test run --scenario integration_extension_roundtrip --scenario integration_custom_theme_file --quiet --no-color
.venv\Scripts\python.exe -m tools.smoke_test snapshot --scenario integration_extension_roundtrip --scenario integration_custom_theme_file
.venv\Scripts\python.exe -m tools.smoke_test compare --quiet --no-color
```

说明：
1. 第一条验证既有注册表守卫（name 唯一 / tag 已声明 / 协程 / docstring /
   primary_tag）接纳新 scenario；
2. `run` 直接执行两个新 scenario（scenario 本体不在 pytest 全量执行，由
   冒烟工具与 release gate 执行——与仓库现状一致，见
   `test_smoke_harness.py` 模块 docstring）；
3. `snapshot` 生成 2 个基线 json（连同 scenario 一起提交）；
4. `compare` 验证零漂移（防 SVG 提取格式回归）。

## 风险与回滚

- `ayu` 模板 replace 失配 → 按"执行者注意 1"的备选形态落定；回滚 =
  `git checkout -- tools/smoke_test/scenarios/__init__.py` + 删除
  `modules.py` 与 2 个基线 json。
- scenario 的 message 断言依赖命令行反馈时序 → 用 `_base.wait_until` 轮询
  替代直接断言（view.py 的 `_font_command_stub` 先例）。
- 基线对 Textual 8.2.8 SVG 格式锚定敏感 → `compare` 既是验收也是防回归；
  Textual 升级时全量基线统一重拍（既有机制，非本计划范围）。
- 与既有 scenario 命名冲突风险：`integration_` 前缀在现有基线目录中
  未被占用（已核对 smoke_baselines 文件清单）。

## 执行记录

2026-10-12 wave-2 执行完毕（执行者：plan-executor 子代理；复验：主代理）。

- 实际产物：`scenarios/modules.py`（138 行，2 scenario / 18 checks）+
  `__init__.py` 2 行接线 + 2 个基线
  （`integration_extension_roundtrip.json` 1248 B /
  `integration_custom_theme_file.json` 1027 B）。
- 验收：两新 scenario `run` 18/18 checks（exit 0）；全量 `compare`
  111/111 scenarios、1341/1341 checks 全 MATCH（exit 0）；
  `run --tag integration` 8/8（exit 0）；`test_smoke_harness.py`
  25 passed（注册表守卫自动受检）；`pyright` 2 文件 0 诊断。主代理复跑
  run/compare/harness 同结果。
- 偏离（均附实测依据，详见执行汇报）：
  1. 扩展 action 回调签名带 `ctx`（`registries.py` 的
     `ActionRegistry.execute` 以 `action.func(ctx)` 调用，零参 lambda 被
     guarded 回调吞成错误）；
  2. `no_load_errors` 收窄到本扩展前缀（loader 重跑启动装载会重报 app
     启动时其他用户扩展的历史错误，全量断言环境脆弱）；新增
     `loaded_record_clean` check 落实"loader.loaded 记录 error is None"；
  3. 注 3 的假设被实测证伪：`rt_custom` 残留导致全量 `compare` 首跑
     `regress_theme_expansion: DRIFT`（该 scenario 枚举
     `theme.available()` 逐名产生 check，modules 组先于 regression 组）；
     修复 = scenario 返回前 `THEMES.pop` 清理 `rt_custom-*`（沿用
     `test_theme_palettes.py:387` 先例），修复后零漂移；
  4. 主题注册名落定为 `rt_custom-dark/-mirage/-light`（模板 `Theme(name=)`
     实参全字替换，`_ayu`→`_rt_custom` 连带更名）；
  5. 模板路径用 `yate.paths.package_root()`（仓库规定的资源目录唯一入口，
     反对散落 `Path(yate.__file__)` 运算）。
- 基线在偏离 1/3 修复前 snapshot，修复后全量 compare MATCH 证明现行代码
  可复现基线，无需重拍。
- 提交：commit `0bc0434`（test(smoke): add extension and custom theme
  scenarios）。
