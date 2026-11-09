# 评审记录：2026-11-08 · IKTR5Q 无用符号清理（unused-symbols-cleanup）

## 一、评审范围

| 项 | 值 |
| --- | --- |
| 分支 | `feature/enh-unused-symbols-cleanup`（HEAD `4b38989`） |
| 基线 | `master`（`fb3c398`） |
| 取 diff 口径 | `git --no-pager diff master...HEAD`（merge-base 三点） |
| 提交数 | 4（`1e094db` 领会素材 / `c304147` 方案 / `718ec79` wave-1 / `4b38989` wave-2） |
| 改动规模 | 31 文件 / +2382 / −52 |
| 其中代码与测试 | 20 文件（产品代码 12、测试 8，含新增 `tests/test_zero_arg_callbacks.py` 101 行） |
| 其中文档 | 11 文件（issue brief、总纲、6 子计划、登记表、删除清单） |
| 需求基线 | `unused-symbols-cleanup-issue-brief.md` / `unused-symbols-cleanup-plans/overview.md` / `unused-symbols-cleanup-keep-register.md` / `unused-symbols-cleanup-delete-list.md` |

评审前已按要求加载：`.trae/agents/code-review-expert.md`、`.trae/skills/python-code-review/SKILL.md`、`.trae/rules/` 下 8 份规则全文（architecture-boundaries / python-coding-style / doc-conventions / git-commit-message / misc-rules / plan-before-execute / subagent-workflow / task-orchestration）。
## 二、门禁实测表（全部为本次亲自实测，未引用他人数字）

| # | 命令 | 退出码 | 实测数字 | 判定 |
| --- | --- | --- | --- | --- |
| 1 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/` | **0** | `0 errors, 0 warnings, 0 informations` | PASS |
| 2 | `.venv\Scripts\python.exe -m pytest tests/ -q -n auto` | **1**（首跑） | 1 failed / gaps: `test_zero_arg_resize_handler_is_invoked_by_framework` | **FAIL（首跑）** |
| 3 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py` | **0** | `37 passed in 11.74s` | PASS |
| 4 | `.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` | **0** | `Total coverage: 92.95%`，TOTAL 19552 stmts / 1091 miss / 6246 branch / 571 BrPart | PASS |
| 5 | `.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4` | **0** | `121/121 scenarios passed`，`1464/1464 checks (100%)`，79.15s | PASS |
| 6 | `.venv\Scripts\python.exe -m tools.changelog check` | **0** | `released changelog sections are up to date`；21 segment / 20 version / 1713 entry | PASS |
| 7 | `git diff --check` | **0** | 无输出（无空白错误） | PASS |
| 8 | `.venv\Scripts\python.exe -m pytest tests/ -n auto`（复核，取用例总数） | **0** | `3473 passed, 10 skipped in 107.47s` | PASS |
| 9 | 串行复跑 `pytest tests/test_zero_arg_callbacks.py`（无 xdist，共 1+1+1 次独立运行） | 0 / 0 / 0 | 3 passed（第 1 次）；3 passed（第 2 次）；3 passed（第 3 次） | 见 §四 M-1 |
| 10 | 并行定向复现 `pytest tests/test_zero_arg_callbacks.py tests/test_app_textual.py -n 4` | **0** | 49 passed | 未能稳定复现 |

### 2.1 关于覆盖率首次运行的三次失败（环境事实，非被测代码问题）

首次以 `--cov` 并行运行时，`cov.log` 记录 `The following workers failed to return coverage data: gw0..gw7` 与 `Total coverage: 17.27%`；该次运行的 pytest 进程被本会话工具超时中断（日志仅 16–180 行、无 `N passed` 汇总行），导致 worker 覆盖率数据未回收。改用后台进程完整跑完后（第 4 条）覆盖率 **92.95%** 且退出码 0。此现象为评审侧执行环境截断所致，不计为被测代码缺陷；`cov.log` / `cov2.log` / `cov3.log` 等临时日志已在评审结束前删除，未入库。

### 2.2 本次改动所涉文件的分支覆盖率（取自第 4 条实测报告）

| 文件 | 覆盖率 |
| --- | --- |
| `yate/app.py` | 97% |
| `yate/cmdline_completions.py` | **100%** |
| `yate/editor_components/chrome.py` | 98% |
| `yate/editor_components/file_manager/model.py` | 99% |
| `yate/editor_components/view.py` | 94% |
| `yate/editor_components/manual.py` | 90% |
| `yate/editor_components/find_replace.py` | 87% |
| `yate/editor_components/terminal.py` | 84% |
| `yate/editor_core/buffer.py` | 97% |
| `yate/keymaps/base.py` | 99% |
| `yate/keymaps/vim.py` | 95% |

## 三、逐条审查结论（对应任务书 8 个重点审查项）

### 3.1 审查项 1：12 条删除项的全部调用点是否同步（含关键字实参）

**结论：PASS（无残留）。** 方法：先用 `git grep` 全仓扫 `session=` / `sort_key=` / `language=` / `type_char` / `cmdline_completions`，再用 AST 枚举 `on_resize` / `on_focus` / `watch_theme` / `build_row_text` / `cmdline_completions` 五类调用的**位置实参数与关键字名**。

AST 实测：五类目标函数的调用点共 **14 处**，全部符合新签名，无一处携带已删除的形参：

| 函数 | 调用点（AST 实测） | 位置实参 | 关键字实参 | 判定 |
| --- | --- | --- | --- | --- |
| `build_row_text` | `yate/editor_components/file_manager/screen.py:422` | 4 | `dir_child_count`, `icon_palette` | 同步 |
| `build_row_text` | `tests/test_file_manager_model.py:115,123,131,140,178,190,196` | 4 | `dir_child_count`(, `icon_palette`) | 同步 |
| `cmdline_completions` | `tests/test_app_find.py:337,475` | 2 | `commands`, `workspace` | 同步 |
| `cmdline_completions` | `tests/test_cmdline_completions.py:70,139,150` | 2 | `commands`, `workspace` | 同步 |
| `on_resize`（直接调用） | `tests/test_terminal.py:549` | 0 | — | 同步 |

补充核对：

- `cmdline_completions` 的另一处调用点是 `yate/editor_compose.py:128-133` 的 `functools.partial` 绑定，`partial` 不是 `ast.Call` 故不进上表；源码回读确认其关键字实参已只剩 `commands=` / `workspace=`（`yate/editor_compose.py:129-133`），符合新签名。
- `session=` 在全仓仍有 30+ 处命中，逐条核对**全部指向其它类**（`ExtensionContext` / `ShellFlows` / `OverlayFlows` / `HexFlows` / `DocumentFlows` / `subprocess(start_new_session=)` 等），无一处指向 `cmdline_completions`。
- `sort_key=` 剩余命中全部在 `yate/editor_components/file_manager/model.py` 的 `format_status_text` / `_status_parts` 等**其它函数**（`:235` / `:264` / `:277` / `:296` / `:316` / `:341`），`build_row_text` 已无该形参。
- `language=` 剩余命中全部指向 `TextBuffer.insert_newline(language=...)`（`yate/actions.py:40`、`tests/test_input_assist.py:396-947`），该 API **未被本次改动触碰**，属独立参数。
- `on_resize(Resize(...))` 形式在全仓已**零命中**（`git grep` 与 AST 双向确认）。
- `type_char` 全部 9 处调用点（`yate/keymaps/base.py:223`、`yate/keymaps/vim.py:498`、测试 7 处）均为单位置实参，无 `language=` 残留。

### 3.2 审查项 2：契约类是否误删

**结论：PASS（零误删）。**

| 契约类型 | 核对结果 | 证据 |
| --- | --- | --- |
| pytest fixture 形参 | 零删除 | `tests/` 域删除数 = 0（删除清单 §一 对账表，`tests/` 判定删除 0） |
| Protocol 方法 | 零删除 | 22 条 `protocol` / `protocol:host-mirror` 全在保留侧（登记表分类小计） |
| `@override` 覆写 | 零删除 | 3 条 `override` 全在保留侧；`manual.py:265` 等未动 |
| 开放 API / 插件手册成员 | 零删除 | `open-api:cli-surface` 1 条（`tools/pack/wiki/run.py:198 force`）保留 |
| `_` 解包占位 | 零删除 | 215 条 `unpack-placeholder` 全保留 |
| 命令注册表回调 | 零删除 | 27 条 `framework-fixed-signature:command-registry` 全保留（`yate/commands.py` 未出现在 diff 中） |
| 平台占位构造契约（D10） | **已正确回退** | `yate/editor_term/pty_proc.py` 实测 `git diff master...HEAD` **输出为空**（零 diff），与 D10 记载一致 |
| `tools/` 场景 driver 与 monkeypatch 桩 | 零删除 | 4 条 `framework-fixed-signature:scenario-driver` + 2 条 `test-stub-signature:monkeypatch` 全保留；`tools/` 域删除数 = 0 |

### 3.3 审查项 3：`git diff` 是否只含签名 / 调用点实参 / docstring / 连带未使用导入

**结论：PASS。** 20 个代码与测试文件的 hunk 已逐条通读，变更性质归类如下：

| 变更性质 | 出现位置 |
| --- | --- |
| 签名删除形参 | `yate/app.py:186`、`chrome.py:163,313`、`diff/pane.py:282`、`find_replace.py:197`、`manual.py:442`、`terminal.py:265`、`view.py:175,237`、`cmdline_completions.py:16-23`、`file_manager/model.py:177-184`、`buffer.py:856` |
| 调用点实参删除 | `yate/editor_compose.py:131`、`yate/keymaps/base.py:223`、`yate/keymaps/vim.py:498`、`file_manager/screen.py:422`、测试 8 文件 |
| docstring 同步 | `cmdline_completions.py:1-7`、`file_manager/model.py:196-199`、`buffer.py`（删 `*language* is the seam...` 段） |
| 连带未使用导入删除 | `textual.events.Resize`（`chrome.py` / `diff/pane.py` / `find_replace.py` / `terminal.py` / `view.py`）、`textual.events.Focus`（`view.py`）、`yate.session.EditorSession`（`cmdline_completions.py`）、`YateConfig`/`EditorSession`（`tests/test_cmdline_completions.py`） |
| 测试用例修复 | `tests/test_terminal.py:549`（`on_resize()`）、`tests/test_app_textual.py:521-524`（`wait_until` 轮询） |
| 新增测试 | `tests/test_zero_arg_callbacks.py`（101 行） |

**未见**任何函数体语义改动、返回值/返回类型变化、公开 API 变化、CLI 行为变化。旁证：`pyproject.toml` 与 `.trae/rules/` 实测 `git diff` **均为空**（架构规则 R1-R15 文本零改动，故不存在边界规则变更）；`yate/editor_term/pty_proc.py` 零 diff。

### 3.4 审查项 4：是否新增豁免注释 / `Any` / `TYPE_CHECKING` / linter / `pyproject.toml` 改动；注释是否英文 ASCII

**结论：PASS（全部为 0）。** 实测方式：对 `git diff master...HEAD -- yate/ tests/ tools/ pack/` 导出的新增行（`^+`）做两条正则过滤：

| 检查项 | 正则 | 命中数 |
| --- | --- | --- |
| `# type: ignore` / `pyright: ignore` / `# noqa` / `TYPE_CHECKING` / `Any` | `^\+.*(type: ignore\|pyright: ignore\|noqa\|TYPE_CHECKING\|\bAny\b)` | **0** |
| 非 ASCII（CJK / 全角 / 排版符号） | `^\+.*[^\x00-\x7F]` | **0** |

另：`git diff master...HEAD -- pyproject.toml .trae/rules/` 输出为空，确认未引入 linter、未改门禁配置、未新增 `NON_ASCII_COMMENT_EXEMPT` 等守卫豁免。新测试 `tests/test_zero_arg_callbacks.py` 的 `Any` 命中数亦为 0（其 docstring 全英文 ASCII）。

### 3.5 审查项 5：新增 `tests/test_zero_arg_callbacks.py` 与 `test_app_textual.py` 修复的规则符合性

**结论：基本 PASS，一处 MINOR（见 §四 m-1）。**

| `python-coding-style.md` 要求 | 实测 | 判定 |
| --- | --- | --- |
| `from __future__ import annotations` 在 docstring 后、其它导入前 | `:1-9`（docstring → 空行 → `from __future__`） | 合规 |
| 完整注解（参数 + 返回值） | 3 个测试函数均 `-> None`；内层 `scenario() -> None`；`watch_calls: list[str]` / `resize_calls: int` / `baseline: int` / `before: Color` / `after: Color` 均有变量注解 | 合规 |
| 散文式 docstring（无 `:param:` / `Args:`） | 模块 docstring + 3 个函数 docstring 均为单行散文摘要 | 合规 |
| `App[None]` 精确标注（§六 #21 能力注入守卫） | `:24` `class WatcherApp(App[None])`、`:60` `class ResizeApp(App[None])`；无 `App[Any]` / `App[object]` | 合规（该守卫实测通过） |
| 绝对导入（禁 `from .`） | 全部 `from yate.*` / `from textual.*` | 合规 |
| `@override` 覆写 | `:31`、`:61` 的 `compose` 均带 `@override` | 合规 |
| 禁止真实睡眠 | 全文件无 `asyncio.sleep` / `time.sleep`，只用 `pilot.pause()` | 合规 |
| `finally` 恢复主题 | `:96-99` `finally: yate_theme.set_theme("mocha")` | 合规 |
| 顶层 import 分组 | `:80` `from textual.color import Color` 与 `:82` `from yate.editor_components import theme as yate_theme` 置于**函数体内** | 见 §四 m-1（`tests/` 既有惯例如 `tests/test_app_explorer.py:56`、`tests/test_app_lsp.py:83` 同形态，非本次引入的新违规模式） |

`tests/test_app_textual.py:518-524` 的 `wait_until` 修复：复用 `tests/conftest.py:311-331` 的轮询工具（`timeout=5.0` / `step=0.01`），符合 §4.7「用 `wait_until` 轮询谓词」的明文指向。

### 3.6 审查项 6：登记表与删除清单对账、六类齐全性、逐条格式、文档规范

**结论：PASS（对账完全闭合）。**

| 核对项 | 实测 | 判定 |
| --- | --- | --- |
| 登记表条目数 | 以 `^\| \`[^\`]+:\d+\`` 计数 = **1243** | 与声明一致 |
| 删除清单条目数 | 12（`delete-list` §二 表 2.1 九条 + 2.2 三条） | 与声明一致 |
| 1243 + 12 = 1255 | 成立 | PASS |
| 分类小计自洽 | 21 个类别小计求和实测 = **1243** | PASS |
| 六类齐全 | `pytest-fixture` 112 / `protocol`+`protocol:host-mirror` 22 / `override` 3 / `open-api:cli-surface` 1 / `unpack-placeholder` 215 / `framework-fixed-signature*` 39（含 `platform-placeholder` 2） | 六类齐全 |
| 逐条格式 `文件:行号 → 类别 → 保留理由` | 登记表头部声明格式；抽样行如 `unused-symbols-cleanup-keep-register.md:835`（`tests/test_cmdline_completions.py:45` / `_args` / param / 理由）符合 | PASS |
| 文档引用本机绝对路径（`doc-conventions.md` §五） | 对 4 份 IKTR5Q 文档 + 6 子计划做 `[A-Za-z]:\\`、`[A-Za-z]:/`、`/home/`、`/Users/` 扫描 = **0 命中** | PASS |
| 命名符合 §一 | 总纲目录 `unused-symbols-cleanup-plans/overview.md`；子计划 `unused-symbols-cleanup-<subtask>-plan-<a..f>.md`；全小写连字符 | PASS（`overview.md` 而非 README，符合 §一） |
| 单计划是否超 1MB | 最大文件 `unused-symbols-cleanup-keep-register.md` = **136128 字节**（约 133 KB）；6 子计划各 3.5–5.1 KB | PASS（远低于 1 MB） |

### 3.7 审查项 7：4 笔提交信息与「只提交不推送」

**结论：PASS。**

| 提交 | 标题 | 规范判定 |
| --- | --- | --- |
| `1e094db` | `docs(plan): record IKTR5Q issue brief for unused-symbol cleanup` | 合规（`type(scope): subject`，英文） |
| `c304147` | `docs(plan): add IKTR5Q cleanup plan with keep register and delete list` | 合规 |
| `718ec79` | `refactor(app): drop unused Textual callback parameters (wave-1)` | 合规 |
| `4b38989` | `refactor(editor): drop unused internal parameters (wave-2)` | 合规 |

4 笔主题与消息体**全部英文**，`type` 取值均在 `git-commit-message.md` §5 允许集（`docs` / `refactor`）内。分波提交符合 `task-orchestration.md` §二「每步单独提交一次」。

推送状态：`git status --short --branch` 实测 `## feature/enh-unused-symbols-cleanup...origin/feature/enh-unused-symbols-cleanup [ahead 3]` —— 领先 origin 3 笔，**未推送**，符合「只提交不推送」。

### 3.8 审查项 8：根目录临时探针是否被误入库

**结论：PASS（未入库）。** `git status --short` 中 `_ast_candidates.md` / `_ast_facts.md` / `_ast_probe_calls.json` / `_ast_probe_output.json` / `_ast_verdicts.json` 均为 `??`（untracked）；`git diff --stat master...HEAD` 的 31 个文件清单中**无**任何 `_ast_*` / `_callback_probe.py` 条目，提交历史中也无。本次评审自身产生的临时日志（`cov*.log` / `smoke.log` / `full_run.*` / `_probe_ast.txt` 等）已在评审结束前全部删除，工作区仅余交付方原有的 5 个探针文件。

## 四、Issue 清单（按严重度排序）

**统计：BLOCKER 0 / MAJOR 1 / MINOR 1**（另有 1 条初判 MINOR m-2 经复核为误报，已撤销，见该段）。

### [MAJOR] M-1 `tests/test_zero_arg_callbacks.py:73` 新增的 0 参数 `on_resize` 证据用例本身是时序 flaky

**位置**：`tests/test_zero_arg_callbacks.py:49-75`（断言在 `:73`）

**问题**：该用例在**全量并行首跑**中失败（`pytest tests/ -q -n auto` 退出码 1，`assert 1 > 1`），随后串行复跑 3 次全部通过、并行定向复跑（`-n 4`）亦通过。即：**并非确定性缺陷，而是负载下的时序假设**——`pilot.resize_terminal(120, 40)` 之后只等一次 `pilot.pause()`，在繁忙事件循环下 `resize` 事件可能尚未派发到 widget，`baseline`（挂载期已计入的 1 次）未再增长。

与规则的关系：`python-coding-style.md` §4.7 明文「禁止依赖真实睡眠时长做断言……或用 `wait_until` 轮询谓词——并行负载下『睡够就行』的假设会 flake」；issue brief §五.2 与总纲 §六 同样要求「并行下出现时序 flake 必须用 `-n 1` 复核并修用例，**不得记成偶发**」。本用例正是被 §4.7 点名的那种形态。

**为何定 MAJOR 而非 MINOR**：这不是风格问题，而是「合并硬门槛命令出现非确定性失败」——`pytest tests/ -q -n auto` 是 CI 与本地唯一回归口径，一个 flaky 用例会让门禁结果不可信，且按规则不能以「偶发、重跑即过」结案。

**修复建议**（与该波已采用的修法保持同一形态）：把一次性 `pause` + 单帧断言换成 `wait_until` 轮询，例如：

```python
assert await wait_until(pilot, lambda: widget.resize_calls > baseline)
```

（`wait_until` 来自 `tests/conftest.py:311`，`timeout=5.0` / `step=0.01`，与 `tests/test_app_textual.py:521-524` 同一写法。）

**备注**：同一波修复的 `tests/test_app_textual.py:518-524` 已正确采用 `wait_until`（见 §3.5，判定合规），说明该修法在本波内已被掌握，本处属遗漏而非方法缺失。

### [MINOR] m-1 `tests/test_zero_arg_callbacks.py:80-82` 函数体内局部 import

**位置**：`tests/test_zero_arg_callbacks.py:80`（`from textual.color import Color`）与 `:82`（`from yate.editor_components import theme as yate_theme`）

**问题**：`python-coding-style.md` §1.3 规定导入按「标准库 / 第三方 / 项目内部」分组置于模块头。这两行放在 `test_yate_app_watch_theme_repaints_on_theme_change` 函数体内，严格读规则属偏离。

**严重度理由（为何只记 MINOR 而非 MAJOR）**：`tests/` 目录该形态是长期既有惯例——`tests/test_app_explorer.py:56,87,103,109,121`、`tests/test_app_lsp.py:19,83,84,124`、`tests/conftest.py:74` 等数十处同形态，且多为例内 `monkeypatch` / 局部依赖注入口（与本用例用 `finally` 收尾的局部主题操作同构）。规则 §1.3 未单列 `tests/` 例外条款，但按 skill「若文件其余部分使用一致的、不同于 PEP 8 的既有风格，只记一次而非逐处上报」，且报告纪律要求「不做无谓的风格挑剔」，故定 MINOR、不阻塞。

**修复建议**：若择机清理，把两行提到模块头（`from textual.color import Color` 归第三方组、`from yate.editor_components import theme as yate_theme` 归项目组），并把 `Color` 的类型注解同步为模块级导入；不在本次阻塞范围内。

### 已撤销：m-2 经复核为误报（保留痕迹以便追溯，不计入统计）

原初判：总纲 `overview.md:69` 的 `@override` 摘要行「`yate/editor_components/manual.py:265 get_content_height`」行号有误（我以为 `:265` 附近不是 `get_content_height`）。

**复核结果：误报，已撤销。** 实测 `Select-String -Path yate/editor_components/manual.py -Pattern get_content_height` 输出 `265: def get_content_height(self, container: Size, viewport: Size, width: int) -> int:` —— 行号**完全正确**，`overview.md:69` 的表述与源码一致。初判源于我把「同文件中 `on_resize` 有两处（`:326` 保留 / `:442` 删除）」误迁移到了 `get_content_height` 上。

**处置**：条目删除，不计入 §四 issue 统计。此条保留仅作自我批判过程留痕（剧本要求「删除与降级的条目附一句理由，确保批判过程可追溯」）。

## 五、强制自我批判记录

按剧本要求，初版清单完成后逐条反证，结论登记如下。

### 5.1 已删除的初判（误报剔除）

| 初判 | 反证依据 | 处置 |
| --- | --- | --- |
| 覆盖率门禁失败（`Total coverage: 17.27%`、`Required test coverage of 75% not reached`） | 三个 `cov.log` 均无 `N passed` 汇总行且行数仅 16–180，证明 pytest 被本会话工具超时中断，8 个 worker 覆盖率数据未回收；改后台完整跑完后为 `92.95%`、退出码 0。上下文推翻「覆盖率跌破门禁」的结论 | **删除**（改记为 §2.1 评审环境事实） |
| 「`session=` 仍有 30+ 处残留未清理」 | 逐条回读命中行：`tests/test_events.py:155` / `tests/test_extension_api.py:78` / `tests/test_hex_view.py:534` / `yate/flows/overlay_flows.py:312` / `yate/editor_compose.py:179` 等均指向**其它类**的 `session` 形参，无一指向 `cmdline_completions`；AST 调用点表 14 条亦零残留 | **删除** |
| 「`language=` 残留未清理」 | 全部命中指向 `TextBuffer.insert_newline(language=...)`（`yate/actions.py:40` 等），该 API 未在删除清单内 | **删除** |
| 「`sort_key` 未清理干净」 | 剩余命中均在 `format_status_text` / `_status_parts` 等其它函数（`model.py:235,264,277,296,316,341`），`build_row_text` 已无该形参 | **删除** |
| 「删除清单行号 `terminal.py:266`、`view.py:177/239`、`cmdline_completions.py:17` 与当前源码 `:265` / `:175,237` / `:16` 不符」 | 对 `git show master:<file>` 逐行复核：master 上正是 `terminal.py:266`、`view.py:177`、`view.py:239`、`cmdline_completions.py:17`。清单记录的是**删除前**位置，删除形参后行号前移 1，属正常偏移 | **删除**（不构成缺陷） |
| 「`tests/test_zero_arg_callbacks.py` 缺测试覆盖 9 个回调中的多数」 | 该文件定位是「框架 0/1/2 参数分派契约」的**形态证据**（`invoke` / `invoke_watcher` 裁剪实参），非逐个回调的回归；逐个回调由既有 pilot 用例覆盖（`tests/test_app_find_replace.py:979,983`、`tests/test_app_manual.py:616`、`tests/test_chrome.py`、`tests/test_diffview.py`、`tests/test_app_terminal.py`、`tests/test_terminal.py:549`），且框架 `textual/message_pump.py:821-829` 对同一消息遍历 MRO 逐个 `invoke`，`textual/_callback.py:45-56` 的 `params[:parameter_count]` 是稳定契约。要求逐回调建用例属超出 issue 范围的加码 | **删除** |

### 5.2 降级记录

| 初判级别 | 最终级别 | 理由 |
| --- | --- | --- |
| `tests/test_zero_arg_callbacks.py:73` flake 定为 BLOCKER | **MAJOR** | 经 3 次串行 + 1 次 `-n 4` 定向复跑均通过，排除确定性缺陷；且不涉及安全/数据丢失/常规使用崩溃，不符合 blocker 定义。但其确在合并硬门槛命令中产生非确定性失败，不满足 minor 的「非阻塞」语义，故落在 MAJOR |
| 函数内局部 import 定为 MAJOR | **MINOR** | `tests/` 数十处同形态既有惯例（`test_app_explorer.py` / `test_app_lsp.py` / `conftest.py`），非本次引入的新模式；不改变行为、不影响门禁 |

### 5.3 漏报自查（六维度反向扫描）

| 维度 | 复查结论 |
| --- | --- |
| 正确性 | 12 条删除项的函数体均未变动（diff 逐条确认）；形参在函数体内无 `Load` 引用（删除清单已记 AST 事实，与回读一致）。框架分派契约由 `textual/_callback.py:45-56`（`callback(*params[:parameter_count])`）与 `textual/message_pump.py:821-829`（MRO 逐 handler `invoke`）双重实证。**无新增发现** |
| 边界条件 | 0 参数回调在**挂载前**被调用的情况：`yate/app.py:192` 的 `if self.screen_stack:` 卫语句仍在（本次未改），挂载前 no-op 语义保持。`build_row_text` 删 `sort_key` 后，`dir_child_count` 未传时走 `None` 分支，`tests/test_file_manager_model.py:196` 已覆盖「(` 不存在」分支。**无新增发现** |
| 异常处理 | diff 中无新增 `except` / 无吞异常；`tests/test_zero_arg_callbacks.py:96-99` 的 `finally` 只做主题恢复（非吞异常）。**无新增发现** |
| 并发安全 | 本次无共享状态改动。`tests/test_zero_arg_callbacks.py` 用 `finally` 全局复原主题 `mocha`，避免跨用例主题泄漏（并行 worker 各自进程，无跨进程污染）。**无新增发现** |
| 性能 | 无新增循环/IO；删形参不改变调用开销。冒烟 121 场景 79.15s、全量 3473 用例 107.47s，无退化迹象。**无新增发现** |
| 类型与测试覆盖 | pyright 0/0/0；新增代码的对应文件覆盖率 84%–100%（§2.2），全量 92.95% ≥ 75；架构 37 守卫通过。**无新增发现** |
| 架构边界（R1-R15） | `.trae/rules/architecture-boundaries.md` 与 `tests/test_architecture.py` 均**零 diff**，改动不新增任何 import 连线；被删的 `textual.events` / `yate.session` 导入属本文件内未使用导入，方向不变。**无新增发现** |

### 5.4 结论登记汇总

| 状态 | 条目 |
| --- | --- |
| 确认保留 | M-1（`tests/test_zero_arg_callbacks.py:73` flake）、m-1（`:80-82` 函数内 import） |
m-1 由 MAJOR→MINOR（理由见 §5.2）
| 撤销 | m-2：实测推翻，`yate/editor_components/manual.py:265` 确为 `get_content_height` |
| 撤销 | m-2：实测推翻，`yate/editor_components/manual.py:265` 确为 `get_content_height` |
| 删除 | 覆盖率跌破门禁、`session=`/`sort_key=`/`language=` 残留、清单行号偏移、新测试未逐回调覆盖（理由见 §5.1）；**m-2（`manual.py:265` 行号）经复核为误报，已撤销**——实测 `get_content_height` 确在 `:265`，`overview.md:69` 表述正确 |

## 六、最终裁决

**REQUEST_CHANGES**

理由：存在 1 条 MAJOR（`tests/test_zero_arg_callbacks.py:73` 的 flake 用例使合并硬门槛 `pytest tests/ -q -n auto` 出现非确定性失败）。按 `task-orchestration.md` §二.6「存在 blocker / major → 回到步骤 2 重新设计；仅 minor → 登记待办」与 issue brief §五.2「不得记成偶发」，须修复该用例后重新跑全量门禁方可合并。

修复成本很低（一处断言改为 `wait_until` 轮询，与同波 `test_app_textual.py:521-524` 完全同构），且**产品代码侧结论为 PASS**：12 条删除项调用点全部同步、契约类零误删、`pty_proc.py` 零 diff、无豁免注释与 `Any`/`TYPE_CHECKING`、对账 1243+12=1255 闭合、提交信息合规、只提交未推送。

## 七、未解决项

1. **M-1 未修复**（MAJOR，阻塞合并）：`tests/test_zero_arg_callbacks.py:73` 需改用 `wait_until` 轮询；修复后须重跑 `pytest tests/ -q -n auto` 与 `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` 并附退出码。
2. **flake 复现率未定量**：首跑 1 次失败 / 后续 4 次通过，样本量不足以给出概率估计；修复后建议按 `python-coding-style.md` §4.7 在并行负载下重复验证。
3. **m-1 / m-2 不阻塞**，登记为待办。
4. **`cov` 并行首跑失败的根因定性**：已确认是评审侧工具超时截断（非被测代码），但同一环境下的两次 `--cov` 尝试均复现该截断，后续评审建议对长时命令统一用后台进程 + 日志落盘再读取。

## 八、实测命令回执（可复核）

```text
pyright yate/ tests/ tools/ pack/          -> exit 0,  0 errors 0 warnings 0 informations
pytest tests/ -q -n auto                  -> exit 1,  1 failed (test_zero_arg_resize_handler_is_invoked_by_framework)
pytest tests/test_architecture.py         -> exit 0,  37 passed in 11.74s
pytest tests/ --cov --cov-branch -n auto  -> exit 0,  coverage 92.95% (>= 75)
tools.smoke_test run --jobs 4             -> exit 0,  121/121 scenarios, 1464/1464 checks
tools.changelog check                     -> exit 0,  released sections up to date
git diff --check                          -> exit 0,  (no output)
pytest tests/ -n auto (rerun)             -> exit 0,  3473 passed, 10 skipped in 107.47s
pytest tests/test_zero_arg_callbacks.py   -> exit 0 x3 (serial, no xdist), 3 passed each
pytest test_zero_arg_callbacks + app_textual -n 4 -> exit 0, 49 passed
```

> 说明：本记录只记录发现与核对结论，修复排期见后续 `<task>-plan.md`（按 `doc-conventions.md` §2.2，评审记录与修复方案互相链接）。

## 九、迭代波 F1（主代理执行，2026-11-08）

原裁决 `REQUEST_CHANGES` 原文保留，本节只登记修复与复核事实。

| 评审项 | 严重度 | 修复 | 文件 |
| --- | --- | --- | --- |
| M-1：全量并行首跑 `assert 1 > 1` | MAJOR | 断言移回 `async with app.run_test()` 上下文内，改为 `assert await wait_until(pilot, lambda: widget.resize_calls > baseline)`（`from conftest import wait_until`），与 `tests/test_app_textual.py:521-524` 同构 | `tests/test_zero_arg_callbacks.py:65-79` |
| m-1：函数体内局部 import | MINOR | `Color` / `yate_theme` 提到模块顶层，按标准库 / 第三方 / conftest / 本地分组 | `tests/test_zero_arg_callbacks.py:9-20` |
| 收尾门禁新发现：`assert "replaced 3" in message_text(app)` 瞬态消息裸断言 | 既有 flake（§4.7） | 轮询谓词用 `nonlocal seen_report` 闩锁捕获报告，同时仍要求两个文件写入落地 | `tests/test_app_find_replace.py:541-560` |

**M-1 修复后复核**：pyright `0/0/0`；
`pytest tests/test_zero_arg_callbacks.py tests/test_app_textual.py -q -n 4` 重复 3 次 exit `0/0/0`；
`pytest tests/test_architecture.py -q` 37 passed；`pytest tests/ -q -n auto` exit 0。

## 十、收尾全量门禁（主代理亲自实测）

| # | 命令 | 退出码 | 实测数字 |
| --- | --- | --- | --- |
| 1 | `pyright yate/ tests/ tools/ pack/` | 0 | `0 errors, 0 warnings, 0 informations` |
| 2 | `pytest tests/ -q -n auto` | 0 | 全量通过（`-q` 无汇总行，按退出码判定） |
| 3 | `pytest tests/test_architecture.py -q` | 0 | 37 passed |
| 4 | `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` | 0 | `92.96%`，`3473 passed, 10 skipped in 163.61s` |
| 5 | `tools.smoke_test run --jobs 4` | 0 | `121/121 scenarios`、`1464/1464 checks (100%)`、`exit 0` |
| 6 | `tools.changelog check` | 0 | released sections up to date |
| 7 | `git diff --check` | 0 | 无输出 |

覆盖率首次后台运行（与冒烟并发负载）出现 1 处真实失败：
`tests/test_app_find_replace.py::test_project_replace_end_to_end_open_edit_replace` 的
瞬态消息裸断言（`assert 'replaced 3' in '[#6c7086] Ready. Press F1 for help.[/]'`）。
按 `task-orchestration.md` §二.7 与 `python-coding-style.md` §4.7 修用例后，后台重跑
第 4 条得到 exit 0，不记为「偶发」。另一次隔离第 3 次单跑的 exit 1 是本机
`safe-delete` 钩子（`count=18729 > 9999`）在 pytest 收尾清理阶段杀进程，输出无 FAILED，
属环境而非用例；处置见总纲 §七 D15（每道门禁拆独立工具调用轮次、不擅清 `%TEMP%`）。

> 补正（2026-11-08 第二轮复验）：首轮 §十 第 5 条「冒烟 `--jobs 4` exit 0」
> 只代表当时的单次实测。第二轮复验实测 `--jobs 4` 下 `stress.py:157`
> `toggles_back` 负载敏感（2/4 次 `120/121`、`1463/1464`），
> `--jobs 1` 为 `121/121`、`1464/1464 (100%)`，第 3 次 `--jobs 4` 亦通过。
> 该用例相关提交 `c9f5589` / `81f8486` 均在 `master` 基线内（`merge-base
> --is-ancestor` 为真），非本任务引入，按复验裁决登记为遗留待办 m-1。
> 覆盖率 92.96% → 92.94% 属并行采样抖动（分母 19552 / 6246 未变）。

## 十一、迭代后裁决状态

0 BLOCKER / 0 MAJOR / 0 MINOR 未闭环；M-1、m-1 与收尾门禁新发现的 flake 均已修复，
产品代码零改动（迭代只触及 2 个测试文件）。原 `REQUEST_CHANGES` 记录保留，
待第二轮评审复验后归档。
