# wave-3 / plan-d：行为矩阵与配置 / `:set` 单测

- 总纲：[overview.md](overview.md)；主计划：[../which-key-auto-trigger-plan.md](../which-key-auto-trigger-plan.md)
- 依赖：wave-1 `plan-a`（config / commands）、wave-2 `plan-c`（流程门控 + `_make_flows` 新参数）全部验收通过
- 同波并行：`plan-e`（冒烟场景，`tools/**`），文件互不重叠

## 一、输入

- 主计划 §四行为矩阵；issue §三 7 条验收标准；`plan-c` 落地后的 `WhichKeyFlows.refresh()` 分支顺序。
- 复用基建：`tests/test_whichkey_flows.py:34-69` `_PanelRecorder`（`shown` / `clears` / `last`）与 `_make_flows(keymaps, window_pending=..., window_chord_hints=..., which_key_enabled=..., which_key_auto_enabled=...)`；`tests/conftest.py:366-377` `make_action_context()`；`tests/test_config.py:37-49` `_load()`；`tests/test_set_options.py:97-125` `_ConfigEditor` / `_set_driver()`。

## 二、独占文件清单（只改这些）

1. `tests/test_whichkey_flows.py` — **仅追加用例**（`plan-c` 已改 `_make_flows`，此处不得再改其签名 / 默认值）
2. `tests/test_config.py`
3. `tests/test_set_options.py`

## 三、新增测试用例（逐条：验证目标 / arrange / act / assert）

### `tests/test_whichkey_flows.py`（追加）

1. `test_behavior_matrix_of_master_and_auto_switches` — 覆盖 issue 四行矩阵，用 `@pytest.mark.parametrize("master,auto", [(True,True),(True,False),(False,True),(False,False)])`。
   - arrange：`vim = VimKeymap()`；`ctx = make_action_context()`；`vim.handle_key(ctx, "d")`；`flows, panel = _make_flows(KeymapSet({"vim": vim}, "vim"), which_key_enabled=lambda: master, which_key_auto_enabled=lambda: auto)`。
   - act：先 `flows.refresh()`，记录 `shown_before = list(panel.shown)` / `clears_before = panel.clears`；再 `flows.toggle()`。
   - assert：`(True,True)` → `shown_before[-1][0] == "d"` 且 `len(shown_before[-1][1]) > 0`，toggle 后 `panel.shown[-1][0] == "vim"`；`(True,False)` → `shown_before == []`、`clears_before == 1`，toggle 后 `panel.shown[-1][0] == "vim"` 且非空；`(False,*)` → `shown_before == []`，toggle 后 `panel.shown == []`（no-op）且 `panel.clears >= clears_before`。
2. `test_refresh_auto_disabled_hides_pending_candidates` — 验证关闭自动态不弹候选、也不改键位状态。arrange：vim 按 `"d"`、`auto=False`；act `flows.refresh()`；assert `vim.pending_prefix() == "d"`、`panel.shown == []`、`panel.clears == 1`。
3. `test_refresh_auto_disabled_hides_ctrl_w_chord` — 验证 `ctrl+w` 链（不经 `refresh_ui`）同样被门控。arrange：`_make_flows(..., window_pending=lambda: True, which_key_auto_enabled=lambda: False)`；act `refresh()`；assert `panel.shown == []`、`panel.clears == 1`。
4. `test_toggle_works_when_auto_disabled` — 验证核心需求：F9 手动 toggle 可用。arrange `auto=False`；act `toggle()` → assert `panel.shown[-1][0] == "vim"` 且 `len(panel.shown[-1][1]) > 0`；再 `toggle()` → assert `panel.last == "clear"`；再 `flows.refresh()` → assert 无新增 `shown`。
5. `test_refresh_auto_disabled_preserves_pinned_sheet` — 验证钉住态不被清除 / 覆盖。arrange `auto=False`，先 `toggle()` 钉住；再 `vim.handle_key(ctx, "d")` 并令 `window_pending=lambda: True`；act `refresh()`；assert `panel.shown[-1][0] == "vim"`、`all(header not in ("d", "ctrl+w") for header, _ in panel.shown)`、钉住之后的 `panel.clears` 不增加。
6. `test_auto_reenabled_restores_candidates` — 验证运行期重新开启。arrange `auto = [False]`、`which_key_auto_enabled=lambda: auto[0]`、vim 按 `"d"`；act `refresh()` → assert `panel.shown == []`；`auto[0] = True`；`refresh()` → assert `panel.shown[-1][0] == "d"` 且 `"dd" in {e.key for e in panel.shown[-1][1]}`。
7. `test_master_switch_off_wins_over_auto_disabled` — 验证两开关同时关闭时总开关语义不变。arrange `master=False`、`auto=False`、`window_pending=lambda: True`；act `refresh()` + `toggle()`；assert `panel.shown == []` 且 `panel.clears >= 1`（toggle no-op）。
8. `test_vsc_never_auto_pops_with_auto_disabled` — 验证 vsc 不受影响。arrange `KeymapSet({"vsc": VscKeymap()}, "vsc")`、`auto=False`；act `refresh()` → assert `panel.shown == []`；`toggle()` → assert `panel.shown[-1][0] == "vsc"`；`toggle()` → assert `panel.last == "clear"`。
9. `test_hide_after_manual_unpin_does_not_auto_pop` — 验证解除钉住后继续敲前缀不会重新自动弹出（issue 验收第 2 条）。arrange `auto=False`，`toggle()` 两次（钉住→解除），vim 按 `"g"`；act `refresh()`；assert `panel.shown == []`、`vim.pending_prefix() == "g"`。

### `tests/test_config.py`（追加）

10. `test_which_key_auto_defaults_true` — `assert cfg.YateConfig().which_key_auto is True`。
11. `test_which_key_auto_rc_value_applied(tmp_path)` — `_load("which_key_auto = False\n", tmp_path)`；assert `config.which_key_auto is False` 且 `config.errors == []`；并断言 `config.which_key is True`（总开关不被牵连）。
12. `test_which_key_auto_rejects_non_bool_keeps_default(tmp_path)` — `_load('which_key_auto = "yes"\n', tmp_path)`；assert 字段仍为 `True` 且 `any("which_key_auto must be True or False" in e for e in config.errors)`。
13. `test_known_options_lists_which_key_auto` — `assert "which_key_auto" in cfg.KNOWN_OPTIONS`（防 rc 白名单漏登）。

### `tests/test_set_options.py`（追加）

14. `test_set_which_key_auto_on_off_roundtrip` — `_set_driver()`；`entry.func("which_key_auto=off")` → assert `editor.config.which_key_auto is False`、`editor.refresh_calls == 1`、`editor.whichkey.clears == 0`（关键差异：不无条件清面板）、消息行含 `"auto trigger off"`；`entry.func("which_key_auto=on")` → assert `True`、`refresh_calls == 2`、`clears == 0`。
15. `test_set_which_key_auto_invalid_value_reports` — `entry.func("which_key_auto=maybe")`；assert 消息行含 `"which_key_auto must be on|off"`、`editor.config.which_key_auto is True`、`editor.refresh_calls == 0`、`editor.whichkey.clears == 0`（状态不变）。
16. 既有守卫 `test_set_option_specs_cover_all_dispatched_options` / `test_set_option_aliases_are_unique_across_specs` / `test_set_option_names_feed_cmdline_completions` 自动覆盖新选项，不改断言（若红说明 `plan-a` 接线漂移，回到 wave-1 修）。

**架构守卫**：不新增 `tests/test_architecture.py` 用例（依据主计划 §七：无新 import 连线 / 模块 / 协议，`:set` 表一致性已有专门守卫）。

## 四、验证方案与可执行验收命令

- 验证目标：四行矩阵、自动 / 手动互不干扰、总开关优先、运行期切换、非法值、vsc 不变、rc 白名单与默认值。
- 一并回归的既有范围：`tests/test_whichkey_flows.py`（全部）、`tests/test_config.py`、`tests/test_set_options.py`（含表一致性守卫）。
- 命令（worktree cwd，PowerShell）：

```powershell
.venv\Scripts\python.exe -m pyright tests/test_whichkey_flows.py tests/test_config.py tests/test_set_options.py
.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py tests/test_config.py tests/test_set_options.py -q
.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py tests/test_config.py tests/test_set_options.py -q -n 1
git diff --check
```

- 通过判定：四条退出码 0；`-q` 无汇总行时以退出码为准，需要数字用 `--collect-only -q` 统计。
- 负向演练（推荐，非强制）：临时把 `refresh()` 的 auto 闸门挪到 pinned 之前，确认用例 5 判红后还原；验证用例确实钉住了契约而非恒真。演练后须清 `__pycache__` 并复跑（本环境 pyc 时序伪影已知）。
- 无法自动化的部分（真实终端手感 / 视觉）由 `plan-e` 的 Textual pilot 冒烟覆盖。

## 五、输出

- 16 条用例（其中 3 条为既有守卫的回归确认，不新增断言）；新增 / 修改代码路径全覆盖；`plan-a` / `plan-c` 的默认值与门控顺序均有正反断言。
- 测试代码遵守 `python-coding-style.md`（`from __future__ import annotations`、完整注解、ASCII 注释 / docstring、`pytest.raises` 用在此处无需、无真实睡眠依赖）。

## 六、风险与回滚

| 风险 | 缓解 | 回滚 |
| --- | --- | --- |
| 既有 `_make_flows` 调用点因新参数报错 | `plan-c` 已给 helper 默认值并透传；本计划不改 helper | 回退本波新增用例并修 helper |
| 用例恒真（未真正验证分支顺序） | 用例 5 明确断言 pinned 优先 + 负向演练 | 补断言后复跑 |
| vim 前缀状态在 `escape` 后不确定 | 流程单测直接驱动 `vim.handle_key`，不依赖 Textual 按键取消语义 | 调整 arrange，不改产品代码 |
| 并行负载下时序 flake | 本波全是 headless 纯状态用例，仍按 `-n 1` 复核 | 修用例而非记成偶发 |

## 七、报告格式

用例清单与数量、四条命令实测退出码、`--collect-only -q` 计数（若取）、负向演练结果、未解决项。偏离须显式列出并给依据。
