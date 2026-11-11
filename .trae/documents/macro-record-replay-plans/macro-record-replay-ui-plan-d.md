# 子计划 d：录制指示 / which-key 提示 / `:macro-*` 命令（wave-2，主代理亲改）

> 唯一规范来源：本文件 + `../overview.md` §2.7/§2.8/§2.9。

## 1. 输入

- `statusbar.py:46-74`（`mode_chip` 纯函数）、`:122-235`（`refresh_status`
  fingerprint 短路）；R13：bar 自绘、Editor 只触发刷新。
- `whichkey_flows.py:80-103`（refresh 优先级链）、`:141-196`
  （`_candidates` / `_sheet_entries`）。
- `actions.py:26-60`（`populate` + `reg` 先例）；`commands.py:260-330`
  （`register_commands` + `_saveas`/`_edit` 参数解析先例）。

## 2. 独占文件

`yate/editor_components/statusbar.py`、`yate/flows/whichkey_flows.py`、
`yate/actions.py`、`yate/commands.py`、新建 `tests/test_macro_commands.py`。

## 3. 具体修改

1. `statusbar.py`：`refresh_status` 在模式 chip 后追加宏段——
   `session.macro_recording` 非空 → `rec @{reg}`（读 session 已注入；
   fingerprint 输入纳入宏态避免陈旧缓存）；纯文本拼接，不改 CSS/样式。
2. `whichkey_flows.py`：`refresh()` 优先级链在 ctrl+w 之后插 awaiting
   分支（总纲 §2.9）：awaiting=="record" → 单条提示行（寄存器 a-z0-9）；
   awaiting=="play" → 两条（`@ again repeats last` + 寄存器行）。数据
   直读 session，不新增依赖。
3. `actions.py`：`populate` 注册 `macro_record_prefix` /
   `macro_play_prefix`（动作体设 `ctx.session.macro_awaiting`，见总纲
   §2.7；描述文案对齐邻近条目）。
4. `commands.py`：注册 `:macro-record` / `:macro-play` / `:macro-repeat`
   （总纲 §2.8 参数解析与报错规格；error 走 `editor.message`？命令
   handler 的报错先例以 `_edit`/`_enew` 为准——按既有 message/error
   通道输出，登记实际采用形态）。

## 4. 测试用例（headless 命令级 + statusbar 纯函数级）

| 用例 | 三要素 |
| --- | --- |
| `test_macro_record_command_without_args_while_recording_stops` | 录制中 `:macro-record` → 停止；未录制 → error 提示 |
| `test_macro_record_command_with_invalid_register_errors` | `:macro-record !` → error、无状态变化（AC7） |
| `test_macro_play_command_parses_register_and_count` | `:macro-play a 3` → 重放 3 遍（AC2） |
| `test_macro_play_command_rejects_bad_count` | `:macro-play a 0` / `a x` → error |
| `test_macro_repeat_command_replays_last_register` | `:macro-repeat` → last；`:macro-repeat 2` → 2 遍 |
| `test_mode_chip_or_statusbar_shows_recording_indicator` | 录制态文本含 `rec @a`；停止后消失（AC5） |
| `test_whichkey_flow_shows_macro_awaiting_hint` | awaiting 态 refresh → 提示行出现；清后消失 |

## 5. 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_macro_commands.py -q
.venv\Scripts\python.exe -m pytest tests/test_whichkey_flows.py tests/test_statusbar.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m tools.changelog check
```

（`tests/test_statusbar.py` 不存在则以实际状态栏测试文件名为准，先探针
`Get-ChildItem tests/test_*status*`，报告登记。）

## 6. 风险与回滚

statusbar fingerprint 变更引发刷新频率上升 → 仅宏态翻转时变化，实测
全量 pytest；whichkey 优先级插入影响 ctrl+w 面板 → `test_whichkey_flows`
既有矩阵全绿为准。回滚：各文件独立 revert。
