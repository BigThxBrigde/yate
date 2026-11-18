# PR Review — `feature/feat-soft-wrap`（合并前 · 第二轮）

> 评审日期：2026-11-18（无人值守）｜模式：`review`（只读评审发现 + 主代理闭环修复）
> 对象：`feature/feat-soft-wrap` 相对 `master`（merge-base / base HEAD `015deee5`），
> 评审起点 HEAD `b1e56325`，ahead 23 / behind 0；评审起点 43 文件 +2919/−51，
> 含三次 master 合流（!139 option-spec-unify / !140 marks-jumplist / 一次 test-only 合流）。
> issue IKVRXT「软换行」；无噪音文件（无 lock/pyc/二进制）。
> 本文为事实记录：发现证据 + 修复 commit + 门禁实测，不替代合并决策。

## 〇、评审执行方式（偏离登记）

- 按 `pr-review` skill 派 2 名分维度只读评审员（`pr-func`：功能/健壮性/可维护性；
  `pr-perf`：性能/安全/架构/门禁），团队模式 `bypassPermissions`，任务书自包含六维度
  与唯一规范来源；模型要求按用户指令写入任务书（主代理模型，不改 agent 定义文件）。
- 两名成员自 spawn 起累计约 55 分钟，跨多次探活零回信、零落盘产物（任务书限定只读，
  故无文件产出可查），按 `subagent-workflow.md` §五.3 判死零产出。
- 按 `task-orchestration.md` §三由**主代理亲自**执行 pr-review 剧本：独立跑六道硬门禁 +
  六维度读码自审 + 目标缺陷运行时探针。本报告全部数字与发现均来自主代理实测，
  不采信任何子代理自述。
- 这是流程偏离（两名评审员零交付 → 主代理兜底），如实登记；与上轮
  `2026-11-17-pr-review-feature-feat-soft-wrap.md` §〇 同类。

## 一、Overall

**REQUEST_CHANGES → 修复后 APPROVE**。本轮新发现 **1 MAJOR / 0 BLOCKER**：
wrap-on 下含宽字符/tab 的行，行尾 block cursor 因 cell/char 单位混用而消失。
该 MAJOR 已当轮修复（带回归用例，负向演练先红后绿）；复查上轮 3 个 MAJOR 与
3 个 minor 的处置仍成立、!139/!140 合流交互无回归；修复后六道门禁全绿。
建议按 §四 遗留 minor 酌情处理后合流。

## 二、门禁实测（主代理独立执行，exit code 权威）

修复前后各跑一轮；下表为**修复后**最终数字。

| 门禁 | 结果 | exit |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/ -q -n auto` | 全绿（10 skipped，无 failed） | 0 |
| `pytest tests/test_architecture.py -q` | 44 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | TOTAL 93.03%（阈值 75%），3915 passed / 10 skipped | 0 |
| `tools.smoke_test run --jobs 4` | 124/124 场景、1511/1511 checks（详见下方伪影说明） | 0（串行复核） |
| `git diff --check master...HEAD` | 无输出 | 0 |

**修复前数字**（对照）：pyright 0 / pytest 全绿 / 架构 44 / 覆盖率 90.36%
（3914 passed / 10 skipped）/ 冒烟 124/124·1511 / diffcheck 0——全 exit 0。
修复后覆盖率上升至 93.03%（新增回归用例覆盖此前未触达的 EOL 绘制分支）。

**环境伪影（非产品缺陷，未改任何断言）**：修复后首轮并行冒烟 `stress_rapid_toggles`
出现 1510/1511（11/12）；`--jobs 1` 串行全量仍复现一次同一场景 11/12，但**单独跑该
场景** 12/12 通过（3.62s），再次串行全量 124/124·1511（86.75s）通过。按
`python-coding-style.md` §4.7 / `subagent-workflow.md` §三.3，判定为负载敏感的时序
假设（快速 toggle 的合帧窗口），非 MAJOR 修复引入（修复仅触及 `render_line` 的 EOL
padding 单元比较，与该场景切换逻辑无交集），不修改任何测试断言。

## 三、发现与闭环

### MAJOR-1（已修）wrap-on 下行尾 block cursor 在含宽字符/tab 的行上消失

- 位置：`yate/editor_components/view.py:625`（`render_line`）
- 问题：`render_line` 判断「末 span 需要追加一个 padding cell 绘制行尾 block cursor」
  时用 `end == len(offsets) - 1`——`end` 是 `span.cell_end`（**单元格偏移**），
  `len(offsets)-1` 是**字符数**。纯 ASCII 行两者相等故测试全绿；一旦行内含宽字符
  （CJK）/tab/组合符，单元格数 > 字符数，`span.cell_end == offsets[-1] > len(line)-1`，
  条件恒假，padding cell 不进入绘制区间，行尾 block cursor 不可见。
  - 实证探针（临时脚本，验证后删除）：同样 `wrap on` + 光标置于行尾，行 `"a日bc"`
    （4 字符 / 5 单元格）——`wrap=False` 行尾段含 `reverse=True`（cursor 样式），
    `wrap=True` 行尾段 `reverse=False`（cursor 丢失）。对照纯 ASCII 行 wrap on/off
    均正常，确认为单元格/字符单位混用。
  - 影响面：仅在 wrap **开启**时触发（默认 wrap off 的 wrap-off 分支用
    `scroll_col` 开窗，不受影响）；属于本分支新功能的边界态功能缺陷。
- 修复：`end == offsets[-1]`（`offsets[-1]` 即该行展开后的总单元格宽度），并补注释
  说明为何不能用字符数比较。新增回归用例
  `tests/test_soft_wrap_chunked.py::test_wrap_eol_block_cursor_painted_with_wide_char`。
- 验证：负向演练（`git stash` 回退源码修复）用例 red（exit 1，`assert []`）；
  恢复修复后 green（exit 0）。软换行 4 个测试文件 35 用例全绿。

### MINOR-1（已修，随 MAJOR-1 同轮）WrapLayout 类 docstring 缓存键漏列 document

- 位置：`yate/editor_components/wrap_layout.py:88-92`
- 问题：类 docstring 写 `version_key` 对应 `(content_version, text_w, wrap_enabled)`，
  遗漏第 4 项 document identity（MAJOR 修复 `0e25ca48` 引入），与 `update()` docstring
  及实际 4 元组的 `version_key` 不一致。
- 修复：docstring 更正为 `(content_version, text_w, wrap_enabled, document)`。纯注释变更，
  随 MAJOR-1 一并纳入回归门禁。

## 四、六维度结论

### 维度 1 功能正确性与健壮性 — PASS（1 MAJOR 已修）

- **AC1-AC9** 逐项复核（显示层折行零改 buffer、单元格/tab/宽字符边界、wrap-off 零回归、
  vim gj/gk、alt+z 双 keymap、续行 gutter、chunked 逻辑行口径、性能、双语）与上轮一致。
- **上轮 3 MAJOR 复查**：`0e25ca48`（缓存键含 doc identity）、`003432e6`（visual gj/gk 保 anchor）、
  `ed74926f`（wrap-off O(1) identity 快路径）在合入 !139/!140 后仍保留、无回归。
- identity `cell_end=0` 哨兵在 wrap-off 全部 span 消费点安全（render_line 文本窗口、
  buffer_pos_from_mouse、reveal_cursor、move_display_line 均走各自 wrap-off 分支，不读 span cell 窗口）。
- `_wrap_line` 边界（宽字符/tab 整字入下一行、孤立超宽字符独占行、空行、text_w=1）经
  `test_wrap_layout.py` 全绿背书；空 buffer 恒 1 行，`move_display_line` 无零行越界。

### 维度 2 安全 — PASS

diff 为渲染/键位/配置/文档，无新文件 I/O、反序列化、网络、shell 注入面或硬编码密钥。

### 维度 3 性能 — PASS

- WrapLayout.update 缓存键 4 元组 O(1) 比较；wrap-off O(1) identity 快路径零行扫描
  （`test_disabled_wrap_identity_update_is_o1` 背书）；wrap-on 重建只在 key 变化时。
- render_line 每帧 offsets/styles/kinds 各构建一次（perf-audit 后的合并结果），未回退。

### 维度 4 可维护性 — PASS（1 minor 已修，见 §三 MINOR-1）

类型注解完整、docstring 英文散文、ASCII 注释、绝对导入、无新增 Any/type:ignore/Protocol。

### 维度 5 架构边界 — FAIL→PASS（BLOCKER by definition 无命中）

- 新模块 `wrap_layout.py` 为纯 L2 计算（无 widget 基类、无向上依赖），R1-R15 无违规；
  keymaps(L1) 经 `KeyUi.move_display_line` 回调注入，符合 R4。
- `view.py`(816)/`editor.py`(840) 体量豁免在合入 !139/!140 后仍与规则 §三.7 文本、
  `SIZE_EXEMPT_FILES` 两处同步；架构测试 44 passed（本轮新增 marks-jumplist 守卫）。
- **!139 交互**：`wrap` 已迁为 `OPTION_SPECS` 单表 `OptionSpec(kind="bool")`，
  `KNOWN_OPTIONS`/`SET_OPTION_SPECS`/补全候选由通用循环派生，`:set wrap` →
  `_apply_wrap` → `Editor.set_soft_wrap` 与 alt+z 共享一条消息/重绘路径；
  `test_option_specs.py` 数量 14、两条顺序断言含 wrap，全绿。
- **!140 交互**：vim/vsc 键位并集含 marks/jumplist 与 soft-wrap 键位，无覆盖；
  `test_action_table.py` / 架构漂移守卫全绿；双语 manual 键位表并存无冲突。

### 维度 6 硬门禁 — PASS（BLOCKER by definition）

见 §二表，6 项全 exit 0（修复后最终轮）。

## 五、强制自我批判（已执行）

- 初版关注点逐条回代码实证：`end == len(offsets)-1` 的单元格/字符混用先用
  `cell_offsets`/`expand_char` 探针确认数值差异，再用完整 app render 探针确认
  wrap-on 下行尾 cursor 确实消失（对照 wrap-off 正常），非误报。
- 反证排除：`logical_to_display` 的 `last` 与 `_syntax_kinds` 的 `len(offsets)-1`
  均按字符索引 offsets，用法正确（非同类 bug），未误改。
- 修复后逐项复核：`offsets[-1]` 恒等于展开单元格总数，与 `span.cell_end`（末 span
  的 cell 终点）同一单位；负向演练 red→green 钉死因果关系。
- 门禁两处失败（并行 1510/1511、串行复现一次）经隔离单跑 12/12 + 串行全量 124/124
  确认时序伪影，剔除为环境原因，未改断言。
- 反向扫漏报：复查 diff 无新 I/O/注入面；复查 3 个历史 MAJOR 与 3 个 minor 的下游调用点无遗漏。

## 六、结论与遗留

`Overall: APPROVE`（修复 1 MAJOR + 1 minor 后）。分支未推送、未合入 master。

- 遗留 MINOR（非阻断，沿用上轮）：CHANGELOG Unreleased 条目待合流后由 `tools.changelog`
  重生成补链接；`architecture-boundaries.md` §三.7 把 editor.py 精确行数写死在规则文本的
  脆弱守卫，另案优化。
- 本轮 2 名评审员零产出、主代理兜底的偏离见 §〇；建议后续 pr-review 沿用运行时有效模型
  派发或主代理直做，省去判死窗口。
