# P1 Suggestion 修复计划

> 来源：[review.md](../../issues/review.md) 2026-09-16 审查 Suggestion 段（2026-09-23 复核后
> 仍存在的条目）。按主题分批，批内按影响排序；每条含证据、策略、测试要点。
> **本文档仅为计划，未实施。** 统一门槛同 [P0](P0_critical_fixes_plan.md)
> （pyright 零诊断、pytest 全绿、**冒烟 `python -m tools.smoke_test run --fail-only`
> 全绿**——每批收尾必跑）。
>
> **2026-09-24 状态复核**（对照当前代码逐条核实）：S7 已随 PR #13 审查修复；
> S14 的实现已重构（set.discard → Timer + scheduled key），缺陷残余形态与修法已按
> 新代码改写；S11 / S12 / S17 补入核实结论。另将 review.md 2026-09-23 / 2026-09-24
> 各审查段仍未修复的条目补入为**批次六**（正确性与语义）、**批次七**（渲染 / 性能）
> 与批次四增补（S42 / S43）。

---

## 批次一：语法高亮性能（regex_backend.py，两正则条目同文件同批）

### S1 — 主正则每次 tokenize 重新编译

**证据：** [regex_backend.py:412-431](../../../yate/editor_syntax/regex_backend.py)
`_code_line_pattern(spec)` 每次调用重建 parts 并 `re.compile`；
`tokenize_document`（L704）逐次调用。

**策略：** `functools.lru_cache` 缓存（spec 为不可变 dataclass，可哈希；
若含 list 字段则改用 `field(default=tuple)` 或按 `id(spec)` 缓存）：

```python
@lru_cache(maxsize=None)
def _code_line_pattern(spec: LangSpec) -> re.Pattern[str]:
    ...
```

**测试：** 现有高亮测试全绿即可（纯缓存，无行为变化）；可加一条
`_code_line_pattern(spec) is _code_line_pattern(spec)` 断言缓存命中。

### S2 — 配置模式布尔词每行编译 7 次

**证据：** [regex_backend.py:674-676](../../../yate/editor_syntax/regex_backend.py)
循环内 `re.finditer(rf"(?<![\w]){word}(?![\w])", line)`。

**策略：** 模块级预编译单一交替模式：

```python
_CONFIG_BOOL_RE = re.compile(r"(?<!\w)(?:true|false|null|yes|no|on|off)(?!\w)")
# 循环替换为：
for m in _CONFIG_BOOL_RE.finditer(line):
    _emit(tokens, m.start(), m.end(), "constant")
```

**测试：** 现有 config 高亮用例全绿；补一条 `on/off/yes/no` 命中与
`only`（词内）不命中的边界断言。

---

## 批次二：正确性与语义

### S6 — 终端模拟器宽字符在最后一列被丢弃

**证据：** [emulator.py:426-430](../../../yate/editor_term/emulator.py)
宽字符到达最后一列仅置 `autowrap` 标记即返回，字符未显示。

**策略：** 与 ASCII autowrap 语义对齐——最后一列的宽字符：在倒数第二列
落一个占位（或按 xterm 行为留在 pending 状态），换行后在下一行行首完整
渲染。最小方案：宽度 2 的字符 col==width-1 时先执行换行，再在新行 col 0
正常放置。注意与现有 `autowrap` 延迟换行机制（先写后换）保持一致。

**测试：** `tests/test_terminal.py` 新增：`printf` 序列在行末列写入宽
字符（如「中」），断言其出现在下一行首列而非丢失；行中间宽字符行为不变。

### S4 — 资源管理器 `create()` 同步打开新文件

**证据：** [explorer.py:385-387](../../../yate/editor_view/explorer.py)
新建后直接 `self.open_path(target)`。

**策略：** 改 `self.open_path_later(target)`，与其余打开路径一致
（避免在树事件回调里同步做 LSP open / 语法装载）。

**测试：** app 级用例：explorer 中新建文件 → 断言新 tab 打开且为空缓冲
（`open_path_later` 语义下加 `await pilot.pause()`）。

### S5 — `_original_excepthook` 在导入时捕获

**证据：** [logs.py:278-280](../../../yate/logs.py) `CrashService.__init__`
（import 期）捕获 `sys.excepthook`；若宿主在 import yate 之前安装了自己的
hook，链路仍对；但在 install() 之后有人替换 hook 时，恢复会覆盖他人。

**策略：** 捕获延迟到 `install()` 首次调用时；`uninstall()` 恢复到
install 时刻的值。构造函数不再触碰 `sys.excepthook`。

**测试：** `tests/test_logs*`：安装前伪造自定义 excepthook → install →
uninstall → 断言还原为伪造 hook 而非系统默认。

### S7 — `fc-cache` 使用 `shell=True`

> ✅ **已修复（2026-09-24，PR #13 审查修复）**：[fonts.py:267-283](../../../yate/services/fonts.py)
> 已改列表参数（无 shell、无重定向字符串），补 `timeout=10`，失败记 `log.debug` 不打断安装。
> 守卫：`test_install_unix_refreshes_the_cache_when_available`（断言 `"shell" not in kwargs`）、
> `test_install_unix_survives_a_failing_cache_refresh`（timeout / OSError 两变体）。
> 以下原始计划存档。

**证据：** [fonts.py:265-272](../../../yate/services/fonts.py) 带中文注释
说明「等价原来的 os.system」。

**策略：** 列表参数 + 显式展开，删掉 shell 依赖与重定向：

```python
subprocess.run(
    ["fc-cache", "-f", str(Path.home() / ".local" / "share" / "fonts")],
    check=False,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
```

**测试：** 单测 monkeypatch `subprocess.run` 断言 argv 列表与 kwargs
（Linux-only 条件跳过）。

### S10 — `_exit_code` 语义模糊

**证据：** [pty_proc.py:557-566](../../../yate/editor_term/pty_proc.py)
`STILL_ACTIVE` 与 API 失败均返回 `None`。

**策略：** 拆分两种状态——返回 `Optional[int]` 改为
`Optional[int]` + 独立 `is_running()` 查询，或返回
`Literal["running", "failed"] | int` 的窄类型。最小改动：新增
`_exit_code_or_failed()` 内部方法区分三态，公开 `exit_code` 保持兼容；
调用点（L533 状态栏轮询）按需采用。

**测试：** Windows/POSIX 各一条：活进程 → running；退出进程 → 代码；
句柄无效 → failed。

### S25 — `segments.py` 的 `position` 一名两义

**证据：** [segments.py:102](../../../tools/changelog/segments.py)（段序号）
与 [segments.py:122](../../../tools/changelog/segments.py)（commit 位置）。

**策略：** 循环变量改名 `seg_index`（L102-110），L122-127 保持 `position`；
纯重命名零行为变化。

**测试：** 现有 changelog 测试全绿即可。

---

## 批次三：渲染路径冗余（editor.py，一次渲染帧内重复计算）

### S12 — `diagnostics_on_line` 每行调两次

**证据：** gutter（[editor.py:424-427](../../../yate/editor_view/editor.py)）
与下划线（[editor.py:571-590](../../../yate/editor_view/editor.py)）各查一次。
*2026-09-24 核实：仍存在（editor.py:424 与 :576）；review.md 2026-09-24 审查的
存量 Minor「render_line 每行重复查询 LSP 诊断两次」与本条为同一问题，合并跟踪。*

**策略：** 渲染帧开头对可见行范围算一次
`dict[int, list[Diagnostic]]` 传入两处；或至少在行渲染函数内查一次
以参数下传 gutter。

**测试：** monkeypatch `diagnostics_on_line` 计数，渲染含诊断的 5 行
断言调用次数 ≤ 行数。

### S13 — `_welcome_lines()` 每帧重建

**证据：** [editor.py:495-510](../../../yate/editor_view/editor.py) 无缓存。

**策略：** 以 `keymaps.active_name`（或 keymap 对象 id）为键缓存
`tuple[str, ...]`；键不变直接返回。

**测试：** 渲染两次 welcome 断言返回同一对象；切换 keymap 后重建。

### S14 — 丢弃过期 highlight 结果后仍强制一个防抖窗口（2026-09-24 按现行代码改写）

**证据：** 实现已重构（原「集合 discard」路径不存在了）：现在由 `_hl_timer`
（Textual Timer）+ `_hl_scheduled_key` 防重（[editor.py:289-311](../../../yate/editor_view/editor.py)）。
在途 worker 的过期结果在 [editor.py:345-349](../../../yate/editor_view/editor.py) 被丢弃：
仅 `refresh()` 返回，`_hl_scheduled_key` 保留过期键、`_hl_tokens` 等缓存不清。
下一次渲染走 `_tokens_for`（L275-286）的「版本落后但同文档」分支，以
`_HIGHLIGHT_DEBOUNCE_S`（0.08s）重新调度——即使此时已没有待处理编辑，
也要多等一个防抖窗口才能拿到新 token。

**注意：** 「discard 后保留旧 `_hl_tokens` 上色」是**有意设计**（L113-115 注释：
避免编辑后整屏闪白）。原计划「discard 时同时清四个缓存属性」与该设计冲突，**作废**。

**策略（修订）：** discard 分支为当前状态立即重排一次，跳过多余防抖窗口：

```python
if self.doc is not doc or buf.content_version != version:
    self.refresh()
    self._schedule_highlight(0.0)  # 立即重排：过期丢弃不该再付一个防抖窗口
    return
```

worker 组本就 exclusive（`group="highlight"`），被丢弃的 worker 已结束，
立即重排不会产生并发 tokenize。

**测试：** 现有 highlight 防抖用例全绿；补一条：制造 doc 切换使在途结果被丢弃，
断言新 pass 立即启动（`_hl_scheduled_key` 更新为新键，无 0.08s 等待）。

### S15 — `_cursor_anchor()` 每渲染调用 3+ 次

**证据：** [editor.py:151-158](../../../yate/editor_view/editor.py)
每次遍历 pane 树；渲染路径多处独立调用。

**策略：** 渲染入口算一次存帧局部变量下传（与 S12 同一批做，模式相同）。

**测试：** monkeypatch 计数断言单帧调用次数为 1。

### S16 — terminal.py 死条件分支

**证据：** [terminal.py:280](../../../yate/editor_view/terminal.py)
`cell.char if cell.char != " " else " "` 恒等。

**策略：** 简化为 `cell.char`，删分支。

**测试：** 现有终端渲染用例全绿。

### S17 — `reconcile` 冗余滚动恢复

**证据：** [panes.py:461-467](../../../yate/editor_view/panes.py) reconcile 重建后恢复
**全部叶子**的滚动；而调用链上的 [apply_doc](../../../yate/editor_view/panes.py#L160-L178)
（L175-178）已对活动叶子恢复过滚动。
*2026-09-24 核实：两侧语义确有重叠——reconcile 面向结构变化后全量恢复，
apply_doc 面向 tab 切换只恢复活动叶子；重复的是「活动叶子」那一份。*

**策略：** reconcile 的恢复循环跳过即将获焦的活动叶子（`if leaf is focus: continue`），
非活动叶子的恢复保留；或反之收敛到一侧，实施时按调用图定。**实施前先写清
两者差异再动手。**

**测试：** 分屏场景：切分 → 关闭一半 → 断言剩余叶子滚动位置保留。

---

## 批次四：测试卫生

### S20 — 30 秒 sleep 子进程

**证据：** [test_lsp.py:847](../../../tests/test_lsp.py)
`args=["-c", "import time; time.sleep(30)"]`。

**策略：** 改自终止脚本 `import time; time.sleep(2)` + 测试断言上限收窄；
或用事件文件自删。清理失败路径已在测，缩短暴露窗口即可。

### S21 — 硬编码版本 `"0.2.4"`

**证据：** [test_theme_palettes.py:271](../../../tests/test_theme_palettes.py)。

**策略：** 改 semver 解析断言（`re.fullmatch(r"\d+\.\d+\.\d+", ...)` +
非空校验），与发版解耦；保留 `test_pyproject_keeps_the_single_dynamic_version_source`。

### S23 — `--limit` 无测试

**策略：** `tests/test_changelog_tool.py` 补两条：`--limit 1` 只出最新
1 条 commit；`--limit 0` / 负数的行为按实现固化（报错或空输出）。

### S28 — 测试深访私有 highlight 属性

**证据：** [test_app_textual.py:204-314](../../../tests/test_app_textual.py)
直接断言 `_hl_tokens` 等。

**策略：** **不引入 Protocol**（架构规则 R2 禁止）。在 `editor_view/editor.py`
加一个公开的只读探针方法（如 `highlight_probe() -> tuple[...]` 返回
frozen dataclass），测试改走探针；或退一步仅收敛到一个 `_hl_state()`
调试入口。二选一在实施时定，倾向前者。

### S29 — `_FakeApp` 未实现全部 hooks

**证据：** [test_editor_core.py:394-406](../../../tests/test_editor_core.py)
最小 stand-in，新 action 未实现即 AttributeError。

**策略：** `__getattr__` 返回记录调用的 no-op（测试可断言被调），并在
docstring 注明「新 action 默认 no-op」；比逐个补方法抗演进。

### S42 — 过时注释与已落地行为矛盾（2026-09-24 审查增补）

**证据：** [test_app_textual.py:3781-3786](../../../tests/test_app_textual.py)
注释仍称原子写是「separate hardening change」，实际已实现。

**策略：** 更新注释并补断言磁盘字节完好。

### S43 — `except BaseException:` 缺理由注释（2026-09-24 审查增补）

**证据：** [pty_proc.py:78](../../../yate/editor_term/pty_proc.py) 同文件其它宽捕获
均有理由注释，此处置漏（`document.py` 侧已补，re-raise 不吞异常，纯风格合规）。

**策略：** 补一行理由注释。

---

## 批次五：工具链

### S22 — `generate()` 用 `date.today()`

**证据：** [cli.py:92](../../../tools/changelog/cli.py)。

**策略：** `generate(..., date: str | None = None)`；CLI 加 `--date YYYY-MM-DD`；
未给时保持 `today()`。

**测试：** 传 `--date` 断言输出段头日期；不传回退 today。

### S27 — `files_dirty` 前导空格路径

**证据：** [cli.py:63-75](../../../tools/release/cli.py)
`line[3:].strip().strip('"')`——porcelain 对带空格路径的引号规则处理粗糙。

**策略：** 改 `git status --porcelain -z`（NUL 分隔，无引号歧义）解析；
保持返回签名不变。

**测试：** 临时仓库建带空格/引号文件名的 dirty 文件，断言 files_dirty
返回准确路径。

### S11（收尾）— `walk_files` 递归深度

**证据（2026-09-24 更新）：** [workspace.py:252](../../../yate/services/workspace.py) 仍为
嵌套递归 `walk()`；符号链接环已防（L244-248）。新增的 `limit: int = 5000` 参数
只限**文件总数**，不限递归深度，极深目录（>1000 层）的 `RecursionError` 风险未变。
[visible_tree](../../../yate/services/workspace.py#L255-L272)（L255-272）同样递归且**无**
symlink 环防护（review.md 2026-09-24 审查存量条目），一并纳入本条改造。

**策略：** 改显式栈迭代（保持现有排序语义：目录优先、name.lower()），
`visible_tree` 同批改迭代并补与 `walk_files` 相同的 symlink 环防护。
**注意**：改迭代时逐层排序行为必须与
现测试基线一致（`test_workspace_filter` 有顺序断言）。

**测试：** 现有用例全绿 + 新增 1500 层深链目录（临时构造）不炸 + 指向祖先的
symlink 展开不栈溢出。

---

## 批次六：2026-09-23 / 2026-09-24 审查补充（正确性与语义）

> 来源：[review.md](../../issues/review.md) 2026-09-24 状态复核时补入——
> 「补全弹窗按键放行修复的附带发现（2026-09-23）」、「冒烟补场景调查（2026-09-23）」、
> 「PR #13 审查修复（2026-09-24）」遗留项、「全量代码审查（2026-09-24）」存量 Minor
> 与 Suggestion、「复审补充（logs.py）（2026-09-24）」中**仍未修复**的条目。
> 低影响 / 纯清理类的同源条目归入 [P2](P2_nice_to_have_plan.md)（N18–N31）。

### S30 — Esc 关闭补全弹窗后，在途 worker 把它重新显示

**证据：** [completion.py:128](../../../yate/completion.py) `popup.close()` 只改弹窗
状态、不取消已排队的请求；`_stale()`（[completion.py:202-219](../../../yate/completion.py)）
只比较文档 / 行 / 列 / 前缀与挂载状态，不检查「用户已显式关闭」，worker 落地后仍
`popup.show()`（实测 Esc 后约 0.1s 弹窗重现，UX 抖动）。

**策略：** 关闭时记录「用户已忽略」标记（或递增 generation / 取消在途 worker），
`_worker` 与 `_stale()` 一并检查；用户再次主动触发（`Ctrl+Space`，或继续输入使
前缀变化）时清除。注意与 `after_editor_key` 的 `schedule()` 区分：后者属主动输入
路径的 guarded re-query，应保留。

**测试：** pilot 用例：弹窗打开 → Esc → 推进防抖与 worker 落地 → 断言
`is_open` 保持 False；再按 `Ctrl+Space` → 弹窗恢复。

### S31 — vim 操作符删除（`dw` / `d$`）不写寄存器

**证据：** [vim.py:477-490](../../../yate/keymaps/vim.py) `buf.delete_selection()`
返回值被丢弃且该方法不自设 register；对照 visual 路径（L217-219）显式写
`buf.register`。复现：`yy` → 移动 → `dw` → `p` 粘出旧行。存量缺陷。

**策略：** 与 visual 路径一致，捕获返回值写入 `buf.register`。

**测试：** `yy` → 移动 → `dw` → `p` 断言粘出被删文本；`dw` → `p` 断言粘出被删词。

### S32 — PTY 启动失败后终端永久空白无法复活

**证据：** [terminal.py:104-121](../../../yate/editor_view/terminal.py) `self.proc = proc`
在 `await proc.start()` **之前**赋值；spawn 失败只 settle future 不调 `_on_exit`，
`dead` 恒 False → `started` 恒 True → 重生分支永不触发，只能重启应用。存量缺陷。

**策略：** `spawn_shell` 失败分支复位 `proc=None` / `dead=True`，让面板回到可重生状态。

**测试：** monkeypatch spawn 抛错 → 断言面板进入 dead 态且重生路径可达。

### S33 — 失败扩展模块残留 `sys.modules`

**证据：** [extensions.py:389-423](../../../yate/services/extensions.py) `exec_module`
抛异常后不清理，半初始化模块可被后续 import 命中。存量缺陷。

**策略：** except 分支先 `sys.modules.pop(module_name, None)` 再记录错误。

**测试：** 构造 import 即抛错的扩展 → 断言模块名不在 `sys.modules`。

### S34 — `bind_key` 的 keymap 名拼写错误静默无绑定

**证据：** [extensions.py:290-301](../../../yate/services/extensions.py)
`keymaps.get(target)` 返回 None 直接跳过，无任何提示。存量缺陷。

**策略：** 未命中时 `log.warning`（或向 `api.message` 写提示），列出可用 keymap 名。

**测试：** 以不存在的 keymap 名调用 → 断言出现警告且不抛异常。

### S35 — `dg` / `yg` 空 motion 仍报 "deleted" / "yanked"

**证据：** [vim.py:303-321](../../../yate/keymaps/vim.py) `"g"` 未排除出操作符
motion——`gg` 是位置跳转不是操作符范围，空 motion 仍报已删除 / 已复制。

**策略：** 操作符等待态排除 `"g"`。

**测试：** `dg` / `yg` 后断言无 deleted/yanked 消息、缓冲不变。

### S36 — 崩溃报告 / trace 日志文件名秒级碰撞

**证据：** [logs.py:396-401](../../../yate/logs.py) `build_err_path` 秒级时间戳，且
L319 以 `"w"` 模式打开；[logs.py:522-523](../../../yate/logs.py) trace 同秒级命名
（`mode="a"` 只交织不覆盖）。同秒双进程启动：后者截断前者头部、崩溃报告互毁，
trace 的会话 header 混入同一文件。存量问题，多实例共享数据目录时场景真实。

**策略：** 文件名追加 pid（`crash-YYYYMMDD-HHMMSS-<pid>.err`）或改微秒精度
时间戳；trace 同理。

**测试：** 固定同一时刻两次调用 `build_err_path`（monkeypatch 时钟）断言路径不同。

### S37 — 删除最后选中项后 `_last_selected` 悬挂

**证据：** [explorer.py:107,119-123](../../../yate/editor_view/explorer.py)
`_restore_cursor` 未命中时不清 `None`。

**策略：** 未命中时 `_last_selected = None`。

**测试：** 选中末项 → 删除 → 断言 `_last_selected is None`。

### S38 — `KeymapSet` 空字典抛裸 `StopIteration`

**证据：** [keymaps/registry.py:19-21](../../../yate/keymaps/registry.py)
`next(...)` 无默认值，空注册表时抛裸 `StopIteration`，难定位。

**策略：** 显式 `raise ValueError("no keymaps registered")`。

**测试：** 空注册表调用断言 `pytest.raises(ValueError)`。

### S39 — symlink 重定向即可改变信任对象（需先定方案）

**证据：** [trust.py](../../../yate/services/trust.py) 信任按「读取时 resolve 后的
路径」匹配：store 中某条目本身是 symlink 路径时，链接被重定向后**无需重新
`:trust`** 即信任到新目标。来源：PR #13 审查附带发现，改动面超出当轮，未修。

**策略：** 彻底修复需改存储策略（落盘真实路径 / inode 校验 / `:trust` 时拒绝
写入 symlink 路径），**实施前先定方案**；短期最小加固是 `:trust` 写入前
resolve 并拒绝 symlink 条目。注意现有
`test_startup_treats_a_literal_symlink_entry_as_its_resolved_root`
固化了「字面 symlink 条目按 resolve 后根等价」的归一化行为，改方案时需同步调整。

**测试：** 依最终方案补守卫（symlink 重定向后必须重新 `:trust`）。

---

## 批次七：2026-09-24 审查补充（渲染 / 性能）

### S40 — 文档搜索每按键全量重渲染所有块 widget，无防抖

**证据：** [manual.py:341-379](../../../yate/editor_view/manual.py) 每按键重建全部
块 widget，大文档输入卡顿。存量缺陷。

**策略：** 仿 `EditorView._HIGHLIGHT_DEBOUNCE_S` 用
`asyncio.get_running_loop().call_later` 防抖，窗口期合并查询后再重建。

**测试：** pilot 连续输入多字符，monkeypatch 重建函数计数，断言调用次数
小于按键数且最终内容正确。

### S41 — dirty 状态下每次 `modified` 查询 O(N) tuple 分配

**证据：** [document.py:86-88](../../../yate/editor_core/document.py) 状态栏每键
查询，回退路径构造行元组比较；代码注释已自认知该权衡。

**策略：** 按 `content_edits` 缓存上次判定（编辑计数不变直接返回缓存布尔，
计数变化才重算并刷新缓存）。

**测试：** 现有 modified / undo / redo 用例全绿；补一条跨 undo 的判定正确性断言。
