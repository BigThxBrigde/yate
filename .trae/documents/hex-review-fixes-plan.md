# hex-review-fixes-plan

来源：`feat/hex-feat` 分支的 pr-review（review 模式，2026-10-25）产出 2 个
major + 2 个 minor findings。本计划是其修复方案与执行记录的唯一规范来源：
执行者以本文为准，不要凭常识猜。

## 一、目标与非目标

### 目标

1. **F1（major）**：消除 chunked 文档远跳时的 UI 线程全量回读——
   `ensure_row` 改为按 chunk 按需加载，行加载状态从"连续水位线"改为
   "已加载区间表"，单次渲染最多读 1 个 chunk（256 KiB）。
2. **F2（major）**：`:fullload`（`Document.promote_to_full`）保留
   `read_only` 状态，修复 `-R`/只读会话中大文件升级后变为可写的契约漏洞。
3. **F3（minor）**：删除 `yate/editor_view/hexview.py` 死代码
   （`_format_hex` / `_format_ascii` / 未使用的模块级 `log` 及其 import）。
4. **F4（minor）**：`OverlayFlows.write_hex_edits` 把连续脏字节合并为
   单次写调用（减少半套用窗口，保持就地写语义）。

### 非目标

- 不手改 `CHANGELOG.md`（文件头声明由 `python -m tools.changelog` 生成、
  禁止手编；行为变更已在 `yate/docs/yaterc.{en,zh}.md` 手册披露）。
- 不改 `ChunkedTextFile` / `ChunkedBinaryFile` 的 L0 语义（测试与门禁已锁）。
- 不重设计后台扫描 worker（占位行扩展机制不变）。
- 不处理 hex 临时文件原子写（temp+replace）路线（见备选 D，否决）。

## 二、备选方案与否决理由

### F1 的备选

- **A（采纳）**：按 chunk 按需加载 + buffer 已加载区间表。
  单次渲染工作量有界（≤1 chunk 读 + 一次 LRU 命中查询），跳转即时可见，
  滚动回看时 gap chunk 逐个按需加载，无需后台排水 worker。
- **B（否决）**：保留水位线 + 后台 worker 渐进排水 gap。
  否决：goto 末行后目标行在 gap 排完前一直是占位行（体验更差）；
  worker 生命周期复杂化；排水最终仍要读完全程，只是把卡顿摊开。
- **C（否决）**：per-row loaded 位图。否决：多 GB 日志行数达千万级，
  内存 O(rows) 不可接受；区间表是 O(chunks)（1 GiB ≈ 4096 项）。
- **D（否决）**：保留水位线、只把填充起点钳到 `max(filled_rows, chunk_start)`。
  否决：直接违反 `rows_loaded` 契约——已填充的 gap 行被报为未加载，
  每帧重填 + watermark 语义损坏。

### F2 的备选

- **A（采纳）**：在 `promote_to_full` 原语内保留 `old.read_only`。
  覆盖全部设置来源（startup `-R`、扩展 API、LSP 只读）。
- **B（否决）**：在 `ChunkedFlows.promote_to_full` 里重新应用
  `startup_readonly`。否决：只覆盖 startup 一条路径，扩展/其他只读
  来源仍丢失；且原语层修复无需 flows 层知情。

### F4 的备选

- **A（采纳）**：连续偏移聚合为 run、每 run 一次 `seek+write`。
- **B（否决）**：临时文件 + `os.replace`。否决：改变 inode/句柄语义
  （Windows 上并发读者失效），对字节级补丁是过度设计，且就地写是
  既有文档化语义。

## 三、现状事实（file:line，2026-10-26 实测）

- `yate/flows/chunked_flows.py:86-111`：`ensure_row` 以
  `start = buf.filled_rows`（`yate/editor_core/buffer.py:230-232`）为
  填充起点，读到 `chunk_end`（目标行所属 chunk 末尾）——
  全量扫描完成后远跳 = UI 线程顺序读完全部中间 chunk。
- `yate/editor_core/buffer.py:133-135`（`_filled_rows`）、
  `:234-243`（`rows_loaded` 水位线比较）、`:255-267`（`fill_lines`）。
- `filled_rows` / `rows_loaded` 消费面实测：产品代码仅
  `chunked_flows.ensure_row`；其余为
  `tools/smoke_test/scenarios/chunkedview.py:104,121`（`rows_loaded`）
  与 `tests/test_document_chunked.py`。无其他产品调用方。
- `yate/editor_core/document.py:245-268`：`promote_to_full` 仅保留
  `tab_width` / `use_spaces`，`read_only` 丢失；
  `yate/flows/document_flows.py:156-158` 的 `_apply_session_readonly`
  只在打开时设置一次，不会重放。
- `yate/editor_view/hexview.py:435-443`：`_format_hex` / `_format_ascii`
  全仓（yate/ + tests/ + tools/）零调用；`:36` 模块级 `log` 零调用。
- `yate/flows/overlay_flows.py`（`write_hex_edits`）：当前按
  `for offset in sorted(edits): seek; write 1 byte` 逐字节写。
- 体量守卫：`buffer.py` 现测 1192 行（豁免名单内，修改后须按
  `splitlines()` 口径复测并同步
  `.trae/rules/architecture-boundaries.md` §三.7 条目行数）。

## 四、目标设计

### F1：buffer 已加载区间表 + ensure_row 按 chunk 填充

```mermaid
flowchart TD
    A["render_line(row)"] --> B["ensure_row(doc, row)"]
    B --> C{"rows_loaded(row, 1)<br/>区间二分查询"}
    C -->|已加载| Z["return（O(log k)）"]
    C -->|未加载| D["chunk_for_row(row) 定位所属 chunk"]
    D --> E{"rows_loaded(chunk_start,<br/>chunk_rows)"}
    E -->|整 chunk 已载| Z
    E -->|未载| F["read_rows(chunk_start, chunk_rows)<br/>≤1 chunk，LRU 缓存"]
    F --> G["fill_lines(chunk_start, rows)<br/>合并区间 + content_version++"]
    G --> Z
```

- **buffer 侧**：删除 `_filled_rows` 水位线与 `filled_rows` 属性；
  新增平行数组 `_loaded_starts` / `_loaded_ends`（合并、不相交、有序），
  `rows_loaded` 用 `bisect` 做区间覆盖检查；`fill_lines` 落行后合并标记
  `[start, end)`；`set_text` 清空区间表。填充原语仍忽略 `locked`、
  不计 `content_edits`、bump `content_version`（语义不变）。
- **flows 侧**：`ensure_row` 先查目标行（快路径），未加载则定位所属
  chunk，整 chunk 未加载才读——读取量从"水位线到目标 chunk 末尾"
  收窄为"单个 chunk"。
- 冒烟场景 `chunkedview.py` 用 `rows_loaded(0,1)` / `(total-1,1)` 等待，
  区间语义下行为不变，无需改动。

### F2：promote 保留 read_only

`promote_to_full` 中随 `tab_width` / `use_spaces` 一并保留
`buf.read_only = old.read_only`（docstring 同步）。

### F4：写回 run 聚合

连续偏移（`offset == run_end`）合并为一个 run，每 run 一次
`seek + bytes(edits[o] for o in range(run_start, run_end))`；
TOCTOU / conflict 闸门与返回指纹语义不变。

## 五、分步实施计划

> 执行者：plan-executor（独占文件清单见下）。每步完成即跑该步验收命令，
> 通过后**单独提交一次**（提交信息已给定；PowerShell here-string 书写；
> 只提交、不推送）。全部步骤完成后由主代理亲自跑全量门禁。

**独占文件清单（只改这些，不动其它任何文件）**：

- `yate/editor_core/buffer.py`
- `yate/flows/chunked_flows.py`
- `yate/editor_core/document.py`
- `yate/editor_view/hexview.py`
- `yate/flows/overlay_flows.py`
- `tests/test_document_chunked.py`
- `tests/test_overlay_flows_hex.py`
- `.trae/rules/architecture-boundaries.md`（仅 §三.7 buffer.py 行数复测值）
- `.trae/documents/hex-review-fixes-plan.md`（仅"六、执行记录"回填）

### Step 1 — F1 buffer 区间表（`fix(chunked)` 前半）

- 输入：§四 F1 设计 + §三 现状行号。
- 改动：`yate/editor_core/buffer.py`（区间表 + `rows_loaded` 重写 +
  `fill_lines` 标记 + `set_text` 清空 + 删 `_filled_rows`/`filled_rows` +
  docstring 同步；模块 docstring 的 chunked 段落一并更新）。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_document_chunked.py -q
  .venv\Scripts\python.exe -m pyright yate/editor_core/buffer.py
  ```
  （`filled_rows` 移除后若有测试引用报错，按 §六测试改造同步改——
  本步允许同 commit 内改 `tests/test_document_chunked.py` 的
  `test_fill_lines_progresses_watermark_without_edits` 改名与断言适配。）
- 体量复测：`.venv\Scripts\python.exe -c "print(len(open('yate/editor_core/buffer.py', encoding='utf-8').read().splitlines()))"`，
  把新行数写入 `.trae/rules/architecture-boundaries.md` §三.7
  `editor_core/buffer.py` 条目（保留原登记链，追加本次复测）。
- 提交：`fix(chunked): track loaded rows as merged intervals in TextBuffer`

### Step 2 — F1 ensure_row 按 chunk 填充（`fix(chunked)` 后半）

- 改动：`yate/flows/chunked_flows.py` `ensure_row` 按 §四 F1 重写
  （docstring 同步）；`tests/test_document_chunked.py` 重写
  `test_chunked_flows_ensure_row_fills_requested_chunk` 为区间语义，
  新增 `test_ensure_row_fills_only_the_owning_chunk`（跳末行 → 末 chunk
  已载、中部 gap 未载、`buffer.line(mid) == ""`；再 ensure 中部 → 其
  chunk 已载）。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_document_chunked.py tests/test_session.py -q
  .venv\Scripts\python.exe -m pyright yate/flows/chunked_flows.py
  ```
- 提交：`fix(chunked): load rendered chunks on demand instead of draining the fill gap`

### Step 3 — F2 promote 保留 read_only（`fix(document)`）

- 改动：`yate/editor_core/document.py` `promote_to_full` 加
  `buf.read_only = old.read_only`（docstring 补一句）；
  `tests/test_document_chunked.py` 新增
  `test_promote_to_full_preserves_read_only`
  （chunked + `read_only=True` → promote → `read_only is True` 且
  `locked is False`）。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_document_chunked.py -q
  .venv\Scripts\python.exe -m pyright yate/editor_core/document.py
  ```
- 提交：`fix(document): preserve the read-only flag across :fullload promotion`

### Step 4 — F3 死代码清理（`refactor(hexview)`）

- 改动：`yate/editor_view/hexview.py` 删除 `_format_hex` /
  `_format_ascii` / 模块级 `log` / `from yate.logs import tracing`。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pyright yate/editor_view/hexview.py
  .venv\Scripts\python.exe -m pytest tests/test_hex_view.py -q
  ```
- 提交：`refactor(hexview): drop the dead format helpers and unused logger`

### Step 5 — F4 写回 run 聚合（`fix(hex)`）

- 改动：`yate/flows/overlay_flows.py` `write_hex_edits` 循环聚合
  （docstring 补"contiguous runs coalesce"一句）；
  `tests/test_overlay_flows_hex.py` 新增
  `test_write_hex_edits_coalesces_contiguous_edits`
  （`{0:0x41, 1:0x42, 2:0x43, 100:0x44}` → 三个字节与 100 偏移逐字节正确，
  其余原样）。
- 验收命令：
  ```powershell
  .venv\Scripts\python.exe -m pytest tests/test_overlay_flows_hex.py tests/test_hex_view.py -q
  .venv\Scripts\python.exe -m pyright yate/flows/overlay_flows.py
  ```
- 提交：`fix(hex): coalesce contiguous dirty bytes into single writes`

## 六、执行记录（收尾回填）

### 6.1 Step 1-5 实测命令与退出码（2026-10-26，plan-executor 实测）

| Step | 命令 | 退出码 | 备注 |
|---|---|---|---|
| 1 | `pytest tests/test_document_chunked.py -q` | 1 → 0* | *首次 1：2 个失败——`test_chunked_flows_ensure_row_fills_requested_chunk`（ensure_row 仍引用已删除的 `filled_rows`，该产品代码属 Step 2 范围，见 §6.2 偏离 1）与执行者首次误写的 gap 断言（已修正，非计划问题）；以 Step 2 完成后的状态复跑通过（14 passed） |
| 1 | `pyright yate/editor_core/buffer.py` | 0 | 0 errors, 0 warnings |
| 1 | `python -c "...splitlines()..."` | — | buffer.py 实测 1224 行，已回填 `architecture-boundaries.md` §三.7 |
| 2 | `pytest tests/test_document_chunked.py tests/test_session.py -q` | 0 | 38 passed |
| 2 | `pyright yate/flows/chunked_flows.py` | 0 | 0 errors, 0 warnings |
| 3 | `pytest tests/test_document_chunked.py -q` | 1 → 0 | 首次 1：既有 `test_promote_to_full_restores_editing` 依赖旧缺陷行为（chunked 一律 `read_only=True`，promote 后丢失才可编辑），按 §6.2 偏离 2 做最小适配后通过（14 passed） |
| 3 | `pyright yate/editor_core/document.py` | 0 | 0 errors, 0 warnings |
| 4 | `pyright yate/editor_view/hexview.py` | 0 | 0 errors, 0 warnings |
| 4 | `pytest tests/test_hex_view.py -q` | 0 | 40 passed |
| 5 | `pytest tests/test_overlay_flows_hex.py tests/test_hex_view.py -q` | 0 | 57 passed |
| 5 | `pyright yate/flows/overlay_flows.py` | 0 | 0 errors, 0 warnings |

提交（6 个，均只 add 该步涉及文件、未推送）：
`a62ec80` Step 1 → `b9bd16d` Step 2 → `6a3cd3d` Step 3 →
`362041a` Step 4 → `1828397` Step 5 → 本条 docs 提交。

### 6.2 偏离计划记录

1. **Step 1 验收命令的中间红状态（计划拆分固有）**：Step 1 删除
   `filled_rows` 后，Step 1 自身的验收命令
   `pytest tests/test_document_chunked.py` 必然在
   `test_chunked_flows_ensure_row_fills_requested_chunk` 上失败——
   `chunked_flows.ensure_row`（产品代码，属 Step 2 文件）仍引用
   `buf.filled_rows`，而计划禁止 Step 1 提交触碰它。计划 §七 亦将
   Step 1-2 列为同一回滚单元。处置：如实记录失败与原因，Step 1 按计划
   文件清单提交，Step 2 修复后该测试随区间语义重写通过。
2. **Step 3 适配一处既有测试**：`test_promote_to_full_restores_editing`
   此前依赖"F2 修复后消失"的行为（chunked 缓冲区固定
   `read_only=True`，promote 后 read_only 丢失才可 type_char）。按计划
   "若某步验收命令失败，修复后重跑" 的授权做最小适配：promote 前显式
   `doc.buffer.read_only = False`（保持该测试原意——验证 promote 恢复
   可编辑），另按计划新增
   `test_promote_to_full_preserves_read_only` 锁定 F2。
3. 其余无偏离：区间表实现（bisect + 平行数组 + 合并）、ensure_row
   单 chunk 读取、run 聚合语义均按 §四 落地；未触碰非清单文件；
   未执行计划外测试/门禁（全量门禁由主代理收尾统一执行）。

### 6.3 主代理全量门禁实测数字（2026-10-26，最终树 @ `336cc80`）

| 门禁 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| pyright strict | `-m pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations | 0 |
| pytest 并行 | `-m pytest tests/ -q -n auto` | 全绿 | 0 |
| 架构测试 | `-m pytest tests/test_architecture.py -q` | 全绿（37 用例） | 0 |
| 覆盖率 | `-m pytest tests/ --cov=yate --cov-branch -n auto` | **91.92%**（≥75 门槛）；buffer 96% / chunked 93% / hexview 96% / chunked_flows 84% | 0 |
| 冒烟 | `-m tools.smoke_test run --jobs 4` | **117/117 场景，1410/1410 检查** | 0 |

### 6.4 收尾迭代与调度记录

1. **冒烟不变量修复（`336cc80`）**：首轮全量冒烟
   `chunked_text_open_and_scroll` 的 harness 不变量
   `invariant:saved_matches_disk` 失败（13/14），`--jobs 1` 单场景确定性
   复现（非时序 flake）。根因：旧水位线设计下远跳会顺带填满全程，
   `get_text()` 恰等于磁盘；F1 改为按需加载后 gap chunk 合法保持占位行，
   "整 buffer == 磁盘"前提对 chunked 文档不再成立。修复：
   `tools/smoke_test/harness.py` 对 chunked 文档改为只比对已加载行与磁盘
   字节；其余场景的不变量行为不变，基线不受牵动（chunked 场景无基线
   文件）。修复后全量冒烟 117/117 全绿。
2. **code-review-expert 判死（零产出）**：spawn 后两轮探活（约 16 分钟）
   无回信、只读评审无任何落盘产物，按 `subagent-workflow.md` §五.3 判死，
   未原样重试；评审职责由主代理按剧本兜底完成（逐 diff 对照计划 §四
   核查实现与测试语义 + 收尾门禁独立复跑，成员自报数字一律未采信）。

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| 区间表回归渲染路径（空行/占位渲染错乱） | 既有 309 行 chunked 测试 + 冒烟 chunked 场景全量重跑；`attach` 首屏填充语义不变 | `git revert` Step 1-2 提交 |
| `filled_rows` 移除破坏未知调用方 | §三 已实测消费面仅 `ensure_row`；pyright 全量门禁兜底 | 同上 |
| 只读保留后 `-R` 大文件行为变化（更严格） | 这是修复目标本身；新增测试锁定 | `git revert` Step 3 提交 |
| run 聚合写回行为变化 | 既有逐字节正确性测试（散布编辑）不動，新增连续 run 测试 | `git revert` Step 5 提交 |

## 八、批准记录

无人值守时段（用户指令"进入无人值守所有问题无须过问"）：
按 `task-orchestration.md` §二.5 bypass 条款，本方案视为已批准，
直接进入执行；收尾门禁（pyright + pytest + 架构测试 + 覆盖率 + 冒烟）
不由本条豁免，主代理亲自跑。
