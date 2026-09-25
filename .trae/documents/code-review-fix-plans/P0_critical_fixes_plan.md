# P0 Critical 修复计划

> 来源：[review.md](../../issues/review.md) 2026-09-16 审查 Critical 段（2026-09-23 复核后仍存在的 7 条）。
> 按风险排序：数据/可用性损坏（1–3）→ 交互缺陷（4–5）→ 工具链（6–7）。
> 每条含现状证据、根因、修复策略、测试方案。
>
> **2026-09-24 状态复核**（对照当前代码逐条核实）：C1 / C2 已随提交 `e5a3001` / `dc1f3ac`
> 修复，C6 / C7 已于同日落库（各条附「✅ 已修复」标注与实际落点），加上此前的 C3 / C4 / C5，
> **P0 全部 7 条清零**。
>
> 统一门槛：`python -m pyright yate/ tests/ tools/` 零诊断；`pytest tests/ -q` 全绿；
> **`python -m tools.smoke_test run --fail-only` 全部场景通过（exit 0）——每批修复验证的
> 最后一步必须冒烟全绿，否则该批不算完成**；
> 架构边界遵守 `architecture-boundaries.md` R1–R11（禁止新增 Protocol / TYPE_CHECKING）。

---

## C1 — LSP `_read_loop` 未捕获所有异常，请求永久挂起

> ✅ **已修复（2026-09-24，提交 `e5a3001`）**：[client.py:429-465](../../../yate/editor_lsp/client.py)
> 失败收尾提取为 `_fail_pending()`（置错误信息、对全部挂起 future `set_exception` 并清空），
> `_read_loop` 增加 `except Exception` 兜底（`log.exception` + fail pending）并在 `finally`
> 对非 STOPPED 退出统一置 `FAILED`；`start_request` 在 FAILED 态直接拒绝新请求（后续
> `request()` 立即失败而非挂起），与本计划策略一致。守卫：
> `test_malformed_frame_marks_failed_and_fails_requests`（畸形帧触发白名单外的
> `LspProtocolError` → 状态 FAILED、挂起的 `request()` 以异常结束、后续 `request()` 立即失败）。
> 以下原始计划存档。

**文件：** [yate/editor_lsp/client.py:419-435](../../../yate/editor_lsp/client.py)

**现状证据：** `_read_loop` 仅捕获 `asyncio.CancelledError` 与
`(LspError, ConnectionError, EOFError)`，捕获后已能置 `FAILED` 并对挂起
future `set_exception`；但 `ValueError`、`AttributeError`、内存畸形帧等
其它异常会直接逸出循环，`read_task` 静默死亡，客户端状态停留在 `READY`
（状态只在上述三个异常分支更新），`request()` 的 `await future` 永久挂起。

**根因：** 异常白名单与「transport 层任何失败都必须转化为连接失效」的
不变量不匹配——白名单覆盖了已知异常，漏掉未知异常的代价是整条会话挂死。

**修复策略：** 把「失败收尾」提为独立方法，任何非取消异常统一走它：

```python
async def _read_loop(self) -> None:
    try:
        while True:
            ...  # 原循环体
    except asyncio.CancelledError:
        raise
    except (LspError, ConnectionError, EOFError) as exc:
        self._fail_pending(exc)          # 现有逻辑提取
    except Exception as exc:             # noqa: BLE001 - transport 层兜底
        log.exception("LSP read loop crashed (%s)", self.config.name)
        self._fail_pending(exc)
    finally:
        self._set_state(ServerState.FAILED)  # 无论从哪条路径退出都失效
```

`_fail_pending(exc)`：对 `_pending` 中全部 future `set_exception` 并清空；
`finally` 兜底保证状态机与 future 表一致。

**测试：** 新增用例——向 transport 喂一段能触发非白名单异常的畸形字节
（如构造让解析器抛 `ValueError` 的帧），断言：`client.state is FAILED`；
挂起的 `request()` 以异常结束而非挂起；后续 `request()` 立即失败。

---

## C2 — LSP `register_server` 取消旧任务与 `_starting` 清理竞态

> ✅ **已修复（2026-09-24，提交 `dc1f3ac`）**：[manager.py:227-235](../../../yate/editor_lsp/manager.py)
> `ensure_client` 的收尾改为条件弹出（`if self._starting.get(key) is task`）——「谁跟踪谁清」，
> 被取消路径的清理仍由 `register_server` 同步过滤完成，与本计划策略一致。守卫：
> `test_register_replace_race_keeps_new_starting_task_tracked`（慢启动 server 的启动中途
> `register_server` 替换同名配置：旧任务被取消、新任务的 `_starting` 条目不被旧任务的
> 收尾弹掉、并发 `ensure_client` 只产生一个 client）。以下原始计划存档。

**文件：** [yate/editor_lsp/manager.py:105-108](../../../yate/editor_lsp/manager.py)、
[manager.py:225-230](../../../yate/editor_lsp/manager.py)

**现状证据：** `register_server` 替换配置时按 key 取消旧启动任务并同步
过滤 `_starting`；而 `ensure_client`（L224-229）的
`finally: self._starting.pop(key, None)` 无 identity 检查。

**根因：** 旧任务被 `cancel()` 后，正在 `await task` 的调用方的 `finally`
会稍后执行 `pop(key)`——此刻 key 里装的已是**新**任务，弹掉后新任务失去
跟踪，第三个并发调用者会再启一个重复进程。

**修复策略：** 条件弹出（identity 检查），两处都改：

```python
# ensure_client / _start_client 的收尾
finally:
    if self._starting.get(key) is task:
        self._starting.pop(key, None)
```

被取消路径的清理已由 `register_server` 同步过滤完成，条件弹出保证
「谁跟踪谁清」。

**测试：** 新增竞态用例——启动一个慢启动 server（启动函数内
`await asyncio.sleep(...)` 可被打断），在启动中途 `register_server`
替换同名配置，断言：旧任务被取消、新任务的 `_starting` 条目不被旧任务
的收尾弹掉、并发 `ensure_client` 只产生一个 client。

---

## C3 — `replace_all` 批量替换后未钳制光标

> ✅ **已修复（核实 2026-09-24）**：[search.py:143-151](../../../yate/editor_core/search.py) 替换循环
> 结束后、记录 undo 前对光标做 `min(col, len(line))` 钳制，与本计划策略一致；守卫为冒烟 harness
> 的全局 `invariant:cursor_col`（每场景校验光标在行内）。尚无专属单测，实施 C3 相关改动时可顺手
> 补一条「replace_all 缩短行后光标仍落行内」的用例。以下原始计划存档。

**文件：** [yate/editor_core/search.py:118-145](../../../yate/editor_core/search.py)

**现状证据：** 替换循环结束后仅 `buffer.anchor = None` 并提交 undo，无
`min(c, len(line))` 钳制；行变短后光标列越界。

**根因：** 逐行替换改变了行长度，但只维护匹配位置，未回写光标。

**修复策略：** 循环结束后对光标（及若有选区的 anchor）钳制：

```python
r, c = buffer.cursor
buffer.cursor = (r, min(c, len(buffer.lines[r])))
```

**测试：** 构造三行 `"abcabc"`，光标置于行尾后 `replace_all("abc", "")`，
断言 `buffer.cursor` 落在行内（`(0, 0)`）；再测替换后行变得更长的场景
保证光标不回退。

---

## C4 — 补全弹窗打开时吞掉所有按键（含 Ctrl+S / Ctrl+Z）

> ✅ **已修复（2026-09-23，提交 `bbeb5f6`）**：方向与计划一致（白名单反转），落点不同——
> 弹窗分支现居 [editor.py:576-590](../../../yate/editor.py)（`Editor.handle_key`），只消费
> `tab` / `enter` / `up` / `down` / `escape`，其余键不再消费、直接落入后续正常分发
> （未引入独立的 `_dispatch_behind_popup`）。守卫：`test_completion_popup_keeps_typing_and_filters`、
> 冒烟 `regress_completion_popup_keys` / `regress_completion_staleness`。以下原始计划存档。

**文件：** [yate/editor.py:552-564](../../../yate/editor.py)

**现状证据：** `popup.is_open` 分支处理 tab/enter/up/down/escape 后，
**所有其它键**无条件 `return True`——保存、撤销、移动全部被吞。

**根因：** 分支语义写成了「弹窗打开时消费一切」，而真实需求是「弹窗
拥有少数几个导航键，其余照常分发」。

**修复策略（最小改动，白名单反转）：** 弹窗只消费它拥有的键，其余
落入后续正常分发链（keymap → raw dispatch；打字仍经
`after_editor_key` 刷新补全，行为不变）：

```python
if popup.is_open:
    if event.key in ("tab", "enter"):
        self.accept_completion()
    elif event.key == "up":
        popup.select_prev()
    elif event.key == "down":
        popup.select_next()
    elif event.key == "escape":
        popup.close()
    else:
        # 弹窗不拥有的键（ctrl+s 保存、ctrl+z 撤销、移动等）照常分发
        return self._dispatch_behind_popup(event)
    return True
```

`_dispatch_behind_popup` 复用现有分发逻辑（chord → prompt → raw）；
不采用「硬编码 ctrl+s/ctrl+z 放行集合」方案——按键表随 keymap 变化，
反转白名单从根上消除遗漏。

**测试：** 弹窗打开状态下按 ctrl+s → 文档落盘且弹窗存活；按 ctrl+z →
撤销生效；按普通字符 → 插入且补全刷新；tab/enter/up/down/escape 行为
不变。接入现有冒烟 `completion` 场景补两条断言。

---

## C5 — 命令面板 CJK 填充宽度错位

> ✅ **已修复（2026-09-24）**：[palette.py:266-268](../../../yate/editor_view/palette.py) 已改用
> `theme.cell_len(display)` 计算填充并附注释说明 CJK 双 cell 宽度（同记录于 review.md
> 2026-09-24 审查 Minor 段）。以下原始计划存档。

**文件：** [yate/editor_view/palette.py:266](../../../yate/editor_view/palette.py)

**现状证据：** 提示列填充用 `len(display)`；CJK 字符占 2 单元格，
`len` 少算导致右侧 hint 错位。

**修复策略：** 项目已有统一宽度助手（[chrome.py](../../../yate/editor_view/chrome.py)、
[completion.py](../../../yate/editor_view/completion.py) 均在用）：

```python
# Before:
pad = " " * max(1, width - len(display) - len(hint) - 2)
# After:
pad = " " * max(1, width - theme.cell_len(display) - theme.cell_len(hint) - 2)
```

同时审查同函数内其余 `len()` 参与对齐处一并替换。

**测试：** 冒烟 palette 场景新增一条：注册一个含中文 label 的命令
（或直接断言 SVG 文本行中 hint 列位置），验证 CJK 项与 ASCII 项的
hint 列对齐。

---

## C6 — 发布工具硬编码 `"master"` 分支

> ✅ **已修复（2026-09-24）**：[release/cli.py:188-201](../../../tools/release/cli.py) 新增
> `_default_branch()`——`git symbolic-ref refs/remotes/origin/HEAD` 检测，`GitError`（非零
> 返回码/无 git/超时）返回 None 不猜测；[release/cli.py:262-267](../../../tools/release/cli.py)
> `release()` 增加 `branch: Optional[str]` 参数，push 前 `branch or _default_branch(repo)`，
> 仍为 None 则 RuntimeError `cannot determine the default branch; pass --branch`（计划原示意
> 的 `sys.exit` 落地为同语义的 RuntimeError，走 main() 既有错误处理路径）；`main()` 暴露
> `--branch`。守卫：`tests/test_release_tool.py` 四条（origin/HEAD 检测、无 origin 返回 None、
> 不可判定时中止且不 push、`--branch` 透传）。运维注记：本仓库当前无 `origin/HEAD`，实际发布
> 需 `--branch master` 或先 `git remote set-head origin --auto`。以下原始计划存档。

**文件：** [tools/release/cli.py:187-234](../../../tools/release/cli.py)

**现状证据：** 流程末尾硬编码 `git_push(repo, "master")`——在 `main`
或其它默认分支的仓库上，bump/changelog/gate/tag 全部完成后才失败，
代价最大。

**修复策略：** 动态检测 + 显式覆盖（检测失败时不猜）：

```python
def _default_branch(repo: Path) -> Optional[str]:
    r = run_git(repo, "symbolic-ref", "refs/remotes/origin/HEAD")
    if r.returncode == 0:
        return r.stdout.strip().rsplit("/", 1)[-1] or None
    return None

# release():
branch = args.branch or _default_branch(repo)
if branch is None:
    sys.exit("cannot determine the default branch; pass --branch")
git_push(repo, branch)
```

`--branch` 同时用于 push 与任何分支相关步骤；`symbolic-ref` 失败
（裸仓库/异常配置）直接报错退出而非回退猜测。

**测试：** 单测 `_default_branch`（真实临时 git 仓库：默认分支、
`--branch` 覆盖、无 origin 时报错三条路径）；e2e 发布流程测试如已有
则补 main 分支仓库变体。

---

## C7 — Changelog `check` / `zh-commit` 忽略 `--overrides`

> ✅ **已修复（2026-09-24）**：[changelog/cli.py:270-294](../../../tools/changelog/cli.py)
> 三个子命令 parser（generate / check / zh-commit）均暴露 `--overrides`
> （`type=Path, default=None`），main() 分发前统一
> `overrides = args.overrides or translations.DEFAULT_OVERRIDES_PATH` 并透传给
> `generate` / `check` / `zh_commit`。校准：计划原文只点名 check / zh-commit（称 generate
> 可用），实测 generate 的 parser 同样未暴露该参数，按 review.md 原条目「一致地传递给所有
> 子命令函数」口径一并补齐。守卫：`test_check_overrides_flag_is_honored`、
> `test_zh_commit_overrides_flag_writes_custom_file`、
> `test_generate_overrides_flag_renders_translations`。以下原始计划存档。

**文件：** [tools/changelog/cli.py:267-299](../../../tools/changelog/cli.py)

**现状证据：** 函数层 `check()` / `zh_commit()` 已接收 `overrides_path`
参数；但 CLI 绑定处两个子命令 parser 未暴露 `--overrides`，调用时未
传入——`generate` 可用，`check`/`zh-commit` 静默用默认值。

**修复策略：** 参数补齐 + 一致透传：

```python
for sub in (check_parser, zh_commit_parser):
    sub.add_argument("--overrides", type=Path, default=None, ...)
# 调用处
overrides = args.overrides or DEFAULT_OVERRIDES_PATH
... check(..., overrides_path=overrides)
... zh_commit(..., overrides_path=overrides)
```

**测试：** `tests/test_changelog_tool.py` 新增：`check --overrides`
指向自定义文件时生效（如缺条目时报错行为随 overrides 变化）；
`zh-commit --overrides` 同理。

---

## 执行顺序建议（2026-09-24 更新：C1–C7 全部完成）

1. ~~**C1 + C2 同批**~~（已完成：提交 `e5a3001` / `dc1f3ac`，含守卫测试，门禁全绿）；
2. ~~**C6 + C7**~~（已完成：release 分支检测 + changelog `--overrides` 全子命令透传，
   守卫落位，门禁全绿）。
