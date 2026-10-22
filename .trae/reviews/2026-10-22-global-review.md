# 2026-10-22 全仓库全局代码评审（master `f7adf9d`，v0.2.12）

- 分支 / 基线：`master` @ `f7adf9d`（工作区干净，版本 v0.2.12）
- 范围：**全仓库**——`yate/` 约 140 个 `.py`（L0–L4 全部包、`flows/`、`extensions/`）+
  `tools/` 约 70 个 `.py`（mdlint / pack / smoke_test / changelog / release / translate / yxp / probes）；
  `tests/` 不逐行审，由门禁覆盖
- 形态：**只读事实文档**（`../rules/doc-conventions.md` §二.1）——只记录发现与核对结论，
  不含修复排期；修复动作若获批准另立 `.trae/documents/<task>-plan.md`
- 执行方式：**5 个 `code-review-expert` 代理分域**（4 个主域 + 1 个补审盲区），每个代理：
  读取 `.trae/agents/code-review-expert.md` → 依次加载 `python-code-review` 与
  `TRAE-code-review` 双框架 → 按 `文件:行号` 合并发现（冲突以 `TRAE-code-review` 为准）→
  执行强制自我批判；主代理对**全部 18 条 WARNING 逐条回读源码复核**，并亲跑四道门禁
- 交叉引用：前序全仓审核
  [`2026-10-20-full-repo-trae-code-review.md`](2026-10-20-full-repo-trae-code-review.md)、
  [`2026-10-18-full-repo-audit-r3.md`](2026-10-18-full-repo-audit-r3.md)、
  [`2026-10-17-four-skill-review.md`](2026-10-17-four-skill-review.md)
- 修复方案：[global-review-fixes-plans/overview.md](../documents/global-review-fixes-plans/overview.md)
  （38 项全部完成，执行记录见该总纲 §八）

## 一、门禁复测（主代理亲跑，本会话）

| 门禁 | 命令 | 结果 |
|---|---|---|
| pyright strict | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | **0 errors / 0 warnings / 0 informations**，exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | **36 passed**，exit 0 |
| 覆盖率 | `.venv\Scripts\python.exe -m pytest tests --cov=yate --cov-branch --cov-report=term-missing --cov-fail-under=75 -n auto` | **2858 passed / 9 skipped**，覆盖率 **91.96% ≥ 75**，exit 0（142.98s） |
| 冒烟 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | **112/112 场景、1354/1354 检查**，exit 0（87.39s） |

说明：覆盖率统计面为 `--cov=yate`，`tools/` 不计入覆盖率门面，仅由 pyright 覆盖类型面。

## 二、执行方式

1. **分区**：
   - **A** L4 外壳 + L3 调度核心（`app/cli/__main__/editor/actions/commands/registries/session/`
     `diagnostics/dist_meta/paths/config/yaterc*/logs`）；
   - **B** L3 流程模块（`flows/*`）+ 扩展系统（`services/extensions/*`、`extensions/*`）
     + `services/*` 其余模块；
   - **C** L2 组件 `editor_view/*` + L1 `keymaps/*` + `keyproto/*`；
   - **D** L0 叶包（`editor_core` / `editor_lsp` / `editor_syntax` / `editor_term` /
     `editor_sprites`）+ `tools/*`；
   - **E 补审**：C/D 自述未深审的 `manual.py` / `diff_pane.py` / `themes.py` / `icons.py`、
     `vim.py` 剩余段落（全 1368 行）、`ts_backend/languages.py`、`tools/smoke_test` 场景与报告。
2. **双框架合并**：每个代理先跑 `python-code-review` 六维度框架，再用 `TRAE-code-review`
   独立过一遍；两份发现集按位置对齐，冲突时以 `TRAE-code-review` 为准，仅一方报出的保留
   并标注来源。本次各域均**无结论冲突**。
3. **强制自我批判**：逐条回读证据、剔除误报、修正级别、登记状态；主代理再对全部 WARNING
   回读源码复核（见各条“主代理核对”）。

## 三、结论总览

**0 CRITICAL / 18 WARNING / 20 SUGGESTION。四道门禁全绿，未发现常规使用即触发的缺陷；
18 条 WARNING 全部属于测试未覆盖的潜伏缺陷或风险面。**

| 域 | WARNING | SUGGESTION |
|---|---|---|
| L4/L3 核心 | 1 | 3 |
| flows / services / 扩展 | 2 | 3 |
| editor_view / keymaps / keyproto | 6 | 2 |
| L0 叶包 / tools | 7 | 8 |
| 补审（editor_view 补盲 / vim / smoke） | 2 | 4 |
| **合计** | **18** | **20** |

## 四、WARNING（18）

### L4/L3 核心（1）

**W-01 `language_servers[].filetypes` 未裁剪空白，静默产生永不匹配的 LSP 配置**
[yaterc_options.py:590-603](../../yate/yaterc_options.py#L590-L603)：
`filetypes = [ft.lstrip(".") for ft in filetypes]` 只去前导点；`_require_str_list`
（[:646-660](../../yate/yaterc_options.py#L646-L660)）只拒绝纯空白项、返回原始字符串，
因此 `" py "` 被接受。该值随后作为 `_by_filetype` 键写入
[manager.py:186-189](../../yate/editor_lsp/manager.py#L186-L189)，永远匹配不上任何文档
filetype（注释已声明 canonical form 意图）。修：`ft.strip().lstrip(".")`，`.strip()` 后为空
则沿用现有 `any(not ft)` 拒绝路径。
**主代理核对**：源码与 `_require_str_list` 行为一致，确认。

### flows / services / 扩展（2）

**W-02 替换确认循环把“跳过”计入“已替换”数量**
[prompt_flows.py:147-150](../../yate/flows/prompt_flows.py#L147-L150)、
[:184-190](../../yate/flows/prompt_flows.py#L184-L192)：`n` 分支执行
`self._confirm_done += 1  # skip the match _advance selected`，而 `_finish_or_advance`
用同一计数器生成结束语 `replaced {self._confirm_done} occurrence(s)`。全程按 `n`（0 次实际
替换）也会报 “replaced N occurrence(s)”；混合 y/n 时数字也偏高。现有测试只覆盖“全 y”与
“n 后 q”。修：独立 `_replaced` 计数器仅在 `replace_current()` 返回 True 时自增，并在
`_end_confirm` 重置；补 `y, n, y` 用例。
**主代理核对**：计数器复用路径确认。

**W-03 打开文档未处理 `OSError`：同步路径启动崩溃 / 异步路径静默失败**
[document_flows.py:171-188](../../yate/flows/document_flows.py#L171-L188)（同步）、
[:190-205](../../yate/flows/document_flows.py#L190-L205)（异步）只处理“非文本文件返回 None”；
[session.py:96-115](../../yate/session.py#L96-L115) 的 `Document.open(path)` →
`read_bytes()` 可抛 `PermissionError`/`OSError`（文件被占用、权限不足；`.py`/`.txt` 经
`is_text_file` 直接判文本，不做读探测）。同步路径（启动目标 / 资源管理器新建后打开）异常
无兜底，经进程级异常钩子直接退出；异步路径（`:e`/`:sp`，`exit_on_error=False` worker）只进
devtools 日志。[overlay_flows.py:160-163](../../yate/flows/overlay_flows.py#L160-L163) 对同一
风险已有 `except OSError` 先例。修：两处捕获 `OSError` → 消息行 warn 并返回 `None`。
**主代理核对**：`session.open` 无异常转换，确认。

### editor_view / keymaps / keyproto（6）

**W-04 零宽字符使渲染与光标坐标系不一致**
[cells.py:97-118](../../yate/editor_view/cells.py#L97-L118) 的 `cell_offsets` 对
`cell_width == 0` 仍按 `max(1, …)` 前进一格，而
[:121-131](../../yate/editor_view/cells.py#L121-L131) 的 `expand_char` 把组合符附加到前一格
（占 0 格）。[editor_view/editor.py:385-390](../../yate/editor_view/editor.py#L385-L390) 同时
用两者（cells 定宽、offsets 定位），组合符后光标/选区/语法着色整体右移。修：`cell_offsets`
对 0 宽字符沿用上一格偏移。

**W-05 `chr()` 未校验范围，可令输入线程永久退出**
[frames.py:94-97](../../yate/keyproto/frames.py#L94-L97)：`char_text` 直接
`chr(self.char)`；帧字段为任意十进制（模块自述帧输入未认证）。`CSI 1114112;…_` 触发
`ValueError` → [driver_windows.py:238-242](../../yate/keyproto/driver_windows.py#L238-L242) 的
blanket `except Exception` 记录后退出监控循环，此后键盘全部失效（仅日志可见）。
修：`if not 0 <= self.char <= 0x10FFFF: return ""`。
**主代理核对**：`_decode_frame` 已防空字段，独漏范围；异常捕获位置确认会结束 `run()`。

**W-06 无历史查找时 `;` / `,` 报 “unknown action: find repeat”**
[vim.py:738-740](../../yate/keymaps/vim.py#L738-L740)：仅当 `self.last_find is not None`
才重复查找，否则落到 `_extension_binding`（[:265-278](../../yate/keymaps/vim.py#L265-L278)）；
表项 [vim.py:163-164](../../yate/keymaps/vim.py#L163-L164) 的 action 名为 `"find repeat"`，
全仓无该 action 注册（grep 仅此一处），最终状态栏打印 unknown action。修：空态显式
`return True` 或移除该表项。

**W-07 `parse_key` 静默丢弃未知修饰词**
[keys.py:93-107](../../yate/keymaps/keys.py#L93-L107)：`modifiers = set(tokens[:-1])`
后只识别 shift/alt/ctrl，`<meta-s>`/`<cmd-s>`/拼写错误 `<ctr-s>` 均返回 `"s"`，扩展绑定会
静默绑到裸键；同函数对不可表示的 shift/ctrl 组合是显式 `raise`（[:114-130](../../yate/keymaps/keys.py#L114-L130)）。
修：未知修饰词一律 `ValueError`。

**W-08 vim NORMAL 的 count 状态在非 motion 命令后泄漏**
[vim.py:764-830](../../yate/keymaps/vim.py#L764-L830)：`u` / `ctrl-r` / `J` / `ctrl-d,u,f,b`
/ `i` / `o` / `O` 分支均未清 `count_str`（`_exit_multi` 不清），insert 的 Esc 也不调
`_clear_pending`。探针复现：`3 i X <Esc>` 后按 `x` 删除 3 字符；`3 u` 后 `x` 同样删 3。
与已修复的 R-57（`d2dd`）同类，现有用例只钉 `d2dd`
（`tests/test_vim_keymap.py:1689`）。修：这些分支统一 `_clear_pending()`（或按 vim 语义消费
count），补用例。
**主代理核对**：所列分支均无清理调用。

**W-09 `validate_theme` 漏校验 20+ 个颜色字段，非法用户主题注册后在渲染期崩溃**
[themes.py:461-532](../../yate/editor_view/themes.py#L461-L532) 只遍历
`_MAPPED_COLOR_FIELDS`（13 个），而模块 docstring
（[:19-22](../../yate/editor_view/themes.py#L19-L22)）承诺 “every color must parse”；
`selection_bg` / `match_bg` / `on_accent` / `mode_*_bg` / `syn_*` 等未校验，却被
[find_replace.py:342](../../yate/editor_view/find_replace.py#L342)（Rich markup）、
[themes.py:125-135](../../yate/editor_view/themes.py#L125-L135)（`Style(color=...)`）、
[statusbar.py:68-74](../../yate/editor_view/statusbar.py#L68-L74) 直接消费。探针：
`match_bg='not-a-color'` / `syn_keyword='nope'` 的主题 `validate_theme()` 返回空，随后
`StyleSyntaxError` / `ColorParseError`。修：按 `dataclasses.fields` 遍历全部颜色槽。

### L0 叶包 / tools（7）

**W-10 整词搜索在 regex 模式下丢失边界锚**
[project_search.py:59-68](../../yate/editor_core/project_search.py#L59-L68)：
`rf"(?:(?<=\W)|^){pattern}(?=\W|$)"` 未给 `pattern` 加分组，顶层 `|` 切断锚。
`foo|bar` + `whole_word` 生成 `(?:(?<=\W)|^)foo|bar(?=\W|$)`：`xbar` 命中 `bar`（缺前边界）、
`foobar` 命中 `foo`（缺后边界）。修：`rf"(?:(?<=\W)|^)(?:{pattern})(?=\W|$)"`。
**主代理核对**：拼接代码确认。

**W-11 LSP 返回的负行号未钳制，可把文档塌缩为一行**
[parsing.py:117-125](../../yate/editor_lsp/parsing.py#L117-L125)：`_range_from` 仅 `int()`，
`_range_to_buffer_cols` 只对“取列”做 `0 <= r < len(lines)` 保护，返回的 `r0/r1` 未钳制；
[completion_flows.py:319-332](../../yate/flows/completion_flows.py#L319-L332) 把
`(r0, c0)` 直送 `replace_range`，[buffer.py:399-406](../../yate/editor_core/buffer.py#L399-L406)
的 `_delete_range` 对负行号走 Python 负索引。探针：
`TextBuffer('aaa\nbbb\nccc\nddd').replace_range((-1,0),(2,0),'X')` → `['Xccc']`，四行变一行。
修：行列钳制到 `[0, len(lines)-1]` / 行长（必要时丢弃越界 completion）。
**主代理核对**：消费链三段源码一致；Ctrl+Z 可恢复，故维持 WARNING 而非 CRITICAL。

**W-12 `max_file_bytes` 在读完整文件之后才判，限流不保护内存**
[project_search.py:145-152](../../yate/editor_core/project_search.py#L145-L152)：
`data = path.read_bytes()` 之后才 `if len(data) > max_file_bytes`，2 GB 文件仍会被整体读入
后丢弃，与 docstring “are skipped” 的语义不符。修：先 `path.stat().st_size` 比较。
**主代理核对**：顺序确认。

**W-13 ConPTY 读循环复用未重置的 `read_bytes`，失败读重发旧 chunk**
[pty_proc.py:600-620](../../yate/editor_term/pty_proc.py#L600-L620)：`read_bytes` 只在循环外
初始化一次；`ReadFile` 失败时不写计数，但代码先 `count = read_bytes.value` /
`if count: emit_output(...)` 再判 `if not ok … break`。一次失败读会在退出前重复投递上一块
终端字节（画面重影）。修：每次调用前置 `read_bytes.value = 0`，或改 `if ok and count`。
**主代理核对**：顺序与初始化位置确认。

**W-14 wiki 孤儿英文页永不被清理**
[wiki.py:1534-1539](../../tools/pack/wiki.py#L1534-L1539)：`digests[page.zh_target]`
只记中文目标；[:1613-1652](../../tools/pack/wiki.py#L1613-L1652) 的
`recorded = set(manifest)` 因而只含 `*.zh.md`，而
[`prune_orphan_pages`](../../tools/pack/wiki.py#L566-L595) 只删除 `posix in recorded`
的文件。源文档删除后 `foo.en.md` 既不在 keep 也不在 recorded → 永久残留，与 docstring
“Deletes generated wiki pages whose source document no longer exists” 不符（现有测试只断言
zh 孤儿）。修：manifest 同时记录/推导 en 目标。
**主代理核对**：`recorded = set(manifest)` 与 manifest 只写 zh 键确认。

**W-15 `crlf` 规则永不触发**
[lint_lua.py:243-253](../../tools/lint_lua.py#L243-L253)：`path.read_text(encoding="utf-8")`
的通用换行会把任意平台的 `\r\n` 归一为 `\n`，随后 `if "\r" in source` 只能命中孤立 `\r`
（旧 Mac），CRLF 文件全部漏检，而模块 docstring 明列 “crlf LF line endings only”。
修：`path.open(encoding="utf-8", newline="")`（同
[mdlint/lint.py:147](../../tools/mdlint/lint.py#L147) 先例）。
**主代理核对**：读取方式确认。

**W-16 `yxp --create … --force` 对任意同名目录 `rmtree`**
[yxp/cli.py:246-264](../../tools/yxp/cli.py#L246-L264)：`if target.exists(): …
shutil.rmtree(target)` 不校验目标是否为脚手架（无 manifest / 标记检查），而 docstring 声称
“an existing **scaffold** directory of the same name is removed”；在既有项目目录下执行
`--create foo --force` 会整体删除该目录（不可恢复）。修：仅当目标含 `MANIFEST_NAME` 且
名称匹配时才允许删除，否则要求显式确认。
**主代理核对**：删除路径无条件确认。

### 补审（2）

**W-17 冒烟报告把“崩溃场景”计为通过**
[report.py:219-235](../../tools/smoke_test/report.py#L219-L235)：分组表
`passed = sum(1 for r in group if r.fail_count == 0)` 未看 `r.error`；而
[:356-374](../../tools/smoke_test/report.py#L356-L374) 的 summary 与 CLI 退出码使用
`fail_count == 0 and r.error is None`。崩溃场景 checks 为空 → fail_count 0，分组副标题显示
`1/1 scenarios` 绿勾，同时 exit 1，同一报告两种结论。修：两处都加 `and r.error is None`。

**W-18 冒烟场景依赖固定睡眠等防抖落地**
[regression.py:23-26](../../tools/smoke_test/scenarios/regression.py#L23-L26) 定义
`_SETTLE_S = 0.3`，用于等 0.12s 自动补全防抖 + worker 落地（注释自述 “so a late
popup.show() cannot race an assertion”）；在
[:262](../../tools/smoke_test/scenarios/regression.py#L262)、266、279、284、299 使用。
违反 `../rules/python-coding-style.md` §4.7「禁止依赖真实睡眠时长做断言」；`--jobs 4` 下
worker 晚于 0.3s 即可 flake。同文件已有 `wait_until` 先例。修：monkeypatch 防抖常量或改
`wait_until(pilot, lambda: …)` 轮询谓词。

## 五、SUGGESTION（20）

| # | 位置 | 问题与建议 |
|---|---|---|
| S-01 | [app.py:103-111](../../yate/app.py#L103-L111)、[theme.py:98-108](../../yate/editor_view/theme.py#L98-L108) | yaterc `theme` 与 `--theme` 原样传给精确匹配的 `set_theme`，而 `Editor.set_theme` 先 `strip().lower()`；大小写/空白输入在启动时报 unknown theme。建议 L4 入口统一归一化 |
| S-02 | [config.py:66-67](../../yate/config.py#L66-L67)、[diagnostics.py:171-173](../../yate/diagnostics.py#L171-L173) | `Any` 注解缺 `# noqa: Any - <理由>`（python-coding-style §3.3；同仓库 `yaterc_options.py` 已按规范标注） |
| S-03 | [editor.py:727-734](../../yate/editor.py#L727-L734) vs [:768-771](../../yate/editor.py#L768-L771) | `ctrl+space` 分支位于 `prompt_bar.active_mode` 早返回之前，命令行激活时可能在其上方弹编辑器补全（代码路径推演，未做 pilot 复现） |
| S-04 | [data_store.py:54-57](../../yate/services/data_store.py#L54-L57) | 盘符检查漏 `C:foo/bar`（drive-relative）形态：POSIX 接受、Windows 拒绝，与 docstring 的可移植承诺不符（仍在 data_root 内，无逃逸风险） |
| S-05 | [api.py:254-267](../../yate/services/extensions/api.py#L254-L267) | `buffer` / `doc` / `workspace` 三个公共属性缺返回注解（python-coding-style §3.1；pyright strict 不报此缺陷） |
| S-06 | [user_setup.py:274-279](../../yate/services/user_setup.py#L274-L279) | `cleanup_defaults` 的 `any(base.iterdir())` 在 try 之外，目录不可读时把 `OSError` 抛给“错误收集”函数；复用 `_cleanup_plan` 的 entries 或 `suppress(OSError)` |
| S-07 | [terminal.py:393-416](../../yate/editor_view/terminal.py#L393-L416) | `_cell_style(cell: Any, t: Any)` / `_cursor_style` 用 `Any` 掩盖现成的 `Cell` 与 `theme.Theme` |
| S-08 | [find_replace.py:102-125](../../yate/editor_view/find_replace.py#L102-L125) | 渲染路径按文件组调 `path.resolve()`（`root.resolve()` 参与 lru 键），首次结果渲染对每个命中文件同步 stat；建议 root 解析一次并下移 worker |
| S-09 | [vim.py:500-603](../../yate/keymaps/vim.py#L500-L603)、[:1254-1256](../../yate/keymaps/vim.py#L1254-L1256) | VISUAL 模式无前缀状态，`g`/`f`/`F`/`t`/`T`/`r` 被静默吞掉；手册 [manual.en.md:599-601](../../yate/resources/manual.en.md#L599-L601) 却称 “motions extend the selection”。复用 `self.prefix` 或显式 fall-through 并文档化 |
| S-10 | [vim.py:1260-1299](../../yate/keymaps/vim.py#L1260-L1299)、[manual.en.md:546](../../yate/resources/manual.en.md#L546) | `dj`/`dk`/`dG` 按字符删而非 vim 的整行语义（`dj` 会留下半行）；改 linewise 或手册注明“仅字符范围”（docstring 已自述 charwise） |
| S-11 | [manual.py:477-485](../../yate/editor_view/manual.py#L477-L485) | worker `exit_on_error=False`，read 只捕 `OSError`；`UnicodeDecodeError` 逃逸会让 viewer 永久 loading（同文件 `_render_or_failure` 已论证该风险）。捕获 `Exception` + `log.exception` 降级为错误行 |
| S-12 | [languages.py:280-295](../../yate/editor_syntax/ts_backend/languages.py#L280-L295) | `load_language` 接受任意 name，`drop_language` 对 `BUILTIN_PACKS` 名直接 return；扩展以内置语言名注册后回滚不卸载。`load_language` 对内置名拒绝或改覆盖标记 |
| S-13 | [pty_proc.py:511-519](../../yate/editor_term/pty_proc.py#L511-L519) | 第二条 `CreatePipe` 失败直接抛错，第一条管道 `in_read/in_write` 未关闭（单次泄漏 2 个句柄） |
| S-14 | [buffer.py:1047-1060](../../yate/editor_core/buffer.py#L1047-L1060) | 末行粘贴空行寄存器：`text[:-1]` 为空时 `move_line_end(); move_left()` 在列 0 左移到上一行末尾，光标落错行；仅当 `text[:-1]` 非空时 `move_left()` |
| S-15 | [release/cli.py:119-129](../../tools/release/cli.py#L119-L129)、[:280-286](../../tools/release/cli.py#L280-L286)、[:363-368](../../tools/release/cli.py#L363-L368) | 快照 `read_text` / 回滚 `write_text` 的 “byte-exact” 依赖工作区恰好 CRLF；`autocrlf=input/false` 检出时回滚不逐字节一致。改 `read_bytes`/`write_bytes` |
| S-16 | [translations.py:31-52](../../tools/changelog/translations.py#L31-L52) | `zh_overrides.json` 语法错误时 `JSONDecodeError` 直接冒泡成 traceback（`changelog/cli.py` 无兜底）；捕获并给单行 `error:` + exit 1 |
| S-17 | [search.py:151-172](../../yate/editor_core/search.py#L151-L172) | `replace_all` 直接写 `buffer.lines[row] = "".join(out)`，替换串含 `"\n"` 会破坏行不变式（UI 不可输入换行，仅扩展/API 可达）；改走 `replace_range` 或拒绝 |
| S-18 | [diff.py:56-63](../../yate/editor_core/diff.py#L56-L63) | `align(row)` 无边界检查，`align(-1)` 静默返回最后一行映射；加 `0 <= row < len(...)` 校验 |
| S-19 | [protocol.py:161-173](../../yate/editor_lsp/protocol.py#L161-L173) | docstring 称容忍裸 OS 路径，但 `C:\foo\bar` 被 `urlparse` 解析成 scheme=`c`，返回 `Path('\\foo\\bar')`（盘符丢失）；检测单字母盘符前缀按原样 `Path(uri)` |
| S-20 | [document.py:86-95](../../yate/editor_core/document.py#L86-L95) | `_decode` 以 `utf-8` 优先，BOM 文件把 `\ufeff` 留作首行首字符（影响光标/列计算/搜索）；先 `utf-8-sig` 再 `utf-8`，保持回写一致 |

## 六、自我批判登记（删除 / 降级项）

各域在输出前均执行了强制自我批判，以下为主要剔除项（保留可追溯性）：

- **A 域删除**：`registries.unregister` 回滚丢内置项（`ExtensionAPI` 已快照恢复）、
  `ctrl+@` 未聚焦时行为（`TerminalPanel.on_key` 自行消费）、`ctrl+w` 被窗口 chord 吞
  （`try_window_prefix` 先判 `active_mode`）、`diagnostics` 对 `root_markers=None` 的担忧
  （类型恒有默认值）、`YateApp.self.config` 覆盖（Textual `App` 无该成员）、
  `session.retarget` 陈旧路径（`Document.path` setter 失效 `_resolved`）、`Leaf.states`
  无界增长（无实测影响）；一条 WARNING 降为 SUGGESTION（主题大小写一致性）。
- **B 域删除**：`shell.run_shell` Windows UTF-8 乱码（探针未复现）、`open_diff` 捕获面
  （`_decode` 永不抛错）、`Workspace.validate_name` 保留设备名（调用方已捕 `OSError`）、
  `:saveas` 根目录联动（与 `open_target` 策略一致）、扩展装载计数口径（de-dup 已文档化）、
  同步 `api.shell` 阻塞（docstring 明示设计）。
- **C 域删除**：statusbar 非 str provider（不可达未证实）、`terminal.on_paste` 空壳不消费
  （无其他 Paste 处理器、无后果）；`find_replace` 渲染期 `resolve()` 由 WARNING 降为
  SUGGESTION（lru 缓存仅首帧）。
- **D 域删除**：`manager.ensure_client` STARTING 客户端（`_starting` 表内不可达）、
  `LspClient.start()` 取消路径（`stop()`/`shutdown_all()` 覆盖）、`PtyProcess.write` UI 阻塞
  （docstring 声明有界）、`_ConPty` 每块复制 / `notify_edit` 每键 `get_text()`（预优化）、
  `win32im_probe` 缺 `__main__` 守卫（一次性探针）；两条 WARNING 降级
  （`CreatePipe` 泄漏 → SUGGESTION；release 字节精确 → SUGGESTION）。
- **E 域删除**：`_warn_degraded_once` 非 tracing 不可见（注释与实现不符、无行为损失）、
  `_schedule_rerender` 定时器不取消（无正确性影响）、同名覆盖内置主题（可能为特性）；
  `manual` 文档读取由 WARNING 降为 SUGGESTION（触发概率低、可 Esc 退出）。

## 七、覆盖率缺口与评审盲区

- 覆盖率（分支模式，`--cov=yate`）：总 **91.96%**（16274 statements / 1047 missed，499
  部分分支）。相对薄弱：`keyproto/driver_windows.py` **26%**（122-242、259-294，Windows
  实机驱动整体未测）、`flows/shell_flows.py` 63%、`extensions/example_ext.py.example` 48%、
  `editor_term/pty_proc.py` 81%（228-351）、`editor_term/shells.py` 78%、
  `editor_view/explorer.py` 81%、`cli.py` 86%、`user_setup.py` 80%。
- `tools/` 不在覆盖率统计面（仅 pyright 类型面覆盖）。
- 本轮补审后仍未深审的部分：`editor_syntax/langdefs.py` 的 757 行语言数据表（只核构造 /
  注册 / 解析段）、`editor_sprites/chars/*` 位图数据（依赖 import 期 `_validate` 统一校验）、
  `tools/smoke_test` 的 `harness.py` / `cli.py` / `baselines.py`（仅交叉核对）。均属声明式
  数据或测试基础设施。

## 八、口径说明

- 规则文本 [architecture-boundaries.md](../rules/architecture-boundaries.md) §三.7 登记
  `editor.py` 行数为 1060（2026-10-20 复测），本次实测 **1133 行**；`SIZE_EXEMPT_FILES`
  只存文件名不存行数，守卫不受影响，规则文本建议随下次修改同步。
- 架构守卫实测 36 条，与规则 §六 的 36 条清单一致。
- 全量门禁命令与 CI 口径一致（`-n auto` / `--jobs 4`）；本次全部一次通过，无并行时序失败。
