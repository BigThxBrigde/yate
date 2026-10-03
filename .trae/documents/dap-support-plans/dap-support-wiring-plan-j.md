# dap-support plan-j：Editor 接线 / 动作 / 命令 / 调试键位（W5，全计划枢纽）

主计划依据：§5.1、§5.5、§5.6；§1 Editor 中枢行。

## 目标

把 plan-a/b/e/f/i 的产物接进 L3：`ed.dap` 构造与事件接线、DebugPanel 挂载
与面板互斥、8 个动作、`:debug` 系列命令、vsc/vim 调试键位 + DBG 帮助分类、
退出关闭、R11 白名单登记。

## 非目标

不写视图层（plan-i 已交付）；不改 diagnostics（plan-k）；不改文档（plan-l）。

## 独占文件清单（只改这些）

- `yate/editor.py` —
  `ed.dap = DapManager(...)` 构造于 :91-94 旁（`on_event` 落
  `DapSync.on_event`，镜像 `ed.lsp` lambda）；on_mount :425-426 区挂
  DebugPanel（compose :416-420 `#bottom-dock`、TerminalPanel 之上，初始
  `display=False`，`apply_height` 用 `terminal_height`）并把 gutter 执行行
  查询回调、面板数据协作者注入 plan-i 的 widget；按键路由 :576-578 区加
  面板互斥（开 DebugPanel 先 `terminal_panel.close()`，反向亦然）与调试键
  fallback；调试动作用 `self.app.run_worker(..., group="dap",
  exclusive=False, exit_on_error=False)`（范式 :832-835；Editor 是 L3 唯一
  App 句柄持有者）；`on_unmount` :462 后并列
  `await self.dap.shutdown_all()`（try/except 隔离，:449-464 区）；
  扩展加载 :429 / yaterc 注册 :430 零改动；
- `yate/dap_sync.py`（新增）— `DapSync` 镜像
  [lsp_sync.py](../../yate/lsp_sync.py)（`on_event(kind)` :80 范式）：
  stopped/continued → 刷视图/面板/状态栏；output → 面板或 "●" 提示；
  terminated → 退出码消息 + 恢复 gutter；failed → 红字原因（未装 adapter
  给 `pip install debugpy` 提示）；**不持 App 句柄**（worker 经 Editor 注入
  `spawn`，能力注入守卫 `test_flow_modules_hold_no_app_handle`）；
- `yate/actions.py` — `populate`（:26-196）注册
  `debug_start_or_continue / toggle_breakpoint / step_over / step_into /
  step_out / pause_debug / debug_stop / debug_panel`（动作体转发
  editor/dap_sync；`command_prompt` :175 不动）；
- `yate/commands.py` — `register_commands`（:80-365，范式 :333-335）注册
  `:debug [path]` / `:cont(:continue)` / `:break` / `:next` / `:step` /
  `:finish` / `:pause-debug` / `:debug-stop` / `:debug-restart`（报 "not
  yet"）/ `:eval [expr]` / `:debug-panel [out|info]`；
- `yate/keymaps/vsc.py` — 常量区 :10-18 加 `DBG = "Debug"`；绑定
  F5/F6/F9/F10/F11/F12/Shift+F5/Shift+F11（主计划 §5.5 表）；
- `yate/keymaps/vim.py` — 同组调试键仅 NORMAL/VISUAL（INSERT 不拦截）；
- `tests/test_architecture.py` — `UI_FROZEN_FILES`（:114-165）登记
  `yate/dap_sync.py`（R11）；负向演练：临时移除登记确认拦截后还原；
- `tests/test_dap_tui.py` — 追加真接线用例：F7 开 ex 行、F5 无会话
  launch/PAUSED continue/RUNNING 提示、`:debug/:next/:cont/:debug-stop`
  在假 manager 下动作正确、未保存提示、面板互斥、Editor 关闭路径调
  `dap.shutdown_all`。

## 实施要点

1. 依赖就绪检查：plan-a（Shift+F5/F11 解析）、plan-b（F5 已腾出）、
   plan-e（DapManager）、plan-f（api.dap，扩展注册时序）、plan-i（面板）。
2. `debug_start_or_continue` 状态分发表（无会话=launch、PAUSED=continue、
   RUNNING=noop 提示）；F9 无会话允许切断点（launch 时统一下发）。
3. `set_debug_options(config.debug_options)`（plan-h 产物）在构造后注入。
4. 架构自检清单逐项过（主计划引 architecture-boundaries §五）：无
   `*Controller` 命名、无 `self.app` 在流程模块、日志走 tracing 惰性 %。

## 验收命令

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dap_tui.py tests/test_action_table.py tests/test_command_path_args.py tests/test_vsc_keymap.py tests/test_vim_keymap.py tests/test_architecture.py -q
.venv\Scripts\python.exe -m pyright yate/ tests/
.venv\Scripts\python.exe -m pytest tests/ -q
```

## 风险与回滚

- editor.py 是全应用枢纽：改动按上述锚点最小侵入，逐 commit 分小步
  （构造/挂载/路由/关闭可分四次提交）。
- R11 登记遗漏导致架构测试红：负向演练已含在本计划验收。
- 回滚：editor.py/actions.py/commands.py/keymaps 各自独立 commit，
  可按文件 revert；dap_sync.py 删除 + 白名单行移除。
