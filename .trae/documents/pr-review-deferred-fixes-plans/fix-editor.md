# 子计划 fix-editor — m8 `alt+shift+f` 改走 action 注册

**Worktree 根**：`../yate-file-manager`（分支 `feat/file-manager`）。
**评审依据**：`.trae/reviews/2026-11-01-pr-review-feat-file-manager.md` §一 m8（先读全文）。

## 独占文件

- `yate/editor.py`

## 修改点

`editor.py:896-901`（`handle_key` 内，当前实测）：

```python
# alt+shift+f opens the file manager overlay: same alt+shift shape
# as the two chords above (no raw byte form, keymap row is
# help-only), so the real dispatch is by key name here.
if event.key == "alt+shift+f":
    self.filemanager_flows.open_overlay()
    return True
```

改为：

```python
if event.key == "alt+shift+f":
    self.execute_action("file_manager")
    return True
```

与上方 `alt+shift+s` → `execute_action("toggle_screensaver")`（893-895）同形。
按键名拦截本身保留（alt+shift 组合弦无原始字节形态，注释前两句仍成立），
第三句补一短句说明调用已改走 action 注册表（扩展重绑/包装 `file_manager`
即可生效）。

**前置核实（必做）**：grep `yate/actions.py` 确认 `file_manager` 动作注册体确实
路由到 `filemanager_flows.open_overlay()`（评审记录引 `actions.py:218-219`，
行号可能漂移，按内容定位）。若注册体路由不一致，**停下上报**，不得自行改
`actions.py`（不在独占清单）。

## 自测

```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/        # 0 诊断
```

另 grep `tests/` 中覆盖 `alt+shift+f` / `handle_key` 和弦的既有用例文件并运行
（如无专属用例则运行 `tests/` 下 grep 命中的 editor 键位相关文件；一条都没有时
如实汇报「无既有和弦用例，仅 pyright 把关」）。

## 执行纪律

- 只改 `yate/editor.py`；不新增用例（评审未要求，避免越界）。
- 完成后**不提交**，汇报：diff、核实结论（注册体路由原文）、自测退出码。
