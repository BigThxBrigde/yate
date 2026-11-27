# 2026-11-08 IKTF4Y 扩展信任加固评审（#64）

- 分支：`feature/enh-extension-trust-hardening`，范围 `af81d11..HEAD`（6 笔提交，非 8 笔：`3af3c3a`、`31ce397`、`01a80d3`、`3a93570`、`9112a91`、`aa72147`；由 `git log --oneline af81d11..HEAD` 实测）。
- 评审者：`code-review-expert`（`.trae/agents/code-review-expert.md`）；`Skill` 工具返回 `Skill "python-code-review" not found`，因此手工应用了 `.trae/skills/python-code-review/SKILL.md` 中的回退框架（6 个维度 / 3 个严重级别 / 发现项格式），以及 agent 文件中较旧的 `blocker` / `major` / `minor` 标签。已应用强制自我批评。
- 范围：6 个产品文件 `yate/services/shell.py`、`yate/services/trust.py`、`yate/services/data_store.py`、`yate/services/yxp/{install,manifest}.py`、`yate/services/extensions/{api.py,lua/runtime.py}`、`yate/cli.py`、`yate/diagnostics.py`、`yate/flows/shell_flows.py`，两个 Lua 接口面，11 个测试文件，8 篇双语文档，11 篇计划/issue 文档。
- 需求来源：[`../documents/extension-trust-hardening-issue.md`](../documents/extension-trust-hardening-issue.md)（Gitee IKTF4Y，8 个发现项 + 第 5 节验收）；计划与裁决见 [`../documents/extension-trust-hardening-plan.md`](../documents/extension-trust-hardening-plan.md) 与 [`../documents/extension-trust-hardening-plans/overview.md`](../documents/extension-trust-hardening-plans/overview.md)。
- 结论：**BLOCKED（阻塞）— 1 个阻塞项 / 1 个严重 / 4 个次要**。只读事实文档；整改不在此处安排。

## 1. 实际执行的门禁命令（评审者，退出码）

完整的六道门禁运行按指令交由主代理；下表为评审者本人执行的内容。

| 命令 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/services/shell.py ... yate/flows/shell_flows.py`（9 个改动产品模块） | 0 errors, 0 warnings, 0 informations | 0 |
| 对 11 个改动测试文件执行 `python -m pyright` | 0 errors, 0 warnings, 0 informations | 0 |
| `pytest tests/test_architecture.py -q` | 37 passed | 0 |
| `pytest tests/test_trust.py test_data_store.py test_shell.py test_diagnostics.py test_yxp.py test_extension_api.py test_extension_bridges.py test_cli.py test_shell_flows.py test_lua_engine.py -q -n 1` | 全绿（3 处跳过：`test_trust.py:94` POSIX 位、`test_shell.py:355/366` POSIX shell 发现） | 0 |
| `pytest ... --cov=yate.services.shell,trust,data_store;yate.diagnostics;yate.services.yxp.install --cov-branch --cov-fail-under=0` | TOTAL 96%; trust.py 100%, shell.py 97%, diagnostics.py 98%, install.py 93%, data_store.py 90% | 0 |
| `python -m tools.mdlint yate/docs yate/resources README.md README.zh.md --auto-lang --check` | `check: 311 violation(s) in 21 files`（既有基线；见第 3 节） | 1 |

上述针对性运行仅用 `-n 1` 执行；未出现仅在并行时失败的情况，因此这些文件无需区分 flake 与缺陷。`pytest tests/ -q -n 1` 已启动但在约 10% 处超出工具超时（已完成部分未观察到失败）；全量套件仍是主代理的门禁。

改动模块中未覆盖的行均为既有错误分支，非新代码：`shell.py:108-109`（双重失败回收 `log.error`）、`data_store.py:102-104/148-150/161-163`（`OSError` 警告）、`install.py:109-110`（`mkdir` 的 `OSError`）。

## 2. 发现项

### [blocker] 1 —— Lua `yate.shell_argv` 首次使用时抛出 `TypeError`

- 证据：`yate/extensions/_yate.lua:159-161` 转发 `api.shell_argv(argv)`；`yate/services/extensions/api.py:624` 标注 `argv: Sequence[str]`；`yate/services/shell.py:155-159` 执行 `args = list(argv)`，然后 `label = " ".join(args)`。
- Lua table 以 `lupa.lua54._LuaTable` 形式到达；对其执行 `list()` 得到的是整数**键**而非字符串值，因此 `args == [1, 2]`，`" ".join` 抛出 `TypeError: sequence item 0: expected str instance, int found`。
- 直接针对已交付代码复现（退出码 1）：
  `python -c "from lupa.lua54 import LuaRuntime; from yate.services.shell import run_argv; rt=LuaRuntime(unpack_returned_tuples=True); rt.globals().run_argv=run_argv; rt.execute('return run_argv({\"echo\",\"hi\"})')"` -> 回溯终止于 `shell.py:159` 的 `label = " ".join(args)` / `TypeError: sequence item 0: expected str instance, int found`。对原始转换的探针显示 `TYPE _LuaTable` / `ASLIST [1, 2]`。
- 影响：该接口在六处被记录为可从 Lua 调用（`_yate.lua:74`、`_yate.d.lua:63`、`yate/docs/extensions.en.md:1041`、`extensions.zh.md:951`、`manual.en.md:1264`、`manual.zh.md:1135`），却在文档记录的首次调用时崩溃。按"常规使用即崩溃"规则定为 `blocker`。没有测试覆盖 Lua 到 Python 的路径：`tests/test_extension_api.py:580-610` 只测 Python 侧 `api.shell_argv`；`tests/test_lua_defs.py:41,77` 只断言文本一致性。
- 修复方向：在 `run_argv` 中归一化（例如接受 `str` 的可迭代对象并逐元素校验、给出清晰的 `ValueError`），或在边界处转换 —— 但 `_LuaTable` 必须按值读取（对 `1..n` 做序列推导或使用 `table.unpack`），而非用 `list()`。补一个真实的 lupa 往返测试（由 `requires_lupa` 门控），断言 `yate.shell_argv({"echo", "x"})` 返回 `ShellResult` 形态的值，使 `test_lua_defs` 的文本一致性无法再掩盖此问题。

### [major] 2 —— 符号链接的信任存储：`:trust` 报告成功但从未持久化

- 证据：`yate/services/trust.py:83-85` 使 `load_trusted_workspaces` 对符号链接存储返回 `set()`，而 `trust_workspace`（`trust.py:128`）查询同一加载器只是为了跳过重复写入，随后经该链接在 `trust.py:140-141` 追加，并在 `:144` 返回 `True`。
- 复现（退出码 0）：`trust_workspace(repo, link) -> True`、`is_trusted(repo, link) -> False`，且链接目标确实收到了解析后的仓库行。
- 影响：用户若把 `~/.yate/trusted_workspaces` 符号链接到 dotfiles 仓库，会从 `yate/flows/extension_flows.py:79-91` 在消息栏看到 `trusted <cwd>`，该会话中扩展得以加载，但之后每次启动都会静默拒绝（`is_trusted` 为 False），只有每次读取时的一条警告。这属于 fail-closed，故定为 `major` 而非 `blocker`，但命令输出在事实层面错误，且该条目无法通过 UI 撤销。
- 修复方向：在写入侧也拒绝符号链接存储（返回 `False`、给出同样的警告），或让读取侧跟随链接，同时对记录的值保持"无链接根路径"的不变式。无论选择哪种，都在 `trust.py` 的 docstring 中记录；该 docstring 目前只覆盖符号链接的*父目录*。

### [minor] 3 —— 尽管计划第 3 节承诺，`DataExtensionBridge` 的 docstring 未更新

- `yate/services/extensions/bridges.py:461-471` 仍只说名称经由 `yate.services.data_store` 处理；未提及新的真实路径拒绝。计划表格（`extension-trust-hardening-plan.md:57`）写明"`bridges.py` docstring 由 plan_b 覆盖"；但 `bridges.py` 不在改动文件列表中。行为本身正确且已测试（`tests/test_extension_bridges.py:570-600`），因此仅为文档漂移。

### [minor] 4 —— `ExtensionAPI.shell_argv` 的返回标注宽于实际

- `yate/services/extensions/api.py:624` 返回 `ShellResult | None`，但 `run_argv` 从不返回 `None`；这个联合类型是从 `shell` 照搬而来，后者的 `None` 来自 `_ctx.run_shell`。无害，但迫使调用方无谓地做空值检查，并削弱了 docstring 描述的契约。

### [minor] 5 —— `run_argv` 的标签对含空格的参数有损

- `yate/services/shell.py:159` 用 `" ".join(args)` 作为 `ShellResult.command`，由输出浮层渲染。`["echo", "a b"]` 与 `["echo", "a", "b"]` 产生相同标签。docstring 已记录标签语义，因此属已接受的设计，但采用感知引号的 join（或携带原始向量）可让浮层无歧义。

### [minor] 6 —— 计划记录 8 笔提交，分支实际 6 笔

- `.trae/documents/extension-trust-hardening-plan.md:146` 与任务书都写 8 笔提交；`git log --oneline af81d11..HEAD` 列出 6 笔（`3af3c3a`、`31ce397`、`01a80d3`、`3a93570`、`9112a91`、`aa72147`）。波次表将 4 个波次映射到 6 笔提交，因此更像计数笔误而非工作丢失；仍值得修正，使记录与分支一致。

## 3. 已验证无误（显式无发现项声明）

记录于此，以免主代理重复争论这些点。

### S-02 yxp 校验和门控

- 拒绝确实发生在最前：`yate/services/yxp/install.py:87-93` 在 `records.is_symlink()` 探测（`:101`）之前、在 `ext_dir.mkdir`（`:107`）之前、在任何记录写入之前抛错。`ext_dir`/`package` 来自 `default_extensions_dir()` 与 `read_package()`，两者均无副作用（`manifest.py:82-84`、`:147+`）。
- 两个产品调用点行为正常：`yate/cli.py:317-326` 传入 `allow_unverified=args.allow_unverified`；`yate/commands.py:576` 使用默认值，因此 `:install-extension` 会拒绝。不存在第三个调用点（`git grep install_package -- yate tools pack`）。
- 消息/常量契约成立：`CHECKSUM_NAME` 从 `manifest.py:53` 导入（非字面量），且 `tests/test_yxp.py:262` 匹配 `missing 'checksum'`。
- 旧的选择加入测试是改写而非绕过：`test_install_without_checksum_installs_unverified`（`test_yxp.py:251-256`）与 `test_install_without_checksum_logs_warning`（`:608-615`）现在都传入 `allow_unverified=True`，新的默认拒绝测试断言 `not base.exists()` 且无记录。
- CLI 子进程路径已端到端验证（`tests/test_cli.py`，2 passed），包括 `Path.home()/.yate/extensions/hello.py` 不存在的断言。

### S-05 data_store 真实路径门控

- `_assert_inside_data_root`（`data_store.py:38-42`）将 `target.resolve()` 与 `data_root().resolve()` 比较，调用点包括 `resolve()`（`:86`）、`write_text` 中 `mkdir` 之后（`:122`）以及 `remove` 中 `unlink` 之前（`:143`）；未覆盖的中间段仅为既有的 `OSError` 警告。
- 中间目录的符号链接已覆盖，因为 `Path.resolve()` 会解析每一个组成部分，与四个新测试相符（write/remove/read/names 各自断言*外部*文件未被触碰）。
- 测试并非空洞：符号链接确实在本机创建（对 `test_data_store.py` 运行 `pytest -k symlink` -> `4 passed`，无跳过），且 `test_remove_...` 断言受害文件的内容幸存。
- `DataExtensionBridge` 的失败契约完整：`False` / `None` / `[]` 加一条警告（`bridges.py:473-504`），在 `test_extension_bridges.py:596-600` 通过 caplog 检查断言。

### S-03 shell 重构

- `_capture`/`_popen` 是纯抽取：`run_shell` 保留 `shell=True`、相同的 Popen kwargs、`[yate] failed to run shell` 的 OSError 回退（`shell.py:135-136`）、rc 124 及 `[yate] command timed out after {timeout}s` 消息（`:112-114`）；4 个超时/kill-tree 测试通过。
- `run_argv` 使用 `shell=False`，在 `Popen` 之前以 `ValueError` 拒绝空向量（`:156-157`，由 `spy_popen` 测试证明），并将启动失败降为 rc 1（`:162-163`）。
- cwd 确实单一来源：`shell_cwd`（`shell.py:63-65`）被 `ShellFlows._cwd`（`shell_flows.py:112-116`）与 `ExtensionAPI.shell_argv`（`api.py:634-639`）共用，且 `test_shell_flows.py:128-137` 钉住了这个共享助手。
- 门面契约完整：`len(yate.services.extensions.__all__) == 14`（实测），`yate/editor.py` 与 `tests/test_architecture.py` 不在 `git diff --name-only` 中（800 行守卫未动），三向 Lua/Python 一致性守卫通过。

### S-04 信任加固

- `_POSIX` 是模块级接缝，默认为 `os.name == "posix"`（`trust.py:48`）；`_chmod_quietly`（`:58-65`）覆盖**两处**调用点（`:139` 目录、`:143` 文件），并记录警告而非使用 `contextlib.suppress`。测试断言恰好两条警告（`test_trust.py:120`）。
- 符号链接拒绝仅针对存储**文件**（`:83`），因此符号链接的父目录（`$HOME` -> 别处）不受影响，与 `:14-17` 的 docstring 及所述合法布局一致。
- docstring 未宣称超出实现的内容：永久路径授权、手动撤销、尽力而为的 POSIX chmod、Windows ACL 明确不在范围内（`:1-17`）。未承诺内容指纹或 ACL。

### S-01 Lua 信任边界

- `_COMPILE_EXPR`（`runtime.py:69`）是无插值的字面量，两个暂存全局变量都在 `finally` 中无条件清除（`:97-99`），因此异常路径也被覆盖；恶意 chunkname 测试通过，并断言之后两个全局变量均为 `None`。
- 误导性措辞已去除：`package.path` 注记现明确说明 `io`/`os` 保持可用且这并非沙箱（`runtime.py:118-125`），`manual.{en,zh}.md` 与 `extensions.{en,zh}.md` 中亦同步。
- 剩余三处"无文件 I/O"命中是随附游戏库中的编码约定（`game_engine.lua:22`、`engine_layout.lua:30`、`engine_json.lua:19`），并非运行时沙箱声明 —— 正确地未作改动。
- 契约钉定测试是真实的：`test_lua_engine.py:392-398` 断言 `type(os.execute)..type(io.open)..type(require) == function:function:function`。
- plan_d 的偏离正确：`runtime.eval("return ...")` 确实抛出 `LuaSyntaxError: unexpected symbol near 'return'`（已复现，退出码 1），因此 `runtime.execute` 是正确调用；`_compile_chunk` 保留 `eval`，因为 `_COMPILE_EXPR` 是裸表达式。

### S-07 诊断隐私注记

- `_PRIVACY_NOTE`（`diagnostics.py:66-70`）在分隔线之后、section 循环之前输出（`:111-112`），即位于第一个 `[system]` section 之前；测试断言索引顺序（`test_diagnostics.py:62-69`）且彩色输出逐字保留该注记。未脱敏任何字段：`format_report` 只增加了两行。

### 文档与工程纪律

- 8 篇面向用户的文档成 en/zh 配对，并互相引用确实存在的锚点（`extensions.en.md:134` "Trust model"，由 `:925` 跳转；`extensions.zh.md:118` "信任模型"，由 `:844` 跳转）。
- 未承诺任何未实现的能力：无"signed"、无 lockfile、无 CI SCA、无 Windows ACL —— 每一项都标为已知限制/单独跟踪（`README.md:65-69`、`README.zh.md:93-96`、`extensions.en.md:163-166`）。
- 8 篇文档共新增 144 行，**无一**超过 100 字符，因此 `mdlint` 退出码 1 完全是既有的 311 处违规基线，而非新增债务。
- 无 `# type: ignore`、无 `# pyright: ignore`、无裸 `except:`、无相对导入、新增 Python 行中非 ASCII 字符为零，且每个改动的模块都有 `from __future__ import annotations`。
- 6 笔提交均使用英文约定式提交标题并带正文。

## 4. 强制自我批评日志

本报告发出前，每个初始候选都对照源码重读。

| # | 候选 | 状态 | 理由 |
|---|---|---|---|
| 1 | Lua `shell_argv` 的 `TypeError` | **保留为阻塞项** | 通过重读 `shell.py:155-159` 并经真实 `run_argv` 复现回溯再次验证；六处文档宣传该接口，且无测试覆盖 Lua 路径。这不是 UserError 式的优雅失败 —— 而是在文档记录的调用上未捕获的 `TypeError`。 |
| 2 | 符号链接信任存储的不对称 | **保留为严重** | 经执行复验（先 `True` 后 `False`）；未能上调为阻塞项，因为无数据丢失、无安全绕过、无崩溃 —— 它以 fail-closed 收场，但给出了误导性的成功消息。 |
| 3 | `bridges.py` docstring 漂移 | **保留为次要** | 确认计划承诺了该编辑，但 `bridges.py` 不在 diff 中；行为正确，故为次要。 |
| 4 | ShellResult 联合标注 | **保留为次要** | 确认 `run_argv` 无 `None` 返回路径；仅涉及标注，两种写法下 pyright 均无诊断。 |
| 5 | 有损的 `command` 标签 | **保留为次要** | 在 `shell.py:159` 确认；从疑似的正确性 bug 降为次要，因为 `run_argv` 的 docstring 将拼接标签记录为有意设计。 |
| 6 | 6 与 8 的提交计数差异 | **保留为次要** | 用 `git log --oneline` 实测；仅影响计划记账。 |
| 7 | 候选：`data_store` TOCTOU 仍存在 | **删除** | check/`mkdir`/`unlink` 序列仍有理论上的窗口，但模块 docstring 与第二次复查正是 issue S-05 所要求的缓解范围；标记"TOCTOU 仍存在"属于无依据的诉求，而非有证据支撑的缺陷。 |
| 8 | 候选：无 `--install-extension` 时也接受 `--allow-unverified` | **删除** | 已验证 `parse_args(["--allow-unverified"])` 在安装列表为空时成功且不执行任何操作；静默空操作 flag 与该解析器中其它副命令 flag 一致。 |
| 9 | 候选：符号链接测试在 Windows 上空洞 | **删除** | 运行后被否证：`-k symlink` 在 `test_data_store.py` 上 4 passed 且无跳过，在 `test_extension_bridges.py` 上 1 passed。 |
| 10 | 候选：`_POSIX` 接缝把仅测试用的开关泄漏进生产 | **删除** | 该接缝是调用时读取的模块级常量，默认值正确；它是在 Windows 上触发该警告的最小方式，且已如此记录。 |
| 11 | 候选：chunkname 现接受任意文本（契约放宽） | **删除** | `_MODULE_NAME_RE` 仍对共享模块名把关；chunkname 只是作为值传入的诊断标签，issue 指出的注入风险已消失。 |

遗漏维度反向扫描：并发（无新增共享可变状态；`_capture` 为每进程独立）、性能（启动路径无新增 I/O 或循环；信任读取的成本未变）、异常处理（每个新增 `except` 都记录日志 —— 已验证三个改动的 L0 叶子模块中无裸 except 或 `except Exception`）、类型（20 个改动 Python 文件的 pyright strict 均为 0）、测试覆盖（新增分支行均已覆盖，除第 1 节列出的既有 `OSError` 警告）。

## 5. 后续事项（此处未修复）

1. 合并前修复发现项 1，并补一个 lupa 门控的 Lua 往返测试；考虑扩展 `tests/test_lua_defs.py` 或新增测试，使文本一致性永不再代替运行时调用。
2. 决定符号链接存储策略（发现项 2），并对齐 `trust.py` 的 docstring、`trust_workspace` 的返回值与 `:trust` 消息。
3. 更新 `DataExtensionBridge` 的 docstring（发现项 3），并修正计划中的提交计数（发现项 6）。
4. 确认主代理负责的其余门禁：`pyright yate/ tests/ tools/ pack/`、`pytest tests/ -q -n auto`、覆盖率 `--cov-fail-under=75`、`tools.smoke_test run --jobs 4`、`tools.changelog check`。
5. 按计划裁决，S-06（依赖 / lockfile / CI SCA）与 S-08（`--translate-cmd`）保持仅文档记录/单独跟踪；文档已如实说明，不预期代码改动。

## 6. 主代理勘误与迭代处置（2026-11-08）

- 提交计数更正（次要项 #6）：`git log --oneline af81d11..HEAD` 实测为 **6** 笔提交（`3af3c3a`、`31ce397`、`01a80d3`、`3a93570`、`9112a91`、`aa72147`）。"8 笔提交"的数字来自主代理的评审任务书，而非 `extension-trust-hardening-plan.md`；本记录 `:58` 处对计划行 `:146` 的引用实际指向波次 4 的占位行。索引条目 #64 记录的是实测的 6。
- mdlint 范围：评审者扫描了 `yate/docs yate/resources README.md README.zh.md`（311 处命中，均为既有）。波次 3 门禁只扫描 8 个改动的文档：基线 199 / 当前 199 / 归一化 diff 0。两者都只含既有项；文件集合不同解释了总数不同。
- 阻塞项 #1 在 `24f3ba4` 中修复：L3 边界助手 `_argv_values()` 读取从 1 开始的 Lua table 的 `values()` 而非整数键，`shell_argv` 现返回 `ShellResult`，且 `@requires_lupa` 往返测试断言真实的 `ShellResult`（rc 0，输出 `argv-lua-ok`）。主代理重跑：pyright 0，合并回归 297 passed / 1 skipped。
- 严重项 #2 在 `f526733` 中修复：`trust_workspace` 在写入侧拒绝符号链接存储并返回 `False`；新测试证明写入侧零副作用；`trust.py` 的 docstring 与 4 篇双语文档已对齐。主代理对这 4 篇文档重跑 mdlint：基线 146 / 当前 146 / 归一化 diff 0。
- 次要项 #3 在 `f526733` 中修复（`DataExtensionBridge` 的 docstring 保留原子写入的说明并加入真实路径规则）；次要项 #4 在 `24f3ba4` 中修复（返回类型收紧）。
- 次要项 #5 单独登记为待办：`ShellResult.command` 是展示标签（`run_argv` 的 docstring 写明"not an executable command string"）；感知引号的 join 会波及标签消费方、Lua 接口面及每一处标签断言，因此改动成本大于收益。
- 迭代设计与验收标准：[extension-trust-hardening-review-fixes-plan.md](../documents/extension-trust-hardening-review-fixes-plan.md)。
- 复审（索引 #65，范围 `aa72147..HEAD`）：首次复审 spawn 无返回且未写文件；一次变更配置的重试（批次 1 -> 2，拆为 F1/F2）交付了两份独立的 `code-review-expert` 记录（`2026-11-08-extension-trust-hardening-r2-lua.md` 与 `...-r2-trust.md`）。两者均 APPROVE，且 **0 blocker / 0 major**；阻塞项 #1 与严重项 #2 均确认闭合。其 5 个新次要项已分流：3 个在 `aa112a0` 中修复（收紧负向测试的异常类型、准确的 `:trust` 拒绝消息加回归测试、中文换行重排），2 个附理由登记（dict 按值读取属调用方契约违约；两种 Lua-table 读取约定属可维护性事项）。
- 最终六道门禁，由主代理在这些次要修复后重跑：pyright `yate/ tests/ tools/ pack/` 为 0；`pytest tests/ -q -n auto` 退出码 0（3479 收集 = 3469 passed / 10 skipped）；架构 37；覆盖率 92.96%（阈值 75）；冒烟 121/121 场景、1464/1464 检查；`tools.changelog check` 0 且 `git diff --check` 0。工作区干净，未推送、未合并进 develop。
- 分支命名偏差（用户于 2026-11-08 在结项报告后指出）：该 worktree 最初以 11-07 之前的斜杠形式 `enh/extension-trust-hardening` 创建，违反了 `task-orchestration.md` §二.1（`feature/<fix|feat|enh|ref>-<task>`）。它在 `e27c007` 中被重命名为 `feature/enh-extension-trust-hardening`，但那次迟到的重命名只运行了 `git diff --check`，从未在计划或本评审记录中登记为偏差。根因：`doc-conventions.md` §七 中过期的交叉引用仍引用旧的斜杠格式。本轮对齐该交叉引用，在主计划 §九 登记此偏差，并按重命名纪律重跑全部六道门禁。用 `git worktree list` 验证的当前状态：worktree `yate-extension-trust-hardening` + 分支 `feature/enh-extension-trust-hardening`（类型 `enh` 遵循 issue 标题前缀 `ENH - [安全审计]`），parent `develop` @ `af81d11`。本次更正后的第三轮六道门禁全部退出码 0：pyright 0、pytest 3469 passed / 10 skipped、架构 37、覆盖率 92.96%、冒烟 121/121 且 1464/1464 检查、changelog 0、diffcheck 0。
