# SP1 — editor_core 内核（N1 N5 N6）

> 波次一 · 规模 M · [P2 原文](../P2_nice_to_have_plan.md)为唯一规范来源。

## 独占文件清单

**产品（任务书逐文件显式授权）：**
- `yate/editor_core/document.py`（N1）
- `yate/editor_core/buffer.py`（N5）
- `yate/editor_core/search.py`（N6）

**测试：** `tests/test_editor_core.py`（仅新增用例；既有用例不许改）

不许动其它任何文件；范围外发现上报主代理。

## 第 0 步：现状复核

逐条核对 P2 原文锚点（N1: document.py 打开归一 LF；N5: buffer.py 空格缩进按 tab_width 移除；
N6: search.py `replace_current` 独立实现），行号漂移就记录到本文件「校准记录」段并同步 P2 原文。
任何条目已消失（他处修复）→ 免实施、只回填。

## 条目执行

### N1 — 保存按原始主导 EOL 写回（行为变更）

1. **输入**：P2 原文 N1 行（策略：打开时记录原始主导 EOL，保存按其写回；仅已存在文件，新文件一律 LF）。
2. **步骤**：
   - `Document` 打开时检测各行尾，取主导 EOL（crlf / lf / cr）存实例属性；
   - `save()` 按该属性写回（LF 文件与新建文件维持现状，写 LF）；
   - docstring 说明行为（含 `:w` 外部改 EOL 的边界：以打开时检测为准）。
3. **输出**：CRLF 文件编辑保存后行尾仍为 CRLF；LF 文件不变。
4. **验收**：新增 round-trip 用例——构造 CRLF 文件 → 打开 → 编辑 → 保存 → 重新读断言 CRLF 保留；
   新建文件保存仍 LF；CR 单独成类时按记录值写回。
5. **注意**：与原子写（mkstemp + os.replace）协同——检测发生在 load 阶段，不碰保存链。

### N5 — Outdent 对齐上一个 tab stop

1. **输入**：P2 原文 N5 行（`rrem = removed % tab_width`，`removed - (rrem or tab_width)`；整 Tab 剥离保留）。
2. **步骤**：仅改空格缩进分支；整 Tab 剥离与混合缩进现状路径保持。
3. **输出**：tab_width=4 时「3 空格」outdent 移除 3、「8 空格」移除 4。
4. **验收**：新增两断言用例（3 空格 → 0；8 空格 → 4）；既有 outdent 用例全绿。

### N6 — `replace_current` 复用 `replace_range`

1. **输入**：P2 原文 N6 行（内部改调 `replace_range`，删重复实现）。
2. **步骤**：改为委托调用；确认光标/undo 语义与现实现一致（读两侧代码比对后再删）。
3. **输出**：行为零变化，重复实现删除。
4. **验收**：既有 replace 用例全绿；如发现委托后语义差异（如 anchor 处理），停下上报，不得静默改语义。

## 收尾清单

- [ ] `.venv\Scripts\python.exe -m pyright yate/editor_core/document.py yate/editor_core/buffer.py yate/editor_core/search.py tests/test_editor_core.py` → 0 诊断
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_editor_core.py -q` → exit 0
- [ ] 报告：改动清单 + 实跑命令与结果 + N1 行为变更说明（供用户人工确认）+ 校准记录

## 校准记录

（2026-09-25 实施）

- 三条锚点全部仍存在，无失效条目；门禁实测：pyright 0 诊断、`test_editor_core.py` 全绿
  （新增 6 条：CRLF round-trip、CR 写回、新建 LF、outdent 两条、单步 undo 契约）。
- **N1 行为变更校准**：`Document.__init__` 新增 `eol: str = "\n"` 字段；`open()` 归一化前调
  新增的 `_dominant_eol(text)`（统计 CRLF/孤立 LF/孤立 CR 取最频，并列按 CRLF > LF > CR）；
  `save()` 在 encode 前按 `self.eol` 回写。原子写链路未动。**待用户在真实 CRLF 文件上
  人工确认**；不满意可低成本回退（`Document.eol` 单点）。
- **N6 语义校准（主代理接受）**：空替换从静默 no-op 变为删除匹配——`replace_current`
  无产品调用方（仅测试触达），差异不可达；regex 反向引用展开保留。
- N5：空格分支改 `rrem = removed % tab_width`、`" " * (removed - (rrem or tab_width))`，
  整 Tab 剥离不动，删除 `max(0, …)`。
