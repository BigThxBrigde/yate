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

---

## :cd command (2026-11-01)

**范围**：`git show aeedd05` 单笔（6 文件 +343 / −0）：`yate/commands.py` +31（`_cd` +
`_make_cd_completer` + 注册）· `yate/flows/document_flows.py` +18（`open_directory`）·
`tests/test_cmd_cd.py` +228（7 用例）· 双语手册各 +1 行 · 方案 `cd-command-plan.md` +64。
**框架**：`python-code-review` 六维度（正确性 / 安全 / 性能 / 风格 / 可维护性 / 异常处理）
＋ 本角色强制自我批判（登记见 §三）。
**结论**：REQUEST_CHANGES —— **0 blocker / 1 major / 7 minor**；六道门禁全绿（§四），
M1 修完即可合并。

### 一、发现清单（按严重度）

#### [major] M1 — `:cd` 不剥引号：引号包裹的合法目录被判为「不是目录」

- **位置**：`yate/commands.py:331-336`（`_cd`）；对照 `yate/commands.py:324-325`（`_edit`）。
- **证据**：
  - `yate/editor.py:1223-1231`：`run_command` 用 `text.split(maxsplit=1)` 切出命令名与
    参数后**原样** `entry.func(args)` 下发 —— 引号不会被框架剥离，只能由各命令自行处理。
  - 仓库内所有单路径命令都在第一行剥引号：`:e`（324-325）、`:saveas`（265-266）、
    `:split` / `:vsplit`（294-300）、`:install-extension` / `:uninstall-extension`
    （557-571）；`:diff` 的 usage 文案还直接教用户 `(quote paths with spaces)`（539-540）。
  - `tests/test_command_path_args.py:1-8` 的模块 docstring 把这条约定写成契约
    （"`_strip_quotes`（pair stripping for the single-path commands）"），并有
    `:e "..."` 含空格真实路径的 pilot 用例。
  - 本机实测：`Path(chr(34) + "C:/Program Files" + chr(34)).is_absolute()` → `False`，
    于是 `resolve_input_path` 走相对分支（`document_flows.py:130-133`）拼到 workspace root
    上，`is_dir()` 为假 → 告警文案变成 `not a directory: <root>\"C:\Program Files\"`。
- **影响**：Windows 上 `C:\Program Files`、`D:\My Docs` 一类目录，用户按 `:e` 的既有习惯
  加引号会被拒绝并看到拼接过 root 的怪异路径；`:cd "..."` 与 `:e "..."` 行为分裂。
  缓解：仅 warn，root 与文档状态不变，且不加引号时反而可正常工作 —— 故定 major 而非 blocker。
- **修法**：
  ```python
  def _cd(args: str) -> None:
      args = _strip_quotes(args.strip())
      if not args:
          ...
  ```
  并补一条 `fx.entry.func(f'"{sub}"')` → `root == sub` 的用例（现有 7 例均未覆盖引号形态）。

#### [minor] m1 — `:cd` 补全把**文件**也当候选

- **位置**：`yate/commands.py:243-252`；`yate/services/workspace.py:659-667`。
- **证据**：`path_matches` 只在 `entry.is_dir()` 时补尾 `/`（665），但**目录与文件都进结果**
  （666-667）；`_make_cd_completer` 直接复用该结果、不做目录过滤。`:cd` 只接受目录
  （`document_flows.py:299-301`），故 Tab 会把 `file.txt` 递进去，选中后必然得到
  「not a directory」。
- **测试盲区**：`tests/test_cmd_cd.py:205-228` 只造 `alpha` / `data` 两个目录，未造文件，
  断言无法暴露。
- **修法**：completer 内过滤（`if candidate.endswith("/")`）或给 `path_matches` 增加
  `dirs_only: bool = False` 形参（默认不变，`:e` / `:split` 零影响）；补「文件不出现在
  `:cd` 候选」用例。

#### [minor] m2 — `is_dir` 探测逻辑出现第三份副本

- **位置**：`yate/flows/document_flows.py:266-271`（`open_path`）、`294-298`（新增
  `open_directory`）、`312-317`（`open_path_async`）。
- **证据**：三段 `try: ...is_dir() / except OSError: is_dir = False` 逐字重复；
  `open_directory` 还先 `resolve_input_path`（294），随后在被它调用的 `open_path` 里
  二次 resolve（266）、二次探测（268）—— 正确但重复编排。
- **修法**：私有 `_probe_is_dir(self, path: Path) -> bool`（语义不变：探测失败按非目录），
  三处复用；`open_directory` 只保留门禁 + 转发。

#### [minor] m3 — 新增的 `except OSError` 分支零覆盖

- **位置**：`yate/flows/document_flows.py:297-298`。
- **证据**：§四 覆盖率原文把 `297-298` 列为 missing 行（本次新增代码中唯一未覆盖行；
  `_cd` 331-336 与 `_make_cd_completer` 234-253 全覆盖）。
- **修法**：`patch.object(Path("…"), "is_dir", side_effect=OSError)`（或 monkeypatch 目标实例）
  断言 warn 且 root 不变。

#### [minor] m4 — 无工作区根时 bare `:cd` 打印 `workspace root: None`

- **位置**：`yate/commands.py:334`；依据 `yate/editor.py:229-232`、`yate/services/workspace.py:127-128`。
- **证据**：`Workspace()` 允许 `root is None`，`editor.py:232` 注释明确「不带参数启动时
  workspace root is None」；此时 f-string 直接把 `None` 印到消息行。
- **修法**：`root if root is not None else "(none)"`（或退化为 cwd），并补一条 root 为 None 的用例。

#### [minor] m5 — 盘符形态两处不归一（分隔符混用 + 裸盘符被按「驱动相对路径」解析）

- **位置**：`yate/commands.py:249-251`。
- **证据 a（分隔符）**：`path_matches` 的目录候选恒用 `/`（`workspace.py:665`），盘符候选取
  `str(Path("C:\\"))` → `C:\`（实测 `str(Path("C:/"))` 为单个尾反斜杠）；同一候选列表混用两种分隔符。
- **证据 b（裸盘符）**：实测 `Path("D:").is_absolute()` → `False`，且
  `Path("root") / Path("D:")` → `Path("D:")`（drive-relative 丢弃左侧）。故 `:cd D:`
  （vim 用户自然写法）走 `resolve_input_path` 的相对分支，最终 `set_root` 解析到**该盘当前目录**
  而非盘符根。补全给的是 `D:\` 正确形态，实际踩中率低，故 minor。
- **修法**：候选形态统一（如 `drive.name + os.sep`）；`_cd` 对裸盘符（`len(args) == 2 and args[1] == ":"`）
  补尾分隔符，或在手册/命令描述里注明需写 `D:\`。

#### [minor] m6 — `test_cd_accepts_drive_root` 的 `list_drives` monkeypatch 是死设置

- **位置**：`tests/test_cmd_cd.py:150-151`。
- **证据**：执行链 `_cd`（`commands.py:331-336`）→ `open_directory` → `open_path`
  （`document_flows.py:264-302`）全程不调用 `list_drives()`；它只被 `_make_cd_completer`
  的闭包在**补全时**读取，而该用例不调用 completer —— monkeypatch 与断言
  `root == Path(anchor)` 无关。
- **修法**：删掉这两行；或把用例改成同时驱动 completer（与 m1 的新用例合并）。

#### [minor] m7 — 方案文档与实现不一致（实现是对的，文档会误导后续）

- **位置**：`.trae/documents/cd-command-plan.md:26-27`、`:32`。
- **证据**：方案写 `editor.documents.open_directory(...)`，`Editor` 上并无 `documents`
  属性（`editor.py:442` 声明的是 `document_flows: DocumentFlows`）；`:32` 写盘符候选
  `f"{d.path}{os.sep}"`，而 `str(Path("C:\\"))` 已带尾分隔符（实测），照抄会得到双分隔符。
- **结论**：实现两处都正确偏离方案（优点，见 §二），但留在仓库里的方案会误导同类改动；
  建议按实现同步并注明偏离原因。

### 二、契约与架构核对（通过项）

| 核对点 | 结论 | 依据 |
|---|---|---|
| `open_directory` 与 `open_path` 语义正交 | ✅ 只给目录分支加门禁：非目录 warn 且**不动 root**，`:e` 的「文件回落」路径不进入 `:cd` | `document_flows.py:286-302` vs `264-284` |
| 不重复编排 | ✅ 复用 `open_path` 的目录分支（`set_root` + `refresh_tree` + reveal + focus + 消息），未复制一套；仅探测逻辑重复（m2） | `document_flows.py:302` → `271-281` |
| 无参/有参分支 | ✅ 无参只报告不改状态；有参剥空白后转 L3（引号问题见 M1） | `commands.py:331-336` |
| 盘符尾分隔符契约 | ✅ `list_drives` 产出 `Path("C:\\")`（`workspace.py:584-586`），`str()` 自带尾分隔符，不再追加 → 无 `D:\\` 双分隔符 | `commands.py:246-251`；本机实测 `str` 形态 |
| 去重 | ✅ `candidate != prefix` 使「prefix 已是盘符根」时不自荐；跨源重复不可达（`path_matches` 恒补 `/`，永不产出 `D:\`） | `commands.py:250`；用例 `test_cmd_cd.py:226-228` |
| 属性名真实性（stub 是否掩盖） | ✅ 测试 stub 的 `document_flows` / `workspace.root` / `set_root` / `list_drives` / `message(text, kind=)` 均与真实编辑器一致 | `editor.py:442`（`document_flows`）、`editor.py:735`（`message` 签名）、`workspace.py:151,572` |
| L4→L0 依赖方向 | ✅ `commands.py` 只用既有 `path_matches` / `Workspace` 接口，无新 `editor_view` 依赖；`document_flows.py` 无新增 import | 架构守卫 37 用例通过（§四） |
| 并发安全 | ✅ `:cd` 同步走 UI 线程，与 `:e <目录>` 完全同路径（`open_path_async` 目录分支亦转同步 `open_path`）：无新增竞态、无 worker 生命周期变化 | `document_flows.py:304-319` |
| 性能 | ✅ 补全每次击键 `list_drives()` 26 次 `Path.exists()`（`workspace.py:584-587`，未缓存），与既有 `:e` 补全的目录扫描同量级，可接受 | 读码 + `list_drives` docstring |
| 双语手册一致性 | ✅ `manual.en.md:767` / `manual.zh.md:701` 一一对应，语义一致（含盘符根与无参行为） | 逐字比对 |
| 有意偏离（不作发现） | 📌 无参 `:cd` 在 vim 里回 `$HOME`、此处改为报告当前根：手册与命令描述两处均已声明，属文档化偏离 | `manual.*.md`、`commands.py:375` |
| 提交信息 / 方案先行 | ✅ `feat(commands): add :cd …` 符合 `git-commit-message`；`cd-command-plan.md` 在位，符合 `plan-before-execute` | `git show aeedd05` |

### 三、强制自我批判登记

| 条目 | 初判 | 复核实证（重读代码） | 结论 |
|---|---|---|---|
| M1 | major | `editor.py:1223-1231` 原文直传 + 6 处同类调用点约定 + `tests/test_command_path_args.py:1-8` 契约 + 本机探针 | **确认保留**（缓解存在但用户自然写法必踩、报错含拼接后怪路径，不足以降级） |
| m1 | minor | `workspace.py:659-667` 确证文件入列；`test_cmd_cd.py:205-228` 无文件候选 | 确认保留 |
| m2 | minor | 重读 266-271 / 294-298 / 312-317 三段逐字重复 | 确认保留 |
| m3 | minor | 覆盖率输出原文列出 `297-298` | 确认保留 |
| m4 | minor | `editor.py:232` 注释 + `workspace.py:127-128` | 确认保留 |
| m5 | minor | 探针两项（分隔符、`Path("D:")` 与拼接结果）均已实测 | 确认保留（两证据合并为一条） |
| m6 | minor | 重读 `_cd`→`open_directory`→`open_path` 链路，确认无 `list_drives` 调用 | 确认保留 |
| m7 | minor | `cd-command-plan.md:26-27,32` 对 `editor.py:442` 与 `str()` 实测 | 确认保留 |
| （初版）盘符候选未排序 | minor | `path_matches` 结果排序、盘符追加在尾；Tab 循环与分组显示无实证危害 | **删除**（风格挑剔、无实证） |
| （初版）`open_directory` 二次 resolve 属性能问题 | minor | 单次 `Path` 拼接，O(1)，无实测影响 | **删除**（并入 m2 的去重建议，不单列为性能项） |

**漏报自查**：正确性（无 blocker —— 目标路径全部经 `is_dir` 门禁、异常不外溢）、边界条件
（M1 引号 / m4 无根 / m5 裸盘符）、异常处理（m2 / m3 的 `OSError` 探测面）、并发（§二已核，
无新竞态）、性能（26 次 `exists()`，已判可接受）、类型（pyright 0，无缺口）、
测试覆盖（m3 + M1 / m1 的用例空档）—— 各维度均已覆盖，无重大遗漏。

### 四、门禁实测（本机亲自执行，退出码与数字均为原文）

| # | 命令 | 结果 | 退出码 |
|---|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pyright yate/flows/document_flows.py yate/commands.py tests/test_cmd_cd.py` | `0 errors, 0 warnings, 0 informations` | 0 |
| 2 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 全绿（本机 `-q` 无汇总行，按退出码判定；同批覆盖率运行给出 3300 passed / 10 skipped） | 0 |
| 3 | `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | **3300 passed / 10 skipped**；TOTAL 19209 stmts / 1112 missing / 6160 branches / 574 partial → **92.69%**（阈值 75 通过） | 0 |
| 4 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 37 用例全通过 | 0 |
| 5 | `.venv\Scripts\python.exe -m pytest tests/test_cmd_cd.py -q` | 7 passed | 0 |
| 6 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4 --quiet` | **121/121 scenarios、1463/1463 checks（100%）**，79.60 s | 0 |

**覆盖率口径**：全量分支覆盖率 92.69% 高于 75 门槛。本改动新增/修改代码的未覆盖行仅
`document_flows.py:297-298`（新增 `except OSError` 分支，见 m3）；`commands.py` 未覆盖行
（`66-67, 329, 366, 369, 401-405, 411-413, 432-439, 445-452, 477, 513, 531, 535-536, 551, 572-573, 600`）
均为存量行，与本次改动无关；`_cd`（331-336）与 `_make_cd_completer`（234-253）全覆盖。

### 五、合并建议

- **M1 必修**（一行改动 + 一条引号用例，见 §一）；**m1 / m3 建议同轮补**（同属本次新增
  代码的验收面：目录-only 候选、`OSError` 分支）；m2 / m4 / m5 / m6 / m7 可评估后置，但须
  登记（m7 建议随本次一并勘误，避免方案文档继续误导）。
- 结论：**REQUEST_CHANGES（1 major / 0 blocker）**；M1 修复后本笔可合并。
