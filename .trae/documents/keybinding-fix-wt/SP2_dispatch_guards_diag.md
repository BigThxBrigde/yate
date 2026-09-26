# SP2 — 派发层回归守卫（ctrl+p / ctrl+1 / ctrl+shift+e）+ 未映射键诊断日志

> 前置：SP1 已提交
> 预估：40min　|　独占文件：`yate/editor.py`、`tests/test_app_textual.py`

## 目标

1. 用 pilot 守卫锁住 `Editor.handle_key` 的 event.key 分支（`editor.py:618-626`）——本次重构顺带修好的
   `ctrl+p` 与既有 `ctrl+1`/`ctrl+shift+e` 不再因未来重构回退；
2. D2 决策落地：`raw is None` 静默丢键处加 debug 日志，终端键位问题可取证。

## 实施步骤

### 步骤 2.1　诊断日志（D2）

文件 `yate/editor.py`，第 629-632 行（当前）：

```python
        raw = event_to_raw(event.key, event.character)
        if raw is None:
            return False
        return self.handle_raw_key(raw)
```

`if raw is None:` 分支改为：

```python
        raw = event_to_raw(event.key, event.character)
        if raw is None:
            # Unmapped names are normal (mouse-less widgets, exotic terminals),
            # so this stays a debug log: YATE_TRACE turns it into evidence.
            log.debug("unmapped key event: %s (character=%r)", event.key, event.character)
            return False
        return self.handle_raw_key(raw)
```

（`log` 已存在于 `editor.py:73`，无新增导入。）

### 步骤 2.2　pilot 守卫测试

文件 `tests/test_app_textual.py`。沿用既有模板 `test_type_save_find_help_keymap`（L93-98：
`tmp_path` 建文件 → `YateApp` → `app.run_test(size=(100, 30))`）。新增一个测试函数
（命名遵循 `test_<behavior>_<condition>_<expected>`），一次 `run_test` 内完成三段断言：

1. `await pilot.press("ctrl+p")` → 断言文件面板出现（按该文件既有 palette 断言写法：
   检查 palette 屏 / 输入框是否 `app.screen` 可见——参照 `test_explorer_open_file`（L353）等
   现有用例对 overlay/palette 的查询方式）；
2. 关闭面板（`pilot.press("escape")`）后 `await pilot.press("ctrl+1")` →
   断言 `isinstance(app.focused, EditorView)`（focus_editor 语义）；
3. `await pilot.press("ctrl+shift+e")` → 断言焦点移到 explorer（`app.focused is app.editor.explorer_tree`，
   属性名以 `yate/editor.py` 实际为准，实施时核对）。

> 说明：`pilot.press` 合成的是规范 `Key` 事件，测不到终端字节层（这正是 Issue 只在真机浮现的原因），
> 守卫目标是**派发分支**；终端字节层由 SP1 的映射单测 + SP5 真机矩阵覆盖，两层互补。
> 测试 docstring 中必须写明这一边界（沿袭该文件注释风格）。

## 测试（完成后立即执行，全绿才可提交）

```powershell
d:\Programming\yate\.venv\Scripts\python.exe -m pytest tests\test_app_textual.py -q
d:\Programming\yate\.venv\Scripts\python.exe -m pyright yate tests
```

## 验收标准

- [ ] 新守卫测试通过；**反向演练一次**：临时注释 `editor.py:624` 的 `ctrl+p` 分支 → 守卫变红 → 还原（确认守卫有效）；
- [ ] 全量 `pytest tests/ -q` 无回归（pilot 测试有并发干扰史，失败先重跑确认再定位）；
- [ ] pyright 0 诊断。

## 回滚

单 commit revert；诊断日志与守卫测试互不依赖，可分两次提交（推荐：2.1 一个 commit，2.2 一个 commit）。
