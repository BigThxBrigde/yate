# repo-audit-r2 · plan_c：静默吞异常收口与防抖定时器生命周期

- 波次：**wave-2**（与 `plan_d` 并行，文件互不重叠）
- 来源维度：1（功能正确性 / 竞态与时序）、5（健壮性）
- 状态：**待批准**（本阶段不改代码、不改测试）

---

## 一、输入

- 总纲：[`overview.md`](overview.md) §五 维度 1/5、§六 M-1、M-2
- 规范依据：
  - `python-coding-style.md` §4.5 第 3 条：「`except` 块内**至少记录日志或向用户反馈**；
    **禁止静默吞异常**」
  - `architecture-boundaries.md` §三.5③ / R12（新增 log 走
    `log = tracing.get_logger(__name__)`，L0 层不得为日志引入 textual 依赖）
- 既有结论关系：
  - M-2 是 **F-7 的残留** —— `2026-10-16-full-repo-audit.md` §二 维度 5 明确列出
    4 处「实质静默吞异常（无 log 无反馈）」并「登记待办」；本轮复核 4 处**逐字未变**
    （`manager.py:367`、`manager.py:446`、`user_setup.py:279`、`fonts.py:226`）
  - M-1 是**全新** —— 既有审计的 S40/R-72 系列只覆盖「防抖可测性」，未覆盖
    「屏幕卸载后定时器是否仍触发」
- 前置条件：wave-1（`plan_a` ∥ `plan_b`）验收通过

## 二、独占文件清单（只改这 4 个文件）

1. `yate/editor_view/manual.py`
2. `yate/editor_lsp/manager.py`
3. `yate/services/user_setup.py`
4. `yate/services/fonts.py`

**测试文件**（同样独占，防止与 `plan_d` 争用 `tests/test_architecture.py`）：

5. `tests/test_manual.py`（**新建**）
6. `tests/test_lsp.py`（既有，追加用例）
7. `tests/test_user_setup.py`（既有，追加用例）

**不要动** `yate/editor_view/find_replace.py` 与 `yate/editor_view/diffview.py`
（两者的 `on_unmount` 已正确，**只作为对照基准引用，不得修改**）。

---

## 三、具体修改

### M-1 · `yate/editor_view/manual.py` —— `MarkdownDocScreen` 缺 `on_unmount`

**现状**（实测）：

- `manual.py:219-220`：`MarkdownDocScreen.__init__` 持有
  `self._search_timer: asyncio.TimerHandle | None = None` 与 `self._pending_query`
- `manual.py:333-345`：`_schedule_search` 用 `asyncio.get_running_loop().call_later(...)`
  武装定时器
- `manual.py:166`：`on_unmount` 只存在于 **`DocScroll`**（L154 那个 `VerticalScroll` 子类），
  `MarkdownDocScreen`（L175）**全文没有 `on_unmount`**（实测 `findstr /n "def on_unmount"`
  在 `manual.py` 只有第 166 行一处）
- `manual.py:347-350`：`_flush_search` 回调第一件事是
  `self._search_timer = None` 然后 `_flush_pending_search()`

**为什么是问题**：`_flush_pending_search`（`manual.py:352-362`）虽然有
`if query is None or not self.is_mounted: return` 的挂载守卫，**但守卫只在
`_pending_query is None` 之后才生效**，且 `self._pending_query` 在
`_schedule_search`（`manual.py:342`）已被赋成非 `None`。因此：

1. 用户在 `:manual` / `:changelog` 屏幕里输入搜索词、**在防抖窗口内**按 `esc` 关闭屏幕
   → 屏幕卸载，`_search_timer` **未取消**，定时器仍挂在事件循环上；
2. 窗口到期时 `_flush_search` → `_flush_pending_search` → `_flush_pending_search`
   在 `self.is_mounted` 处返回，**这一次无害**；
3. 但 `self._search_timer` 句柄在卸载后**仍持有一个对已卸载 Screen 的强引用**，
   而 `_flush_search`（`:349`）把 `self._search_timer = None` 之前，句柄的回调闭包
   一直把 Screen 拉在引用链上 —— 反复开关 `:manual` 会在防抖窗口内累积
   「已卸载 Screen」的悬挂闭包，直到各自行使到期被释放。这是**确定性的生命周期泄漏**，
   与 `find_replace.py:210-213`（`FindReplaceScreen.on_unmount` 调 `_cancel_debounce()`）
   和 `diffview.py:157-161`（`DiffScreen.on_unmount` cancel `_recompute_handle`）
   的既有正确形态**不一致** —— 同一个仓里三处同类防抖，两处做了清理、一处没做。

**改法**（与另两处同构，`diffview.py:157-161` 为范本）：

在 `MarkdownDocScreen` 中新增 `on_unmount`（位置：`manual.py:243` 的 `on_mount` 之后，
紧贴同类的生命周期方法，保持 §1.1「方法定义之间空 1 行」）：

```python
    def on_unmount(self) -> None:
        """Drop the pending debounce so no callback outlives the screen.

        A search typed within the debounce window and then dismissed with
        ``escape`` would otherwise leave an armed :class:`asyncio.TimerHandle`
        holding a reference to this unmounted screen until it fires.  Mirrors
        :meth:`FindReplaceScreen.on_unmount` and :meth:`DiffScreen.on_unmount`.
        """
        if self._search_timer is not None:
            self._search_timer.cancel()
            self._search_timer = None
        self._pending_query = None
```

同时在 `_flush_search`（`manual.py:347-350`）**不需要**改动 —— 保留
`self._search_timer = None` 的既有语义（回调自身也要清句柄）。

> **不做**的改动：不给 `_schedule_search` 加 `if not self.is_mounted: return`
> 卫语句 —— Textual 的 `call_later` 只在 Screen 已挂载时才可能被调用（`_schedule_search`
> 由 `on_input_changed`（`:320`）驱动，而未挂载的 Screen 收不到消息），
> 加卫语句是防御性冗余，违反 `python-coding-style.md` §6.1「Special cases aren't
> special enough to break the rules」。

### M-2a · `yate/editor_lsp/manager.py:363-368` —— didClose 通知静默失败

**现状**（实测原文）：

```python
        client = self._clients.get(state.client_key)
        if client is not None and client.state is ServerState.READY:
            try:
                await client.notify("textDocument/didClose",
                                    {"textDocument": {"uri": uri}})
            except (LspError, OSError):
                pass
```

**为什么是问题**：捕获了具体异常类型（写法本身合规），但 `pass` 使失败完全不可见
—— LSP 服务端会继续持有已关闭文档的语法树，用户侧表现为「关掉 tab 后补全/诊断仍
指向旧文件」，而日志与状态栏都无任何线索。违反 `python-coding-style.md` §4.5 第 3 条。
按 R12，本文件（`services/` 之外的 `editor_lsp/`，L0 叶子）**已有**模块级
`log = tracing.get_logger(__name__)`（实测 `manager.py` 顶部有该行），不需新增。

**改法**：

```python
            except (LspError, OSError) as exc:
                # The document is already out of the session; a lost
                # didClose only leaves the server's view stale, so it is
                # logged (never raised) to keep the close path total.
                log.debug("didClose failed for %s: %s", uri, exc)
```

### M-2b · `yate/editor_lsp/manager.py:442-447` —— didSave 通知静默失败

**现状**（实测原文）：

```python
        client = self._clients.get(state.client_key)
        if client is not None and client.state is ServerState.READY:
            try:
                await client.notify("textDocument/didSave",
                                    {"textDocument": {"uri": state.uri}})
            except (LspError, OSError):
                pass
```

**改法**（同 M-2a 形态）：

```python
            except (LspError, OSError) as exc:
                log.debug("didSave failed for %s: %s", state.uri, exc)
```

> **为何用 `log.debug` 而非 `log.warning`**：两条通知都是**尽力而为**的同步动作，
> 服务端不可达时整个 LSP 会话已被 `_flush_change` / 状态栏的 FAILED 态覆盖
> （`manager.py:187-202` 的 `states()` 把 FAILED 显式排在 CONFIGURED 之上），
> 逐文档的失败细节属于排障线索而非用户级事件；`log.debug` 让它进 trace 文件
> （`YATE_TRACE=1`）而不污染正常会话输出。这与既有 `manager.py:397-401` 的
> 「不在此处推进 version/last_synced」的同类保守处理一致。

### M-2c · `yate/services/user_setup.py:274-280` —— 空 base 目录 rmdir 静默

**现状**（实测原文）：

```python
    base_removed = False
    if not any(base.iterdir()):
        try:
            base.rmdir()
            base_removed = True
        except OSError:
            pass
```

**为什么是问题**：`base_removed` 是 `CleanupReport` 的公开字段
（`user_setup.py:287` 返回），调用方 `cli.py:372` 据此 `print(user_setup.format_cleanup_report(report))`
向用户汇报。`rmdir` 失败时 `base_removed` 保持 `False`，报告会说「目录未删除」，
但**为什么**没删（被占用 / 权限不足 / 有隐藏项）完全无从得知。这是 CLI 退出码路径
（`cli.py:373` `return 1 if report.errors else 0`）上的静默分支。

**改法**：并入既有 `errors` 列表（该列表已被 `cli.py:372` 的报告渲染消费）：

```python
    base_removed = False
    if not any(base.iterdir()):
        try:
            base.rmdir()
            base_removed = True
        except OSError as exc:
            errors.append(f"{base.name}/: {exc}")
```

（`errors` 已在 `:272` 处于同一作用域内、`:281` 被 `CleanupReport(errors=errors)` 消费，
无需新增变量。）

### M-2d · `yate/services/fonts.py:222-227` —— 重复字体文件删除静默

**现状**（实测原文）：

```python
        for dup in fonts_dir.glob(f"{ttf.stem}_*.ttf"):
            try:
                dup.unlink()
            except OSError:
                pass
```

**为什么是问题**：`ensure_font` 是「保证字体可用」的承诺函数（`shell_flows.py:136`
经 `asyncio.to_thread` 调用）。删不掉重复副本时函数**静默成功**，用户会看到
字体名重复、Explorer 字体设置里出现两份条目，而没有任何提示 —— 与本函数
其余分支（`shutil.copy2` 不吞异常、注册表项写入失败走 `winreg` 显式路径）
的失败可见性不一致。

**改法**（本文件已有模块级 `log`，实测 `fonts.py` 顶部有 `log = tracing.get_logger(__name__)`）：

```python
        for dup in fonts_dir.glob(f"{ttf.stem}_*.ttf"):
            try:
                dup.unlink()
            except OSError as exc:
                # A locked duplicate is a cosmetic Explorer/font-list
                # artifact, not a reason to fail the whole install; it is
                # logged so the leftover name is traceable.
                log.debug("could not remove duplicate font %s: %s", dup, exc)
```

---

## 四、备选方案与否决理由

| 备选 | 否决理由 |
|---|---|
| M-1 把 `_flush_pending_search` 的 `is_mounted` 守卫提到最前面 | 只能避免「跑一次无用回调」，**不能**解除 TimerHandle 对已卸载 Screen 的强引用 —— 泄漏根因是定时器未取消，不是回调未守卫。守卫前置属于治标。 |
| M-1 给 `manual.py` 新建一个 `ManualScreen` 基类统一挂 `on_unmount` | 该文件里 `DocScroll` / `MarkdownDocScreen` / `_SearchInput` 三个类无共同基类语义（一个是 `VerticalScroll`、一个是 `ModalScreen`、一个是 `Input`），为三行清理代码引入基类违反 `plan-architect-designer.md`「不为假设性需求预造抽象」与 §6.1。 |
| M-2a/b 用 `log.warning` 或 `log.error` | 会让「LSP 服务端未就绪时的正常 didClose 跳过」变成每次保存都打一条 warning —— 而该分支的前置条件已是 `client.state is ServerState.READY`，即失败是**异常态**；`debug` 让 trace 模式下可见、正常会话静默，与同文件 `_flush_change` 的保守处理一致。 |
| M-2a/b 重新抛出 `LspError` | `notify_saved` / `on_document_closed` 的调用方（`lsp_sync.py`、`editor.py` 的 worker）在 `exit_on_error=False` 下会吞掉，但文档关闭路径会因此**中断后续关闭流程** —— 把「一个通知没送到」升级成「关闭 tab 失败」，是行为退化。 |
| M-2c 只记 log 不并入 `errors` | `cli.py:365-373` 的清理路径**不启动 tracing**（`tracing` 只在 `--include-data` 时被 `uninstall`，见 `cli.py:360-364`），所以 log 在该路径上**根本不会被输出**。必须走 `errors` → `format_cleanup_report` → stdout 才有用户可见性。这是本条与 M-2a/b 的关键差异。 |
| M-2d 把失败记入 `errors` 列表 | `fonts.py` 的 `ensure_font` **没有** `errors` 出参（实测签名无该参数），加它会改公开 API 并波及 `shell_flows.py:136` 的调用点与既有测试 —— 超出本轮范围。`log.debug` 是零 API 变更的最小合规形态。 |

---

## 五、新增测试用例（详细三要素）

### 用例组 1 —— M-1 定时器生命周期（新文件 `tests/test_manual.py`）

**用例 1a**

- **用例名**：`test_dismiss_within_debounce_window_leaves_no_pending_timer`
- **前置条件 / fixture**：`tmp_path`；Textual pilot 提供真实事件循环；
  monkeypatch `yate.editor_view.manual.MarkdownDocScreen._run_search` 为
  记录调用的假实现（`calls: list[str]`）。防抖窗口常量是
  `MarkdownDocScreen._SEARCH_DEBOUNCE_S = 0.12`（实测 `manual.py:203`），
  用例内以 `MarkdownDocScreen._SEARCH_DEBOUNCE_S` 引用，不写字面量
- **arrange**：pilot 启动 `YateApp`，`:manual` 打开 `MarkdownDocScreen`，
  往 `#doc-search-input` 发送一次 `Input.Changed`（value = `"exit"`），
  使 `_schedule_search`（`on_input_changed` `manual.py:320-323`）武装定时器
- **act**：**在 `_SEARCH_DEBOUNCE_S` 窗口内**按 `escape` 关闭屏幕
- **断言**：
  1. 屏幕已卸载（`screen.is_mounted is False`）；
  2. **立即**断言 `screen._search_timer is None`（`on_unmount` 已清句柄）；
  3. `screen._pending_query is None`；
  4. `await pilot.pause(_SEARCH_DEBOUNCE_S * 5)` 之后 `calls == []`
     （`_run_search` **从未被调用**）

**用例 1b（反向路径：正常路径不被破坏）**

- **用例名**：`test_search_within_debounce_window_runs_when_screen_stays_mounted`
- **前置条件 / fixture**：同 1a 的 monkeypatch 与 `calls`
- **arrange**：同上打开屏幕并输入 `"exit"`（定时器已武装）
- **act**：**不**关闭屏幕，`await pilot.pause(_SEARCH_DEBOUNCE_S * 5)`
- **断言**：`calls == ["exit"]`（防抖仍然按期触发，`on_unmount` 没有误杀活定时器）
- **反向路径 1c**：**用例名** `test_fire_search_flushed_immediately_still_works`——
  `on_input_submitted`（`manual.py:325-331`）先 `_flush_pending_search()` 再
  `search_step(1)`；act = 输入后立刻按 `enter`；断言 `calls == ["exit"]`
  且 `_search_timer is None`（`on_unmount` 的新增清理不影响既有 flush 路径）

### 用例组 2 —— M-2a/M-2b 静默吞异常（追加到既有 `tests/test_lsp.py`）

**用例 2a**

- **用例名**：`test_document_closed_logs_instead_of_raising_when_notify_fails`
- **前置条件 / fixture**：既有 `lsp_manager` / `make_client` fixture 形态
  （`tests/test_lsp.py` 已有 `client_factory` seam，见其 `:225` 起的 stub 模式）；
  `caplog` fixture，logger 名 `yate.editor_lsp.manager`
- **arrange**：构造一个 `state` 为 READY 的 client，其 `notify` 为
  `async def notify(...): raise LspError("boom")`；把文档登记进 `manager._open`
- **act**：`await manager.on_document_closed(doc)`
- **断言**：
  1. **不抛异常**（调用正常返回，文档关闭流程不被中断）；
  2. `caplog` 中存在 `logger="yate.editor_lsp.manager"`、level `DEBUG`、
     文本含 `didClose failed` 与该 `uri` 与 `"boom"` 的记录；
  3. `doc` 已从 `manager._open` 移除、`manager._change_timers` 无该 `uri` 残留

**用例 2b（反向路径：正常通知不发 debug）**

- **用例名**：`test_document_closed_emits_no_debug_when_notify_succeeds`
- **arrange**：同 2a，但 `notify` 为成功的 async stub
- **act**：`await manager.on_document_closed(doc)`
- **断言**：`caplog` 中**没有**含 `didClose failed` 的记录（证明新加的 log 不刷屏）

**用例 2c / 2d（didSave 同构）**

- **用例名**：`test_document_saved_logs_instead_of_raising_when_notify_fails` /
  `test_document_saved_emits_no_debug_when_notify_succeeds`
- **arrange / act / 断言**：与 2a / 2b 同构，把 `on_document_closed` 换成
  `notify_saved`，把日志文本断言换成含 `didSave failed`

### 用例组 3 —— M-2c（追加到既有 `tests/test_user_setup.py`）

**用例 3a**

- **用例名**：`test_cleanup_reports_the_reason_when_the_base_dir_cannot_be_removed`
- **前置条件 / fixture**：`tmp_path` 作为 `HOME`（该文件既有 `monkeypatch` 隔离 fixture）；
  构造 `base` 目录**非空**且**不可 rmdir** —— 在 Windows 上用
  `monkeypatch.setattr(Path, "rmdir", _raise_oserror)` 精确打桩
  （`OSError` 由桩函数抛出），避免依赖真实文件锁的跨平台差异
- **arrange**：让 base 目录经 `any(base.iterdir())` 判定为空（打桩 `iterdir` 返回空迭代器）
- **act**：调用 `user_setup.cleanup_defaults(force=True)`
- **断言**：
  1. `report.base_removed is False`；
  2. `report.errors` **非空**且至少一条文本含 base 目录名与桩抛出的异常文本
     （原实现下 `errors` 会是空列表 —— 这是本用例的核心回归点）；
  3. `report` 里 `removed_files` / `removed_dirs` 仍正确（本次隔离错误不吞掉其它报告面）

**用例 3b（反向路径）**

- **用例名**：`test_cleanup_reports_base_removed_when_rmdir_succeeds`
- **arrange**：空 base 目录，不打桩 `rmdir`
- **act**：`cleanup_defaults(force=True)`
- **断言**：`report.base_removed is True` 且 `report.errors == []`
  （证明 M-2c 的改造没把成功路径也变成失败）

### 用例组 4 —— M-2d（追加到既有 `tests/test_fonts.py`）

**用例 4a**

- **用例名**：`test_ensure_font_logs_a_locked_duplicate_instead_of_failing`
- **前置条件 / fixture**：Windows-only（该文件既有 `pytest.mark.skipif`
  平台守卫）；`tmp_path` 作为 `fonts_dir`；`caplog`，logger 名 `yate.services.fonts`；
  构造一个**已存在的** `JetBrainsMonoNerdFontMono-Regular_0.ttf` 副本，
  并把 `Path.unlink` 打桩为抛 `OSError`（只针对该 `_0` 副本，其余路径不受影响）
- **arrange**：调用 `fonts.ensure_font(...)`
- **act**：同上（单次调用即 act）
- **断言**：
  1. `ensure_font` **正常返回**（不抛异常）；
  2. `caplog` 含 logger `yate.services.fonts`、level `DEBUG`、文本含
     副本文件名与异常文本；
  3. 字体**主文件**仍存在（副本删不掉不影响主文件可用）

**用例 4b（反向路径）**

- **用例名**：`test_ensure_font_succeeds_without_logging_when_no_duplicate_is_locked`
- **arrange**：无 `_0` 副本，不打桩
- **act / 断言**：`ensure_font` 正常返回，且 `caplog` **无** `could not remove duplicate font` 记录

### 用例组 5 —— 架构守卫（由 `plan_d` 落地，本子计划依赖其受益）

- `tests/test_architecture.py` 新增用例名见 `plan_d` §五 A-4；
  本子计划的 4 处 `except ... pass` 改造落地后，该守卫的**活体负样本归零**，
  即 M-2 在守卫层被永久冻结。

---

## 六、验证方案

| 验证目标 | 命令（PowerShell，仓库根） | 通过判定 |
|---|---|---|
| M-1 定时器生命周期 | `.venv\Scripts\python.exe -m pytest tests/test_manual.py -q` | 退出码 0，用例 1a/1b/1c 全绿 |
| M-2 LSP 通知 | `.venv\Scripts\python.exe -m pytest tests/test_lsp.py -q` | 退出码 0，2a~2d 全绿 |
| M-2c 清理报告 | `.venv\Scripts\python.exe -m pytest tests/test_user_setup.py -q` | 退出码 0，3a/3b 全绿 |
| M-2d 字体 | `.venv\Scripts\python.exe -m pytest tests/test_fonts.py -q` | 退出码 0，4a/4b 全绿（4a/4b 在非 Windows 上自动 skip，须在 Windows 上跑） |
| 改动文件类型零诊断 | `.venv\Scripts\python.exe -m pyright yate/editor_view/manual.py yate/editor_lsp/manager.py yate/services/user_setup.py yate/services/fonts.py tests/test_manual.py` | 0/0/0，退出码 0 |
| 日志惰性格式（R12 连带） | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q -k lazy` | 退出码 0 |
| 全仓零回归 | `.venv\Scripts\python.exe -m pytest tests/ -q` | 退出码 0 |
| 静默吞异常归零（自证） | 见下方命令 | 输出 `[]` |

自证命令（M-2 的四处 `except: pass` 已消除；**注意**过滤器必须排除
`value is not None` 形态与 best-effort 有注释背书的既有块，精确口径见下）：

```powershell
.venv\Scripts\python.exe -c "import ast,pathlib;print([f'{p.as_posix()}:{n.lineno}' for b in ('yate','tools') for p in pathlib.Path(b).rglob('*.py') for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))) if isinstance(n,ast.ExceptHandler) and n.body and [type(s).__name__ for s in n.body]==['Pass'] and 'editor_lsp/client.py' not in p.as_posix()])"
```

**期望输出**：`[]` 或仅剩**本轮明确豁免**的清单项（执行者须在报告中逐条列出豁免项
与其背书注释原文行号，不得静默略过）。

## 七、手工验证（无法自动化的部分）

M-2c 的用户可见面必须手工确认一次（CLI 退出码路径，pytest 不覆盖 stdout）：

1. 在临时 HOME 下执行一次 `--setup-defaults` 建出 `~/.yate`；
2. 用一个被占用的方式阻止其删除（Windows：开着指向该目录的资源管理器窗口 / cmd 会话）；
3. 执行 `.venv\Scripts\python.exe -m yate --cleanup-defaults --include-data`；
4. **预期现象**：stdout 报告中出现一条含该目录名与系统拒绝原因的行
   （原实现下报告只说「目录未删除」而无原因）；退出码为 `0`（`errors` 非空时 `cli.py:373`
   返回 `1`，故预期退出码 **1**，这是**期望**的行为变化——用户现在能看到原因了）。

## 八、风险与回滚

| 风险 | 概率 | 缓解 |
|---|---|---|
| `on_unmount` 与 Textual 的 Screen 栈弹出顺序冲突，导致 `on_unmount` 未被调用 | 低 | 用例 1a 的断言 2/3 直接验证 `on_unmount` 被调用（`_search_timer is None`）；若 Textual 某版本不调 `on_unmount`，1a 会失败并暴露真因，不会静默通过 |
| `log.debug` 在 L0 层引入 textual 依赖（违反 R12） | 零 | 四处改动都用**既有的**模块级 `log`（`manager.py`、`fonts.py` 顶部已有 `tracing.get_logger(__name__)`），不新增 import；验收含 `tests/test_architecture.py -k lazy` 与 UI-free 守卫 |
| `errors.append` 改变 `--cleanup-defaults` 退出码，破坏既有 CLI 测试 | 中 | 用例 3a/3b 双路径覆盖；执行者须额外跑 `.venv\Scripts\python.exe -m pytest tests/test_cli.py -q` 确认退出码相关断言仍成立 |
| `caplog` 抓不到 DEBUG（默认 WARNING 级别） | 中 | 用例 2a/2d/4a 必须显式 `caplog.set_level(logging.DEBUG, logger="...")`，否则断言会假绿 —— 执行者需在用例里写全 |

**回滚**：`git revert <commit>`。M-2a/b/d 只增加日志、M-2c 只增加一条错误报告、
M-1 只增加卸载清理 —— 四者都不改变成功路径的可观测行为，回滚后全部门禁维持原状。
