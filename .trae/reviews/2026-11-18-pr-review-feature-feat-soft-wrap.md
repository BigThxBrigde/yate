# PR Review — `feature/feat-soft-wrap`（合并前 · 第二轮）

> 评审日期：2026-11-18（无人值守）｜模式：`review`（只读评审发现 + 主代理闭环修复）
> 对象：`feature/feat-soft-wrap` 相对 `master`（merge-base / base HEAD `015deee5`），
> 评审起点 HEAD `b1e56325`，ahead 23 / behind 0；评审起点 43 文件 +2919/−51，
> 含三次 master 合流（!139 option-spec-unify / !140 marks-jumplist / 一次 test-only 合流）。
> issue IKVRXT「软换行」；无噪音文件（无 lock/pyc/二进制）。
> 本文为事实记录：发现证据 + 修复 commit + 门禁实测，不替代合并决策。

## 〇、评审执行方式与判死误判更正

- 按 `pr-review` skill 派 2 名分维度只读评审员（`pr-func`：功能/健壮性/可维护性；
  `pr-perf`：性能/安全/架构/门禁），团队模式 `bypassPermissions`，自包含六维度任务书；
  模型要求按用户指令写入（主代理模型，不改 agent 定义文件）。
- **判死误判**：主代理在两名成员约 55 分钟未回信、零落盘时按 §五.3 判死零产出，
  并以 §三 主代理兜底完成自审、修复 1 MAJOR + 1 minor、跑完门禁、提交两笔、
  对外宣告完成。**其后两名成员的报告实际送达**（消息投递延迟，非未产出）：
  `pr-perf` 交 4 MAJOR / 5 MINOR 的完整报告 + 六门禁实测，`pr-func` 交阶段性 5 点方向
  （含弹窗锚点、gj/gk 落点列、render_line 每行重扫）。主代理的「零产出」结论**错误**，
  早先 §一/§六的 APPROVE 结论过早。这是 `feedback_subagent_death_judgment.md`
  「探活超时≠死亡；判死前查可观察产物」教训的重演，登记在此。
- 报告送达后主代理逐条回代码/运行时探针复核，确认其中 4 类问题成立并当轮修复，
  重写本记录。最终交付以本版为准，早先版本作废。

## 一、Overall

**REQUEST_CHANGES → 修复后 APPROVE**。两轮累计发现：

- 主代理自审（判死期间）：1 MAJOR（EOL block cursor 丢失）+ 1 minor（docstring 缓存键）；
- 评审员送达后复核确认：1 MAJOR 功能（弹窗锚点逻辑/显示行混用）、
  2 MAJOR 性能（wrap-on 全量重建、render_line 每行重扫）、1 MAJOR 覆盖缺口（gj/gk 真实映射
  零覆盖）、1 项语义偏差（gj/gk 落点列），以及 5 条 minor。

全部当轮修复，0 项遗留阻断。复查上轮 3 个 MAJOR 与 3 个 minor 的处置仍成立、
!139/!140 合流交互无回归；修复后六道门禁全绿。建议按 §五 遗留 minor 处理后合流。

## 二、门禁实测（主代理独立执行，exit code 权威）

下表为**全部修复后**的最终数字。

| 门禁 | 结果 | exit |
|---|---|---|
| `pyright yate/ tests/ tools/ pack/` | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/ -q -n auto` | 全绿（10 skipped，无 failed） | 0 |
| `pytest tests/test_architecture.py -q` | 44 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch -n auto` | TOTAL 93.14%（阈值 75%），3920 passed / 10 skipped | 0 |
| `tools.smoke_test run --jobs 4` | 124/124 场景、1511/1511 checks（见伪影说明） | 0（串行复核） |
| `git diff --check master...HEAD` | 无输出 | 0 |
| `python -m tools.changelog check` | 0 | 0 |

**环境伪影（非产品缺陷，未改任何断言）**：修复后首轮并行冒烟 `stress_rapid_toggles`
出现 1510/1511（11/12）；`--jobs 1` 串行全量曾复现一次 11/12，但**单独跑该场景**
12/12（3.62s）、再次串行全量 124/124·1511（86.75s）通过。判定为负载敏感时序假设
（快速 toggle 合帧窗口），与本轮修复（渲染 EOL padding / 弹窗锚点 / 折行缓存）无交集。
评审员 `pr-perf` 亦独立记录一次 safe-delete 钩子 10s 超时拖累
`test_macro_wiring.py` 内部 subprocess（单跑 0、全量复跑 0），同类环境伪影。

## 三、发现与闭环

### MAJOR-A（已修）wrap-on 下行尾 block cursor 在含宽字符/tab 的行上消失

- 位置：`yate/editor_components/view.py:625`（`render_line`）
- 问题：`end == len(offsets) - 1` 把 `span.cell_end`（**单元格偏移**）与
  `len(offsets)-1`（**字符数**）比较。纯 ASCII 行两者相等故测试全绿；含 CJK/tab/组合符时
  单元格数 > 字符数，条件恒假，padding cell 不进入绘制区间，行尾 block cursor 不可见。
- 实证：`cell_offsets`/`expand_char` 探针确认单位差异（`'a日bc'` 4 字符 / 5 单元格）；
  完整 app render 探针确认 wrap-on EOL 段 `reverse=False`（wrap-off 为 `True`）。
- 修复：`end == offsets[-1]`（行展开总单元格宽），补宽字符 + tab 两个参数化回归用例
  `test_wrap_eol_block_cursor_painted_with_wide_char`。负向演练（stash 回退源码）red →
  恢复 green。评审员 `pr-perf` 独立以 `'x\ty'`/`'漢a'` 复算确认根因与修法。

### MAJOR-B（已修）弹窗锚点把逻辑行当显示行（wrap-on）

- 位置：`yate/flows/completion_flows.py:293-294`、`yate/flows/hover_flows.py:184-185`
- 问题：补全/hover 弹窗用 `rel_row = logical_row - scroll_offset.y` 与
  `cell - scroll_col` 定位；wrap-on 时 `scroll_offset.y` 是**显示行**偏移且 `scroll_col`
  钉在 0，逻辑行前的每个折行都会让锚点错位。运行时探针实证：逻辑行 2 映射到显示行 7
  （scroll_y=0），旧代码给出 rel_row=2，正确值 7。
- 修复：`EditorView.screen_anchor(row, col)` 统一映射——wrap-on 经
  `WrapLayout.logical_to_display` 得显示行 + 续行内 cell 偏移，wrap-off 退回原公式；
  两条 flows 改调该方法（并移除失效的 `theme` 导入与参数）。补集成用例
  `test_screen_anchor_uses_display_row_when_wrapped`。`pr-func` 首提此点，`pr-perf` 未覆盖此维度。

### MAJOR-C（已修）wrap-on 下每次编辑全量重建 span 表

- 位置：`yate/editor_components/wrap_layout.py:149-155`（`update`）
- 问题：key 变化时对全部行 `enumerate` + `cell_offsets`；`content_version` 每次编辑都 bump。
  实测（主代理探针）：50k 行一次编辑 527.6 ms，200k 行 2139.9 ms；与计划
  `overview.md:330-336`「增量 O(新增行)」冲突。
- 修复：按行缓存上一版 span 组，`text_w`/`tab_width` 不变时内容相同的行直接复用，仅重排
  cumulative 前缀。修复后同机实测：50k 行一次编辑 13.9 ms、200k 行 58.2 ms。补守卫
  `test_edit_reuses_spans_for_unchanged_lines`（monkeypatch `cell_offsets` 计数：4 行改 1 行
  只调用 1 次；resize 令 4 行全部重算）。

### MAJOR-D（已修）wrap-on 下每个显示行重建整行展开（长行每帧 O(可见行×行宽)）

- 位置：`yate/editor_components/view.py:579-584`（`render_line`）
- 问题：`cell_offsets(line)` + `expand_char` 全行展开按显示行重复；一个长逻辑行占满可见
  窗口时每帧 O(可见行 × 行宽)。评审员实测 100k 字符行 ≈57.5 ms/行 ×30 行 ≈1.7 s/帧；
  主代理探针确认 `_wrap_line`（含 cell_offsets）100k 字符 30.7 ms 量级。
- 修复：`EditorView._line_expand_cache` 以 `(document, content_version, logical_row,
  tab_width)` 缓存 cells/offsets，同一逻辑行的续行复用；cells 复制后再加 EOL padding
  保证缓存纯净。补守卫 `test_wrapped_line_expansion_reused_across_display_rows`
  （6 续行只展开 1 次，切逻辑行才失效）。
- 负向演练（真实回归）：首版缓存键漏了 document 身份，`test_app_textual.py::
  test_tab_click_switches_the_rendered_document` 在切标签页时复用旧文档 cells 而失败
  （隔离单跑 exit 1）；补入 `self.doc` 身份后隔离与全量均绿。印证上轮 MAJOR「缓存键缺
  文档身份」同类陷阱。

### MAJOR-E（已修）gj/gk 真实显示行映射零覆盖

- 位置：`yate/editor_components/view.py:414-462`（`move_display_line`）
- 问题：覆盖率 term-missing 显示 433-450 未覆盖；`test_soft_wrap_keys.py` 8 条全用 stub
  回调，从不执行真实映射。补 Textual 集成用例 `test_move_display_line_lands_on_continuation`
  （长行 + wrap on：gj 落续行、wrap off 退化为逻辑行移动）。评审员建议可作为 MINOR，
  主代理按功能主路径风险保留 MAJOR 并补测。

### 语义偏差（已修）gj/gk 落点列未保留续行内 cell 偏移

- 位置：`view.py:451-461`
- 问题：代码取 `span.cell_start` 作落点列并丢弃 `logical_to_display` 的续行偏移，docstring
  却称「mirroring vim screen-column」；计划 `overview.md:341-345` 明确要求保持续行内 cell 偏移。
- 修复：落点 `min(span.cell_start + cell_in_span, span.cell_end)`；更正 docstring；
  测试增断言 `cursor == spans[1].cell_start + 4`（偏移 4 保留）。`pr-func` 与 `pr-perf` 均指出。

### minor（全部已修）

1. `.trae/rules/architecture-boundaries.md`：守卫用例数 42→44 并补登两条新守卫（43 soft-wrap
   键位、44 jumplist 键位）；`keymaps/vim.py` 豁免行数 1534→1595（实测 splitlines）。
   `pr-perf` 提出，主代理复核 `collect-only`=44、vim.py=1595 属实。
2. 缓存键 docstring：`view.py` 与 `wrap_layout.py` 由 3 元组更正为含 document 的元组；
   并进一步把 `tab_width` 纳入**实际** key（五元组），杜绝未来 `:set tab_width` 串表
   （`pr-perf` MINOR-3/4，潜在缺陷当时无运行期入口）。
3. `logical_to_display` 行内线性扫 span → 二分（span cell_end 单调递增，O(log wraps)）；
   `pr-perf` MINOR-5，与仓库「算法优先最低复杂度」口径一致。
4. 判死误判更正（§〇）；EOL 回归用例补 tab 覆盖（评审员要求确认两类）。

## 四、六维度结论

- **维度 1 功能/健壮性 PASS**（MAJOR-A/B/E + 落点偏差全修）：AC1-AC9 复核与上轮一致；
  identity `cell_end=0` 哨兵在 wrap-off 全部消费点安全；`_wrap_line` 边界（宽字符/tab 整字入
  下一行、孤立超宽字符、空行、text_w=1）测试背书；空 buffer 恒 1 行无越界。
- **维度 2 安全 PASS**：无新增 I/O/反序列化/subprocess/eval/路径拼接；`:set wrap` 经
  `OPTION_SPECS` bool 校验，非法值只提示不改状态（有测试）。
- **维度 3 性能 PASS**（MAJOR-C/D 修复后）：wrap-off O(1) identity 零行扫描；wrap-on 编辑
  只重排/复用未变行（50k 行编辑 13.9 ms）；同一逻辑行跨续行只展开一次；`logical_to_display`
  O(log wraps)。
- **维度 4 可维护性 PASS**：类型注解完整、docstring 英文散文、ASCII 注释、绝对导入、
  无新增 Any/type:ignore/Protocol；pyright 0。
- **维度 5 架构 PASS**：`wrap_layout.py` 为 L2 纯计算（只 import L2 `cells`）；R4 经
  `KeyUi.move_display_line`（PEP 695 `type` 别名）回调注入，`editor_compose.py` 接线；
  体量豁免两处同步（view.py 824 / editor.py 844，`SIZE_EXEMPT_FILES` 7 项）；
  !139 单表 wrap `OptionSpec(kind="bool")` 派生齐全；!140 键位并集无冲突（架构 44 passed）。
- **维度 6 硬门禁 PASS**：见 §二，全 exit 0。

## 五、强制自我批判

- 对判死误判：承认 §五.3 判死窗口不足导致零产出结论错误、过早 APPROVE 与对外宣告；
  根因是只看「未回信 + 无落盘」未等消息投递延迟。本版以送达报告逐条回码复核后重写。
- 对每条发现：先用真实函数/探针复算再定性——EOL cursor 用 `cell_offsets`+render 双探针；
  弹窗锚点用 app 探针（逻辑 2 vs 显示 7）；性能用 `WrapLayout.update` 计时前后对照；
  gj/gk 用实际 buffer 断言。剔除误报：`WrapLayout` 对 `identity` 用 `==` 无 `__eq__` 等价
  `is`，无误命中（评审员亦剔除）；`tab_width` 未入键当时无运行期入口，按潜在缺陷 minor 修。
- 修复后逐项验证：新增/修改用例全部先确认能捕获对应缺陷或覆盖真实路径；pyright 0、
  26 条 wrap 定向用例全绿，再跑全量六门禁。
- 环境伪影（冒烟 1510/1511、safe-delete 超时）经隔离单跑 + 串行全量复核确认，非缺陷，未改断言。

## 六、结论与遗留

`Overall: APPROVE`（两轮累计 6 MAJOR + 1 语义偏差 + 7 minor 全部闭环后）。分支未推送、未合入 master。

- 遗留 MINOR（非阻断）：CHANGELOG Unreleased 链接待合流后由 `tools.changelog` 重生成补链接；
  精确行数守卫脆弱性另案。
- 流程建议：后续 pr-review 判死窗口放宽至 >60 分钟并核对消息面；本轮两名评审员实际有产出，
  应与主代理自审合并取证，而非判死后独立收尾。
