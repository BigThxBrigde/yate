# plan-c：接线（L3）

> 总纲见 `overview.md`。前置依赖：plan-b 的新构造参数。
> 本波是单点改动，价值在于把 L0 配置与 L2 组件正式接通并跑架构守卫。

## 一、目标

`OverlayFlows._palette()` 把 `YateConfig.file_preview` 传入 `PaletteScreen`，
Ctrl+P 全链路生效。

## 二、独占文件清单

- `yate/overlays.py`（改）

## 三、逐文件改动明细

`yate/overlays.py` 的 `_palette()`（当前 170-182 行）构造 `PaletteScreen` 时
增传一个关键字参数：

```python
return PaletteScreen(
    mode,
    workspace=self.workspace,
    commands=self.commands,
    actions=self.actions,
    open_path=self._open_path,
    focus_editor=self._focus_editor,
    execute_action=self._execute_action,
    run_command=self._run_command,
    refresh=self._refresh,
    preview=self.config.file_preview,
)
```

- `OverlayFlows.__init__` 已持有 `self.config: YateConfig`（overlays.py:41,60），
  **零新增注入、零新增 import、零白名单变更**。
- `open_command_palette()`（commands 模式）同样经此构造，`PaletteScreen`
  内部自行忽略预览（plan-b 已处理），本波不做模式区分。

## 四、架构边界自检

- R11：流程模块 import `editor_view` 是冻结存量，本次未新增导入 ✓
- 能力注入：不持 App 句柄，`config` 是构造期注入的具体对象 ✓
- R8：`file_preview` 是 frozen dataclass 具体实例 ✓
- R5/R7/R1/R2/R6：改动不触碰这些面；`tests/test_architecture.py` 22 用例
  作为守卫在验收命令中实证 ✓

## 五、验收命令（worktree 内）

```powershell
.venv\Scripts\python.exe -m pytest tests/test_architecture.py tests/test_dispatch_guards.py -q
.venv\Scripts\python.exe -m pyright yate/overlays.py
```

预期：全绿 + pyright 零诊断。

## 六、回滚

单参数回退；与 plan-b 同笔提交，无独立回滚面。
