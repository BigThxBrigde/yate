# toggle-comment pr-review 遗留 MINOR 修复方案

> 来源：`.trae/reviews/2026-11-19-pr-review-toggle-comment.md` §三 MINOR。
> 继承主方案：`toggle-comment-plan.md`（IKWNOG，分支 `feature/feat-toggle-comment`）。
> 本轮为无人值守闭环修复，仅处理两项真实 MINOR；第 3 项「gcc 光标落 marker」经复核
> 符合 vim 惯例且已有回归用例钉住，非缺陷，不修。

## 目标与非目标

- 目标 1：把 kitty/CSI-u 别名 `ctrl+shift+slash` 从 `editor_dispatch.py` 的硬编码
  提升为 `yate/keymaps/keys.py` 的共享常量，消除与 `TOGGLE_KEYMAP_KEY` 的漂移风险。
- 目标 2：`:toggle-comment` 对非空参数给出 usage 警告并拒绝执行，与 `:enew` /
  `:macro-stop` 的无参命令惯例一致。
- 非目标：不改键位语义、不改注释引擎、不改已通过的门禁口径、不新增架构守卫
  （守卫 45 已锁定 `TOGGLE_KEYMAP_KEY` / `TOGGLE_COMMENT_KEY` 在两套 keymap 的共享引用）。

## 改动文件与验收

### 波次 a：别名共享常量

- 输入：`yate/keymaps/keys.py:75-78`（`TOGGLE_KEYMAP_KEY` 定义处）；
  `yate/editor_dispatch.py:41-47`（`_KEYMAP_TOGGLE_NAMES`）；
  `tests/test_toggle_comment.py:164`（别名派发用例）。
- 改动：
  - `keys.py` 新增 `#: Textual event.key alias ...` + `TOGGLE_KEYMAP_ALIAS = "ctrl+shift+slash"`；
  - `editor_dispatch.py` 从 keys 导入并在 `_KEYMAP_TOGGLE_NAMES` 用常量替代字面量；
  - `tests/test_toggle_comment.py` 的别名派发用例改引常量（仍断言派发到 `toggle_keymap`）。
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_toggle_comment.py tests/test_architecture.py -q -n 1`
  全绿；`.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` 零诊断。

### 波次 b：命令参数校验

- 输入：`yate/commands.py:536-537`（`_toggle_comment`）；`tests/test_toggle_comment.py:136`（命令转发用例）。
- 改动：`_toggle_comment(args)` 在 `args.strip()` 非空时 `editor.message("usage: :toggle-comment takes no arguments", kind="warn")` 并返回；
  新增测试：带参时提示 warn 且不调用 action。
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_toggle_comment.py -q -n 1` 全绿。

## 风险与回滚

- 风险低：两处均为局部行为收紧，不改键位/引擎/派发路径。
- 回滚：逐 commit `git revert`（未推送，亦可逐文件还原）。

## 执行记录（2026-11-19，无人值守）

- 波次 a：`47b12c09` 别名共享常量。焦点测试 56 passed（toggle_comment + 架构）、pyright 0。
- 波次 b：`fa1fdd37` 命令参数校验。初版测试替身的 `message` / `execute_action` lambda
  触发 3 处 `reportUnknownLambdaType`，改为显式注解函数 `_command_editor` 后
  pyright 0、焦点测试 16 passed。
- 自审：0 blocker / 0 major；两处修改均局部收紧，无架构/类型逃逸；强制自我批判逐条核对证据真实、
  级别恰当、无漏报。

## 收尾

- 修订评审记录 MINOR 段：标注两项已修及 commit；同步 `.trae/reviews/README.md` 该轮状态。
- 主代理亲跑全量门禁：pyright、pytest -n auto、架构测试、覆盖率、冒烟 --jobs 4、changelog check。
- 按 `git-commit-message.md` 分波次单独提交（只提交、不推送）。
- 门禁结果（主代理实测，exit code 权威）：pyright 0（0 errors / 0 warnings）；
  `pytest -n auto` 全绿（10 skipped，exit 0）；架构 45 passed exit 0；
  覆盖率 `93.15%` ≥ 75，3962 passed / 10 skipped，exit 0；changelog check exit 0；
  冒烟首轮 123/124·1510/1511（`stress_rapid_toggles` sidebar `toggles_back` 已知负载 flake，
  单跑 12/12），复跑 124/124·1511/1511 exit 0。全部门禁通过。
