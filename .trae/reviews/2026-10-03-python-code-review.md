# 全量 Python 代码评审（python-code-review 技能）— 2026-10-03

- **评审对象**：master `2c124a7` 全仓 Python 代码（`yate/` 113 文件、`tools/` 44 文件、`tests/` 57 文件、`pack/` 2 个 spec）。
- **评审方法**：按 `.trae/skills/python-code-review/SKILL.md` 六维度框架（正确性 / 安全 / 性能 / Pythonic / 可维护性 / 错误处理），7 个只读评审子代理按互不重叠模块切分并行执行（A 核心 L4/L1、B 调度 L3、C editor_view、D editor_core+lsp+syntax、E editor_term+keyproto+sprites、F tools、G services+keymaps+extensions+pack、H1/H2 tests 前后半），主代理汇总并逐条核实处置。
- **基线门禁**（worktree `fix/python-code-review` 实测）：`python -m pyright yate/ tests/ tools/` → 0 errors, 0 warnings；`python -m pytest tests/ -q` → 全部通过。
- **总体结论**：`MINOR ISSUES` — 0 CRITICAL / 15 WARNING / 68 SUGGESTION，共 83 项（编号 R-01…R-83）。架构约束专项核查全部通过（无越层导入、无 Protocol/TYPE_CHECKING、无类级滚动条 patch、日志全部惰性 `%` 占位、无 `self.log`/`self.app.log`）。
- **处置**：修复方案见 [`../documents/python-code-review-fixes-plan.md`](../documents/python-code-review-fixes-plan.md)（2026-10-03 用户指令：全部登记项均尝试修复，仅核实后确实无法修复的保留记录）。

---

## A. 核心模块（app / cli / config / logs / session / dist_meta）

**R-01 [WARNING] `yate/dist_meta.py:36-38` — `requirement_groups()` 未处理 `PackageNotFoundError`**
问题：docstring 承诺发行版缺失时返回 `{}`，但 `importlib.metadata.requires()` 在发行版未安装时抛 `PackageNotFoundError`（仅"已安装但无依赖"才返回 `None`）。从源码树直接运行 `python -m yate`（未 pip install）时 `yate --diag` 的 `diagnostics.py:432` 无保护调用即崩溃；同文件其它元数据查询均有 try/except 保护，唯此处遗漏。
修复：`requires()` 调用包 `except PackageNotFoundError: return {}`，并同步修正 docstring 表述。

**R-02 [SUGGESTION] `yate/config.py:299-411` — `_extract_extensions` 与 `_extract_theme_dirs` 近乎逐字重复**
问题：两个 ~45 行函数仅选项名与错误文案不同，后续同类选项会出现第三份拷贝。
修复：提取共享 `_extract_path_list(...)` 帮助函数，两个包装只留选项名与错误前缀。

**R-03 [SUGGESTION] `yate/config.py:268-291` — 失败 rc 文件"出错前已执行"的赋值仍生效，语义未文档化**
问题：所有 rc 文件共享 namespace，标量选项统一跑完后提取；某文件先 `tab_width = 2` 后某行抛异常，该值已生效——"半应用"状态与"problems are collected"的直觉相悖。
修复：在 `load_config` docstring 中明确该语义（选轻量方案，不改执行模型）。

**R-04 [SUGGESTION] `yate/cli.py:175-187` — `--2way` / `--3way` 在缺少 `--diff` 时被静默忽略**
问题：其它 diff 组合规则都走 `parser.error`，唯独此组合既不报错也不生效。
修复：`if (args.two_way or args.three_way) and not args.diff_files: parser.error(...)`。

**R-05 [SUGGESTION] `yate/cli.py:331` — logger 在 `main()` 内构造，偏离模块级 `log` 约定**
问题：全仓均模块级 `log = tracing.get_logger(__name__)`，cli.py 在函数内取 `"cli"`；`yate.logs` 是 stdlib-only 叶子，无推迟必要。
修复：模块顶部导入并建模块级 `log = tracing.get_logger(__name__)`。

**R-06 [SUGGESTION] `yate/logs.py:243-262` — `_SessionFileHandler.emit` 只原谅 `OSError`**
问题：解释器关闭阶段向已关闭流写入抛 `ValueError`，会沿 logging 栈逸出，违背"logging must never break yate"。
修复：`except (OSError, ValueError)`（与 `install()` 的防御一致）。

**R-07 [SUGGESTION] `yate/session.py:87-89,202` — `is_open()`/`retarget()` 每次对全部文档重复 `path.resolve()`**
问题：每次打开文件触发一次全量 resolve（含系统调用），重复计算可缓存。
修复：`Document` 打开时缓存 `resolved_path`，比较用缓存值。

**R-08 [SUGGESTION] `yate/session.py:327-337` — `remove_node` 对畸形输入静默退化**
问题：① `zip(children, sizes)` 长度不一致时静默截断；② target 不在树中时也可能提升唯一子节点改变树形。
修复：用 found 标志区分"未删除"与"真删除"，仅在确实删除后做单子提升。

## B. 调度层（editor / actions / commands / flows）

**R-09 [WARNING] `yate/prompt_completion.py:109-128` + `yate/document_flows.py:363-366` — 补全候选与实际打开路径基准目录不一致**
问题：`_path_matches` 把相对路径解析到 workspace root，但 `_submit_open` / `commands._edit` 把原始相对路径交给按进程 cwd 解析的 `session.open`（全仓无 chdir）。cwd ≠ root 时补全提交后命中"不存在 → 新建幻影 buffer"分支。
修复：在 `_submit_open`（`_open_document` 入口）统一按 workspace root 解析相对路径后再 `open_path_later`，与补全口径一致。

**R-10 [WARNING] `yate/commands.py:142-147` — `:e` / `:diff` / open prompt 不展开 `~`，与 `:sp` 不一致**
问题：`window_flows.split_with_path` 用 `Path(text).expanduser()`，其余路径不展开；Windows 上字面 `~` 被当目录名生成幻影 buffer；补全候选（`prompt_completion.py:115`）做了 expanduser，接受后却打不开，进一步放大不一致。
修复：`_edit`、`_submit_open`、`_diff` 统一 `expanduser()`（收敛到 `_open_document` 入口一次完成）。

**R-11 [SUGGESTION] `yate/commands.py:89-90` — `_saveas` 对未 strip 的参数做去引号**
问题：`_strip_quotes(args)` 少了 `.strip()`（对比 `_edit`），带首尾空白的调用会保留字面引号生成含引号文件名。
修复：与 `_edit` 对齐 `_strip_quotes(args.strip())`。

**R-12 [SUGGESTION] `yate/completion.py:177-179/317-321/348-350` — 标识符前缀回扫逻辑三处重复**
修复：抽模块级 `_identifier_prefix(line, col)`，三处调用。

**R-13 [SUGGESTION] `yate/completion.py:141-147` — 手动补全请求不取消已 arm 的 debounce 定时器**
问题：`request()` 只置 `self._timer = None` 不 `cancel()`，0.12s 后冗余重查。
修复：`request()` 顶部仿 `schedule()` 先 `timer.cancel()`。

**R-14 [SUGGESTION] `yate/document_flows.py:180-186/198-204` — open_path 与 open_path_async 尾部收尾五行重复**
修复：抽 `_after_open(path)` 复用。

**R-15 [SUGGESTION] `yate/document_flows.py:97` — 恒真死分支**
问题：`str(path.parent)` 永不为空，`Path.cwd()` 分支不可达。
修复：简化为 `set_root(path.parent)`。

**R-16 [SUGGESTION] `yate/shell_flows.py:136-144` — `_font_async` 无异常兜底，消息线卡在 "checking…"**
修复：`try/except Exception` 包住 `asyncio.to_thread`，失败经 `_message(..., "error")` 反馈（noqa: BLE001 + 理由）。

**R-17 [SUGGESTION] `yate/diagnostics.py:136-137` — `except Exception: pass` 无日志**
修复：补 `log.debug(..., exc_info=True)`，模块补 `log = tracing.get_logger(__name__)`。

**R-18 [SUGGESTION] `yate/window_flows.py:105-113` — split 成功但文件打不开时留下重复窗格**
修复：`open_path_async` 返回成功与否，失败时回滚 `close_active()`。

## C. editor_view 组件层

**R-19 [WARNING] `yate/editor_view/editor.py:302-311` — `on_key` 无条件吞键（初判与 R10 冲突，待核实）**
问题（子代理原判）：`dispatch_key` 契约返回 bool，但 `on_key` 无条件 `event.stop()` + `prevent_default()`。
**主代理核实**：架构规则 R10 明文要求"处理后 `event.stop()`/`prevent_default()`，未被消费的键不得冒泡到外壳二次派发"——当前实现正是 R10 的落地形态，子代理判据（"unconditional swallowing IS a violation"）与本仓架构规则相反。**处置：按 R10 维持现状，登记为"依规则不修"**。

**R-20 [WARNING] `yate/editor_view/palette.py:307-316` — 只有一条结果时按 Down/ctrl+n 立即执行该项**
问题："唯一匹配立即选中"分支位于覆盖 `("down","ctrl+n","tab")` 的 elif 内，用户仅移动光标却触发打开/执行副作用。
修复：拆开分支，仅 `tab` 且 `len(self._filtered) == 1` 时 `_choose()`。

**R-21 [SUGGESTION] `yate/editor_view/editor.py:881-890` — 渲染热路径每行全量扫描 `search.matches`**
修复：搜索状态设置时按行分桶 `dict[int, list[Match]]`，`_row_style_ranges` 直接查桶。

**R-22 [SUGGESTION] `yate/editor_view/editor.py:438-441` — "无行变化"早退分支不更新 `_hl_version`，每次渲染重复全文档 diff**
修复：该分支返回前同样 `self._hl_version = buf.content_version`。

**R-23 [SUGGESTION] `yate/editor_view/terminal.py:537-538` — `contextlib.suppress(Exception)` 静默吞掉头部更新异常**
修复：收窄或补 `log.debug`。

**R-24 [SUGGESTION] `yate/editor_view/diffview.py:1030-1035` — docstring 与实际 latch 重置点矛盾**
修复：改为指向 `_pane_changed` / `_apply_copy` / `action_undo_pane`。

**R-25 [SUGGESTION] `yate/editor_view/diffview.py:263/608` — `DiffPane.read_only` 只写不读**
修复：删除该属性或让守卫使用它保持单一来源。

**R-26 [SUGGESTION] `editor.py:282-289` / `explorer.py:266-273` / `diffview.py:295-303` — 滚动条主题调色块三处逐字重复**
修复：scrollbars.py 增加 `apply_scrollbar_theme(widget)` 助手，三处单行调用。

**R-27 [SUGGESTION] `yate/editor_view/chrome.py:186-191` — 单条超宽 crumb 不截断，整行溢出**
修复：对第一条 crumb 也按剩余预算截断。

**R-28 [SUGGESTION] `yate/editor_view/completion.py:349-356` — 每次补全请求全量正则扫描所有打开缓冲**
修复：按 `(buffer, content_version)` 建词集缓存，查询时前缀过滤。

**R-29 [SUGGESTION] `yate/editor_view/palette.py:340-343` — `_walk` 兜底硬编码 limit，与 `Workspace.walk_files` 默认值漂移**
修复：直接用 `Workspace(root).walk_files()` 默认 limit。

**R-30 [SUGGESTION] `yate/editor_view/manual.py:96-105/117-122` — 依赖 Textual 私有属性 `_content`/`_segments` 无版本边界注释**
修复：补注释钉住 Textual 8.2.8 契约（不引第三方文档）。

**R-31 [SUGGESTION] 8 个组件 — 主题订阅样板逐字重复**
问题：`_theme_unsubscribe` + on_mount 订阅 + on_unmount 幂等退订 10 行样板 ×8。
修复：提供 `theme` 模块级 helper（保持退订语义不变），逐组件替换。

## D. L0 叶包：editor_core / editor_lsp / editor_syntax

**R-32 [WARNING] `yate/editor_lsp/manager.py:637-640` — 畸形 diagnostics 通知杀死整个 LSP 连接**
问题：`int(start.get("line", 0))` 在值为 `None`/非数字时抛 TypeError/ValueError，`_read_loop` 兜底 `_fail_pending` → 客户端永久 FAILED。其余字段均有 isinstance 防御，唯数值转换遗漏。
修复：逐条目校验类型或 `except (TypeError, ValueError): continue`（附 `log.debug`）。

**R-33 [WARNING] `yate/editor_core/buffer.py:737-744` — 行级 paste below 在最后一行时把寄存器插到当前行上方**
问题：`set_cursor((r+1, 0))` 被钳回 r，随后在 (r,0) 分裂当前行——粘贴行落在当前行上方，且光标落点错，与 vim `p` 语义不符（现有测试未覆盖此场景）。
修复：最后一行以下粘贴改为从当前行末尾追加 `\n` + 文本；补回归用例。

**R-34 [WARNING] `yate/editor_lsp/manager.py:451`（另 519-524, 637-640）— LSP character 偏移按码点使用，未做 UTF-16 转换**
问题：LSP 规范 position.character 是 UTF-16 code unit；非 BMP 字符（emoji、CJK 扩展区）行内补全替换范围与诊断下划线整体错位。
修复：加 `_to_utf16`/`_from_utf16` 助手（BMP-only 快速路径跳过），发送/接收换算；补非 BMP 回归用例。

**R-35 [SUGGESTION] `yate/editor_lsp/protocol.py:112-124` — 头部读取无上限，畸形服务器可无限占用内存**
修复：累积超 64 KiB 即 `LspProtocolError("oversized headers")`。

**R-36 [SUGGESTION] `yate/editor_lsp/manager.py:459` — `except` 吞掉 `asyncio.CancelledError` 破坏取消语义**
修复：`CancelledError` 单独 re-raise。

**R-37 [SUGGESTION] `yate/editor_core/buffer.py:702-703` — `join_lines` 不可达三元分支**
修复：`joined = cur + " " + nxt.lstrip(" \t")`。

**R-38 [SUGGESTION] `yate/editor_syntax/ts_backend/languages.py:166-167` — 同一降级消息 warning + debug 各记一次**
修复：删重复 `log.debug`，统一 `_warn_degraded_once`。

## E. L0 叶包：editor_term / keyproto / editor_sprites

**R-39 [WARNING] `yate/editor_term/emulator.py:293` — 跨读取块分割的多字节 UTF-8 序列被破坏**
问题：`feed` 每次独立 `decode("utf-8", errors="replace")`，块边界切断 CJK/emoji 字符 → U+FFFD 乱码且宽度失真。
修复：`TerminalEmulator.__init__` 持 `codecs.getincrementaldecoder("utf-8")("replace")`，`feed` 增量解码。

**R-40 [WARNING] `yate/editor_term/emulator.py:354-361` — OSC 中间的 ESC 吞掉下一字符；CSI 态把 `\x1b` 当普通参数**
问题：`_osc_via_st` 分支在非 `\` 时提前 return 丢弃本应分发的 ch；`_CSI` 分支把 0x1B 追加进参数。malformed 流上静默错绘。
修复：`_osc_via_st` 非 `\` 时落到正常转义分发链重派 ch；`_CSI` 态把 `\x1b` 视为中止转 `_ESCAPE`。

**R-41 [SUGGESTION] `yate/editor_term/emulator.py:216-218` — `_csi`/`_osc` 缓冲无上限**
修复：设上限（如 OSC 1 MiB、CSI 64 字节），超限弃缓冲回 `_GROUND`。

**R-42 [SUGGESTION] `emulator.py:109-117` 与 `yate/keyproto/legacy.py:38-49` — 两份修饰键转义表已漂移**
问题：emulator `_MOD_ARROWS` 缺 ctrl+shift 箭头等（legacy `_MOD_SPECIAL` 有），对应按键在集成终端被静默丢弃。
修复：emulator 输入路径复用 `keyproto.legacy.textual_key_to_raw`（同 L0，docstring 明言为共享而迁入），或补齐 + 交叉一致性测试。

**R-43 [SUGGESTION] `yate/editor_term/pty_proc.py:268` — Unix spawn 末尾初始 resize 失败会孤儿化已启动子进程**
修复：spawn 内 `try: resize except OSError: pass`（best-effort，ConPTY 侧已对称）。

**R-44 [SUGGESTION] `yate/editor_term/shells.py:35` — Windows 上 `shlex.split(posix=False)` 保留引号字符**
问题：`"C:\...\bash.exe" -l` 被切成带引号碎片，Popen 必失败。
修复：posix=False 结果做去引号清洗，或 Windows 统一 posix=True 重建。

**R-45 [SUGGESTION] `yate/keyproto/frames.py:143-146` — `_pending` 在病态粘贴下无界**
修复：设上限（64 字节），超限当 residual 交 legacy 解析器。

**R-46 [SUGGESTION] `yate/editor_term/emulator.py:827` — `view_lines` 每帧拼接复制整个 scrollback**
修复：索引寻址避免整表拼接（行拷贝是否可去需先确认调用方只读）。

## F. tools/

**R-47 [WARNING] `tools/smoke_test/harness.py:377-378` — invariant 游标列检查可能 IndexError 使整个 harness 崩溃**
问题：列检查无条件索引 `buf.lines[row]`，在 `_run_one` try 之外调用；崩溃场景游标越界时整套件 traceback 终止——恰是 invariant 应"记录失败而非崩溃"的场景。
修复：索引前守卫 `in_lines = 0 <= row < len(buf.lines)`。

**R-48 [WARNING] `tools/smoke_test/cli.py:105-114` — `--json` 报告未做 JSON 可序列化清洗**
问题：杂散 `Path` 值使写报告阶段 TypeError，整个运行前功尽弃（baselines 路径有 `_jsonable` 清洗，此路径没有）。
修复：复用 `baselines._jsonable`（提升为公共 API）。

**R-49 [SUGGESTION] `tools/smoke_test/harness.py:427-431` — `except BaseException` 吞掉 KeyboardInterrupt，Ctrl+C 无法中止套件**
修复：先行 `except (KeyboardInterrupt, SystemExit): raise`。

**R-50 [SUGGESTION] `tools/changelog/translations.py:36-44` — 覆盖表条目非 dict 时裸 AttributeError，detail 未校验为 str**
修复：`isinstance(payload, dict)` 校验 + warning，detail 校验为 str。

**R-51 [SUGGESTION] `tools/changelog/translations.py:47-60` — `save_overrides` 不建父目录不处理 OSError**
修复：`mkdir(parents=True, exist_ok=True)` + OSError 干净报错返回 1。

**R-52 [SUGGESTION] `tools/changelog/gitdata.py:101-112` — `read_tags` 每 tag 单独 spawn 一次 git 子进程**
修复：一次 `for-each-ref --format="%(refname:short) %(objectname)" refs/tags/v*` 批量解析。

**R-53 [SUGGESTION] `tools/changelog/gitee.py:115-130` — pushed_flags 串行逐提交请求远端 API，可能阻塞数分钟**
修复：加提交数上限或 `concurrent.futures` 限并发批量查询。

**R-54 [SUGGESTION] `tools/pack/wiki.py:244-252` — `run_git` 无超时，挂起的 git push 永久阻塞**
修复：加 timeout（如 120s），超时转 stderr 报错返回 1（对齐 `gitdata.run_git`）。

**R-55 [SUGGESTION] `tools/pack/wiki.py:289-294` — 库函数 `load_manifest` 内 `sys.exit(1)`**
修复：抛 `WikiError`，由 `run()`/cli 层统一转退出码（对齐 `TranslateError` 模式）。

**R-56 [SUGGESTION] 仓库根定位逻辑 6 处重复**
问题：`Path(__file__).resolve().parents[2]` 以不同函数名散落 6 处。
修复：tools/ 内单点 `repo_root()` helper，各包导入。

## G. services / keymaps / extensions / pack

**R-57 [WARNING] `yate/keymaps/vim.py:619` — linewise 操作丢弃 motion count 且 `count_str` 泄漏到下一条命令**
问题：`d2dd` 只删 1 行；且 `_clear_operator()` 不清 `count_str`，下一条独立命令意外以 count=2 执行。`;`/`,` 无 last_find 分支同样泄漏。
修复：`n = (op_count or 1) * (typed_count or 1)` 并复位 `count_str`；无 last_find 分支清空 count。补回归用例。

**R-58 [WARNING] `yate/extensions/python_lsp.py:71` — `shlex.split(posix=True)` 在 Windows 上吃掉反斜杠，docstring 示例本身就是坏的**
问题：文档示例 `C:\tools\pyright-langserver.cmd` 被解析成 `C:toolspyright-langserver.cmd`，用户按文档操作 LSP 永远起不来。
修复：`shlex.split(override, posix=os.name != "nt")`。

**R-59 [WARNING] `yate/services/workspace.py:371-376` — `is_text_file` 的 UTF-8 边界截断造成误判**
问题：2048 字节截断落在多字节序列中间时 `UnicodeDecodeError` → 合法中文文本文件被判为二进制，被 quick open 排除。
修复：截尾容错（丢弃尾字节重试）后再判 `\x00`。

**R-60 [WARNING] `yate/keymaps/vim.py:219-224` — 自定义 category 的扩展绑定在 vim 模式下静默失效**
修复：放宽为"非内置 category"即分发，无绑定路径补 `log.debug`。

**R-61 [WARNING] `yate/keymaps/vim.py:288-307` — visual 模式下寄存器等待分支位于 v/V 分支之后，`"v` 行为错误**
问题：VISUAL 下 `"v` 被当作切模式处理（清选区退 NORMAL），normal 模式顺序正确。
修复：`pending_register == ""` 分支移到 esc/v/V 之前，与 `_handle_normal` 对齐。补回归用例。

**R-62 [SUGGESTION] `yate/services/workspace.py:143-153/183-209/229-262` — 每次列目录重新读盘解析 ignore 文件；排序 key 内重复 stat**
修复：按 (path, mtime) 缓存目录级 ignore 解析；排序后 `enumerate` 复用 is_dir。

**R-63 [SUGGESTION] `yate/keymaps/base.py:104-106` — `<shift-up>` 等 shift+特殊键静默丢弃 shift，反向遮蔽 `<up>`**
修复：多字符特殊键拒绝 shift（与 ctrl 处理一致）抛 ValueError。

**R-64 [SUGGESTION] `yate/services/extensions.py:482-490` — 同名不同路径扩展在 sys.modules 相互覆盖，失败 pop 误伤前者**
修复：模块名掺 resolved path 哈希。

**R-65 [SUGGESTION] `yate/extensions/csharp_highlight.py:27` — 捆绑扩展直接 import `LangSpec`，绕过文档化的 `api.highlight.LangSpec` 表面**
修复：改经 API 表面取用。

**R-66 [SUGGESTION] `pack/yate.spec` 与 `pack/yate-onefile.spec` — 约 90 行构建逻辑逐字重复**
修复：抽 `pack/_common.py`，两 spec 只留 Analysis/EXE/COLLECT 差异。

## H. tests/

**R-67 [WARNING] `tests/test_app_textual.py:1899-1927` — `:set theme` 测试泄漏全局活动主题，且 382-385/4959-4963 的恢复在断言之后无 finally**
修复：主题切换包 try/finally（或自动恢复 fixture）。

**R-68 [WARNING] `tests/test_app_textual.py:4248-4256` — `_wait_quit` 用 `suppress(Exception)` 泵，崩溃退出与正常退出无法区分**
修复：泵完后 `assert app._exception is None`（4 处副本同改）。

**R-69 [SUGGESTION] `wait_until` 轮询助手三处重复（`test_app_textual.py:39` / `test_command_path_args.py:34` / `test_completion_popup.py:398`）；`plain_text` 同样重复**
修复：提到 `tests/conftest.py` 共享。

**R-70 [SUGGESTION] `ActionContext`/`KeyUi` 构造样板三处复制（`test_action_table.py:129` / `test_clipboard.py:118` / `test_key_notation.py:22`）**
修复：conftest 提供工厂函数/fixture。

**R-71 [SUGGESTION] `YATE_PYTHON_LSP=off` 进程级环境变量散落三处模块导入期设置**
修复：收敛到 `tests/conftest.py` 集中设置并注释（保持进程级语义）。

**R-72 [SUGGESTION] `tests/test_app_textual.py:429/231` — 防抖等待硬编码 sleep 字面量**
修复：引用 `RECOMPUTE_DEBOUNCE_SECONDS` 常量或改 wait_until。

**R-73 [SUGGESTION] `tests/test_app_textual.py:2229-2329` — 后台线程固定真实 sleep 1.5-2.0s 拖慢套件**
修复：换 `threading.Event` 门闩，断言后立即放行。

**R-74 [SUGGESTION] `tests/test_lsp.py:306-308` — 断言写在假服务端协程里，失败表现为超时丢失信息**
修复：校验移到测试侧。

**R-75 [SUGGESTION] `tests/test_cli.py:283-288` — 子进程断言失败时输出被丢弃**
修复：`capture_output=True` + 失败打印 stderr。

**R-76 [SUGGESTION] `tests/test_editor_core.py:410-417` — 手写 try/except 计标志代替 `pytest.raises`**
修复：改用 `pytest.raises(UnicodeEncodeError)`。

**R-77 [SUGGESTION] `tests/test_panes.py:27` — 模块导入期改 `os.environ` 且从不恢复（与 R-71 合并处置）**

**R-78 [SUGGESTION] `tests/test_screensaver.py:342` — 真实时钟等待 1.1s × 3 处（合计 ~3.3s）**
修复：注入假 `IdleTracker(clock=fake)` 确定性触发（同文件已有示范）。

**R-79 [SUGGESTION] `tests/test_trust.py:90` — 永不失败的断言（同义反复）**
修复：删除该行并以注释说明。

**R-80 [SUGGESTION] `tests/test_pack_wiki.py:140/240` — 硬编码计数 8 重复两处**
修复：动态计算待翻译页数。

**R-81 [SUGGESTION] `tests/test_pack_wiki.py:87-89` — 测试名承诺 reports 但未验证输出**
修复：注入 capsys 断言 stderr。

**R-82 [SUGGESTION] `tests/test_terminal.py:330` — 定长 sleep 后断言读线程输出（CI 不保证）**
修复：复用 `test_pty_proc.py` 的 `_wait_for` 轮询模式。

**R-83 [SUGGESTION] `tests/test_pty_proc.py:461-468` — 事件循环异常处理器未用 try/finally 还原**
修复：包 try/finally。

（另有一条观察不计项：`test_terminal.py` 与 `test_terminal_emulator.py` 的重复用例为再导出契约覆盖，判定刻意分层，仅建议在模块 docstring 点明。）

---

## 专项核查结论（架构与安全）

- 分层：`editor_view` 0 处向上导入；`keyproto/driver_windows.py` 导入 textual 属 Windows 驱动实现（docstring 声明 + 架构注释明文纳入），不判违规；bundled extensions 仅触 `ExtensionAPI` 与叶子模块。
- R2/R6：无新增 Protocol、无 TYPE_CHECKING。
- 日志：全仓惰性 `%` 占位 100% 合规，无 `self.log`/`self.app.log`。
- 安全：无 CRITICAL；`config.py`/`theme.py` 的用户脚本 `exec` 为文档化有意设计；`frames.py` 对粘贴伪造按键帧的威胁有显式接受论证。
- R10 相关：R-19 与架构规则 R10 直接冲突，**依规则不修**（详见该条核实记录）。

## Strengths（各子代理汇总）

undo/redo 记账与原子写等位置数学经得起推敲；异步 worker 纪律好（协程函数传参防泄漏、三态防复活设计）；补全/高亮缓存键控与防抖成熟；ConPTY/终端状态机边角处理正确且竞态窗口逐条注释；扩展加载失败隔离与 trust store 安全设计到位；测试隔离纪律（isolated_home 双保险、mock.patch.dict、回归编号注释）与断言质量高；docstring 全面解释"为什么"。

---

**后续**：逐条核实与修复处置见 [`../documents/python-code-review-fixes-plan.md`](../documents/python-code-review-fixes-plan.md)；修复完成后在本目录 `README.md` 速览表登记闭环状态。
