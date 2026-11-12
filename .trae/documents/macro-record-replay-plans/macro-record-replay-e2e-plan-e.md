# 子计划 e：pilot 端到端与全量验收（wave-3）

> 唯一规范来源：本文件 + `../overview.md` §三 wave 表。可派
> `plan-executor`（Hy4，`bypassPermissions`，探活同回合闭合）或主代理
> 兜底；成员回报数据主代理独立复核。

## 1. 独占文件

只新建 `tests/test_macro_app.py`。

## 2. 用例（pilot 全 app 形态，先例 `tests/test_app_panes.py:35-53`）

| 用例 | 场景 → 断言 |
| --- | --- |
| `test_macro_record_then_replay_matches_manual_sequence` | vim keymap：录 `q` `a` + 编辑序列（如 `x` `i` `foo` `<esc>` `j`）+ `q` 停止 → 新行回放 `@a` → buffer 状态与手动执行同序列一致（AC1） |
| `test_macro_count_prefix_replays_n_times` | vim：`3@a` → 编辑效果精确 3 次；回放后 `count_str` 清零（后续 `x` 单次） |
| `test_macro_play_when_replay_in_progress_is_rejected` | 回放序列含 `@a` 自引用 → 回放终止不崩溃、`app.is_running`、无死循环（AC4） |
| `test_statusbar_shows_recording_indicator_during_record` | 录制中 statusbar 文本含 `rec @a`；停止后消失（AC5，文本断言经 statusbar widget 渲染产物或 refresh_status 返回） |
| `test_register_override_and_independent_registers` | 覆写同名寄存器（AC6）；未录制寄存器 `@z` warn 不干扰 |
| `test_colon_command_entry_matches_key_entry` | `:macro-record a` / `:macro-play a` 与按键路径 buffer 结果一致（AC7） |

## 3. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_macro_app.py -q -n 1
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
```

`test_macro_app.py` 连续 4 次 `-n 1` 全 0（时序敏感口径）。

## 4. 风险与回滚

pilot 时序 → `wait_until` 轮询谓词 + `pilot.pause()`（§4.7，禁真实睡眠）；
e2e 失败先区分产品缺陷 vs 用例时序（`-n 1` 复核），产品缺陷回 wave-1
对应子计划修复并登记。回滚：单文件删除即可。
