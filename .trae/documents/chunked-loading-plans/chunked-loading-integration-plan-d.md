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
