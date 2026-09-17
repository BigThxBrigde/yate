
# :wq 数据丢失残留修复计划

> 目标：修复本次 `:wq` 守护修复未覆盖的两条同类数据丢失路径 ——
> **多 tab 其他 dirty buffer 被静默丢弃**，以及 **Unicode 编码错误崩溃**。
>
> 原则：最小改动、局部修复、对齐已有 `quit(force)` 语义与 except 模式。

---

## 1. 现状事实（代码证据）

| # | 事实 | 证据 |
|---|------|------|
| F1 | `_wq` 先 `save_document()`，guard 过 `doc.modified` 之后调的是 **`app.quit(force=True)`** | [commands.py:61](../yate/app_features/commands.py#L61) |
| F2 | `quit(force=False)` 内置多 tab dirty 拦截：`any(doc.modified for doc in self.docs)` → 提示 `:q! to quit anyway`；**但 `force=True` 跳过这一切** | [app.py:1605-1610](../yate/app.py#L1605-L1610) |
| F3 | `save_document()` 的 except 只覆盖 `OSError`，**不捕获 `UnicodeError`** | [app.py:543](../yate/app.py#L543) `except OSError as exc:` |
| F4 | `_do_save_as()` 同样只捕获 `OSError` | [app.py:565](../yate/app.py#L565) `except OSError as exc:` |
| F5 | `Document.save()` 内部调 `self.path.write_text(text, encoding=self.encoding, newline="\n")`，**当 buffer 含当前文件编码无法表示的字符时抛 `UnicodeEncodeError`**（`UnicodeError` 子类 → `ValueError` 子类，不属于 `OSError`） | [document.py:102](../yate/editor_core/document.py#L102) |
| F6 | 文件编码由 `Document.open` 嗅探确定，候选集为 `utf-8 → locale → cp1252`，**cp1252/gbk 文件含 emoji(😀)、中日韩扩展区字符等必然触发 UnicodeEncodeError** | [document.py:51-60](../yate/editor_core/document.py#L51-L60) |
| F7 | `run_command` 无兜底，任何未捕获异常进入 Textual crash handler → 进程终止（用户工作丢失） | [app.py:1546-1563](../yate/app.py#L1546-L1563)（上一轮审查已确认） |
| F8 | 当前 commit 新增的 5 个 `:wq` 测试中，**两个 mock 了 quit 并断言 `quit_calls == [True]`**（force=True）——改完 Issue 1 后需同步改断言 | [changes.diff:75](../changes.diff) `assert quit_calls == [True]`（两处，约 line 75 与 line 190） |
| F9 | `_wq` 的 `doc.modified` 守卫仅覆盖 **当前 doc**，完全不感知其他 tab 的 dirty 状态 | [commands.py:59](../yate/app_features/commands.py#L59) |

## 2. 根因分析

### Issue 1：`:wq` 静默丢弃其他 tab 的未保存修改

**根因：** `_wq` 使用 `quit(force=True)` 绕过了 `quit()` 内置的多 tab dirty 拦截。

控制流（当前）：
```
:wq → save_document() → 当前 doc 变干净
    → doc.modified == False → guard 通过
    → quit(force=True) → any(dirty)? 跳过 → exit()
    → 其他 tab 的 dirty buffer 被静默丢弃
```

控制流（vim `:wq` 语义）：
```
:wq → save 当前 buffer
    → 如果其他 buffer dirty → 报 E37 "No write since last change" → 不退出
    → 用户需显式 :q! 丢弃 / 分别保存后退出
```

**修复策略：** 把 `quit(force=True)` 改为 `quit(force=False)` 即 `quit()`。当前 doc 已经干净，`quit()` 内部的 `any(doc.modified ...)` 只会因其他 tab 而拦截 —— 语义精确对齐 vim 的 `:w + :q` 行为。

### Issue 2：Unicode 编码错误导致崩溃丢稿

**根因：** `save_document()` 和 `_do_save_as()` 的 except 范围只含 `OSError`，但 `write_text` 在编码不兼容时抛的是 `UnicodeEncodeError`（`ValueError` 子类，Python 3.11+ 继承链：`UnicodeError → ValueError → Exception`），不属于 `OSError`，异常穿透 command handler 进入 Textual crash 流程 → 进程终止 → 内存中的 buffer 全部丢失。

**修复策略：** 两处 except 从 `except OSError` 扩为 `except (OSError, UnicodeError)`。`UnicodeError` 同时覆盖 encode 和 decode 两类（decode 虽然本次不在 save 路径，但未来路径切换可能复用同 except 块），覆盖面足够且不引入运行时误捕获（UnicodeError 是极窄的字符集）。

## 3. 实施步骤

### Step 1 — commands.py：去掉 force

**文件：** `yate/app_features/commands.py`

**位置：** line 61

**改动：**
```python
# Before:
app.quit(force=True)

# After:
app.quit()
```

无需修改 guard —— guard 仍然在 save 后确保当前 doc 干净；`quit()` 内部自动负责其他 tab 的 dirty 拦截。

### Step 2 — app.py：扩展两处 except

**文件：** `yate/app.py`

**位置 A：** `save_document()` line 543
```python
# Before:
except OSError as exc:

# After:
except (OSError, UnicodeError) as exc:
```

**位置 B：** `_do_save_as()` line 565
```python
# Before:
except OSError as exc:

# After:
except (OSError, UnicodeError) as exc:
```

两处改完后，写盘失败（权限、目录、编码）统一走到 `message("save failed: ...", kind="error")`，buffer 保留在内存中，不崩溃。

### Step 3 — 同步更新现有测试

**文件：** `tests/test_app_textual.py`

以下两个测试 mock 了 quit 并断言 `quit_calls == [True]`（force=True），需同步改为 `[False]`：

| 测试函数 | 位置 | 旧断言 | 新断言 |
|---------|------|--------|--------|
| `test_wq_saves_and_quits_when_save_succeeds` | changes.diff ~line 75 | `assert quit_calls == [True]` | `assert quit_calls == [False]` |
| `test_wq_quits_for_clean_named_buffer` | changes.diff ~line 190 | `assert quit_calls == [True]` | `assert quit_calls == [False]` |

四个不 mock quit 的测试（save 失败/未命名 dirty/未命名 clean/...）不受影响 —— 它们测的是 guard 阻断的路径，force 与否都走不到 quit。

### Step 4 — 新增 Issue 1 多 tab 测试

**文件：** `tests/test_app_textual.py`，接在现有 `:wq` 测试块末尾

**场景：** 已打开两个 tab，当前 tab 干净，另一个 tab dirty；`:wq` 不应退出，而应提示 unsaved changes。

```python
def test_wq_does_not_quit_when_other_tab_is_dirty(tmp_path: Path) -> None:
    """Current doc saved successfully, but another tab has unsaved
    changes. :wq must NOT force-quit — the user should be prompted to
    save/close that tab first (vim E37 semantics)."""

    async def scenario() -> None:
        saved = tmp_path / "saved.txt"
        other = tmp_path / "other.txt"
        saved.write_text("already", encoding="utf-8")
        other.write_text("pristine", encoding="utf-8")

        app = YateApp(target=saved, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # open second tab
            app.run_command(f"edit {other}")
            await pilot.pause()
            assert len(app.docs) >= 2
            # dirty the second tab
            await pilot.press("i", "edit", "escape")
            await pilot.pause()
            second_doc = app.doc  # after edit command, current is the second
            assert second_doc.modified

            # switch back to saved.txt (the first tab, clean)
            app.activate_doc(app.docs[0])
            assert not app.doc.modified

            quit_calls: list[bool] = []
            def _record_quit(force: bool = False) -> None:
                quit_calls.append(force)
            cast(Any, app).quit = _record_quit

            app.run_command("wq")
            await pilot.pause()

            # quit was called non-force, so internal any(dirty) check
            # fired and blocked the quit — quit_calls stays empty
            assert quit_calls == [], f"quit should have been blocked, got {quit_calls}"
            assert app.is_running

    asyncio.run(scenario())
```

### Step 5 — 新增 Issue 2 Unicode 编码测试

**文件：** `tests/test_app_textual.py`，接在 Step 4 之后

**场景：** 打开一个 cp1252 编码文件，插入 emoji，`:wq` 应该报错并停在编辑器里（不崩溃）。

```python
def test_wq_does_not_crash_on_unicode_encode_error(tmp_path: Path) -> None:
    """When the file's detected encoding cannot represent the buffer
    content (cp1252 + emoji), :wq must surface a friendly error message
    and keep the editor alive — NOT crash via Textual's exception handler."""

    async def scenario() -> None:
        target = tmp_path / "cp1252.txt"
        # Write a file that Python's detect_encoding would sniff as cp1252
        # (contains 0x80-0xff bytes that are valid cp1252 but not UTF-8)
        target.write_bytes("caf\xe9".encode("cp1252"))  # café in cp1252
        app = YateApp(target=target, keymap="vim")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # Verify encoding was sniffed as cp1252
            assert app.doc.encoding.lower().startswith("cp1252") or \
                   app.doc.encoding.lower().startswith("windows-1252")

            # Insert emoji — cp1252 cannot encode this
            await pilot.press("end")
            await pilot.pilot.paste("😀")
            await pilot.pause()
            assert app.doc.modified

            app.run_command("wq")
            await pilot.pause()

            # Must still be running — save failed, editor alive
            assert app.is_running
            assert app.doc.modified  # buffer untouched
            assert "save failed" in _message_text(app) or "Unicode" in _message_text(app)

    asyncio.run(scenario())
```

## 4. 变更清单汇总

| # | 文件 | 位置 | 改动类型 | 行号 |
|---|------|------|---------|------|
| 1 | `yate/app_features/commands.py` | `_wq` 函数 | 删除 `force=True` | 61 |
| 2 | `yate/app.py` | `save_document()` | except 扩为 `(OSError, UnicodeError)` | 543 |
| 3 | `yate/app.py` | `_do_save_as()` | except 扩为 `(OSError, UnicodeError)` | 565 |
| 4 | `tests/test_app_textual.py` | `test_wq_saves_and_quits_when_save_succeeds` | 断言 `[True] → [False]` | ~75 |
| 5 | `tests/test_app_textual.py` | `test_wq_quits_for_clean_named_buffer` | 断言 `[True] → [False]` | ~190 |
| 6 | `tests/test_app_textual.py` | `:wq` 测试块末尾 | 新增多 tab dirty 测试 | 新增 |
| 7 | `tests/test_app_textual.py` | `:wq` 测试块末尾 | 新增 Unicode 崩溃测试 | 新增 |

**预估改动量：** 生产代码 ~3 行；测试 ~130 行（新增 2 个用例 + 2 处断言微调）。

## 5. 验证策略

1. 跑 `test_wq_*` 全部 7 个测试，必须通过（原 5 + 新 2 + 2 断言微调后）
2. 跑完整 pytest，确保无回归
3. 手工 smoke：
   - 打开两个 tab，tab B dirty，`:wq` 从 tab A 执行 → 应提示 unsaved changes
   - 打开 cp1252 文件（Windows 记事本 ANSI 保存），粘贴 emoji，`:w` → 应看到 save failed，编辑会话不崩溃
   - 正常文件正常保存 → 行为无变化

## 6. 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| `quit()` 非 force 在某些边界下拦截了不该拦截的场景（如 welcome page 的 :wq） | 极低 | 低 | clean buffer 的 `modified` 始终为 False，`any()` 只拦截 dirty tab |
| `UnicodeError` 捕获范围过宽 | 极低 | 低 | UnicodeError 只有 UnicodeEncodeError / UnicodeDecodeError 两个子类，save 路径只会抛前者；即使后者被捕获也符合"保存失败友好提示"语义 |
| Step 4 多 tab 测试的 activate_doc 切换后 current doc 引用错位 | 低 | 低 | 测试里保存了 `app.docs[0]` 引用，activate 用该引用而非 index，避免 tab 数量变化导致的 index 失效 |

计划内容：

**Issue 1 — `:wq` 静默丢弃其他 tab dirty buffer**
- commands.py:61 把 `quit(force=True)` 改为 `quit()`
- 让 `quit()` 内置的 `any(doc.modified ...)` 拦截生效，对齐 vim E37 语义
- 两个 mock quit 的测试断言同步从 `[True] → [False]`
- 新增多 tab dirty 场景测试

**Issue 2 — UnicodeError 崩溃丢稿**
- app.py:543（save_document）和 app.py:565（_do_save_as）两处 `except OSError` → `except (OSError, UnicodeError)`
- 覆盖 cp1252/gbk 文件写 emoji 等无法编码的字符场景
- 新增 cp1252 + emoji 保存测试，验证不崩溃且留友好提示

**总改动量：** 生产代码 3 行；测试 ~130 行（新增 2 用例 + 2 处断言微调）
---

