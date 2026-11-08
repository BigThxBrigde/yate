# 2026-11-09 IKTR5Q 合并前 PR 级预评审记录

> 模式：`review`（[`pr-review` skill](../skills/pr-review/SKILL.md) 默认模式，六维度 + 裁决）。
> 基线 `master` `fb3c398`，范围整条分支 `master..HEAD`（35 文件，`+3009 / -57`），
> 非单文件/片段。主计划
> [`iktr5q-pr-review-plan.md`](../documents/iktr5q-pr-review-plan.md)。
> **AI 预评审，不合并、不推送；最终合流决策归人工评审者。**

Overall: **APPROVE** — 0 BLOCKER / 0 MAJOR / 4 MINOR（2 项已修复，2 项登记待办）

## 一、范围与噪声过滤（skill §一）

`git merge-base master HEAD = fb3c398`；`master` 与 `origin/master` 同步。提交链
8 笔：`1e094db` → `c304147` → `718ec79` → `4b38989` → `179fdf6` → `84074b1` →
`737f186` → `121e291`。35 个改动文件均为源码 / 测试 / 计划 / 评审 / 登记表文档；
diff 内无 `*.pyc`、lock 文件、`*.spec`、二进制资产、`.venv/` 内容，纯格式 hunk
合并进 MINOR 一次性说明，**无噪声可跳过**。

## 二、六维度结论（skill §三）

| # | 维度 | 结论 | 可验证证据 |
| --- | --- | --- | --- |
| 1 | 功能正确性 | 未发现 | 12 条删除项的 17 处调用点全部同步；`git grep -n -E "(session\|sort_key\|language)\s*=" -- <8 个调用点文件>` 无残留对已删函数的调用（剩余命中均为 `insert_newline(language=...)`、`set language=auto` 字符串与其它对象的 `session=` 注入）；`view.on_resize()` 是唯一直接调用；`yate/editor_term/pty_proc.py` 不在 35 文件清单（D10 零 diff）；产品源码 diff 逐 hunk 只见签名 / 实参 / docstring / 连带导入删除，函数体零改动；三处 `wait_until` 修复保留原有 `except OSError: return False` 语义 |
| 2 | 安全性 | 未发现 | 新增代码行扫描 `shell=True`、`pickle`、`eval(`、`exec(`、hardcoded secret、路径穿越反模式 = 0 命中；本 diff 不含 I/O 或命令构造代码 |
| 3 | 性能 | 未发现 | 改动为形参删除与调用点实参删除，未引入循环、I/O、重复计算或字符串拼接；`*.py` 新增行无 >100 字符行 |
| 4 | 可维护性 | 1 条 MINOR（已修复） | `tests/test_zero_arg_callbacks.py` 顶层导入按标准库 / 第三方 / conftest / 本地分组，无函数体内局部 import；注释与 docstring 英文 ASCII；`python-coding-style.md` §五 快速清单可观察项通过；新增行扫描无 `TYPE_CHECKING`、`: Any`、`# type: ignore`、`# noqa`、裸 `except:` |
| 5 | 架构边界 | 未发现 | diff 无新增 import（只有删除），无新增 `Protocol` / `*Feature` / `*Host` / `*Ops` / `*Delegate` / `*Controller` 命名，无 R9 widget id 变化、无 R12/R13 归属变化、无架构守卫豁免或 `pyproject.toml` 改动；架构测试 37 passed |
| 6 | 硬门禁 | 全绿（见 §五） | 主代理亲自逐条实测，7 项退出码全 0 |

## 三、Findings

### [MINOR] `.trae/documents/iktr5q-pr-review-plan.md:37` — 文档内出现本机真实盘符路径（已修复）

Problem: 主计划【领会】范围表把工作目录写成反引号包裹的真实盘符路径，违反
`doc-conventions.md` §五「禁止盘符路径 / 文档不得暴露本机真实路径」；该行是本轮
PR 新增（`git diff master...HEAD -- '*.md'` 命中 `+` 行）。

Fix: 改为可移植写法「续作复用既有 worktree（分支目录，含 `.venv`），不另建沙箱」，
取证命令保留相对写法 `.venv\Scripts\python.exe ...`。修复后对该文件扫描
`[A-Za-z]:[\\/]|/home/|/Users/` = 0 命中。提交 `121e291`。

### [MINOR] `.trae/documents/unused-symbols-cleanup-keep-register.md:1393`、`.trae/reviews/2026-11-08-pr-review-iktr5q-unused-symbols-cleanup.md:336` — 文件末尾多余空行（已修复）

Problem: `git diff --check master...HEAD` 退出码 **2**，两处 `new blank line at EOF`。
上一轮只检查工作树 `git diff --check`（干净时无输出），未检查**累积分支 diff**，
故漏到合并前才暴露。

Fix: 删除两个文件末尾各 1 个空行（字符级 diff 为 `1 deletion` × 2，无整文件重写）。
提交 `121e291`；复验 `git diff --check master...HEAD` 退出码 0。

### [MINOR] `yate/editor_core/buffer.py:856` — 删除 `language` 形参抹掉了 docstring 明确记录的前瞻扩展缝（观察项，不阻塞）

Problem: master 基线 `type_char(self, ch: str, *, language: str = "plaintext")` 的
docstring 明确写「*language* is the seam that keeps the feature extensible per
language ... V1 reads it not at all ... dispatch on the value right here -- no
keymap change needed」，keymaps 传 `ctx.doc.filetype`。本分支删掉形参、3 处关键字
实参调用点与整段 docstring。删除**技术上成立**（函数体零 `Load` 引用），但设计意图
被移除：未来若 `pair_for` 按语言分化，需重新给 `type_char` 加参数并改回
`yate/keymaps/base.py` / `vim.py` 两处调用。

Fix（可选，非必须）：把该形参登记为「有意保留的扩展缝」并恢复签名 + docstring 段 +
3 处调用点（4 文件），对账由 12 删 / 1243 留改为 11 删 / 1244 留；或维持删除并在
计划中记录未来恢复成本（3 行）。裁决：不阻塞合并，按 §四 反馈环登记。

### [MINOR] `179fdf6` — 提交 type `test` 不在 `git-commit-message.md` §5 允许集（登记待办）

Problem: §5 允许集为 `feat|fix|refactor|docs|chore`，该笔用 `test(callbacks):`；
主题与消息体英文、`type(scope): subject` 格式均合规，其余 7 笔 type 全在允许集。

Fix: 该提交已存在于历史且未推送；按 git 安全协议不擅自 `amend` / `rebase` 改写历史，
也不擅自扩大规则允许集。登记为规则层待办（#68 复验已提出同一项），由规则维护者决定。

## 四、反馈环（skill §五）

用户 2026-11-09 质疑 `ctx.buffer.type_char(key, language=ctx.doc.filetype)` 为什么要移除
`language`。主代理**重跑受影响维度**（功能正确性 / 可维护性 / 开放 API）：

- 取证：`git --no-pager diff master...HEAD -- yate/editor_core/buffer.py yate/keymaps/base.py yate/keymaps/vim.py tests/test_input_assist.py`；
  `git --no-pager show master:yate/editor_core/buffer.py` 的 `type_char` 与
  `insert_newline` 实现；`yate/docs` 下 `type_char|insert_newline` 搜索 = **0 命中**。
- 事实：`type_char` 函数体确实零 `Load` 引用 `language`（docstring 自述 "V1 reads it
  not at all"）；3 处带 `language=` 的调用点全部同步，另有 7 处仅位置参数调用不受影响；
  `TextBuffer` 是 L0 内部模型、插件手册未引用，非开放 API；同模块
  `insert_newline(*, language=...)` **保留**，因为它真的用 `rules_for(language)` /
  `opens_block` 做按语言缩进 —— 这正是「未使用才删」的边界。
- 结论：删除符合 IKTR5Q issue §二 点名的「纯内部签名候选」与「能安全删除的全部删除」，
  且七道门禁全绿；但确实移除了被 docstring 明确记录的前瞻设计意图 → **新增上述 1 条
  MINOR 观察**，不升级为 MAJOR（不改变语义/返回类型，恢复成本 3 行）。
- 既有 findings **未撤销**：EOF 空行与文档路径仍属实且已修复；本轮未重新提出已被
  #68 销账的 M-1/m-1。

### 反馈环补充（2026-11-09 第二问：`:set filetype=language` 是否失效）

用户追问删除 `type_char` 的 `language` 后 `:set filetype=...` 是否还起作用。主代理
重跑**功能正确性**维度：

- `git --no-pager diff master...HEAD --name-only` 过滤 `commands.py` / `session.py` /
  `indentation.py` / `editor_syntax` / `editor_lsp` / `options` = **0 命中**，即
  `:set filetype` 的实现与主要消费者全部零改动。
- 实现链仍在：`yate/commands.py:49-51` `_apply_filetype` → `editor.set_filetype(...)`；
  `:set` 键 `yate/commands.py:137` `_FILETYPE_KEYS = {"filetype","ft","language","lang"}`；
  `:filetype` 命令 `yate/commands.py:454-478`（`:ft` / `:language` 别名与 Tab 补全）；
  `yate/config.py:322-326` 的 `filetype=` 选项解析。
- 真正消费 `Document.filetype` 的路径完整保留：`yate/actions.py:40`
  `ctx.buffer.insert_newline(language=ctx.doc.filetype)`（按语言缩进，走
  `rules_for(language)` / `opens_block`）；`yate/commands.py:459` 的
  `language_name(doc.filetype)` 状态栏 / `:filetype` 回显；语法高亮
  `highlight_probe().filetype`；LSP `language_ids` 映射；插件手册
  `yate/docs/extensions.*.md` 把 `doc.filetype` 列为扩展开放 API，
  `:set filetype=<name>` 是扩展语言注册的会话内切换入口。
- 本分支唯一与 `filetype` 相关的改动，是 `yate/keymaps/base.py:223` 与
  `yate/keymaps/vim.py:498` 不再把 `ctx.doc.filetype` 传给从不读它的 `type_char`。
- 实测：`pytest tests/test_app_find.py tests/test_input_assist.py tests/test_app_lsp.py
  tests/test_app_textual.py -q -k "filetype"` → **6 passed，exit 0**（覆盖
  `:set filetype=python` → `doc.filetype == "py"`、`:set filetype` 重绑 LSP 服务器、
  与 `.py` 后缀得到同一缩进规则、语法高亮 probe 跟随切换）。

结论：**`:set filetype=...` 仍完全生效**，删除的只是一条从未被读取的无效传参。
按 skill §五，本次与「`type_char.language`」属同一议题：**未撤销**任何既有 finding、
**未新增** BLOCKER / MAJOR / MINOR，裁决维持 `APPROVE`。

## 五、硬门禁实测表（主代理亲自跑，逐条独立轮次）

| # | 命令 | 退出码 | 实测数字 |
| --- | --- | --- | --- |
| 1 | `pyright yate/ tests/ tools/ pack/` | 0 | `0 errors, 0 warnings, 0 informations` |
| 2 | `pytest tests/ -q -n auto` | 0 | 全量通过（`-q` 无汇总行，只认退出码） |
| 3 | `pytest tests/test_architecture.py -q` | 0 | 37 passed |
| 4 | `pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75` | 0 | `93.02%`，`3473 passed, 10 skipped in 195.20s`，`Required test coverage of 75% reached` |
| 5 | `tools.smoke_test run --jobs 4` | 0 | `121/121 scenarios`、`1464/1464 checks (100%)`、`81.16s` |
| 6 | `tools.changelog check` | 0 | `released changelog sections are up to date` |
| 7 | `git diff --check` / `git diff --check master...HEAD` | 0 / 0 | 均无输出 |

覆盖率用后台进程 + 退出码落盘规避长时工具超时；每道 pytest 拆独立工具调用轮次，
规避本机 `safe-delete` 钩子累计删除阈值（见总纲 D15）。

## 六、Strengths

1. **对账可验证**：登记表 1243 + 删除清单 12 = 1255，六类齐全；wave-2 发现 PTY 真实
   实现类契约后主动回退 2 条删除并同步改账（D10），没有为了凑数字硬删。
2. **调用点纪律**：AST 复扫 40133 条调用点，遗漏的 `tests/test_terminal.py:552` 在执行
   实测中暴露后立即同步（D7）；`git grep` 复查无残留关键字实参。
3. **flaky 用例按 §4.7 修而非记偶发**：三处裸断言改 `wait_until` 轮询 / 闩锁，
   重复实测与全量门禁复核均有记录（D8、D14）。
4. **合并就绪度**：提交链按步骤拆分、只提交未推送、临时探针按 D18 清理、工作树干净；
   本轮补齐了上一轮漏做的累积 `diff --check master...HEAD`。

## 七、执行记录与环境事实

- 3 名 `code-explorer` 只读审查员并行 spawn 全部返回 `code=10003 aborted`（零产出）。
  按 `subagent-workflow.md` §五.4「判死后不得原样重试」与 `task-orchestration.md` §三，
  判定「子代理零产出」，**主代理按 pr-review skill 亲自执行**六维度取证与门禁，
  不原样重试、不救活式重建团队。
- 一次 `.NET` 文件 API 调用未跟随 PowerShell 的 `cd`，误在主工作区写出 2 个 0 字节
  文件；已核对为未跟踪误产物并删除，主工作区 `git status --short` 干净。此为不可逆
  清理，按总纲 §二.5 先在本记录落盘、收尾汇报显式列出。
- 临时门禁日志 `pr_cov.log` / `pr_cov_exit.txt` 未入库、收尾删除（同上登记）。
- 分支状态：远端同名分支含至 `84074b1`（非主代理推送），本轮新增提交未推送、
  `HEAD` 未合流 `master`。

## 八、裁决与行动清单

`Overall: APPROVE`（AI 预评审无阻塞项；人工评审者拥有最终合流决策权）。

1. **合并前必须做**：无。
2. **本 PR 建议做**：无（2 项 MINOR 已在 `121e291` 修复）。
3. **可推迟 / 另案**：`language` 前瞻扩展缝是否恢复（含对账 12/1243 → 11/1244）；
   `test` 提交前缀的规则层决定；冒烟 `stress.py:157 toggles_back` 在 `--jobs 4` 下的
   负载敏感（相关提交在 master 基线内，非本分支引入）。
