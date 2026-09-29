# vim motion 边界偏差修复方案（w/b/$/G，review-vim-keymap 续作）

## 一、目标与非目标

**目标**：修复复查发现的 4 个 master 既有 motion 偏差（均为 L0 buffer 原语行为，vim keymap 只是调用者）：

1. `w` 跨行落下一行 col 0 → vim 落下一行**第一个非空白字符**；
2. `b` 跨行落上一行虚拟行尾列 → vim 落上一行**最后一个词首**；
3. `$` 落虚拟 EOL 列 `len` → vim normal 落**最后一个字符** `len-1`（operator/visual 保持虚拟列，`d$`/`c$` 不变）；
4. `G`/`gg` 落目标行 col 0 → vim normal 落**第一个非空白字符**（operator/visual 保持 col 0 及其既有 `min(1,len)` 修正）。

连带缺陷（实施推演发现，必须一并修）：`dw`/`db`/`yw`/`cw` cursor 在行内最后一个/第一个词时，w/b 跨行 wrap 使半开选区**跨行删除含换行符**；vim 的 exclusive 规则是**止于行边界**（`dw` 在行尾词 = `d$` 语义，不吞换行）。visual 模式的 `w`/`b` 跨行是 vim 行为，保持不变。

**非目标**：d{count}G 的 linewise 语义（现状 charwise，保持）；寄存器/`.`/`>>`/`%` 等已登记非目标；`e` 修复（已完成 `df5a179`）。

## 二、备选与否决理由

- **改 L0 buffer 原语**（`move_right(word=True)` 等做跨行扫描）：否决——vsc keymap 与编辑器其他路径共用这些原语，vim 专属词移动语义泄漏到通用层，影响面不可控。
- **全放 vim.py if 链内联**：否决——跨行扫描是纯函数逻辑，与 `e` 修复同款，放 textobjects.py（"vim-style motions" 的家）可测试、可复用。

## 三、分步实施

### S1 textobjects.py：跨行词首扫描 helper

新增两个纯函数（复用现有 `_is_word` 语义经 buffer 的 `next_word_start` / `prev_word_start`——注意 import 方向：textobjects 与 buffer 同为 L0，textobjects 可 import buffer）：

- `next_word_pos(lines, row, col) -> Pos | None`：行内 `next_word_start`；行内无 → 逐行向下，空行（len==0）停在 (r, 0)（vim 把空行当停点），仅空白行跳过，有内容行落第一个非空白；到底无落点返回 None。
- `prev_word_pos(lines, row, col) -> Pos | None`：行内 `prev_word_start`（须 < col）；行内无 → 逐行向上，空行停 (r, 0)，仅空白行跳过，有内容行落**最后一个词首**（从行尾第一个非空白反推 `prev_word_start(line, 非空白col+1)`）；到顶无落点返回 None。

验收：`pytest tests/test_textobjects.py -q` 新增单测全绿。

### S2 vim.py：motion 分支 + operator 特例

- `_motion` 的 `w`/`b` 分支改用 `next_word_pos` / `prev_word_pos`：无落点原地不动；落点为词首（含尾位），normal 与 select 同列（半开选区 `[start, 词首)` 恰为 vim `dw` 语义），无需 ±1。
- `_apply_operator` 新增行边界特例（与 cw 特判同款模式）：
  - `code == "w"` 且当前行从 cursor 起行内无下一词首 → `code = "$"`（`dw`/`cw`/`yw` 止于行尾，不吞换行）；
  - `code == "b"` 且当前行行内无上一词首 → `code = "0"`（`db`/`cb` 止于行首）。
- `$` 分支：`select=True` 保持 `move_line_end`（虚拟列）；normal 改落 `(r, max(0, len-1))`。已核既有 wrap 测试兼容（`$` 落 `len-1` 后 `e` 仍正确 wrap 到 (1,1)）。
- `G` 分支 count 落点、`_resolve_gg`：normal 落目标行第一个非空白（复用一个小 helper 或内联 `next((i for i,ch in enumerate(line) if not ch.isspace()), 0)`）；`select=True` 保持 col 0（visual 选到行首、operator `min(1,len)` 修正不变）。

改动文件：`yate/keymaps/vim.py`、`yate/editor_core/textobjects.py`、`tests/test_textobjects.py`、`tests/test_vim_keymap.py`（新增：w/b 跨行落点、空行停点、dw/db 行尾特例、$ normal 落点、G/gg first non-blank；钉定冲突则更新）。

### S3 门禁 + 收尾

- `python -m pyright yate/ tests/ tools/`（0 诊断）；
- `python -m pytest tests --cov=yate --cov-branch --cov-fail-under=75 -q`（全绿，覆盖率不回退）；
- `python -m tools.smoke_test run`（89/89）；
- 计划文档回填（本文件 + vim-keymap-review-plan.md 补记）→ 按 git-commit-message 分笔提交。

## 四、风险与回滚

- `$` 落点变更可能触发其他测试钉定：实施时先跑全量测试定位，逐处核对语义再改断言，不许静默改断言。
- `dw`/`db` 特例只影响 operator 路径；visual `w`/`b` 跨行保持——若测试发现 visual 期望不同，以 vim 实际行为为准记录偏离。
- 回滚：单笔 revert fix 提交即可，无数据迁移。

## 五、执行记录（收尾回填）

（待回填）
