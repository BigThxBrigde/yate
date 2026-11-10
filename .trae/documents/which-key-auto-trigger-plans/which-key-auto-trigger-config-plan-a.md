# wave-1 / plan-a：配置项与运行期 `:set` 机制

- 总纲：[overview.md](overview.md)；主计划：[../which-key-auto-trigger-plan.md](../which-key-auto-trigger-plan.md)
- 需求来源：[../which-key-auto-trigger-issue.md](../which-key-auto-trigger-issue.md)（§二.1、§三运行期切换 / 非 bool 值、§六示例配置）
- 同波并行：`plan-b`（文档），文件互不重叠
- 进入条件：方案批准（已自动批准）；退出条件：本文件 §五两条命令退出码 0

## 一、输入

- 主计划 §二调研事实、§四设计契约（命名 `which_key_auto`、默认 `True`、优先级）。
- 既有同构实现：`yate/config.py:169-176,349-354`；`yate/yaterc_options.py:552-559`；`yate/commands.py:106-133`；`yate/yaterc.example:66-69`。

## 二、独占文件清单（只改这些）

1. `yate/config.py`
2. `yate/yaterc_options.py`
3. `yate/commands.py`
4. `yate/yaterc.example`

禁止改动其它任何文件（含 `tests/**`、文档、流程模块）。

## 三、具体修改（`文件:行号` 级）

1. `yate/config.py:38` — `KNOWN_OPTIONS` 中在 `"which_key"` 之后插入 `"which_key_auto"`（保持 tuple 顺序语义；rc 变量白名单由 `_extract_options` 按名取值，前缀同名不冲突）。
2. `yate/config.py:176` 之后 — 新增公共字段与 ASCII 注释：
   `which_key_auto: bool = True`。`#:` 注释说明：仅门控自动触发（挂起前缀与 `ctrl+w` 和弦）；`False` 时 `<f9>` 手动 toggle 仍可用；`which_key=False` 总开关优先；默认 `True` 保持既有行为。注释与 docstring 不得出现 CJK / 全角标点。
3. `yate/config.py:355` 之前（`SET_OPTION_SPECS` 内 `which_key` 条目后）— 新增
   `SetOption(name="which_key_auto", aliases=(), parse=_parse_bool_option, invalid_message="which_key_auto must be on|off (true/false/1/0/yes/no accepted)", summary="which_key_auto=on|off")`。顺序决定 `:set` usage 行；不新增别名、不改 `set_option_names()`（自动派生）。
4. `yate/yaterc_options.py:559` 之后 — 追加与 `which_key` 同构的校验块：
   `which_key_auto = options.get("which_key_auto")`；`isinstance(..., bool)` 为真则 `config.which_key_auto = ...`；否则 `config.errors.append(f"which_key_auto must be True or False, got {which_key_auto!r}")`。不得抽新 helper（既有风格是内联同构块），不得吞异常。
5. `yate/commands.py:121` 之后 — 新增 `_apply_which_key_auto(editor: Editor, value: object) -> None`：
   `enabled = cast(bool, value)` → `editor.config.which_key_auto = enabled` → `editor.refresh_ui()` → `editor.message(f"which-key auto trigger {'on' if enabled else 'off'}", kind="ok")`；
   **不得**无条件调用 `editor.whichkey.clear()`（会抹掉 pinned 面板，见主计划 §四）。docstring 说明 `refresh()` 是唯一决策点且 pinned 分支优先。
6. `yate/commands.py:124-134` — `SET_APPLY.update(...)` 增加 `which_key_auto=_apply_which_key_auto`（与 `SET_OPTION_SPECS` 一一对应，否则 `tests/test_set_options.py:19-32` 守卫判红）。
7. `yate/yaterc.example:69` 之后 — 新增 ASCII 注释块，形如：
   `# Auto-popup for pending chords / ctrl+w (on by default).`
   `# Set False to keep the <f9> pinned sheet but stop automatic popups;`
   `# the which_key master switch still hides everything.`
   `# which_key_auto = True`

## 四、输出

- `YateConfig().which_key_auto is True`；rc `which_key_auto = False` 生效；非 bool rc 值记入 `config.errors` 且保持 `True`。
- `:set which_key_auto=off|on` 经统一表分派，写 config、触发一次 `refresh_ui()`、给消息行反馈；非法值走 `invalid_message` 且不改状态。
- `:set` 用法行、Tab 补全、`SET_OPTION_INDEX` 自动带上新选项（既有守卫覆盖）。

## 五、可执行验收命令（worktree cwd，PowerShell）

```powershell
.venv\Scripts\python.exe -m pyright yate/config.py yate/yaterc_options.py yate/commands.py
.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_set_options.py -q
git diff --check
```

判据：三条退出码均为 0。`pytest -q` 本环境无汇总行，以退出码为准；`test_set_option_specs_cover_all_dispatched_options` / `test_set_option_aliases_are_unique_across_specs` / `test_set_option_names_feed_cmdline_completions` 必须随新选项保持通过。

本波**不新增测试文件**（wave-3 `plan-d` 负责）；新增用例的验证方案见 `plan-d` §四。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| spec 与 apply 不同步导致既有守卫红 | 同一提交内同时改 `config.py` 与 `commands.py`，跑 `tests/test_set_options.py` | 回退两处 |
| `:set` 关闭时清掉 pinned 面板 | `_apply_which_key_auto` 不调 `clear()`，交给 `refresh()` 决策 | 删除该调用并复跑 wave-3 的 pinned 用例 |
| 非 bool 值被静默接受 | 与 `which_key` 完全同构的 `isinstance(bool)` + `errors.append` | 回退 `yaterc_options.py` 改动 |
| 注释出现非 ASCII 触犯架构守卫 | 新增注释全英文 ASCII | 改写文本（不得登记豁免） |

## 七、报告格式

改动清单（文件 + 行数）、实际执行的命令与退出码、未解决项与原因；不得引用他人自述数字。偏离本计划须显式列出并给实测依据。

## 八、执行回填（F1，2026-11-10）

实际命令与退出码（主代理复核）：

- `.venv\Scripts\python.exe -m pyright yate/config.py yate/yaterc_options.py yate/commands.py` → 3 文件 0 errors，退出码 0
- `.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_set_options.py -q` → 全绿，退出码 0
- `git diff --check` → 退出码 0

偏离：无。§三七条修改全部按计划落地，三条表一致性守卫随新选项保持通过。
