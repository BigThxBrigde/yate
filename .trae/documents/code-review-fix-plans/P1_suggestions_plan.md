# P1 Suggestion 修复计划

> 来源：[review.md](../../issues/review.md) 2026-09-16 审查 Suggestion 段（2026-09-23 复核后
> 仍存在的条目）。按主题分五批，批内按影响排序；每条含证据、策略、测试要点。
> **本文档仅为计划，未实施。** 统一门槛同 [P0](P0_critical_fixes_plan.md)。

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

### S14 — highlight discard 后未清过期缓存键

**证据：** [editor.py:346-357](../../../yate/editor_view/editor.py)
discard 只清 `_hl_scheduled_key`，`_hl_tokens/_hl_doc/_hl_version/_hl_filetype`
残留，导致无编辑也强制 80ms 防抖。

**策略：** discard 路径同时清四个缓存属性（或封装 `_clear_hl_cache()`）。

**测试：** 现有 highlight 防抖用例补断言：discard 后 `_hl_tokens is None`。

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

**证据：** [panes.py:474-483](../../../yate/editor_view/panes.py) 恢复逻辑
与调用方 `apply_doc` 重复。

**策略：** 先核实两侧语义（apply_doc 恢复活动叶子、reconcile 恢复全部
叶子？），若确属重复则删除 reconcile 中活动叶子的恢复；若 reconcile
覆盖的是非活动叶子则保留但加注释区分。**实施前先写清两者差异再动手。**

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

**证据：** 符号链接环已防（[workspace.py:244-248](../../../yate/services/workspace.py)）；
实现仍为嵌套递归，极深目录（>1000 层）有 `RecursionError` 风险。

**策略：** 改显式栈迭代（保持现有排序语义：目录优先、name.lower()），
`visible_tree` 如同样递归则一并。**注意**：改迭代时逐层排序行为必须与
现测试基线一致（`test_workspace_filter` 有顺序断言）。

**测试：** 现有用例全绿 + 新增 1500 层深链目录（临时构造）不炸。
