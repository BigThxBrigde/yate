# 2026-11-08 IKTF4Y 扩展信任加固 —— 代码评审 r2（仅 Lua argv 边界）

- 分支：`feature/enh-extension-trust-hardening`，范围 `aa72147..HEAD`；受审提交为 `24f3ba4`（fix(security): normalise Lua argv tables at the extension boundary），2 个文件 / +65 -5。
- 评审者：`code-review-expert`（`.trae/agents/code-review-expert.md`）。`Skill` 工具返回 `python-code-review not found`，因此手工应用了 agent 文件回退框架（6 个维度 / 3 个严重级别 / 发现项格式；`blocker` / `major` / `minor` 标签）。输出前已执行强制自我批评。
- 按指令收窄范围：**仅** Lua argv 边界修复。`trust.py` / `bridges.py` / 文档 / 计划记录 / `README.md` 索引不在范围内，此处不予评审。
- 范围内文件：`yate/services/extensions/api.py`（`:14`、`:88-107`、`:646-663`）、`tests/test_lua_extensions.py`（`:14`、`:34`、`:118`、`:121`、`:333-363`）。
- 为取证而阅读的上下文（只读、未改动）：`yate/services/shell.py`、`yate/extensions/_yate.lua`、`yate/extensions/_yate.d.lua`、`tests/test_lua_defs.py`、`tests/test_extension_api.py`、`.trae/documents/extension-trust-hardening-review-fixes-plan.md` 第 3 节。

## 结论

**APPROVE（批准）— 0 个阻塞项 / 0 个严重 / 3 个次要。**

第一轮的阻塞项 #1（Lua `yate.shell_argv` 首次使用时抛出 `TypeError`）已**闭合**，通过真实的 lupa 往返验证，而非仅靠文本一致性。


## 1. 我本人执行的门禁命令（退出码）

完整的六道门禁套件已按指令由主代理运行，此处不重跑。下表为评审者本人收集的针对性证据。

| 命令 | 结果 | 退出码 |
|---|---|---|
| `python -m pyright yate/services/extensions/api.py tests/test_lua_extensions.py` | `0 errors, 0 warnings, 0 informations` | 0 |
| `pytest tests/test_lua_extensions.py -q -k shell_argv` | `2 passed, 49 deselected` | 0 |
| `pytest tests/test_lua_extensions.py -q`（整个文件） | 51 passed | 0 |
| `pytest tests/test_lua_extensions.py tests/test_extension_api.py tests/test_lua_defs.py tests/test_lua_engine.py -q -n 0`（计划第 3.3 节验收集） | 110 passed | 0 |
| `pytest tests/test_lua_defs.py -q` | `3 passed` | 0 |
| `pytest tests/test_extension_api.py -q -k shell_argv` | `2 passed, 28 deselected` | 0 |

所有运行均使用 `-p no:cacheprovider`；这些文件中未出现仅在并行时失败的情况，因此无需 `-n 1` 复查。


## 2. 四个必答问题的复验

### Q1 —— `_argv_values` 是否覆盖两条路径；鸭子类型是否会误判？（`api.py:88-107`）

**两条路径均正确。**

- Python `Sequence[str]` 路径：`api.py:96` 的 `getattr(argv, "values", None)` 对 `list` / `tuple` / `deque` 为 `None`，于是 `api.py:101` 的 `items = list(argv)` 执行。实测：`_argv_values(["a","b"]) -> ["a","b"]`、`_argv_values(("a","b")) -> ["a","b"]`、`_argv_values(deque(["a"])) -> ["a"]`。
- 从 1 开始的 Lua table 路径：lupa table **不是** `dict`（实测 `isinstance(t, dict) -> False`），但**确实**暴露了可调用的 `values`（实测 `callable(getattr(t, "values", None)) -> True`），因此 `api.py:97-99` 走 `values()` 分支。在 `lua.eval('{ 1, 2 }')` 上实测：`list(t) -> [1, 2]`（整数**键**），而 `list(t.values()) -> [1, 2]`（**值**）。对于像 `{"echo", "hi"}` 这样的字符串 table，`values()` 产出字符串 `["echo", "hi"]`，而 `list()` 产出 `[1, 2]`。因此第一轮阻塞项 #1 的 1-based 键 bug 在正确的层面得到修复：`services/shell.py` 的 `Sequence[str]` 契约保持不变。
- 非字符串条目：`api.py:103-105` 遍历每一项并抛出 `TypeError("shell_argv entries must be strings")`，时机早于 `run_argv` 被调用，因此失败不再表现为 `" ".join`（位于 `shell.py:155+`）内令人困惑的 `TypeError`。该消息在仓库中唯一（grep：仅 `api.py:105`），这就是负向测试的 `match=` 可追溯到源码的原因。
- 鸭子类型误判评估：普通 `dict` **会**被当作 Lua table（`_argv_values({"0": "x", "1": "y"}) -> ["x", "y"]`，实测）。这是真实的行为怪癖，但对照声明的契约**并非**缺陷：该参数标注为 `Sequence[str]`（`api.py:646`），而 `dict` 不是 `Sequence`，因此传入 dict 属于调用方违约，pyright strict 会拒绝。计划的风险行（`extension-trust-hardening-review-fixes-plan.md:198`）已显式登记此权衡，并选择逐项 `isinstance(str)` 校验作为缓解措施，该校验位于 `api.py:104`。记录为下面的次要项 #1，而非阻塞项。

### Q2 —— 新的 lupa 测试是真实往返，还是空洞测试？（`test_lua_extensions.py:333-351`）

**真实往返，非空洞。证据：**

- 实际执行路径：`runtime.execute("return yate.shell_argv({_PY_EXE, '-c', _LUA_CODE})")`（`:344-346`）构造了一个**真实的 Lua table 字面量**，`_yate.lua:159-161` 将其转发为 `api.shell_argv(argv)`，`api.py:663` 通过 `_argv_values` 归一化，随后 `run_argv` 启动进程。该测试受 `requires_lupa` 门控，并在本机**实际运行**（`2 passed, 49 deselected`，未跳过；本机装有 lupa 2.8）。
- 断言都不是平凡的：`isinstance(result, ShellResult)`（`:348`）证明有**真实的** `ShellResult` 跨回 lupa 边界；`result.returncode == 0`（`:349`）证明子进程确实运行了；`"argv-lua-ok" in result.output`（`:350`）证明 `-c` 载荷作为 argv 元素到达了子进程（即向量非空且未被篡改）；`result.cwd == tmp_path`（`:351`）是真正的 cwd 断言 —— `:338` 设置 `bundle.workspace.root = tmp_path`，而 `shell_cwd`（`shell.py:65`）优先采用 `workspace_root` 而非文档目录，因此该值并非偶然。
- `type(yate.shell_argv) == "function"`（`:343`）还证明 Lua 包装器存在，因此缺失包装器不可能悄然通过。
- 负向测试 `test_shell_argv_rejects_non_string_table_entries`（`:354-363`）确实触发了预期失败：`{1, 2}` 传入 Lua 整数，`_argv_values` 在 `api.py:104-105` 拒绝它们，消息经由 lupa 边界浮现。实测 `1 passed`。
- 区分度检查：第一轮的阻塞项是通过 `list()` 触发的，而 `list()` 产出整数键；新的正向测试传入字符串 table，此时 list() 会产生整数键 `[1, 2, 3]`，`run_argv` 会在 `" ".join`（`shell.py` 内）抛错，因此该正向测试在修复前代码上**会**失败。该测试是真正的回归锁，而非同义反复。

残留的严格性缺口（下面的次要项 #2）：负向测试断言的是 `pytest.raises(Exception, ...)` 而非 `TypeError`，因此锁定了消息但未锁定异常类。

### Q3 —— 返回类型收紧，以及 shell.py 是否被改动

**收紧正确且一致。**

- `run_argv` 无条件返回 `ShellResult`（`shell.py:140-119`：超时路径 `:112-114` 与正常路径 `:119` 都会构造并返回 `ShellResult`；空向量情形在 `:157` 抛出 `ValueError`，`OSError` 情形在内部处理）。它从不返回 `None`。因此 `shell_argv(self, argv: Sequence[str]) -> ShellResult`（`api.py:646`）完全正确，docstring 的更新（`api.py:651-653`）说明了原因。
- Lua 包装器及其桩保持兼容：`_yate.lua:157-161` 与 `_yate.d.lua:59-63` 都声明 `---@return any result`，即无约束，因此无需也不曾做 Lua 侧改动。文档（`extensions.en.md:335-337`、`extensions.zh.md:305-306`、`manual.en.md:1264-1267`、`manual.zh.md:1136-1137`）描述 argv 语义时未承诺 `nil`，故不与更严格的标注矛盾。
- `shell.py` 未被改动，经两种方式验证：`git diff aa72147..HEAD -- yate/services/shell.py` 为**空**（退出码 0），且 `git log --oneline -3 -- yate/services/shell.py` 显示最后改动它的提交是 `3a93570`，该提交是 `aa72147` 的祖先。因此 `run_shell` / `run_argv` / `_popen` / `_capture` 与修复前基线逐字节一致。`ExtensionContext.run_shell`（`api.py:170`）与 `ExtensionAPI.shell`（`api.py:642-644`）正确保留 `ShellResult | None`，因为 `_ctx.run_shell` 确实可能返回 `None`。

### Q4 —— 新增阻塞项/严重项，以及第一轮阻塞项的闭合

**无新增阻塞项或严重项。第一轮阻塞项 #1 已闭合。**

已核查且无问题：

- 提交中未新增 `# pyright: ignore` / `type: ignore`；对两个改动文件本地运行 pyright 报告 `0 errors, 0 warnings, 0 informations`（退出码 0）。
- `24f3ba4` 恰好改动 2 个文件（`yate/services/extensions/api.py`、`tests/test_lua_extensions.py`）；`git show 24f3ba4 --stat` 予以确认。`yate/editor.py` 未被改动，门面 `__all__` 未被改动（`git diff aa72147..HEAD -- yate/ | findstr` 查找 `pyright:` / `editor.py` / `__all__` 无返回）。
- 未新增相对导入：`api.py:14` 扩展了既有的绝对导入行 `from collections.abc import ...`；`Iterable` 是标准库 ABC，`cast` / `Callable` 此前已导入（`:14`、`:17`）。无 `TYPE_CHECKING`、无新增 `Protocol`，与 `.trae/rules/architecture-boundaries.md` 一致。
- 分层保持：lupa 相关知识留在 L3 扩展适配器（`api.py`）中，未下沉到 L0 的 `yate/services/shell.py`；`api.py` 在服务中仅导入 `yate.services.shell`，未引入 `editor_view` / `editor` / `app` 依赖边。
- 契约完整：`test_extension_api.py:585-608`（Python `list` 路径、元字符不解释、带 `Popen` spy 的空向量 `ValueError`）仍原样通过；既有的 `assert result is not None`（`:589`）如今虽冗余但无害，且不在本次修复的写入范围内。
- `tests/test_lua_defs.py` 的三面静态守卫通过（`3 passed`），因此 Lua/Python 表面一致性未变。

第一轮阻塞项 #1 的闭合证据：崩溃原为 `TypeError: sequence item 0: expected str instance, int found`，由 `list(_LuaTable)` 产出整数键所致。修复后，同一真实 Lua 调用返回 `ShellResult(returncode=0, output containing argv-lua-ok, cwd=tmp_path)`，并在真实测试中断言。根因在边界处解决，契约层未动。


## 3. 新发现项

### [minor] 1 —— `_argv_values` 按值读取调用方传入的 `dict`（已接受的权衡，原因已记录）

- 位置：`yate/services/extensions/api.py:96-99`。
- 实测：`_argv_values({"0": "x", "1": "y"}) -> ["x", "y"]`，即 mapping 被静默当作 Lua table，其**值**成为 argv。普通 `Sequence[str]` 调用方不受影响。
- 为何是次要而非严重：声明的参数为 `Sequence[str]`（`api.py:646`），`dict` 不是 `Sequence`，且 pyright strict 会标记此类调用，因此需要有违约的调用方才会触发。计划已登记该权衡并选择逐项校验作为缓解（`extension-trust-hardening-review-fixes-plan.md:198`，实现于 `api.py:104`）。其失败模式也是响亮的报错，而非静默破坏合法向量。
- 可选加固（批准不要求）：用 `not isinstance(argv, Mapping)` 或 `not isinstance(argv, Sequence)` 为该分支加门控，使 mapping 被既有的 `TypeError` 拒绝，而非变成 argv。若采纳，请在 `:354` 附近补一个测试。

### [minor] 2 —— 负向 lua 测试匹配的是 `Exception`，而非 `TypeError`

- 位置：`tests/test_lua_extensions.py:362` —— `pytest.raises(Exception, match="shell_argv entries must be strings")`。
- `match` 字符串对 `api.py:105` 唯一，因此该断言可追溯到源码、并非空洞；但任何携带该文本的异常都能满足它。建议改用 `pytest.raises(TypeError, match=...)`，这是 `extension-trust-hardening-review-fixes-plan.md:98-101` 自身的要求（收紧到实测类型）。实测行为支持 `TypeError`：`api.py:105` 抛出的正是它。lupa 会跨边界重抛，因此收紧前先验证传播后的异常类。
- 非阻塞：该测试确实能捕获丢失校验的回归。

### [minor] 3 —— 同一模块中用两种不同写法读取 Lua table

- 位置：`api.py:96-99` 使用 `values()`；`api.py:126-148`（`_coerce_completer_result`）使用可调用的 `keys()` 加从 1 开始的 `__getitem__` 遍历。
- 两者都正确，且都在真实 lupa table 上实测过，因此这是可维护性问题而非正确性问题：未来的读者需要调和两种模式。可选地在 `_coerce_completer_result` 旁抽出一个小的 `_lua_table_values(raw)` 助手，或在某处 docstring 中说明两者为何不同（completer 跳过非字符串且不得强制转换；argv 则拒绝它们）。


## 4. 强制自我批评（各候选状态）

| 候选 | 反证 | 状态 |
|---|---|---|
| `_argv_values` 鸭子类型对 `dict` 误判 | 真实（`{"0": "x"} -> ["x"]`），但需要 `Sequence[str]` 契约违约；pyright 会拒绝；计划已登记权衡并加了逐项校验 | **保留，次要项 #1**（非严重：无合法调用方路径） |
| `str` 输入被拆成字符：`_argv_values("ab") -> ["a", "b"]` | 实测。**非回归**：`str` 是 `Sequence[str]`，修复前 `run_argv("ab")` 同样执行 `list()` 得到 `["a", "b"]`，再 `join` 成 `"ab"`，结果一致。本次提交未改变行为 | **删除**（既有问题，非本次引入） |
| `pytest.raises(Exception, ...)` 过宽 | `match` 文本对 `api.py:105` 唯一，故断言可追溯；仅未锁定异常类 | **保留，次要项 #2**（从本可能的严重项降级：该测试确实能捕获回归） |
| 同一模块两种 Lua-table 写法 | 在真实 lupa table 上均正确 | **保留，次要项 #3**（降为可维护性） |
| `result.cwd == tmp_path` 可能同义反复 | `:338` 设置了 `workspace.root`；`shell_cwd`（`shell.py:65`）优先采用它，故断言是真实的 | **删除**（无缺陷） |
| 新测试可能空洞 | 正向测试让真实的 `{...}` 字面量穿过 `_yate.lua` -> `api.shell_argv` -> `run_argv`，断言真实的 `ShellResult`、`returncode == 0`、子进程 stdout 与 cwd。在修复前会失败，因为 `list()` 产出整数键 | **删除**（无缺陷） |

遗漏维度反向扫描：正确性（已覆盖，Q1/Q2）、边界条件（空向量仍会抛 `ValueError`（经 `run_argv:157`），由 `test_shell_argv_rejects_empty_vector` 验证；非字符串条目已覆盖）、异常处理（spawn 前校验；消息唯一）、并发（未新增共享可变状态；纯局部函数）、性能（对小 argv 多一次 `list()` —— 可忽略）、类型（pyright 0；标注朝正确方向收紧；`shell` 正确保留 `| None`）、测试覆盖（新增真实测试 + 既有 Python 路径测试；`test_lua_defs` 一致性未变）。未发现进一步缺口。

## 5. 结论与建议

**从 Lua argv 边界角度批准合并：0 个阻塞项 / 0 个严重 / 3 个次要。**

- 第一轮阻塞项 #1：**已闭合**（真实 lupa 往返、真实 `ShellResult`，在 `test_lua_extensions.py:333-351` 中断言；根因在 L3 边界处解决）。
- 第一轮次要项 #4（`ShellResult | None` 过宽）：在 `api.py:646` **已闭合**。
- 上述三个次要项均为可选润色，均不阻塞合并。次要项 #2 成本最低、价值最高（锁定 `TypeError`）。
- 按指令不在本次范围内：信任存储的写入侧对称性、bridges docstring、文档、计划/记录修正 —— 本轮未评审。
