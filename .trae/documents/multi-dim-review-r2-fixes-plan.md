# 2026-11-05 全仓多维度评审（第二轮）修复方案

> 与 [评审记录](../reviews/2026-11-05-multi-dim-review-r2.md) 互链；本文件只管
> 「确认缺陷如何改」，评审记录只管「只读事实与裁定」，两者不合并。
> 主计划见 [multi-dim-review-r2-plan.md](multi-dim-review-r2-plan.md) Step 7。
> 本轮全部修复落在 `yate/`（产品源码），按 `subagent-workflow.md` §一.3
> 「子代理不得修改产品源码」由**主代理亲自执行**；子代理只承担只读审查与收尾复核。

基线：worktree `enh/multi-dim-review-r2`（master `75bccfa`），沙箱 `.venv`（Python 3.13.2）。
所有验收命令解释器统一 `.venv\Scripts\python.exe`，工作目录为 worktree 根。

## 一、修复清单（F1–F10）

### F1 [MAJOR] D1-1 `is_text_file` 把「非法 UTF-8 但无 NUL」的二进制判为文本

- 证据：`yate/services/workspace.py:583-590`；`chunk.decode("utf-8")` 抛错后无条件
  `chunk[: exc.start].decode("utf-8")` 再 `return b"\x00" not in chunk`。PNG 头
  `b"\x89PNG\r\n\x1a\n"` 无 NUL，因此被判为文本；`yate/session.py:114,140`
  据此允许打开二进制文件（返回文档而非 `None`），预览/会话行为错误。
- 改法：用增量解码器 `codecs.getincrementaldecoder("utf-8")().decode(chunk, final=False)`；
  尾部的半个多字节序列被缓冲而不报错，任何其它非法字节仍抛 `UnicodeDecodeError`
  并由既有 `except (OSError, UnicodeDecodeError)` 统一返回 `False`。新增 `import codecs`
  （stdlib 组，`fnmatch` 之前）。更新该函数注释，说明「仅容忍 2048 字节边界截断」。
- 新增用例：`tests/test_workspace_filter.py` 追加
  `test_is_text_file_rejects_invalid_utf8_without_nul`（PNG 头写盘 → `False`）与
  `test_is_text_file_rejects_invalid_continuation_at_boundary`（边界处非法续字节 → `False`）；
  既有 `test_is_text_file_tolerates_a_cut_multibyte_sequence` 必须继续绿。
- 验收：`.venv\Scripts\python.exe -m pytest tests/test_workspace_filter.py -q` → exit 0。

### F2 [MAJOR] D2-1 `terminal.shutdown` 静默吞异常

- 证据：`yate/editor_components/terminal.py:182-186`，`except Exception: pass`（有
  `# noqa: BLE001` 但无日志），违反 `python-coding-style.md` §4.5。
- 改法：`except Exception as exc:  # noqa: BLE001 - ...` + 
  `log.debug("terminal wait_closed failed: %s", exc)`（模块已有 `log`）。
- 验收：`pytest tests/test_terminal.py tests/test_app_terminal.py -q` → exit 0。

### F3 [MINOR] D2-2 `tools/` 五处 `except Exception` 缺 `# noqa: BLE001`

- 证据：`tools/mdlint/cli.py:227,238,324`、`tools/pack/wiki/lint.py:129,354`；
  `yate/` 内 64 处全部合规，仅 `tools/` 新拆分模块遗漏形式标记。
- 改法：五行分别补 `# noqa: BLE001 - <具体理由>`，理由不得笼统写「ignore」。
- 验收：`pyright tools/` 0 诊断 + `pytest tests/test_pack_wiki_lint.py -q` → exit 0。

### F4 [MINOR] D2-4 `pty_proc.py` 六处 best-effort `pass` 无 tracing

- 证据：`yate/editor_term/pty_proc.py:182-183,205-206,289-293,319-320,346-350,358-359`；
  上一轮已修外四处，这六处内部分支仍静默。
- 改法：逐个改为 `except ... as exc:` + 一条 `log.debug("...: %s", exc)`（惰性 `%`，
  模块级 `log` 已存在）；不改变控制流，不新增对外异常。
- 验收：`pytest tests/test_pty_proc.py tests/test_app_terminal.py -q` → exit 0。

### F5 [MINOR] D10 三处跨层调用失败无日志

- 证据：`yate/editor_components/terminal.py:577-580`（spawn 失败只写 prompt）、
  `yate/editor_components/palette.py:234-235`（目录扫描 `except OSError: entries = []`）、
  `yate/flows/shell_flows.py:137-142`（字体安装失败只写 prompt）。
- 改法：terminal 两个 except 各补 `log.warning("terminal failed to start: %s", exc)`；
  palette 补 `log.warning("palette file index failed: %s", exc)`；
  shell_flows 补 `from yate.logs import tracing` + 模块级 `log = tracing.get_logger(__name__)`
  （L3→L0 方向合法）与 `log.warning("font setup failed: %s", exc)`。
- 验收：`pytest tests/test_terminal.py tests/test_palette.py tests/test_shell_flows.py -q` → exit 0。

### F6 [MINOR] D4 五处「有标准低复杂度替代」的朴素算法

按「构建期即取最低时空复杂度」逐处改为索引/增量结构，行为不变：

| 子项 | 位置 | 改法 |
|---|---|---|
| F6a | `yate/services/yxp/manifest.py:177` | 循环前 `payload_names = set(payload)`，成员测试改用集合 |
| F6b | `yate/yaterc_options.py:103,151` | `_extract_path_list` 用 `seen = set(target)` 累加；`_extract_disabled_extensions` 用 `seen = set(config.disabled_extensions)` 累加（保持 list 顺序与类型） |
| F6c | `tools/pack/wiki/report.py:116-119` | 先按 `page.group` 分桶一次 `dict[str, list[WikiPage]]`，循环内直接取桶 |
| F6d | `yate/editor_core/search.py:72-84` | `_nearest_index` 用 `bisect_left(self.matches, (row, col), key=lambda m: (m.row, m.start))` 替代线性扫描（matches 已按 row/start 升序产生） |
| F6e | `yate/services/extensions/loader.py:119,170-172,202-204` | 新增 `_by_resolved: dict[Path, LoadedExtension]` 索引，两处 `self._resolved.add(...)` 同步写入，`load_file` 命中重复路径直接返回索引记录 |

- 验收：`pytest tests/test_yxp.py tests/test_yaterc.py tests/test_pack_wiki_report.py tests/test_editor_core.py tests/test_extensions.py -q` → exit 0；
  若用例文件名不符，以 `-q -k "yxp or yaterc or wiki or search or extension"` 收口并以 exit code 为准。

### F7 [MINOR] D1-2 `walk_files` 未命中缓存分支返回共享列表

- 证据：`yate/services/workspace.py:424` 返回 `files` 本体，命中分支 `:369` 返回 `.copy()`。
- 改法：`return files.copy()`，消除调用方改列表污染缓存的隐患（Suspect 直接销账）。
- 验收：随 F1 用例一起跑。

### F8 [MINOR] D12 新方案文档含本机绝对路径

- 证据：`.trae/documents/multi-dim-review-r2-plan.md:54,61,65`（worktree 绝对路径）。
- 改法：改为中性表述（如「主工作区」「独立 worktree 根目录」），去掉盘符与用户目录。
- 验收：全文 grep 盘符路径与用户目录字面量命中 0。

### F9 [MINOR] D7 规则文本登记漂移（仅文档，不动代码语义）

- 证据：`.trae/rules/architecture-boundaries.md:308`（vim.py 登记 1528 行，实测 1531）
  与 `:319`（把真实目录 `editor_components/file_manager/` 写成 `filemgr/`）。
- 改法：308 行**保留历史事实**并追加「2026-11-05 multi-dim-review r2 复测 1531 行，
  维持豁免」；319 行改为正确目录；`tests/test_architecture.py` 的 `SIZE_EXEMPT_FILES`
  注释追加同日复测说明（两处同步）。
- 验收：`pytest tests/test_architecture.py -q` → exit 0（37 守卫用例数不变）。

### F10 [MINOR] D13 计划文档验收命令中的覆盖率阈值口径

- 证据：主计划 Step 5 命令未带 `--cov-fail-under`，与 `misc-rules.md` §三「覆盖率阈值
  75 单源于 pyproject.toml」一致；无需改代码，只在评审记录门禁表写明「阈值来自
  pyproject.toml，未额外覆盖」作为事实登记。

## 二、登记不修（Deferred，评审记录须逐条列理由）

| id | 事项 | 不修理由 |
|---|---|---|
| D1 | 架构 Mermaid L3 未登记 `editor_compose` / `editor_dispatch` 节点与同层连线 | 按规则「新增合法连线须先修订图并补守卫用例」，会连带 37→38 守卫数与多处文档同步，属架构决策，非评审轮可随手改 |
| D2 | `.trae/rules/architecture-boundaries.md` §三.5 例外表未列 yxp 门面导入 | 同属架构登记，需架构裁决后单独提交 |
| D3 | §三.8 文本「类型注解 + `None` 初值」与代码纯注解不一致 | 代码形态（pyright strict）是正确的一侧；改规则文本属规范修订，另案 |
| D4 | `tests/test_architecture.py::test_missing_theme_source_suffixes_is_detected` 只扫顶层 | 守卫加宽是有价值建议，但会改变守卫覆盖面，需负向演练与单独登记，另案 |
| D5 | `yate/services/yxp/records.py` 等新子包 `Any` 注解缺 `# noqa: Any` 理由 | 全仓既有面（`**kwargs: Any`、LSP JSON）一致，非新增体系性漂移，列 Suggestion |
| D6 | 9 处 >100 字符行 / `# pyright: reportPrivateUsage=false` 抑制风格 | 格式与配置建议，不改行为，列 Suggestion |
| D7 | `tools/pack/wiki/sources.py` lossy decode、`yxp.install` 非 `YxpError` 回滚、截图子进程超时、pack 固定 tmp 名并发 | 均为 Suspect：缺用户场景/契约证据，按证据纪律不得当 finding 修 |
| D8 | README 登记项存量（本机路径迁移、#53 手册版本、cli.py 排版、lua lint CI lupa skip 等） | 既有登记项，本轮只做有效性复核，不批量清扫（`doc-conventions.md` §五） |

## 三、Suspects / Suggestions 处置

- 五名审查员报出的全部 Suspects 在评审记录 Suspects 段逐条列出（含「缺什么证据」），
  **不在本修复方案内改代码**；其中 D1-13（`yate.editor` logger 命名空间）经主代理回查
  `tests/` 无 `caplog.at_level(..., logger="yate.editor")` 依赖，按 Step 4 规则删除并引反证。
- F7 把 D1-2 从 Suspect 直接销账；D2-5（workspace 9 处 `except OSError`）降级为
  Suggestion：docstring 定义降级契约且有断言固定返回值，非静默失败路径。

## 四、执行与验收

1. 独占文件清单（主代理）：`yate/services/workspace.py`、
   `yate/services/yxp/manifest.py`、`yate/yaterc_options.py`、
   `yate/services/extensions/loader.py`、`yate/editor_core/search.py`、
   `yate/editor_components/terminal.py`、`yate/editor_components/palette.py`、
   `yate/flows/shell_flows.py`、`yate/editor_term/pty_proc.py`、
   `tools/mdlint/cli.py`、`tools/pack/wiki/lint.py`、`tools/pack/wiki/report.py`、
   `tests/test_workspace_filter.py`、`tests/test_architecture.py`、
   `.trae/documents/multi-dim-review-r2-plan.md`、`.trae/rules/architecture-boundaries.md`。
2. 每改完一组先跑该组验收命令，再进入下一组；避免一次改 16 个文件后无法定位回归。
3. 全部改完后由主代理**亲自**复跑六道门禁（命令见主计划 Step 5），真实退出码写入
   评审记录「修复后复核」段；blocker / major 归零方可收尾。
4. 收尾复核按 [code-review-expert](../agents/code-review-expert.md) 剧本派评审者，
   判死前给足 ≥30 分钟窗口并查落盘产物；零产出则主代理兜底自审并如实标注。

## 五、风险与回滚

| 风险 | 处置 |
|---|---|
| F6d bisect 假设 matches 有序被打破 | `next()` 的既有间接用例（前向/后向/回绕）+ 本轮新增 `test_nearest_index_bisect_boundaries`（经公开 `next()` 覆盖 cursor=0 / cursor=len / 前后向回绕 / 空集，避免 pyright `reportPrivateUsage`）；如任何用例失败立即回退该子项并降级为 Suggestion |
| F6e 新增索引与 `_resolved` 不同步 | 两处写入点成对修改；`teardown_all` 遍历 `loaded` 语义不变 |
| F4 在 reader 线程新增日志 | 仅 `log.debug`，tracing 默认静默，不改变线程/控制流 |
| F1 增量解码器改变既有截断用例行为 | `test_is_text_file_tolerates_a_cut_multibyte_sequence` 为守门用例，先跑旧用例再跑新用例 |
| 规则文本改动触发守卫 | F9 不改 `SIZE_EXEMPT_FILES` 集合内容，`pytest tests/test_architecture.py` 必须 37/37 |
| 修复引入回归 | 逐笔 `git revert` 回滚；分支独立、不推送 |
