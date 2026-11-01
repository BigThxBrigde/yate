# pr-review · `feat/file-manager` 合并前预评审 — 2026-11-01

**Overall: BLOCKED — 1 blocker / 1 major / 11 minor**

**模式**：`pr-review` skill 的 `review` 模式（AI pre-review + human decision，合流决策归人）。
**范围（Step 1）**：`git diff 630b7e6...HEAD`，23 笔提交 / 52 文件 / +6549 −198；
`630b7e6` 与本地 `master` 同位（当前无需 rebase）。工作树干净。
**噪声过滤**：无 `*.pyc` / lock / 二进制 / 纯重排 hunk——全部 52 文件均按内容评审
（`tools/changelog/zh_overrides.json` 只核对 zh 覆盖，不逐条读译文）。
**分支级视角**（区别于两轮过程评审）：提交序列完整性、跨提交回归、CHANGELOG / 双语指南
与代码一致性、与 master 合并的预期冲突面，均单列于 §五。
**既有评审基线**：`.trae/reviews/2026-10-31-file-manager.md`（1B/4M/6m 全闭环 + `:cd`
增量 0B/1M/7m 全闭环）。本次独立复核其闭环质量，并只报**过程评审未覆盖**的问题；
重复项一律不重提（见 §四 自我批判登记的「feedback loop」段）。

---

## 一、发现清单（按严重度）

### [blocker] B1 — `copy_entry` 把目录粘进自身子树 → `RecursionError` + 应用退出 + 磁盘垃圾树

- **位置**：`../../yate/services/workspace.py:478-492`（`copy_entry`，无自嵌套守卫）、
  `../../yate/editor_view/filemgr.py:865-888`（`action_paste`，`except (FileExistsError, OSError)` 在 883 行）。
- **问题**：`shutil.copytree` **没有** `_destinsrc` 自嵌套守卫（`shutil.move` 才有，
  实测 `inspect.getsource`：`copytree` 源码不含 `_destinsrc`）。当 `dest_dir` 位于 `src` 子树内时，
  `copytree` 逐层递归复制自己，直到 `RecursionError`；`RecursionError` 是 `RuntimeError`
  子类，**不在** `action_paste` 的捕获集合里，上抛到 Textual 消息泵。
- **实测证据**（本机亲跑，两条独立探针）：
  1. L0 直调：`Workspace(base).copy_entry(A, A/"sub")`（A 内含 sub）→
     `elapsed=0.45s / error=RecursionError: maximum recursion depth exceeded /
     created_paths=500 / max_depth=499`（500 层垃圾树留在用户目录里）。
  2. 端到端 pilot（真屏 + `y` `l` `l` `p` 四键，脚本放 %TEMP%，不落仓库）：
     `RecursionError`、`app exception: RecursionError`、`return_code: 1`、
     `paths left on disk: 489`。`App._handle_exception` 的 docstring 原文为
     "Always results in the app exiting"（`textual/app.py:3263-3283`）——即**应用退出**。
- **可达路径**：光标停在目录 `A` → `y`（复制）→ `l` 进入 `A` → `l` 进入 `A/sub` →
  `p`。四键，全在正常键位内；属于用户点错目标的常见误操作。
- **对照**：剪切同场景被 `shutil.move` 的 `Error("Cannot move a directory ... into itself")`
  挡住（`Error` ⊂ `OSError` → 被捕获 → 输入行报 `paste failed:`）。只有**复制**缺少守卫。
- **修法**（`workspace.py`，`FileExistsError` 检查之前）：
  ```python
  target = dest_dir / src.name
  if src.is_dir():
      try:
          target.resolve().relative_to(src.resolve())
      except ValueError:
          pass
      else:
          # OSError, not ValueError: the screen's paste handler catches
          # (FileExistsError, OSError) and reports on the input line.
          raise OSError(f"cannot copy {src.name} into itself")
  if target.exists():
      raise FileExistsError(f"{target.name} already exists")
  ```
  并补两条用例：目录 → 自身子树（断言 `OSError`、源树未被改动、**无残留新目录**）、
  剪切同场景（断言 `paste failed:` 文案，锁定既有 `shutil.Error` 行为）。

### [major] M1 — POSIX 上文件系统根会进入**空盘符层死胡同**（`h` / `--file-manager /`）

- **位置**：`../../yate/editor_view/filemgr.py:163-167`（`__init__` 起始态）、
  `../../yate/editor_view/filemgr.py:713-730`（`action_up`）、
  `../../yate/editor_view/filemgr.py:271-290`（`_reload` 对 `_cwd is None` 走 `list_drives()`）、
  `../../yate/services/workspace.py:572-587`（`list_drives` 在非 win32 恒返回 `[]`）。
- **问题**：盘符层被建模为 `_cwd is None`，而该层的**唯一**内容来源是
  `Workspace.list_drives()`——POSIX 上恒为空。于是：
  - 在 `/` 按 `h`（或 `Left` / `Backspace`）→ `_cwd = None` → 中栏空列表，左栏
    `(no parent directory)`；
  - 该状态下 `action_up` 首行 `if self._cwd is None: return`、`action_open` 因
    `_cursor_entry()` 为 `None` 直接返回、`action_refresh` / `action_cycle_sort` 只重列同样的空列表
    → **无法回到 `/`，只能 `q` / `Esc` 关屏**；
  - 启动形态同样中招：`yate --file-manager /` 直接进空屏（`initial_dir` 为根时同样落到 `_cwd=None`）。
- **实测证据**（pilot 探针，`Workspace` 子类令 `list_drives()` 返回 `[]`，等价 POSIX 分支，
  起始目录为文件系统根）：
  `initial cwd: None / entries: []`；随后 `h` / `l` / `j` / `r` 逐键后仍为
  `cwd=None entries=0`——四键全无效。
- **影响面**：Gitee Go 流水线是 Linux 腿（`.workflow/test.yml`），Linux 用户完全可达；
  现有 Windows-only 用例（`tests/test_filemgr.py:818-849`）在 POSIX 上 skip，覆盖不到。
- **修法**：空盘符层不应存在，两处入口都加判据：
  ```python
  # __init__
  start = (initial_dir or root or Path.cwd()).resolve()
  at_root = start.parent == start
  self._cwd: Path | None = None if at_root and workspace.list_drives() else start

  # action_up
  if self._cwd.parent == self._cwd:
      if not self.workspace.list_drives():
          return  # POSIX: no drive level, stay at the file-system root
      self._cwd = None
      self._reload()
      return
  ```
  补一条 POSIX 用例（`monkeypatch.setattr(Workspace, "list_drives", lambda self: [])`，
  在根按 `h` 断言 `_cwd` 不变、仍列出根目录内容）。若产品裁定 POSIX 不提供盘符层，
  须在 `file-manager.zh/en.md` §1 与 §3 明示。

### [minor] m1 — `:cd` 补全的「目录过滤」字面量写错：`"\""` 实为**双引号**，不是反斜杠

- **位置**：`../../yate/commands.py:245-248`（注释 245-247 + 语句 248）。
- **问题**：`dirs = [c for c in matches if c.endswith(("/", "\""))]`——第二个元素是
  `"`（一个双引号字符），源码里应为 `"\\"`。实测 `repr` 该行：
  `'... if c.endswith(("/", "\\""))]'`。后果：
  1. 注释「drive roots keep `os.sep`」不成立——`path_matches` 的目录候选**恒以 `/` 结尾**
     （`workspace.py:664-665`），盘符候选由后面的循环单独追加，所以这段 `"\""` 在现数据流里是死分支；
  2. 反向误放行：POSIX 上文件名以 `"` 结尾时会被当成目录候选。
- **修法**：
  ```python
  # ``path_matches`` marks every directory candidate with a trailing "/"
  # on every platform; files never carry it.
  dirs = [c for c in matches if c.endswith("/")]
  ```

### [minor] m2 — m1 的回归用例是**空转**的：文件在候选算完之后才创建

- **位置**：`../../tests/test_cmd_cd.py:264-274`。
- **问题**：`empty = completer("")` / `partial = completer("d")` 在 264-266 行**先**求值，
  `afile.txt` 在 268 行才 `write_text`，273-274 行却断言 `"afile.txt" not in empty`。
  由于候选是立即求值的 `list`，该断言恒真——`986b6ad` 修 m1 引入的目录过滤**从未被验证**。
- **实测**：`path_matches("", Workspace(tmp))` 在文件存在时返回
  `['afile.txt', 'alpha/']`（本机探针），说明只要顺序正确，这条断言本可抓住缺陷
  （也能抓住 m1 的字面量错误）。
- **修法**：把 `write_text` 提到 264 行之前，并顺带断言 `"afile.txt" not in completer("a")`。

### [minor] m3 — Q4 改造后遗留的死分支：`parent_and_siblings` 的盘符层分支不可达

- **位置**：`../../yate/editor_view/filemgr_model.py:233-248`（根分支 244-247）、
  唯一调用点 `../../yate/editor_view/filemgr.py:363-366`（前置守卫 `self._cwd.parent == self._cwd`）。
- **问题**：`_render_parent` 只在 `_cwd` 非空且**不是**根时调用该函数，故函数内
  `if current.parent == current:` 分支（含 `list_drives()` 调用与 `None` 返回）
  在生产路径上**永不执行**；`tests/test_filemgr_model.py:212-234` 仍在断言这段死行为
  （monkeypatch `sys.platform` 后断言返回盘符条目），给出「左栏承载盘符层」的错误保证。
- **修法**：删掉该分支（及死假设用例），`parent_and_siblings` 收敛为
  「返回 `(current.parent, list_dir(current.parent))`」；若保留则必须让
  `_render_parent` 的守卫改回委托（当前 Q4 终裁是盘符在中栏，故应删除）。

### [minor] m4 — 双语指南 §1 把盘符层写在**左栏**，与实现和测试相反

- **位置**：`../../yate/docs/file-manager.zh.md:16-17`、`../../yate/docs/file-manager.en.md:18-21`。
- **问题**：两份指南均称「到达文件系统根后，**父目录栏**变为盘符虚拟层」。实际实现
  （Q4 执行期终裁）是**中栏**列出盘符、左栏显示 `(no parent directory)`——
  `tests/test_filemgr.py:831-834` 正是这样断言的。指南还因此从未说明「根层按 `h` 进盘符层」
  这一 Q4 主功能，Windows 用户只能靠试键发现。
- **修法**：§1 改为「中栏列出盘符（左栏占位 `(no parent directory)`）」，并在 §3 导航表
  `h/Left/Backspace` 行补「在文件系统根进入盘符层（Windows）」。

### [minor] m5 — 预览「文本装配」在 palette 与 filemgr 逐字重复（抽取只做了一半）

- **位置**：`../../yate/editor_view/palette.py:399-423` 与 `../../yate/editor_view/filemgr.py:461-480`。
- **问题**：plan-b 把 IO / tokenize / cache 抽到 `preview.py`，但 Rich Text 装配
  （token 列钳制、gap 填充、`… truncated at N lines` 文案）仍是两份**逐字相同**的副本，
  连 docstring 都近似。任一侧的钳制修复都必须手工复制到另一侧。
- **修法**：在 `preview.py` 增纯函数
  `def preview_text(data: PreviewData, t: Theme, max_lines: int) -> Text`，
  两屏各自 `pane.write(preview_text(data, theme.active(), self.preview.max_lines))`；
  `tests/test_palette_preview.py` 已有装配断言，可平移到新函数。

### [minor] m6 — `--file-manager` 的 CLI 校验缺口：非目录路径静默空屏 + 与 `--diff`/`--hex` 未互斥

- **位置**：`../../yate/flows/filemanager_flows.py:99-103`（只判 `initial_dir.exists()`）、
  `../../yate/cli.py:283-291`（只判与位置参数互斥）。
- **问题**：
  1. `yate --file-manager somefile.txt`：`exists()` 为真 → 屏幕把 `_cwd` 设为该文件路径 →
     `Workspace.list_dir` 的 `except (PermissionError, OSError)` 吞掉 `NotADirectoryError`
     （`workspace.py:283-291`）→ 中栏空列表、左栏是其父目录的正常列表，无任何提示。
  2. `yate --file-manager --diff a b` / `--file-manager --hex x`：`_validate_diff_args` /
     `_validate_hex_args` 彼此的互斥矩阵没有把新旗标纳入，两个屏幕都会经
     `call_after_refresh` 入栈，结果取决于入栈顺序。
- **修法**：`open_fullscreen` 改 `_probe_is_dir` 语义的判定（`try: initial_dir.is_dir()`），
  非目录时 `self._message(f"not a directory: {initial_dir}", "error")` 并返回；
  `_validate_file_manager_args` 补 `if args.diff_files: parser.error(...)` /
  `if args.hex_file: parser.error(...)`，与既有 argparse 口径一致（exit 2）。

### [minor] m7 — 应用内手册：新命令与新键位双缺（而同一批的 `:cd` 入表了）

- **位置**：`../../yate/resources/manual.zh.md:701` 附近（命令表）、`:432` 附近（键位表）；
  `../../yate/resources/manual.en.md:767` 附近。
- **问题**：本分支给命令表加了 `:cd` 行，但 `:file-manager` 不在命令表、
  `Alt+Shift+F` 不在键位表，全文亦无「文件管理器」词条（grep 0 命中）。
  `:project-replace` / `:trust` / `:palette` 等同类命令都在表内，故这是同批改动的内部不一致；
  用户唯一发现途径是键位表/which-key 之外的偶然尝试。
- **修法**：命令表补
  `` | `:file-manager` | — | open the lf-style file manager overlay (Alt+Shift+F) | ``（zh 同步），
  键位表补 `Alt+Shift+F` 行。

### [minor] m8 — `alt+shift+f` 直调 flows，绕过 action 注册（与 `alt+shift+s` 先例不一致）

- **位置**：`../../yate/editor.py:896-901`；对照 `:893-895`（`alt+shift+s` → `execute_action`）。
- **问题**：`actions.py:218-219` 注册了 `file_manager` 动作、两套键位表也都绑了
  `<alt-shift-f>` → `file_manager`，但真实派发点在 `handle_key` 里直接调
  `self.filemanager_flows.open_overlay()`，于是动作注册与键位表对该和弦只剩「帮助展示」作用；
  扩展若重绑/包装 `file_manager` 动作（`ActionRegistry` 的公开面）不会生效。
- **修法**：`self.execute_action("file_manager")`（与 `toggle_screensaver` 同形，一行改动）。

### [minor] m9 — `is_mounted` 守卫是**空操作**：Textual 从不清零该标志

- **位置**：`../../yate/editor_view/filemgr.py:443`（`_load_preview_worker`）、
  同文件 `:219-222`（`_wire_mount` docstring 已把这一点写对）；`../../yate/editor_view/palette.py:227,382` 同形。
- **问题**：`Widget.is_mounted` 返回 `self._is_mounted`；Textual 8.2.8 只在挂载成功处置
  `True`（`textual/message_pump.py:612,668`），**没有任何一处复位为 `False`**——本分支
  `_wire_mount` 的 docstring 明确记录了同一事实。因此 `if not self.is_mounted: return`
  永不触发，docstring「关闭后不再绘制」的保护实际来自
  `Widget._on_unmount → workers.cancel_node(self)`（`textual/widget.py:4849-4851`）。
  当前无害（worker 被取消），但下次照抄这段「保护」就会误以为已防住卸载后回调。
- **修法**：改用 `if not self.is_attached: return`（`_wire_mount` 用的正是该判据），或删掉守卫并把
  docstring 改成「卸载即取消 worker，无需自查」。

### [minor] m10 — 中栏 `nav()` 重映射零用例：防吞键机制没有任何守卫

- **位置**：`../../yate/editor_view/filemgr.py:95-121`（`_FileListView.action_nav` 的 6 路分派）、
  `../../yate/editor_view/filemgr_keys.py:57-64`（`LIST_BINDINGS`）。
- **问题**：专项覆盖率实测 `filemgr.py` **87%（546 stmts / 49 missing）**，缺行含
  `109-121`——即 `left` / `right` / `home` / `end` / `pageup` / `pagedown` 到屏幕动作的**全部**
  分派体。现有用例只按 `j`/`k`/`l`/`h`/`gg`。该类 docstring 自述这段代码的存在理由
  正是「`ScrollableContainer` 会吞掉这些键」，属规则 §五「按键分支只消费自己真正处理的键」
  的同族风险，却无回归面。
- **修法**：在 `tests/test_filemgr.py` 补一条 pilot：`right` 进目录、`left` 回父目录、
  `pagedown`/`pageup` 移动光标、`home`/`end` 到首末行。

### [minor] m11 — 目录预览每次光标移动都从零 `list_dir`（与已登记的 M3 延迟项相邻）

- **位置**：`../../yate/editor_view/filemgr.py:389-438`（`_refresh_preview` →
  `_render_dir_preview`），触发点 `:559-564`（`ListView.Highlighted`）。
- **问题**：光标每次落到目录项，都会在 UI 线程对**被高亮目录**做一次完整
  `list_dir`（`iterdir` + 每子项 `is_dir()` stat + 排序），随后才切前 100 条渲染。
  在含数千子项的大目录里，连续 `j`/`k` 就是每键一次全量 scandir+stat+sort。
  过程评审的 M3 只覆盖 `_reload` / `_refilter` 的列表侧，未含本路径；方案 §二 的
  P2 延迟项写的是「中栏万级条目增量刷新」，此路径属于同一立项的漏登部分。
- **修法**：用 `(path, mtime_ns)` 记忆化目录预览（`_dir_preview_cache`，`r` 时清空），
  或先 `os.scandir` 取前 `_DIR_PREVIEW_CAP` 条即渲染（排序可退化为 `scandir` 顺序）。

---

## 二、六维度核对（逐项过，只列结论与依据）

| 维度 | 结论 | 依据 |
|---|---|---|
| 1 功能正确性 | B1 / M1 两处实证缺陷；其余主路径与 Q1/Q2/Q3/Q4 裁决一致 | Q1 dirty 门禁 `filemanager_flows.py:213-217` 现算 `doc.modified` 并拒切；Q2 `sorted(self._marked)` + 仅进首个目录 `:180-190`；Q3 dismiss-then-callback 顺序 `filemgr.py:743-753` 与 `Screen.dismiss` 同步出栈一致 |
| 1b 边界条件 | 空目录 / 根层 / 盘符 / 未保存缓冲 / 多选集合均已核；**根层 POSIX = M1**；`rename`/`delete` 对文件系统根有显式 guard（`filemgr.py:837-838,844-845`） | 逐路径读码 + 两条 pilot 探针 |
| 2 安全 | 无新增注入面：无 shell、无 `eval`/`pickle`；文件名经 `validate_name` 拦 `/` `\` `:`（`workspace.py:429-442`）；`copy/move` 目标名取自已存在条目；路径来自用户输入但只做文件系统操作 | `subprocess`/`eval` 全 diff 零命中 |
| 3 性能 | m11 一处；其余与已登记延迟项（M3 全量版：目录级增量 stat）重合，不重复计 | `_child_counts` 已改 `setdefault` 缓存（`filemgr.py:316-318`）、`_refilter` 已免二次 stat（`:292-305`），上次评审 M3 的轻量修法确已落地 |
| 4 可维护性 | m5 重复实现、m9 空守卫；其余符合 `python-coding-style` §五（`from __future__` 齐备、PEP 695 `type` 别名、`X | None`、惰性 `%` 日志、无裸 `except`、绝对导入、行宽 ≤100） | pyright strict 0 诊断；`ruff`-口径人工抽查无命中 |
| 5 架构边界 | 全绿：R3（`filemgr.py` 只收 `Workspace`/`FilePreviewConfig`/回调，无 `yate.editor`/`yate.app` 导入）、R11（`UI_FROZEN_FILES["flows/filemanager_flows.py"]` 三条与实际 import 一一对应）、R12（模块级 tracing、无 `self.log`）、R13/R15（`theme.attach` 自持 + 三栏 `apply_slim_scrollbars`/`apply_scrollbar_theme`）、R9 无关（组件自持 tcss，文件头已声明 selector 归本组件）、flows 不持 App 句柄（`exit` 经 `bind_exit` 晚绑定）、无新 `Protocol`/`TYPE_CHECKING`/`Any` | 架构 37 用例通过；`filemgr.py` 888 行（`splitlines` 实测）与 `SIZE_EXEMPT_FILES` + 规则 §三.7 登记**逐字一致** |
| 6 硬门禁 | 五项全绿（§三） | 本机亲跑，退出码原文 |

---

## 三、门禁实测（本机亲自执行，2026-11-01，数字与退出码均为原文）

| # | 命令 | 结果 | 退出码 |
|---|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | `0 errors, 0 warnings, 0 informations` | 0 |
| 2 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | 全绿（`-q` 本机无汇总行，按退出码判定） | 0 |
| 3 | `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch --cov-fail-under=75 -n auto` | `3304 passed, 10 skipped in 251.06s`；TOTAL 19207 stmts / 1107 missing / 6162 branches / 575 partial → **92.71%**（阈值 75） | 0 |
| 4 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 37 用例全通过 | 0 |
| 5 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4 --quiet` | **121/121 scenarios / 1463/1463 checks（100%）**，83.44 s | 0 |
| 附 | `.venv\Scripts\python.exe -m tools.changelog check` | `released changelog sections are up to date`；unreleased 仅「lags 1 commit」（生成型提交自身，正常） | 0 |

**新增代码覆盖（专项用例子集口径，7 个 filemgr/cd 测试文件一次跑）**：

| 文件 | 语句 | 缺失 | 分支 | 部分 | 覆盖率 | 未覆盖行（摘要） |
|---|---|---|---|---|---|---|
| `editor_view/filemgr.py` | 546 | 49 | 162 | 30 | **87%** | `109-121`（nav 重映射全分派，见 m10）、`640-666`（rename/delete 取消与错误分支）、`694`（空列表 `G`）、`709`（半页早退）、`721`（盘符层 `h` 早退，见 M1）、`742/862/875`（`open`/`clip`/`paste` 早退）、`806-808`（清过滤） |
| `editor_view/filemgr_model.py` | 99 | 0 | 30 | 1 | **99%** | `171->173`（`stat is None` 分支） |
| `editor_view/preview.py` | 89 | 4 | 10 | 0 | **96%** | `114-115`（读失败降级）、`166`（`items()`）、`197`（`clear()`） |
| `editor_view/filemgr_keys.py` | 6 | 0 | 0 | 0 | **100%** | — |

全量 92.71% 与上一轮 92.45% / 92.69% 同量级，无下降；缺口集中在 `filemgr.py` 的
键位分派与错误分支（m10 / M4 后续）。

---

## 四、强制自我批判登记

### 4.1 逐条反证与结论

| 条目 | 复核实证（重新读码 / 实测） | 结论 |
|---|---|---|
| B1 | `inspect.getsource(shutil.copytree)` 实测无 `_destinsrc`；L0 探针 500 层 + `RecursionError`；pilot 端到端 `return_code 1` + 489 条残留；`recursion` 属 `RuntimeError`，确认不被 `except (FileExistsError, OSError)` 捕获；`App._handle_exception` docstring「Always results in the app exiting」 | **确认保留（blocker）** |
| M1 | pilot 探针：起始根 → `_cwd=None`、`entries=[]`，`h`/`l`/`j`/`r` 全部无效；`action_up` 首行早退、`action_open` 因无条目早退；`list_drives` 的 POSIX 分支返回 `[]` | **确认保留（major）**：初判曾考虑 minor（「只是空屏，Esc 可退」），因「进入后无任何键可恢复 + 启动形态同样中招 + CI Linux 腿可达」维持 major |
| m1 | `repr` 行原文确认第二元素是 `"`；`path_matches` 目录候选恒补 `/`（`workspace.py:664-665`） | 确认保留 |
| m2 | 读测试：264/266 求值、268 建文件、274 断言；`path_matches("")` 探针返回含文件 | 确认保留（且它正是 m1 未被抓住的原因） |
| m3 | 唯一调用点前置守卫 `_cwd.parent == _cwd` 已排除根分支 → 分支不可达；死假设用例在位 | 确认保留 |
| m4 | 指南原文 vs `tests/test_filemgr.py:831-834` 断言（左栏 `(no parent directory)`、盘符在中栏） | 确认保留 |
| m5 | 两段 20 行代码逐字比对 | 确认保留（可维护性，MINOR） |
| m6 | `exists()` vs `is_dir()`；`list_dir` 吞 `NotADirectoryError`；`_validate_*` 三函数对照 | 确认保留（两项合并为一条，避免噪声） |
| m7 | manual 双语 grep：`file-manager` 0 命中；`:project-replace`/`:trust`/`:files`/`:palette` 均在表内 | 确认保留 |
| m8 | `editor.py:893-895` vs `:896-901` 两种写法并存；`actions.py` 已注册同名动作 | 确认保留 |
| m9 | `message_pump.py:612,668` 只有置 `True`；全仓无复位点；本分支 docstring 自证；`widget.py:4849-4851` 才是真实保护 | 确认保留（**但**初判的「卸载后回调会 `NoMatches` 崩溃」**已删除**，见 4.2） |
| m10 | 覆盖率原文列 `109-121` 缺失；现有用例只按字母键 | 确认保留 |
| m11 | `_refresh_preview` → `_render_dir_preview` 每次 highlight 全量 `list_dir`；方案 P2 延迟项未含本路径 | 确认保留（MINOR，与已登记延迟项相邻，不计为新的 major 性能项） |

### 4.2 误报剔除与降级（初版有、最终删除）

| 初版候选 | 处置 | 理由（实证） |
|---|---|---|
| 预览 worker 卸载后 `query_one` 抛 `NoMatches` → 真崩溃 | **删除** | `Widget._on_unmount` 调 `workers.cancel_node(self)`（`textual/widget.py:4849-4851`），`await` 处即取消，await 之后的 `_cursor_entry()` 永不执行；`is_mounted` 守卫才是空操作（保留为 m9，等级从 major 降为 minor） |
| `action_mark` 在列表重建窗口内可能 `IndexError`（`self._entries[index]` 无上界检查） | **删除** | `ListView.clear()` 显式 `self.index = None`（`textual/widgets/_list_view.py:261-270`），`validate_index` 再做区间钳制；`action_mark` 对 `None` 已早退，窗口内不可达 |
| `_reload` / `_refilter` 每击键对全条目 `stat_entry`（性能 major） | **不重提**（feedback loop） | 过程评审 M3 已裁决「P0 只修过滤路径缓存，目录级增量 stat 另行立项」，方案 §二 已登记；本轮未发现新证据推翻该裁决。仅保留**新路径** m11 |
| `list_drives()` 26 次 `Path.exists()` 每次 reload 阻塞 UI | **不重提** | 上一轮已判「非每次 reload；无实测成本证据」；本轮未产生新实测（无断连网络盘可测），按「无实证不留断言」删 |
| `_preview_text` 的 `zip(lines, tokens)` 可能静默丢行 | **删除** | `tokenize_document` 契约「one token list per input line」（`editor_syntax/engine.py:45-49,116-121`），失败路径补 `[[] for _ in lines]` 对齐，长度恒等 |
| `Workspace.remove_entry` 内重复 `import shutil`（模块顶部已导入） | **删除** | 事实成立但纯风格 Nit，价值低于噪声成本 |
| `_wire_mount` 的重试无上限，可能无限自调度 | **删除** | 屏幕卸载后 `call_after_refresh` 投递的对象已停止泵消息，无「活循环」证据；属推测 |
| 文档与实现的三处（缓存共享 / 跨卷拒绝 / 冲突确认）不一致 | **不重提** | 过程评审 m4 已修并复核：`file-manager.zh.md:129,144-145,92` 现与实现一致（本屏独立 16 条缓存、跨卷透明、冲突报 `paste failed:`） |

### 4.3 漏报自查（反向扫六个维度）

- 正确性：逐 action 走读（`action_open/up/escape/refresh/paste/mark/invert/rename/delete/
  new_file/new_dir/cycle_sort/toggle_hidden/half_page`）后补入 B1（`paste` 复制臂）与 M1（`up` 根层）。
- 边界：空目录 / 根层 / 盘符 / 未保存 / 多选 / 名称校验 / 冲突 / 跨卷 全部过；补入 m6（非目录启动路径）。
- 异常处理：全部 `except` 分支逐一对照调用方能捕获的类型，**B1 即由此发现**（`RecursionError` 不在集合内）。
- 并发：`run_worker(exclusive=True, group=...)` + 卸载取消 + `partial` 协程（未启动不泄漏）已核；
  无新增竞态（`_wire_mount` 的 `is_attached` 守卫是上一轮 B1 的正确修法，本轮复核成立）。
- 性能：新增路径仅 m11；`list_dir`/`stat_entry` 的既有成本归 M3 裁决。
- 类型与测试覆盖：pyright 0；覆盖率缺口按文件列出（§三），补入 m10（nav 分派零覆盖）与 m2（空转用例）。

### 4.4 Step 5 feedback loop（与既有评审的关系）

- 上一轮 §二.6 把「预览 worker 的 `is_mounted` 复核」列为**通过项**；本轮以 Textual 源码 +
  本分支自己的 docstring 证伪，按 skill Step 5「有新证据才可重提」把它转为 m9（并附带删除其可能后果）。
- 上一轮 M4（paste 零用例）已闭环：`tests/test_filemgr.py:563-700+` 新增 4 条 paste 用例，
  但**未覆盖**「目录 → 自身子树」这条破坏性分支 → 这正是 B1 逃逸的测试面缺口，
  按「验收失败先追问覆盖了什么行为」记入 B1 的修法要求。
- `:cd` 增量的 m1（补全含文件候选）在 `986b6ad` 声称修复，实测**修复本身带字面量错误
  且回归用例空转**（m1 + m2）——复核闭环质量时按「先红后绿」未做到处理。

---

## 五、分支级观察（合并视角，非缺陷）

1. **提交序列**：23 笔，语义分层清晰（plan-a…g → 接线 → F1/F2 修复波 → `:cd` → changelog），
   每笔单一职责；`fix`/`feat`/`docs`/`test`/`refactor`/`chore` 类型前缀与
   `git-commit-message.md` 一致；无 `wip`/`fixup`/`tmp` 残留；无 `.pyc`、无本机家目录路径
   （守卫 #36 通过）。
2. **跨提交回归**：`palette.py` 的抽取（07c982a）由 `tests/test_palette_preview.py`（+124 行）
   兜底，全量绿；`document_flows._probe_is_dir` 的提取对 `open_path` / `open_path_async`
   行为等价（同一实现，仅去重）。
3. **合并预期冲突面**：`CHANGELOG.md` / `CHANGELOG.zh.md` / `yate/resources/changelog.{en,zh}.md`
   （生成型，双方都改 Unreleased）+ `.trae/reviews/README.md`（同表尾部追加）。
   建议合并时对 changelog 四文件整体**取本分支版本再跑 `python -m tools.changelog generate`**，
   索引表按日期重排一次（README 自身已登记编号分歧先例）。
4. **`zh_overrides` 覆盖**：本分支 20 笔产品/文档提交均有 zh override（`986b6ad`/`aeedd05`/
   `9acd2dc` 等在位）；`check` 报 62 条 unreleased 缺 zh，全为 master 存量，非本分支引入。
5. **与 master 的语义交互**：`--file-manager` 与 `--diff`/`--hex` 的互斥缺口（m6）在合并后
   同样存在，非冲突性；`Workspace` 新增方法为纯追加，explorer 主路径零改动（`list_dir`
   未加 stat），无对外 API 破坏。

---

## 六、处置建议（三档）

**1. Must be done before merge**

- **B1**（`copy_entry` 自嵌套守卫 + 2 条回归用例）：应用退出 + 用户目录残留 500 层垃圾树，
  属「常规使用即崩溃」，且合并后无回滚余地（数据已落盘）。
- **M1**（POSIX 空盘符层）：一行判据即可修；若不修，须在指南与 `action_up` docstring
  同步声明「盘符层仅 Windows 存在」，否则 Linux 用户进入的是**不可恢复**状态。

**2. Should be done in this PR**

- **m2**（空转用例）与 **m1**（字面量错误）：同一处，先改测试顺序（应变红）再修实现，
  按项目「先红后绿」口径留下证据。
- **m3 + m4**（Q4 残留四面：死分支 / 死假设用例 / 双语指南 §1 / 导航表缺 `h` 进盘符层）：
  用户可见的文档错误与误导性测试，与本分支自己的验收清单直接冲突。
- **m6**（CLI 校验缺口）：与既有两个旗标的校验口径对齐，改动小、可测。
- **m7**（手册补两行）：与同批 `:cd` 入表保持一致。

**3. Can be deferred（建议登记后另案）**

- **m5**（预览装配去重）、**m9**（`is_mounted` → `is_attached`，注意 `palette.py` 两处同形）、
  **m8**（改走 `execute_action`）、**m10**（nav 分派补 pilot 用例）、
  **m11**（目录预览记忆化，并入已登记的「中栏万级条目增量刷新」立项）。

---

## 七、Strengths

1. **分层落点干净**：L2 `FileManagerScreen` 只吃 `Workspace` / `FilePreviewConfig` 与 6 个回调，
   编排全在 L3 `FileManagerFlows`；`exit` 端点经 `bind_exit` 晚绑定对齐 `bind_hex_opener`
   先例，`_build_pane_stack` 组装顺序在 `Editor.__init__` 注释里可追（R3/R11/§三.8 逐条成立）。
2. **复用而非复制（做对的一半）**：`preview.py` 把 palette 的 worker/cache/坏文件降级
   抽成单一管线，`PreviewCache` 的 `(mtime_ns, size)` 复验 + FIFO 淘汰是教科书式实现；
   m5 只是把最后 20 行装配也收进去的一步之遥。
3. **破坏性操作有显式确认语义**：`d` 需输 `y`、目录额外标注 `(recursive)`，
   rename/delete 之后经回调同步 `session.retarget` / `close_under` + `refresh_tree`，
   与 explorer 既有语义一致（上一轮 M2 的修法到位）。
4. **不静默丢弃**：Q1 的 dirty 门禁在切换前现算 `doc.modified` 并整体拒绝，
   浮层/全屏两形态同一条路径，`_switch_workspace` 的 `close_active` 循环有终止性论证。
5. **测试风格克制**：新增 1800+ 行用例全部轮询 `conftest.wait_until`、零真实
   `sleep`；双击窗口与 `g` 前缀超时按**消费模块**打补丁；冒烟新增 `--file-manager`
   端到端场景（121/121）填补了上一轮 m6 的空白。
6. **门禁纪律**：五项本机实测全绿（pyright 0 / 3304 passed / 架构 37 / 92.71% / 冒烟 1463 checks），
   B1 与 M1 均**不是**门禁可拦截类（缺用例而非红门），说明本次评审的信息增量来自读码 + 探针，
   而非跑数。
