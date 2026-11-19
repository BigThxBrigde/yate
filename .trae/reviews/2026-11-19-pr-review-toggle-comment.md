# PR Review — `feature/feat-toggle-comment`（合并前）

> 评审日期：2026-11-19（无人值守）｜模式：`review`（AI 预评审 + 主代理闭环修复）
> 对象：`feature/feat-toggle-comment` 相对 `master`（merge-base / base HEAD `50702ec7`），
> 评审起点 HEAD `431ab4f3`，ahead 8 / behind 0；34 文件 +1338/−55；
> issue IKWNOG「双键位统一注释入口」；无噪音文件。
> 本文为事实记录：发现证据 + 修复 commit + 门禁实测，不替代合并决策。

## 〇、执行方式（偏离登记）

- 按 `pr-review` skill 全维度执行。用户要求「全部子代理模型与主代理一致且不修改 agents 文件」，
  现有 spawn 参数无法同时满足，故由主代理亲自执行评审与修复，未派发子代理；
  子代理零产出，无 agents 文件改动。
- 基线按 `task-orchestration.md` §二取 `master`，不采用 skill 默认 `main`。

## 一、Overall

**REQUEST_CHANGES → 修复后 APPROVE**。发现 2 MAJOR，均当轮修复：

- MAJOR-1：`# ` / `// ` 等「仅 marker + 空白」行首次 toggle 塌成空行，二次 toggle 无法还原；
- MAJOR-2：`/*  x */` 等「marker 内侧多余空格」行剥层后丢空白且无法还原。

两项都直接破坏新引擎在 docstring 中承诺的「involution / 严格可逆」核心契约。
修复以 TDD 先红后绿，并补 2 个回归用例；修复后六道门禁全绿，0 项遗留阻断。

## 二、门禁实测（主代理独立执行，exit code 权威）

下表为**全部修复后**的最终数字。

| 门禁 | 结果 | exit |
|---|---|---|
| `pyright yate/ tests/ tools/` | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/ -q -n auto` | 全绿（10 skipped，无 failed） | 0 |
| `pytest tests/test_architecture.py -q` | 45 passed | 0 |
| `pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | TOTAL 93.09%，3959 passed / 10 skipped（修复前实测，本轮同口径） | 0 |
| `tools.smoke_test run --jobs 4` | 首两轮 123/124·1510/1511，第三轮 124/124·1511/1511 | 0（第三轮） |
| `python -m tools.changelog check` | 0 | 0 |

**冒烟负载伪影（非产品缺陷，未改断言）**：修复后前两轮并行冒烟均在
`stress_rapid_toggles` 的 sidebar `toggles_back` 一项失败（1510/1511），
与本轮改动（注释引擎判定形态）无交集；上一轮实现阶段也曾复现同一项首轮失败、
复跑全绿。第三轮 `--jobs 4` 全量 124/124·1511/1511 通过（85.31s，exit 0）。
按 `subagent-workflow.md` §三.3 记为负载敏感时序假设，不修改断言。

## 三、发现与闭环

### MAJOR-1（已修）marker + 空白行首次 toggle 不可逆

**位置**：`yate/editor_core/commenting.py:28`（原 `_line_is_commented`）
**证据**（修复前探针，负向演练 `RED_EXIT=1`）：

```
'# '    -> ''  -> ''    BROKEN
'  // ' -> '  ' -> '  ' BROKEN
'  #  ' -> '   '-> '   ' BROKEN
```

**问题**：判定只看 `line.lstrip().startswith(marker + " ")`。`"# "` 被认定为已注释，
剥层得空串；空行在下一轮 `rows` 过滤中被跳过，永远回不到原文。这违反模块 docstring
「a second toggle restores the exact original text / involution for arbitrary input」。
**修复**：判定要求 `marker + " "` 之后仍有非空白内容（`stripped[len(prefix):].strip()`），
使这类行走「加一层」路径而非「剥层」，从而两次 toggle 严格还原。
**回归用例**：`tests/test_commenting.py::test_marker_plus_space_only_line_round_trips`
（含 `"# "` / `"  // "` / `"  #  "` 三形态）。

### MAJOR-2（已修）块注释内侧多余空格行剥层丢空白

**位置**：`yate/editor_core/commenting.py:41`（原 `_block_is_commented`）
**证据**（修复前探针）：

```
'/*  x */'   -> ' x'    -> ' /* x */'      BROKEN
'/* x  */'   -> 'x '    -> '/* x  */'      BROKEN
'/*   x   */'-> '  x  ' -> '  /* x   */'    BROKEN
```

**问题**：原判定 `startswith(opening + " ") and endswith(" " + closing)` 对内侧
多于一个空格的行也成立，剥层固定切掉每侧一个空格，结果与原文不同；再次 toggle
又按新形态加层，无法还原。
**修复**：识别收敛到引擎自身生成的严格形态——剥出 content 后要求首末字符均非空白；
加层时把原文尾随空白外置到 closing 之后，剥层时再原样还原，从而任意形态都严格可逆。
**回归用例**：`tests/test_commenting.py::test_block_content_with_extra_inner_spaces_round_trips`
（含 5 形态）。边界矩阵复验 `BROKEN: []`。

### MINOR（1-2 已闭环于后续修复波，3 非缺陷）

1. `yate/editor_dispatch.py:45-47`：`"ctrl+shift+slash"` 作为 kitty/CSI-u 别名硬编码在
   dispatch 层，与 `TOGGLE_KEYMAP_KEY` 常量分离；未来改常量名有漂移风险。
   **已修**（`47b12c09`）：别名提升为 `yate/keymaps/keys.py::TOGGLE_KEYMAP_ALIAS`
   共享常量，dispatch 引用该常量；派发用例同步改引常量，焦点测试 + 架构守卫 + pyright 全绿。
2. `yate/commands.py:536`：`_toggle_comment(args: str)` 静默忽略参数；
   `:toggle-comment extra` 不会报错。
   **已修**（`fa1fdd37`）：非空参数时写 `warn` usage 并拒绝执行，与 `:enew` /
   `:macro-stop` 的无参命令惯例一致；补负向用例 `test_toggle_comment_command_rejects_arguments`。
3. `gcc` 后光标落在注释符所在行的首个非空白（即 marker 本身），与 vim 惯例一致；
   已由 `test_gcc_toggles_current_line_and_restores` 钉住，非缺陷，不修。

## 四、六维度结论

- **功能/正确性**：修复前两处可逆性缺陷已闭环；不动点性质经 18 组边界矩阵复验 `BROKEN: []`。
- **安全**：无 secrets / shell / eval / pickle / 路径遍历面；新增代码为纯文本行变换。
- **性能**：`comment_range` 为 O(rows)；`remap` 的前缀扫描为 O(line length)，无 N+1 / 无重复计算。
- **可维护性**：L0 纯函数 + 单一职责；公共 API 有 docstring 与类型注解；pyright 0。
- **架构**：新模块 `yate/editor_core/commenting.py` 属 L0 叶子，只依赖 `collections.abc`；
  L3 `actions.py` 消费 L0 + `editor_syntax`，方向向下；无新增 Protocol / TYPE_CHECKING /
  Any / type: ignore；架构守卫 45（含新增 `test_toggle_comment_keys_are_shared_and_identical`）。
- **门禁**：见 §二，全部 exit 0（冒烟第三轮）。

## 五、Strengths

- 双键位注释与切键位通过共享常量 + name-level dispatch 收口，避免 raw byte 不可区分的根本缺陷；
- 一次 `replace_range` 提交整段选区为单一 undo step，并 remap 选区端点保证二次按下精确还原；
- vim `gc{motion}` 用独立 `comment_pending` 状态复用现有 motion 解析，未污染 operator 状态机；
- 双语手册、which-key 文档、架构守卫与 4 条中文 changelog override 同步完整。

## 六、修复提交

- `680c3780` `fix(comment): keep toggling an involution on ambiguous marker rows`
  （引擎修复 + 2 个回归用例，TDD 先红后绿）
- 本评审记录与索引登记单独一笔提交（不 amend 上一笔，保留其原作者）

## 七、后续 MINOR 修复波（2026-11-19 无人值守闭环）

用户要求闭环修复发现的问题，本轮把上文两项真实 MINOR 一并处理，方案见
`.trae/documents/toggle-comment-review-fixes-plan.md`：

- `47b12c09` `refactor(keys): share the kitty keymap-toggle alias constant`
  —— 别名提升为 `TOGGLE_KEYMAP_ALIAS`（L0 keys），dispatch 引用；焦点测试 56 passed、pyright 0。
- `fa1fdd37` `fix(commands): reject arguments for :toggle-comment`
  —— 非空参数写 warn usage 并返回；初版 lambda 替身触发 3 处 `reportUnknownLambdaType`，
  改显式注解函数后 pyright 0、焦点测试 16 passed。
- 第 3 项（gcc 光标落 marker）复核为非缺陷，不修。

修复波实测（主代理亲跑，exit code 权威）：pyright 0 / pytest -n auto 全绿（10 skipped，exit 0）/
架构 45 passed exit 0 / 覆盖率 93.15%（3962 passed·10 skipped）exit 0 / changelog check 0 /
冒烟首轮 123/124（同一 sidebar flake，单跑 12/12）、复跑 124/124·1511/1511 exit 0。
自审 0 blocker / 0 major；全部遗留项闭环。
