# IKTR5Q 最终删除清单

> 与 [`unused-symbols-cleanup-keep-register.md`](unused-symbols-cleanup-keep-register.md)
> 同时交付，数量可对账：**1255 = 14 删除 + 1241 保留**。
> 逐条判定的机器可读事实见方案总纲
> [`unused-symbols-cleanup-plans/overview.md`](unused-symbols-cleanup-plans/overview.md)。

## 一、总量对账

| 域 | 复扫形参 | 复扫局部名 | 判定删除 | 判定保留 |
| --- | --- | --- | --- | --- |
| `yate/` | 70 | 81 | 14 | 137 |
| `tools/` | 10 | 20 | 0 | 30 |
| `tests/` | 511 | 563 | 0 | 1074 |
| `pack/` | 0 | 0 | 0 | 0 |
| 合计 | 591 | 664 | **14** | **1241** |

删除项全部落在 `yate/` 产品代码的**未使用形参**；`local` 候选 664 条经逐条复核
**全部登记保留**（215 条 `_` 解包占位、349 条解包/循环语义占位、90 条循环目标、
5 条 `nonlocal`、1 条 `global`、4 条嵌套类属性 AST 误报——后者见 §三）。

## 二、14 条删除项（`文件:行号 → 名称 → 类别 → 调用点清单 → 行为一致证据`）

### 2.1 Textual 0 参数回调组（9 条，wave-1）

| # | 文件:行号 | 名称 | 原签名 → 新签名 | 调用点清单 | 行为一致证据 |
| --- | --- | --- | --- | --- | --- |
| 1 | `yate/app.py:186` | `_theme` | `watch_theme(self, _theme: str)` → `watch_theme(self)` | 仓内 0 处直接调用；由 `textual/reactive.py:106-116` `invoke_watcher` 按形参数分派 | 运行时探针：0 参数 watcher 在构造与赋值时各触发 1 次（共 2 次），主题变更重绘断言见 wave-1 plan-a |
| 2 | `yate/editor_components/chrome.py:163` | `_event` | `TabBar.on_resize(self, _event: Resize)` → `on_resize(self)` | 仓内 0 处直接调用；Textual `invoke` 分派 | `textual/_callback.py:45-56` 按 `count_parameters` 裁剪实参；探针 `invoke(w.on_resize, object())` 成功、`resize_terminal` 真实分派 |
| 3 | `yate/editor_components/chrome.py:313` | `_event` | `Breadcrumbs.on_resize(self, _event: Resize)` → `on_resize(self)` | 同上 | 同上 |
| 4 | `yate/editor_components/diff/pane.py:282` | `_event` | `DiffPane.on_resize(self, _event: Resize)` → `on_resize(self)` | 同上 | 同上 |
| 5 | `yate/editor_components/find_replace.py:197` | `event` | `FindReplaceScreen.on_resize(self, event: Resize)` → `on_resize(self)` | 同上 | 同上 |
| 6 | `yate/editor_components/manual.py:442` | `event` | `MarkdownDocScreen.on_resize(self, event: events.Resize)` → `on_resize(self)` | 同上 | 同上 |
| 7 | `yate/editor_components/terminal.py:266` | `_event` | `TerminalView.on_resize(self, _event: Resize)` → `on_resize(self)` | 同上 | 同上 |
| 8 | `yate/editor_components/view.py:177` | `_event` | `EditorView.on_focus(self, _event: Focus)` → `on_focus(self)` | 同上 | 同上 |
| 9 | `yate/editor_components/view.py:239` | `_event` | `EditorView.on_resize(self, _event: Resize)` → `on_resize(self)` | 同上 | 同上 |

**连带动作（属于签名删除的必然连带，非逻辑改动）**：逐个文件复核 `Resize` /
`Focus` / `events` 类型导入，若该文件中已无其它引用则删除该导入——pyright strict
的 `reportUnusedImport` 是硬门槛，留着会判红。既有函数体一行不改。

**调用点事实校正（wave-1 实测后回填）**：本组并非「仓内 0 处直接调用」——
`tests/test_terminal.py:552` 有唯一一处 `view.on_resize(Resize(Size(80, 24),
Size(80, 24)))` 直接调用（AST 调用点清单已记录，初判误读为其它对象的方法调用）。
改签名后主代理同步为 `view.on_resize()`，并删除该用例内 `Resize` / `Size` 两行
局部导入；行为一致（方法体用 `_grid_size()` 取 80x24 fallback，不读事件对象），
该用例与 `tests/test_terminal.py` 全量回归通过。详见总纲 §七 D7。

**改动前后行为一致证据**：9 个形参在函数体内均无 `Load` 引用（AST 逐条事实）；
函数体、返回值、装饰器、类基类、方法名全部不变；`invoke` / `invoke_watcher`
按形参数分派，0 参数形态不消费事件对象；全量门禁 + 新增
`tests/test_zero_arg_callbacks.py` 运行时/pilot 用例（详见 wave-1 plan-a）。

### 2.2 纯内部签名组（5 条，wave-2）

| # | 文件:行号 | 名称 | 原签名 → 新签名 | 调用点清单（全部同步删除对应实参） | 行为一致证据 |
| --- | --- | --- | --- | --- | --- |
| 10 | `yate/cmdline_completions.py:17` | `session` | 删 `session: EditorSession` 关键字形参 | `yate/editor_compose.py:128-133`（`functools.partial` 绑定 `session=ed.session`）、`tests/test_app_find.py:337`、`:475`、`tests/test_cmdline_completions.py:72`、`:142`、`:153`（共 6 处，均为 `session=` 关键字实参） | 函数体只有 `mode` / `commands` / `workspace` 三条路径，`session` 无任何 `Load`；`PromptCompleter = Callable[[str, str], list[str]]` 约束的是 partial 之后的 `(text, mode)`，删 `session` 不改变该契约 |
| 11 | `yate/editor_components/file_manager/model.py:177` | `sort_key` | 删 `sort_key: SortKey` 关键字形参 | `yate/editor_components/file_manager/screen.py:422`、`tests/test_file_manager_model.py:115`、`:123`、`:131`、`:140`、`:178`、`:190`、`:196`（共 8 处，均为 `sort_key=` 关键字实参） | docstring 自述该参数「reserved for a later sort-column indicator and does not affect the rendering」；函数体无 `Load`，8 处调用点全部同步 |
| 12 | `yate/editor_core/buffer.py:856` | `language` | 删 `language: str = "plaintext"` 关键字形参 | `yate/keymaps/base.py:223`、`yate/keymaps/vim.py:498`、`tests/test_input_assist.py:981`（共 3 处 `language=` 关键字实参）；另有 7 处仅位置参数调用，不受影响 | docstring 自述「V1 reads it not at all」；函数体无 `Load`，返回值与文本算法零改动 |
| 13 | `yate/editor_term/pty_proc.py:754` | `owner` | `_UnixPty.__init__(self, owner: PtyProcess)` → `(self)` | `yate/editor_term/pty_proc.py:71` `_UnixPty(self)` → `_UnixPty()` | 私有平台占位类，函数体只 `raise PtyProcessError`；调用点与两个占位类签名同步 |
| 14 | `yate/editor_term/pty_proc.py:759` | `owner` | `_ConPty.__init__(self, owner: PtyProcess)` → `(self)` | `yate/editor_term/pty_proc.py:71` `_ConPty(self)` → `_ConPty()` | 同上 |

**连带动作（属于签名删除的必然连带，非逻辑改动）**：

- `cmdline_completions.py`：删 `from yate.session import EditorSession`；模块 docstring
  删除「the document session」措辞。
- `file_manager/model.py`：复核 `SortKey` 导入是否还被其它函数使用，未使用则删；
  docstring 删除 `*sort_key* is reserved...` 句。
- `buffer.py`：docstring 删除 `*language* is the seam...` 整段（描述已不存在的形参）。
- 以上 docstring 同步是签名删除的必要一致性维护，不改变任何可执行逻辑。

**改动前后行为一致证据**：每个形参在函数体内均无 `Load` 引用；位置与关键字两种
传参方式都已逐处列出并同步；既有测试（补全、文件管理器模型、输入辅助、keymaps、
PTY）在 wave-2 局部验收与最终全量门禁中全绿；`git diff` 只含签名、实参与 docstring
删除。

## 三、明确不删的典型项（详见登记表）

- **4 条 `plain-unread-local` 全部是 AST 误报**：`tests/test_changelog_view.py:208`
  的 `overlays`、`tests/test_overlay_flows_hex.py:238` 的 `st_mtime` / `st_size`、
  `tests/test_shell.py:384` 的 `pid` 都是**嵌套类体内的类属性赋值**，被保守 AST
  口径（含嵌套作用域）误判成「函数局部名」；源码回读确认它们分别被
  `entry.func("zh")`、`fake_stat()`、`_kill_tree(StubProc())` 读取，删除会改变测试
  行为。按 issue §三「逐条核对、确认无用后再删」判定为保留。
- **27 条命令回调 `args`**（`yate/commands.py:266-612`）由 `CommandFunc` 固定签名
  传入；**16 条宿主协议镜像**（`yate/editor_components/highlighting.py:115-148`）
  签名即契约；`tools/pack/wiki/run.py:198 force` 是 CLI 开放 API 且有 3 处关键字
  传参；`tools/pack/wiki/lint.py:275 total` 是进度适配器契约且源码有显式
  `del total`；`tools/screenshots/scenarios.py` 4 条 `fixtures` 受
  `Scenario.driver` 统一签名约束；`tools/smoke_test/scenarios/view.py:219` 的
  `*args/**kwargs` 是 monkeypatch 桩。全部登记保留。
