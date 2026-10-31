# file-manager（IKRZ41）合并前评审 — 2026-10-31

**评审范围**：`feat/file-manager` 分支 `630b7e6..HEAD` 的 10 笔提交（36 文件，+4538 / −186）。
L0 `services/workspace.py` 扩展、L2 `editor_view/{preview,filemgr_model,filemgr,filemgr_keys}.py`
+ `resources/filemgr-screen.tcss`、L3 `flows/filemanager_flows.py` + `editor.py` 接线、
L4 `actions/commands/keymaps×2/cli/app` + `UI_FROZEN_FILES` 登记、双语手册 + 文档索引、7 个新测试文件。
**方案依据**：`../documents/file-manager-plans/overview.md`（总纲，含 Q1/Q2/Q4 裁决）
与子计划 plan-a…plan-g。

**结论**：1 blocker / 4 major / 6 minor。门禁五项实测见 §四；blocker 为
`--file-manager` 启动形态的 `on_mount` 竞态，属可复现的真实缺陷（非偶发，不得记成 flake）。

---

## 一、发现清单（按严重度）

### [blocker] B1 — `FileManagerScreen.on_mount` 在子节点未挂载时 `query_one`，启动形态间歇崩溃

- **位置**：`../../yate/editor_view/filemgr.py:193-201`（`on_mount` 首三行 `query_one`）；
  触发路径 `../../yate/app.py:229-238`（`call_after_refresh` → `open_fullscreen`）。
- **现象**：`on_mount` 抛 `textual.css.query.NoMatches: No nodes match '#filemgr-parent' on
  FileManagerScreen(classes='fullscreen')`，`_reload()` 与 `_apply_theme()` 均未执行 →
  全屏形态打开后无列表、状态栏空白，异常向上冒到 Textual 消息泵（生产上表现为启动即报错退出）。
- **实测证据**（同一命令多次运行结果不一致）：
  - `pytest tests --cov=yate --cov-branch --cov-fail-under=75 -n auto` 第 1 次：
    `FAILED tests/test_app_filemgr.py::test_fullscreen_startup_pushes_filemgr_screen`（exit 1）；
    第 2 次同命令 3277 passed（exit 0）。
  - `pytest tests/test_filemgr.py tests/test_filemgr_model.py tests/test_filemgr_flows.py
    tests/test_app_filemgr.py tests/test_workspace_filemgr.py tests/test_palette_preview.py
    --cov=... -n auto`：复现，堆栈指向 `filemgr.py:195`。
  - `-n 1` 串行复核：4/4 通过，整文件串行 10/10 通过 → **负载触发的时序假设，但缺陷在产品代码**：
    Textual 8.2.8 的 `push_screen` 经 `App._get_screen`（`app.py:2797-2820`）用 `call_next`
    延后挂载 compose 子节点，屏幕自身的 `Mount` 可先于子节点派发，故 `on_mount` 里的
    `query_one` 在慢机/高负载下必然可能落空。
- **建议修法**：把挂载期接线整体延后并对未就绪态重试，例如

  ```python
  def on_mount(self) -> None:
      self.call_after_refresh(self._wire_mount)

  def _wire_mount(self) -> None:
      if not self.query("#filemgr-parent"):
          self.call_after_refresh(self._wire_mount)  # children not composed yet
          return
      ...  # apply_slim_scrollbars / theme.attach / _reload / focus
  ```

  或按 `PreviewLog` 先例把每栏的滚动条接线下沉到各自组件的 `on_mount`（`preview.py:60-68`），
  屏幕级只保留可安全延后的部分。**不要**只放宽测试 `wait_until` 超时——那会把真实竞态藏起来。

### [major] M1 — 盘符虚拟层只能看不能进（Q4 裁决未落地，Windows 专属）

- **位置**：`../../yate/editor_view/filemgr.py:636-639`（`action_up` 在根层直接 `return`）、
  `filemgr.py:185-187`（左栏 `can_focus = False`，仅展示）、
  `../../yate/editor_view/filemgr_model.py:244-247`（只有 `cwd` 为根时才给盘符列表）。
- **问题**：`C:\` 上按 `h` / `Left` / `Backspace` 无任何反应，左栏虽列出盘符但不可聚焦、
  无任何动作能进入盘符项 → 在文件管理器内**无法切换盘符**，只能退出重开。
  与总纲 §三 Q4 裁决「到达根层后 `h`/`Left` 列出盘符虚拟层」的可用语义不符
  （当前是"到根自动展示、且不可进入"）。
- **建议**：区分"根层"与"盘符虚拟层"两个状态（如 `_cwd: Path | None`，`None` 表示盘符层），
  `action_up` 在根层切到盘符层、在盘符层进入所选盘；`#filemgr-parent` 相应可聚焦或改为
  由中间栏承载盘符项。若产品裁定为 P1 延后，须在 `../documents/file-manager-plans/overview.md`
  §三 Q4 与双语手册同步登记，不能留"看起来支持"的展示。

### [major] M2 — 屏幕内重命名 / 删除不与编辑器会话和文件树同步

- **位置**：`../../yate/editor_view/filemgr.py:581-590`（delete / rename 分支），
  仅 `workspace.remove_entry` / `rename_entry` + `workspace.invalidate()` + `_reload()`。
- **对照既有实现**：文件树的同一操作额外做了两步——
  `../../yate/editor_view/explorer.py:518` `session.retarget(path, new_path)`（重命名后让标签跟随）、
  `explorer.py:535` `session.close_under(path)`（删除后关掉其下所有标签），两者随后
  `refresh_tree()`（`explorer.py:519` / `536`）。
- **后果**：
  1. 重命名一个已打开的文件后，标签仍指向旧路径；此时在编辑器里保存，会把**旧文件名重新
     创建出来**，与被重命名的文件并存；
  2. 删除一个已打开的文件后，标签存活并指向不存在的路径，之后再保存会静默复活已删文件；
  3. 两步都不刷新文件树（`workspace.invalidate()` 只清缓存），explorer 继续列出已删/旧名条目，
     直到下一次刷新。
- **建议**：按 R3 边界不要在该屏幕里碰 `session`，改为注入回调（`FileManagerFlows` 已持有
  `session` 与 `explorer_tree`）：`on_renamed: Callable[[Path, Path], None]` →
  `session.retarget` + `explorer_tree.refresh_tree()`；`on_deleted: Callable[[Path], None]` →
  `session.close_under` + `refresh_tree()`。顺带可在此处补 Q1 同源的脏缓冲门禁
  （`close_under` 当前不看 `modified`，属既有行为，非本 diff 引入）。

### [major] M3 — 大目录 / 过滤击键的同步全量工作（可扩展性）

- **位置**：`../../yate/editor_view/filemgr.py:245`（每次 `_reload` 对全部条目 `stat_entry`）、
  `filemgr.py:273-275`（每次 `_rebuild_rows` 对全部目录 `count_children`）、
  `filemgr.py:288-298`（`_render_list` 每次 `clear()` + 全量重建 `ListItem`）、
  `filemgr.py:520-525`（`on_input_changed` → `_refilter`，即**每击键**重跑上述三步）。
- **量化依据**：`../../yate/services/workspace.py:286-289` 的 `list_dir` 已用
  `child.is_dir()` 给每个条目做过一次 `stat`（decorate-sort-undecorate），而 `stat_entry`
  再对同一路径 `stat` 一次 → 每条目 2 次 syscall；再叠加每个目录一次 `scandir`。
  1 万条目 + 1 千子目录量级下，`r` / `s` / `H` 与**每次过滤键入**都在 UI 线程上做
  ~2 万次 syscall 并重建 1 万个 `ListItem`，实测可感知卡顿（属"显著性能问题"）。
- **建议**：三条独立措施，按收益排序——
  1. `list_dir` 侧带回 `is_dir` 已有信息，`stat_entry` 只在**渲染到的行**（可见窗口）按需取，
     或给 `stat_entry` 加批量条目接口供 L0 复用 `os.scandir` 的 `DirEntry.stat()`；
  2. `count_children` 只在目录项首次出现时算一次（`_child_counts` 已是缓存字典，
     但 `_rebuild_rows` 每次全量重算，应改成 `setdefault` 语义 + `r` 时清空）；
  3. 过滤改成增量 `ListItem` 增删或在 worker 里算，避免每击键全量重建。

### [major] M4 — 粘贴 / 剪切 / 复制（唯一破坏性多步流程）零用例覆盖

- **位置**：`../../yate/editor_view/filemgr.py:763-798`（`action_yank` / `action_cut` /
  `action_paste` / `_clip`），覆盖率为 6 文件子集口径下 `filemgr.py` **78%（509 stmts，91 missing）**，
  缺行段含 `783-798`（paste 全段）、`556-559`（`_show_input_error`）、`474-482`（`gg`）、
  `620-634`（半页滚动）、`639`（根层 `h`）、`577-598`（delete/rename 错误与取消分支）。
- **风险**：`p` 走 `move_entry`（**删除源**）或 `copy_entry`；屏幕层的目标目录、剪切缓冲消费、
  冲突提示三条接线目前只有 `Workspace` 层单测（`tests/test_workspace_filemgr.py`），
  屏幕层任何一处接错都是数据面事故，而当前无任何用例。
- **建议**：补 `tests/test_filemgr.py` 用例：`y` → `p` 复制到子目录（源保留、目标存在）、
  `x` → `p` 移动（源消失、缓冲被消费，第二次 `p` 报 `clipboard is empty`）、
  同名冲突 → 底行出现 `paste failed:` 且**两侧文件内容都不变**、以及 `_show_input_error` 的
  Enter 收起。

### [minor] m1 — 死面：未使用的别名 / 注入协作者 / 参数

- `../../yate/flows/__init__.py:47` `type OpenSelectedFn` 全仓无引用（`filemanager_flows.py`
  内联写 `Callable[[list[Path]], None]`）——定义即死代码。
- `filemanager_flows.py:56-69` 注入的 `spawn` / `explorer_tree` / `message` 赋值后全文未再引用
  （预览 worker 用的是 `Screen.run_worker`）。
- `../../yate/editor_view/filemgr_model.py:153-154` `build_row_text(sort_key=...)` 自述
  "reserved for a later sort-column indicator"，当前不参与渲染。
- **建议**：删除或落地。`explorer_tree` 在 M2 的修法里正好要用。

### [minor] m2 — 文件操作报错会清空用户输入并丢弃 prompt 上下文

- **位置**：`filemgr.py:595-598`（失败 → `_show_input(str(exc))`）→ `filemgr.py:554-559`
  （`_show_input_error` 把 `_prompt_kind`/`_prompt_target` 置 `None` 且 `value=""`）。
- **问题**：重命名撞名后，用户输入的 `newname` 与"正在重命名"的上下文都被清掉，只能重新按 `R`
  再输一遍；docstring 自称"Errors keep the input open with the message shown"，实际只保留了
  提示文字。手册 §3 未描述此行为。
- **建议**：错误时保留 `_prompt_kind`/`_prompt_target` 与已输入值，仅把提示写到状态栏或
  placeholder；仅"只读提示"路径才清空上下文。

### [minor] m3 — `--file-manager` 不校验目录存在性

- **位置**：`../../yate/cli.py:283-291`（只校验与位置参数互斥）、
  `filemgr.py:156`（`(initial_dir or root or Path.cwd()).resolve()`，3.6+ 非严格 resolve 不抛）。
- **问题**：`yate --file-manager /does/not/exist` 会进入空列表界面（Windows 上还会同时显示
  盘符栏），无任何提示；用户不知道是路径错还是空目录。
- **建议**：`_validate_file_manager_args` 补 `Path(...).is_dir()` 校验（`parser.error`，
  与既有 argparse 口径一致），或在屏幕 `_reload` 时对 `_cwd` 不存在给出显式占位与消息。

### [minor] m4 — 双语手册三处与实现不符

| 手册表述 | 实现事实 |
|---|---|
| `../../yate/docs/file-manager.zh.md:129` / `file-manager.en.md:143`："最近 16 条预览…**与命令面板共享**" | 两个屏幕各自 `PreviewCache()`（`filemgr.py:171`、`palette.py:151`），只共享管线（`preview.py`），不共享缓存 |
| `file-manager.zh.md:144` / `file-manager.en.md:161`："仅限同卷传输……**拒绝**跨盘符移动条目" | `move_entry` 用 `shutil.move`（跨卷走 copy+delete），`copy_entry` 用 `copy2`/`copytree`，**没有任何跨卷检测或拒绝**；docstring 甚至自述跨卷可用（`workspace.py:497-501`） |
| `file-manager.zh.md:92` / `file-manager.en.md:100`："同名冲突在输入行**确认**/asks on the input line" | 实现只报 `paste failed: <name> already exists`，没有确认/覆盖流程 |

- **说明**：跨卷行为本身优于计划非目标（更可用），但"已知限制"写反了会让用户以为不会发生
  复制；三种表述都需按实现改写（或把跨卷确认为正式支持并从计划非目标移除）。

### [minor] m5 — 隐藏文件开关不刷新文件树

- **位置**：`filemgr.py:669-672`（只 `workspace.show_hidden = not …` + 自身 `_reload()`）。
- **对照**：`../../yate/editor.py:1246` 的 `set_show_hidden` 走同一开关并同时刷新树与状态栏。
- **后果**：手册 §1「隐藏文件…同一份状态」成立，但树视图保持旧集合，直到下一次刷新才同步。
- **建议**：与 M2 同一注入通道（`on_show_hidden_changed`），或直接复用编辑器既有入口。

### [minor] m6 — 新 UI 无端到端冒烟场景

- `tools/smoke_test` 全仓 0 处 `filemgr` / `file-manager` 命中；冒烟 120 场景全通过但**没有任何
  一个覆盖新屏幕**（本次唯一自动化端到端面是 pilot 用例）。B1 恰好说明启动渲染链需要端到端守卫。
- **建议**：新增 1 个场景——`--file-manager` 启动 → 断言三栏标题/状态栏文本 → `j`/`l` 导航 →
  `Esc`/`q` 退出，纳入 117+ 基线。

---

## 二、契约与架构核对结论（通过项）

1. **Q1 dirty 门禁真实成立（不静默丢弃）**：`filemanager_flows.py:179-183` 统计
   `doc.modified` 后 `report(... "warn")` 并拒绝切换，`_switch_workspace` 返回 `False` 时
   不关任何标签、不开任何路径。浮层此际已 dismiss 属总纲 §三 Q1 的 wave-4 裁决（已登记），
   不作为发现。
2. **Q2 字母序**：`filemgr.py:658` `sorted(self._marked)`；`Path` 排序在 Windows 为
   大小写不敏感、POSIX 为字节序，与"字母序第一个目录"裁决一致；混合集合的 report 文案在
   `filemanager_flows.py:150-155`。
3. **`close_active` 循环必然终止**：`../../yate/session.py:201-221` 保证末次关闭追加无路径
   scratch，循环条件 `len(docs)==1 and docs[0].path is None` 必然达成；dirty 前置门禁排除
   "关不掉"的分支。`tests/test_filemgr_flows.py:36-55` 的 stub 与真实语义一致。
4. **`open_path` 事件链复用**：`filemanager_flows.py:184-193` → `../../yate/flows/document_flows.py:264-284`
   （目录 `set_root`+`refresh_tree`+`reveal`，文件 `_open_document`+`_after_open`），未自写
   根切换逻辑。
5. **dismiss-then-callback 时序安全**：Textual 8.2.8 `Screen.dismiss` → `App.pop_screen`
   **同步出栈**（`app.py:3103-3121`），DOM 替换延后；故 `filemgr.py:657-661/666-667`
   "先 dismiss 再回调" 的回调运行在已出栈状态，`has_modal_screen` 已为 False，
   与 Q3 及 `test_filemgr.py:266-267` 断言一致。无双派发（`_Row.on_click` 停掉点击，
   `ListView` 的 `enter` 绑定优先于屏幕级 `enter`）。
6. **预览 worker**：`group="filemgr-preview", exclusive=True` + `is_mounted` 复核 +
   光标复验（`filemgr.py:366-373/394-403`）；缓存按 `(mtime_ns, size)` 复验并即时淘汰过期项
   （`preview.py:168-182`）；协程以 `partial` 传入避免未启动即泄漏（`pyproject.toml`
   的 `filterwarnings=error::RuntimeWarning` 亦为佐证）。
7. **`EntryStat` 平台守卫**：`workspace.py:590-605` 经 `importlib` 动态取 `pwd`/`grp`，
   失败返回 `(None, None)`；`tests/test_pack_spec.py:81-85` 已把两条动态导入登记进
   `_REVIEWED_DYNAMIC_IMPORTS`（否则打包守卫会红）。
8. **架构边界**：R3（`filemgr.py` 无 `yate.editor`/`yate.app` 导入，只收 `Workspace` +
   `FilePreviewConfig` + 回调）；R11 登记与实际 import 一一对应
   （`tests/test_architecture.py:250-254` 的 `commandline` / `explorer` / `filemgr` 三条）；
   R12（模块级 `tracing`，惰性 `%`）；R13（`theme.attach` 自持上色，无 `.styles.*` 直改）；
   R15（`filemgr.py:195-199/207-215` 与 `preview.py:60-76` 三栏均接
   `apply_slim_scrollbars` + `apply_scrollbar_theme`）；命名守卫、PEP 695 别名、
   `filemgr.py` 798 行 < 800、flows 不持 App 句柄（`tests/test_filemgr_flows.py:229-233` +
   架构守卫）均通过。
9. **方案先行**：总纲 + 7 个子计划齐备（`../documents/file-manager-plans/`），Q1/Q2 的
   wave-4 裁决有落盘记录。
10. **测试风格**：全部轮询 `wait_until`、无真实 `sleep`；双击窗口按**消费模块**打补丁
    （`tests/test_filemgr.py:285` 注释正确指出 `from … import` 的按值绑定），
    属本项目既有坑的正确处理。

---

## 三、强制自我批判登记

| 条目 | 处置 | 理由 |
|---|---|---|
| B1 | 确认保留（blocker） | 有完整堆栈与"同一命令两次不同结果"的实证；串行 6/6 通过仅说明**触发条件**是负载，不是缺陷不存在。按本项目口径（并行失败必须查清、不得记成偶发）与"合并硬门槛 = pytest 全绿"，属阻塞项。 |
| M1 | 确认保留（major） | 初判考虑降为 minor（手册只承诺"展示"）；复核总纲 §三 Q4 明确写"到达根层后 `h`/`Left` 列出盘符虚拟层"，且 Windows 上无法切换盘符与"完整文件管理器"目标冲突 → 维持 major。 |
| M2 | 确认保留（major，漏报自查补入） | 初版遗漏；对照 `explorer.py:518/535` 才发现同仓已有正确语义，属本 diff 新引入的不一致。 |
| M3 | 确认保留（major） | 初版只写"可能有性能问题"，复核到 `list_dir` 已 `is_dir()`（`workspace.py:286-289`）这一实证后，重复 `stat` 与每击键全量重建成立，按"显著性能问题"定级。 |
| M4 | 由 minor 上调为 major | 79-798 段是唯一会删除源文件的流程且零用例；`move_entry` 误接即数据面事故，覆盖缺口按 major 记。 |
| m1 / m2 / m3 / m4 / m5 / m6 | 确认保留（minor） | 均为有实证的低风险项，逐条给出位置与修法。 |
| ~~`human_size` 超 1024T 显示 `1048576T`~~ | 删除 | 只影响 >1 PiB 的外观，无实际取值面，属风格挑剔。 |
| ~~`list_drives` 26 次 `Path.exists()` 探测阻塞~~ | 删除 | 仅在"`cwd` 为根"时触发（`filemgr_model.py:244-247`），非每次 reload；无实测成本证据。 |
| ~~`open_path` 抛 `OSError` 致崩溃~~ | 删除 | 复核 `Path.resolve()` 非严格、`set_root` 不抛、`list_dir` 吞 `OSError`（`workspace.py:290-291`），推测不成立。 |
| ~~`_render_list` 后立刻按键可能标记到错行~~ | 删除 | 窗口是一帧内的烘焙索引，后果只是一次标记切换，无用户可见损害，属无实证断言。 |

**漏报自查**：正确性（M2 补入）、边界（m3 补入）、异常处理（m2 补入）、并发（B1）、
性能（M3）、类型（pyright 0，无缺口）、测试覆盖（M4 / m6）均已覆盖。

---

## 四、门禁实测（本机亲自执行，退出码与数字均为原文）

| # | 命令 | 结果 | 退出码 |
|---|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` | 0 |
| 2 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 全绿（本机 `-q` 无汇总行，按退出码判定；同批覆盖率运行给出 3277 passed / 10 skipped） | 0 |
| 3 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 37 用例全通过（进度行 37 个点） | 0 |
| 4a | `pytest tests --cov=yate --cov-branch --cov-fail-under=75 -n auto`（第 1 次） | **1 failed / 3276 passed / 10 skipped**，总覆盖率 92.47%（`test_fullscreen_startup_pushes_filemgr_screen`，见 B1） | **1** |
| 4b | 同命令（第 2 次） | 3277 passed / 10 skipped，TOTAL 19134 stmts / 1155 missing / 6130 branches / 577 partial → **92.45%**（阈值 75 通过） | 0 |
| 5 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | **120/120 scenarios，1446/1446 checks（100%）** | 0 |

**覆盖率口径说明**：全量分支覆盖率 92.45% 高于 75 门槛；新模块在本组用例口径下
`filemgr.py` 78%（509 stmts / 91 missing，缺行见 M4）、`preview.py` 96%（缺 `114-115` / `166` / `197`）、
`filemgr_model.py` 99%（缺 `171->173` 分支）、`filemgr_keys.py` 100%；
全量口径 `workspace.py` 96%（缺 `600-605` 的 POSIX-only `KeyError` 分支、`620->625` 的
`human_size` 循环分支等，其余为存量行）。

---

## 五、合并建议

- B1 必修（改法与复现命令见 §一）；M1/M2 建议本轮修（M2 属一致性缺陷，M1 属裁决未落地）；
  M3/M4 可评估后置但须登记方案；m4（手册三处）建议与代码同轮改，避免用户按错误文档操作。
- B1 与 M4 的修复应带回负向演练：先让用例变红（`-n auto` 下复现启动竞态、paste 断言失败），
  再转绿，避免"改完正好不红"。
