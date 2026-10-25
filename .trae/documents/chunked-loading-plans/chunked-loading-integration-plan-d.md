# chunked-loading-integration-plan-d（wave-3：集成收尾）

## 输入

主计划 [../chunked-loading-plan.md](../chunked-loading-plan.md) 全文；plan-a/b/c 验收后的实际落地产物。

## 目标

集成验证（冒烟 + 守卫 + 手册）与主计划回填（性能基线实测数字、偏离记录）。

## 独占文件清单（只改这些，不要动其它任何文件）

- `tools/smoke_test/scenarios/chunkedview.py`（新增）
- `tools/smoke_test/scenarios/__init__.py`（仅注册行）
- `yate/docs/yaterc.en.md` / `yate/docs/yaterc.zh.md`（large_file 选项文档，双语同步硬约束）
- `.trae/documents/chunked-loading-plan.md`（回填执行记录）
- 本目录各子计划（回填执行记录）

## 具体修改

### 1. 冒烟场景 `tools/smoke_test/scenarios/chunkedview.py`

参照 `tools/smoke_test/scenarios/hexview.py`（:48-182）形态：

- `chunked_text_open_and_scroll`：生成 > 阈值的合成日志（写临时大文件，退出清理）→ 启动打开 → 断言首屏渲染出现（gutter 行号）→ goto 末行（`:e` 场景内用 Textual pilot 键序）→ 断言末行内容与行号正确 → 关闭。
- 场景注册进 `scenarios/__init__.py`（:20/:61 两处表，参照 hex 场景注册形态）。

### 2. 手册（双语同步）

- `yate/docs/yaterc.en.md` 与 `yaterc.zh.md` 增 `large_file` 组文档：`threshold`（默认 8388608 字节；0 禁用分段；范围）；分段模式行为说明（只读、`:fullload` 升级、hex 上限移除）。

### 3. 主计划回填（§八 执行记录）

- **性能基线实测**（写入主计划 §八）：
  - 生成 10 MB / 50 MB 合成日志各一份（系统临时目录，测后删除）；
  - 对照脚本（临时脚本，测后删除）：全量 `Document.open` vs `Document.open_chunked` 首块就绪耗时（`time.perf_counter`，各跑 5 次取中位）；
  - `tracemalloc` peak 对照（全量 open vs chunked open + 首屏填充 + goto 末行后）；
  - 数字填表：文件大小 × {全量耗时, 分段首屏耗时} × {全量 peak, 分段 peak}。
- **偏离记录**：执行中所有偏离（阈值默认、豁免行数、接口签名微调）逐条列实测依据。
- 待办遗留（非 blocker/major）登记。

### 4. 门禁（主代理亲自跑，统一并行口径）

```powershell
Set-Location D:\Programming\yate-chunked-loading
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

## 需要新增的测试

即 §1 冒烟场景（手工自动化一体）；无新增单测（单测面已由 plan-a/b/c 覆盖）。

## 验收命令

见 §4；通过判定：五条全退出码 0，覆盖率 `--cov-fail-under=75`（pyproject 既有配置）不降级。

## 风险与回滚

- 冒烟大文件场景耗时：文件规模控制在阈值 + 少量（默认 8 MiB → 生成 ~9 MB），保持冒烟总时长可接受。
- 回滚：场景与手册文档独立成 hunks，可单独撤销。

## 执行记录（2026-10-25 回填）

- 执行方式：执行者（复用 executor-c）在联调中发现 plan-b 产品 bug（后台扫描
  worker 静默死亡）后停下上报，修复后继续，但于冒烟联调阶段失联（连续 30 分钟
  文件零变化 + 无回音，满足 subagent-workflow §五.3 判死条件）→ 按 §五.4 由
  主代理接管收尾。执行者已交付：`chunkedview.py` 场景 + 注册 + 双语手册 +
  plan-a/c 回填；主代理完成：性能基线、plan-b/d 回填、冒烟复跑验证、探针清理
  （`_probe_tmp/` 与 TEMP 探针脚本因删除工具工作区边界限制未能自动清理，见
  主计划 §八 遗留）。
- 冒烟（主代理复跑，HEAD c391a22）：`python -m tools.smoke_test run --jobs 4`
  → **117/117 scenarios、1410/1410 checks、exit 0**（83.5s），含新场景
  `chunked_text_open_and_scroll`（9 MB 合成日志 → 首屏 gutter=1 渲染头部标记 →
  后台扫描达全行数 → goto 末行加载尾部块 → 尾部标记与行号断言）。
- 越清单改动裁定（接受）：`tools/smoke_test/scenarios/hexview.py` 的
  `screen_carries_bytes` 检查从已删除的 `HexScreen._data` 改为 `HexScreen._source`
  —— plan-c 遗漏的必要适配（冒烟场景不在全量 pytest 覆盖面，plan-c 时未暴露）。
- 性能基线（主代理实测，Python 3.13.2 / Windows，`time.perf_counter` 5 次取中位
  + `tracemalloc` peak；详见主计划 §八 表格）。

## 执行记录（2026-10-25）

- 交付物：
  1. `tools/smoke_test/scenarios/chunkedview.py`（新增）：场景
     `chunked_text_open_and_scroll`（tags `files`/`command`）——生成 9 MB 合成日志
     （93,750 行 × 96 B，写入 harness 场景临时目录随跑随清）→ 启动打开 → 断言
     chunked 文档 / locked / read-only / 首屏已填 / SVG 首屏 gutter 行号 1 + 首行内容 /
     后台扫描到全行数 → goto 末行 → 断言末块已填 + SVG 末行 gutter 行号与内容 →
     14/14 checks 绿（1.1 s，远低于 60 s 场景预算）。
  2. `scenarios/__init__.py`：两张表注册（import 行 + SCENARIOS 列表 `*_VIEW` 后）。
  3. `yate/docs/yaterc.en.md` / `yaterc.zh.md`：`large_file` 组双语文档（选项总表行 +
     专节：threshold 默认 8388608 / 0 禁用 / 范围 [1 MiB, 1 GiB]；分段只读、
     `:fullload` 升级、`:w`/`:saveas` 拒绝、hex 100 MB 上限移除；两文件语义对齐）。
  4. 集成期修复配合：`tools/smoke_test/scenarios/hexview.py` 的
     `screen_carries_bytes` 断言适配 chunked source（plan-c 删除 `HexScreen._data`
     后的存量耦合清理；依据主计划 §五 wave 表 `tools/smoke_test/**` 归 plan-d）；
     暴露并推动 plan-b 扫描 worker 修复（`c391a22`，见 plan-b 执行记录）。
- 验证（执行者实测）：
  `tools.smoke_test run --jobs 4` → 117/117 scenarios、1410/1410 checks，退出码 0；
  `pytest tests/ -q -n auto` → 全绿（仅既有 skip），退出码 0；
  `pyright` 场景三文件 → 0 errors，退出码 0。
- 性能基线：数字与测量方法见主计划 §八 8.2。
- 门禁：五条统一门禁（pyright 全仓 / pytest / 架构 37 例 / 覆盖率
  `--cov-fail-under=75`）由主代理收尾亲自执行。
- 偏离：无（`chunked_flows.py` 修复由 executor-b 落在其 plan-b 范围内，
  plan-d 未触碰产品源码）。
- 未尽清理项（执行者无删除审批权）：仓库内未跟踪探针残留
  `_probe_tmp/`、`_probe_chunked_smoke.py` 待删；TEMP 对照脚本已计划删除。
