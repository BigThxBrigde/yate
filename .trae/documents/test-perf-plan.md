# test-perf 实施计划（issue IKJVL6：单元测试性能与执行速度）

## 一、目标与非目标

**目标**

1. profiling 全量测试，定位慢测试（已完成，见 §二基线）；
2. 优化头部慢测试，把全量时长从 **265.7s** 显著压缩（预期 ≥ 90s 降幅）；
3. 顺带修复 `run_shell` 超时路径的真实产品缺陷（孤儿孙进程 + 固定 5s 延迟）。

**非目标**

- 不改动测试断言语义（守卫的行为不变）；
- 不做 Textual / pytest 层面的全局改造（如 xdist 并行）；
- LSP 3s 级慢测试若根因是协议固有等待则仅登记不强制优化。

## 二、基线与根因（profiling 实测）

全量：`pytest tests/ -q` → **265.7s**（Measure-Command 实测，Windows，worktree 沙箱）。
头部慢测试合计 ≈ **143.7s**：

| 测试 | 基线 (s) | 根因（cProfile / 源码取证） |
|---|---|---|
| `test_workspace_filter.py::test_walk_files_survives_a_1500_level_chain` | 21.16 | 测试桩 `path.relative_to(root)` 每次 O(depth)（3.13 pathlib 走 `_collections_abc.__contains__` 逐级构造 Path，1500 层 → O(n²) ≈ 24.5s 热点）；`_dir_ignores` 对超长路径真实 stat ×2/目录 ≈ 8.3s |
| `test_workspace_filter.py::test_visible_tree_survives_a_1500_level_chain` | 16.38 | 同上 `relative_to` O(n²)（≈24.4s 热点，profiler 放大） |
| `test_app_manual.py` 8 个 manual/doc 测试 | 66.8 合计 | 每个 F8/`:manual` 都让 Textual Markdown widget 解析渲染整份手册（大文档），CPU 密集 |
| `test_app_render.py` 2 个 doc-search 测试 | 18.3 合计 | 同上 |
| `test_app_find.py::test_overlay_commands_clear_stale_message[files]` | 7.88 | 无 root 时 `PaletteScreen._collect_file_entries` 走 `_walk(Path.cwd())`，cwd=worktree 根连 `.venv` 一起 walk（5000 上限）+ 每 file `resolve()` |
| `test_shell.py::test_run_shell_times_out_with_a_message` | 5.12 | **产品缺陷**：`subprocess.run(timeout=0.2)` 超时 kill 的是 cmd.exe，孙进程 `python -c sleep(5)` 持有输出管道，run 内部等管道关闭 → 实等 5s 且孤儿进程存活 |
| `test_lsp.py::test_server_request_and_publish_notification` | 3.01 | 协议握手 + stop 清理固有等待，量级可接受（P2 登记） |

## 三、备选方案与否决理由

1. **【采纳】逐测试针对性修桩/缩小测试数据 + 一处产品修复**——根因明确、改动面小、守卫语义不变。
2. 【否决】pytest-xdist 并行：收益大但引入测试间隔离风险（Textual pilot / tracing / 环境变量），超出本 issue "找出慢测试并优化" 的范围，另立事项。
3. 【否决】降低 1500 层深度：S11 守卫点正是 "超过 Python 默认递归限 1000"，降深度削弱守卫语义。
4. 【否决】给产品 `Workspace.walk_files` 加深度缓存： profiler 显示产品代码在真实树上是线性的（O(n²) 来自测试桩），产品改动无收益。

## 四、分步实施

### Wave A — workspace_filter 测试桩 O(1) 化（tests/test_workspace_filter.py）

- 输入：§二 根因 1/2。
- 改动：
  1. 两个 1500 链测试用 `dict[Path, int]` 深度映射替代 `path.relative_to(root)`（iterdir 递推 O(1)/层）；
  2. walk 测试追加 `monkeypatch.setattr("pathlib.Path.stat", raises)` 消除 `_dir_ignores` 对超长路径的真实 stat（ OSError → stamps=-1.0，与"无 ignore 文件"语义一致）。
- 验收：`pytest tests/test_workspace_filter.py -q` 全绿；两用例耗时 < 2s。

### Wave B — run_shell 超时杀进程树（yate/services/shell.py + tests/test_shell.py，产品修复）

- 输入：§二 根因 7。
- 改动：`run_shell` 改 `Popen` + `communicate(timeout=...)`；超时后 Windows 用 `taskkill /F /T /PID` 杀进程树，POSIX 用 `start_new_session=True` + `os.killpg(SIGKILL)`（fallback `proc.kill()`）；随后 `communicate()` 收尾，返回合成 124 与原消息格式。
- 测试：现有断言不变；追加"子进程无残留"断言（timeout 场景）。
- 验收：`pytest tests/test_shell.py -q` 全绿；`test_run_shell_times_out_with_a_message` < 1.5s。

### Wave C — manual/doc 测试小型 fixture 化（tests/test_app_manual.py + tests/test_app_render.py + 新文件 tests/manual_doc_fixture.py）

- 输入：§二 根因 3/4。
- 改动：
  1. 新增 `tests/manual_doc_fixture.py`：一份小 markdown 常量（含 ≥2 个含 "yate" 的 block、≥12 行各含 "ctrl" 的代码块、1 个含 "item" 单元格的表格），满足全部搜索断言的数据需求；
  2. manual/doc 系测试（test_app_manual 8 个 + test_app_render 2 个）统一 `patch("yate.editor_view.manual.load_doc_markdown", return_value=FIXTURE)`（test_manual_paints_before_content_loads 的 slow_load 已有 patch，改为基于 fixture）；
  3. 断言 `md.source == load_manual_markdown(...)` 改为与 fixture 常量比较（语义不变：加载的是注入的 doc）。
- 验收：10 个测试全绿且各 < 4s；`moved > 0` 等布局断言在 fixture 上成立（若某布局断言确实无法在小文档复现，保留该测试用真实手册并在此登记偏离）。

### Wave D — palette 测试隔离 + lsp 登记（tests/test_app_find.py + tests/test_lsp.py）

- 输入：§二 根因 5/6。
- 改动：`test_overlay_commands_clear_stale_message` 在 `run_command(command)` 前 `app.editor.workspace.set_root(空 tmp 子目录)`，files/palette 索引瞬完；lsp 3s 用例仅在文档登记，不改。
- 验收：`pytest tests/test_app_find.py -q` 全绿；`[files]` 参数 < 3s。

### 执行方式

- A / C / D 文件互不重叠 → 按子代理工作流派 3 个并行成员（acceptEdits），任务书指向本计划 + 独占文件清单；**Wave B 涉产品源码，主代理亲自做**。
- Wave 间无依赖，B 与子代理批次同时开工；回收后主代理重跑各成员名下测试复核。

## 五、收尾门禁

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/
.venv\Scripts\python.exe -m pytest tests/ -q --cov=yate --cov-fail-under=75
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
```

- 全量时长复测（Measure-Command）与基线 265.7s 对比回填；
- 架构测试 25 用例保持全绿；覆盖率 ≥ 75% 不回退。

## 六、风险与回滚

| 风险 | 处置 |
|---|---|
| Wave C 布局断言（同 widget 多行滚动差值）在小 fixture 上不稳定 | 实测调整 fixture；不可复现则该用例保留真实手册，登记偏离 |
| Wave B POSIX 分支本机无法实测 | 代码审查 + Windows 分支测试覆盖；POSIX 语义保持 subprocess 标准用法，CI（Linux）回归兜底 |
| 覆盖率回退（shell.py 改动缩小 / fixture 缩小覆盖面） | 门禁 `--cov-fail-under=75` 强制；不达标补测 |

回滚：各 Wave 独立提交，可单独 revert。

## 七、执行记录（收尾回填）

- 状态：已完成（分支 `enh/test-perf`，无人值守 bypass 模式，未向用户发起审批）。

### 实施与偏离记录

| Wave | 执行者 | 结果 | 偏离 |
|---|---|---|---|
| A workspace_filter 桩优化 | 子代理 wave-a（存活，有落盘产出） | 主代理复核全绿 | 主代理追加补丁：`Path.read_text` 一并 stub（cProfile 二次取证：`_dir_ignores` 缓存 miss 后真实 `open` 超长路径 3002 次占 ~4s；补后 walk 链 4.80s → **0.28s**） |
| B run_shell 进程树修复 | 主代理（涉产品源码） | 5.12s → **0.34s**，全绿，pyright 零诊断 | 无设计偏离；测试断言设计修正一次：孙进程在 kill 前的 0.2s 窗口内即写 marker，"marker 不出现"无法证明未存活——改为记 PID + 存活探测（ctypes OpenProcess / `os.kill(pid,0)`）+ 调用时长 <3s 断言；taskkill /T 有效性经独立探针证实（SUCCESS 终止孙进程 PID） |
| C manual/doc fixture 化 | 子代理 wave-c（存活，有落盘产出） | 10 用例全绿，各 0.4–2.0s | `test_manual_search_step_lands_on_exact_rendered_row` 已 fixture 化（6.90s → 5.47s），剩余为其滚动断言固有成本，接受并登记 |
| D palette 隔离 | 子代理 wave-d（存活，有落盘产出） | `[files]` 7.88s → <0.4s | 主代理追加补丁：`[changelog]`（同参数化测试）仍渲染真实 CHANGELOG（6.91s），统一注入 fixture 后 <0.7s |
| LSP 3s 用例 | 未改 | 维持 3.01s | 按 §一非目标登记（协议固有等待） |

### 成员存活与产出如实报告

- wave-a / wave-c / wave-d 均 spawn 成功、全部有落盘产出、零判死；探活消息未获逐条回执（成员专注执行），产出按文件变化 + 主代理重跑测试认定。
- 收尾：shutdown_request ×3 → 团队删除成功。

### 门禁实测（主代理亲自跑）

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | **0 errors, 0 warnings, 0 informations**（退出码 0） |
| `pytest tests/test_architecture.py -q` | **25 passed** |
| `pytest tests/ -q --cov=yate --cov-fail-under=75` | 全绿，覆盖率 **91.37%**（≥75%） |
| 全量时长（Measure-Command，无 cov） | **265.7s → 143.9s（-45.9%）** |

### 头部慢测试前后对照（实测）

| 用例 | 前 (s) | 后 (s) |
|---|---|---|
| test_walk_files_survives_a_1500_level_chain | 21.16 | 0.28 |
| test_visible_tree_survives_a_1500_level_chain | 16.38 | 0.30 |
| test_manual_search_filters_and_cycles_matches | 12.83 | 1.70 |
| test_doc_search_enter_flushes_pending_query_immediately | 9.49 | 0.88 |
| test_manual_search_no_matches_then_slash_reopens | 9.07 | 1.98 |
| test_doc_search_debounce_merges_rapid_typing | 8.81 | 0.84 |
| test_manual_command_selects_language[en] | 8.28 | 0.44 |
| test_overlay_commands_clear_stale_message[files] | 7.88 | <0.4 |
| test_overlay_commands_clear_stale_message[changelog] | 6.91（复核时实测） | <0.7 |
| test_f8_opens_manual_and_esc_closes | 7.67 | 0.63 |
| test_manual_paints_before_content_loads | 7.62 | 0.49 |
| test_manual_command_selects_language[bogus] / [zh] | 7.44 / 6.98 | 0.43 / ≈0.5 |
| test_manual_search_step_lands_on_exact_rendered_row | 6.90 | 5.47（固有成本，登记） |
| test_run_shell_times_out_with_a_message | 5.12 | 0.34 |
| test_lsp test_server_request_and_publish_notification | 3.01 | 3.01（未改，登记） |
