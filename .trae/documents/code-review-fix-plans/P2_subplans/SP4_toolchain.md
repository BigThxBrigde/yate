# SP4 — 工具链（N13 N14 N15 N16 N17 N29 N32）

> 波次一 · 规模 L · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `tools/smoke_test/harness.py`（N14 N29）
- `tools/smoke_test/testsuite.py`（N15 落点之一）
- `tools/smoke_test/cli.py`（N15 落点之一，`--timeout` 参数）
- `tools/changelog/gitee.py`（N16 函数侧）
- `tools/changelog/cli.py`（N16 调用方侧；主代理实测 `pushed_flags` 调用点在 cli.py:133 后补入授权）
- `tools/changelog/render.py`（N17 被测对象）
- `tools/changelog/gitdata.py`（N32）

**测试：** `tests/test_smoke_tool.py`（新建）、`tests/test_changelog_tool.py`（仅新增用例）

**不许动**：`tools/smoke_test/scenarios/`（终端场景归 SP6 波次二）、其它任何文件。
本子计划改的是冒烟工具自身——波次收尾由主代理跑冒烟全绿，即其端到端验证。

## 第 0 步：现状复核

逐条核对 P2 原文锚点（N13: smoke 工具无自测；N14: `extract_svg_rows` 正则；N15: 场景无整体超时；
N16: `check_commit_pushed` 仅 gitee；N17: `strip_unreleased` 无直接用例；N29: harness
`# type: ignore` 无理由注释；N32: gitdata subject 分隔符无防护）。行号漂移记录到校准段。

## 条目执行

### N13 — smoke 工具纯函数自测

1. **输入**：P2 原文 N13 行（场景解析、报告渲染、`extract_svg_rows`；harness 端到端不测）。
2. **步骤**：新建 `tests/test_smoke_tool.py`，仅覆盖纯函数（导入 tools 包路径参照
   `tests/test_changelog_tool.py` 对 tools 的既有导入方式）。
3. **验收**：新文件内用例全绿；命名遵循 `test_<behavior>_<condition>_<expected>`。

### N14 — SVG 提取的版本漂移诊断

1. **输入**：P2 原文 N14 行（提取失败给明确报错 + 打印 SVG 头部片段；正则收紧并在注释记录适配的 Textual 版本）。
2. **步骤**：读当前 Textual 版本号（`pyproject.toml` / `.venv`）写入注释；正则按当前实测 SVG 格式收紧；
   失败分支报错信息含版本漂移提示与片段。
3. **验收**：喂一条当前格式样例（成功）+ 一条变形样例（失败且报错含片段）两条用例。

### N15 — 单场景整体超时

1. **输入**：P2 原文 N15 行（`asyncio.wait_for(scenario, timeout=per_scenario)`，默认 60s、`--timeout` 可调；超时记 failed 并继续）。
2. **步骤**：定位场景执行入口（testsuite.py / cli.py 按实际代码）；包 wait_for；
   超时场景计入 failed、报告如实呈现、退出码非 0；`--timeout` 进 argparse。
3. **验收**：人造挂起场景（如 `await asyncio.sleep(999)` 的临时场景对象，不经场景注册表）
   断言超时触发且流程继续；既有冒烟 `run --fail-only` 行为不变（主代理收尾实测）。

### N16 — `check_commit_pushed` host 分派

1. **输入**：P2 原文 N16 行（其它 host 由调用方输出「无法核验，跳过 gate」而非当失败；github 可同构实现）。
2. **步骤**：读 gitee.py 与调用方（release gate）现状；最小实现：非 gitee host 返回 None 的路径
   改为调用方明确跳过并提示；github 同构实现**仅在改动面小时做**，否则记录为后续项上报。
3. **验收**：单测 host 分派三态（gitee 正常 / github 按实现 / 未知 host 跳过不失败）。

### N17 — `strip_unreleased` 边界用例

1. **输入**：P2 原文 N17 行（仅有 Unreleased 段 / Unreleased 为空 / Unreleased 在末尾三种）。
2. **验收**：`tests/test_changelog_tool.py` 新增三条直接用例，断言按实现固化的行为。

### N29 — harness `# type: ignore` 理由注释

1. **输入**：P2 原文 N29 行。
2. **步骤**：读 harness.py:274-283 现状（P2 复核时行号），确认是既定豁免则补理由注释归档；
   若能用 `cast()` 消除则优先消除（规范 §4.4），消灭不了再注释。
3. **验收**：pyright 0 诊断；注释或 cast 二者其一落地。

### N32 — gitdata subject 分隔符固化

1. **输入**：P2 原文 N32 行（按实现固化行为或加断言/文档说明——理论性 Low）。
2. **步骤**：读 gitdata.py 的 `maxsplit` 解析；选最小方案：subject 含杂散分隔符的行为
   用一条固化用例 + 一行注释说明边界（不引入解析逻辑变更）。
3. **验收**：新增固化用例；既有 changelog 53 用例全绿。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright tools/smoke_test/harness.py tools/smoke_test/testsuite.py tools/smoke_test/cli.py tools/changelog/gitee.py tools/changelog/render.py tools/changelog/gitdata.py tests/test_smoke_tool.py tests/test_changelog_tool.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_smoke_tool.py tests/test_changelog_tool.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + N16 github 是否实现及理由 + 校准记录

## 校准记录

（实施时回填）
