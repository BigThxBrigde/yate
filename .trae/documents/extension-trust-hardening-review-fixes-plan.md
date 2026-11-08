# IKTF4Y 评审迭代修复计划（wave-4）

> 依据：`.trae/reviews/2026-11-08-extension-trust-hardening.md`（#64，
> `code-review-expert`，范围 `af81d11..HEAD` 6 笔提交，结论
> **BLOCKED — 1 blocker / 1 major / 4 minor**）。
> 按主计划 §七「blocker / major → 回到步骤 2 补设计」落本计划；无人值守批准
> 视为通过。唯一规范来源 = 本计划 + 评审记录 + 主计划 / 子计划。

## 一、裁决与范围

| 评审项 | 级别 | 裁决 | 承载 |
|---|---|---|---|
| #1 Lua `yate.shell_argv` 首调 `TypeError` | blocker | **修复**：L3 扩展边界把 1-based Lua table 归一化为字符串向量；补真实 lupa 往返用例 | F1 |
| #2 符号链接 trust store 读写不对称 | major | **修复**：写侧同样拒绝并返回 `False`，与读侧一致；补用例 + 双语文档 | F2 |
| #3 `DataExtensionBridge` docstring 未提真实路径校验 | minor | **修复**：补一句 | F2 |
| #4 `ExtensionAPI.shell_argv` 返回 `ShellResult \| None` 过宽 | minor | **修复**：改为 `ShellResult` | F1 |
| #5 `run_argv` 的 `" ".join(args)` 标签对含空格参数有歧义 | minor | **登记另案**：docstring 已声明「display label, not executable command」；改成 quoting-aware join 会扩散到 `ShellResult.command` 消费面、Lua 面与全部用例，收益低于回归风险。写入评审遗留待办 | F3 |
| #6 「8 笔提交」记载不实 | minor | **订正**：`git log --oneline af81d11..HEAD` 实测 6 笔；该数字来自主代理下发的评审任务书，不在 `extension-trust-hardening-plan.md`（评审记录的 `:146` 行号引用有误，实际为 wave-4 表格行）。在评审记录追加勘误、索引登记写 6 笔 | F3 |

**非目标**：不改 `run_shell` 语义、不改 `ExtensionContext` / `editor.py`、
不动门面 `__all__`、不改 `.yxp` 默认拒绝、不改 `data_store` 校验、不做
内容指纹 / Windows ACL / lockfile / CI SCA（均属主计划已裁决另案）。

## 二、机械取证（主代理实跑）

- lupa 探针（`.venv\Scripts\python.exe -c`）：`lua.eval('{"echo", "a b"}')`
  → `TYPE <class 'lupa.lua55._LuaTable'>`、`ASLIST [1, 2]`、`LEN 2`、
  `ITEMS echo a b`、`ABC Sequence=False / Mapping=False / Iterable=True`、
  `METHODS values=True keys=True`、`VALUES ['echo', 'a b']`。
  因此 `list(argv)` 取键、`argv.values()` 才取值；`isinstance(..., Mapping)`
  不可用（未注册 ABC），必须按鸭子类型 `.values` 判断。
- trust 链接 store 复现（评审记录 §2）：`trust_workspace(root, link) -> True`
  而 `is_trusted(root, link) -> False`。

## 三、F1 — blocker #1 + minor #4（独占 2 个文件）

**独占文件**：`yate/services/extensions/api.py`、`tests/test_lua_extensions.py`。

### 3.1 `yate/services/extensions/api.py`

- 导入行 `:14` 改 `from collections.abc import Callable, Iterable, Sequence`；
  `:17` 已有 `Any, cast`，保持不变。
- 新增模块级私有函数（放在 `_coerce_completer_result` 之类既有私有助手
  附近，保持 ASCII 注释）：
  ```python
  def _argv_values(argv: Sequence[str]) -> list[str]:
      """Return a string vector from a Python sequence or a 1-based Lua table.

      lupa exposes Lua tables as mapping-like objects whose iteration yields
      integer keys; ``values()`` is the only reliable way to read the argv
      entries.  Entries are validated here so a wrong type raises a clear
      ``TypeError`` instead of failing later inside ``" ".join``.
      """
      values = getattr(argv, "values", None)
      if callable(values):
          reader = cast(Callable[[], Iterable[object]], values)
          items = list(reader())
      else:
          items = list(argv)
      vector: list[str] = []
      for item in items:
          if not isinstance(item, str):
              raise TypeError("shell_argv entries must be strings")
          vector.append(item)
      return vector
  ```
  该函数是 L3 扩展边界的适配器，**不把 lupa 知识下沉到 L0
  `services/shell.py`**；`run_argv` 保持 `Sequence[str]` 契约不变。
- `shell_argv` 签名 `:624` 改 `def shell_argv(self, argv: Sequence[str]) -> ShellResult:`；
  docstring 补一句：Lua 侧传 1-based table，边界适配器读取其值；返回永远不是
  `None`。函数体把 `return run_argv(argv, cwd=cwd)` 改为
  `return run_argv(_argv_values(argv), cwd=cwd)`。

### 3.2 `tests/test_lua_extensions.py`

- 新增 `import sys`（标准库导入组，字母序）与
  `from yate.services.shell import ShellResult`。
- `_ApiBundle.__init__` 把 `workspace=cast(Any, MagicMock())` 提取为
  `self.workspace = cast(Any, MagicMock())` 并在 `ExtensionContext(...)` 里传
  `workspace=self.workspace`，供新用例设置真实的 `root`（否则 MagicMock 会让
  `shell_cwd` → `Path(MagicMock)` 抛 `TypeError`）。
- 新增 `@requires_lupa` 用例
  `test_lua_shell_argv_passes_table_values_without_shell(
      bundle: _ApiBundle, tmp_path: Path) -> None`：
  - arrange：`bundle.workspace.root = tmp_path`；
    `runtime = create_runtime(bundle.api, lua_api_library_source())`；
    `runtime.globals()["_PY_EXE"] = sys.executable`；
    `runtime.globals()["_LUA_CODE"] = "print('argv-lua-ok')"`。
  - act：`result = runtime.execute(
        "return yate.shell_argv({_PY_EXE, '-c', _LUA_CODE})")`。
  - assert：`isinstance(result, ShellResult)`、`result.returncode == 0`、
    `"argv-lua-ok" in result.output`、`result.cwd == tmp_path`。
  - 这必须是**真实 Lua 表**经 `_yate.lua` 包装到 Python 的往返，不能只做
    文本比对；另加一条断言 `runtime.eval("type(yate.shell_argv)") == "function"`
    保证包装存在。
- 新增 `@requires_lupa` 用例
  `test_shell_argv_rejects_non_string_table_entries(bundle, tmp_path)`：
  `runtime.execute("return yate.shell_argv({1, 2})")`；用
  `pytest.raises(Exception, match="shell_argv entries must be strings")`
  （lupa 无 stub，异常经 Lua 边界包装，按本仓库既有做法匹配消息）。
  若实测异常类型/消息形态不同，按实测调整断言并在报告写明证据。
- 既有 `test_bundled_lua_library_compiles_into_runtime` 等用例不改；
  `tests/test_lua_defs.py` 三面静态守护不改（本轮不动 Lua 源码）。

**F1 验收命令**：
```powershell
.venv\Scripts\python.exe -m pyright yate/services/extensions/api.py tests/test_lua_extensions.py
.venv\Scripts\python.exe -m pytest tests/test_lua_extensions.py tests/test_extension_api.py tests/test_lua_defs.py tests/test_lua_engine.py -q
.venv\Scripts\python.exe -m pytest tests/test_lua_extensions.py --cov=yate --cov-branch --cov-fail-under=0 -q
```

## 四、F2 — major #2 + minor #3（独占 8 个文件）

**独占文件**：`yate/services/trust.py`、`tests/test_trust.py`、
`yate/services/extensions/bridges.py`、
`yate/docs/extensions.en.md`、`yate/docs/extensions.zh.md`、
`yate/resources/manual.en.md`、`yate/resources/manual.zh.md`。

### 4.1 `yate/services/trust.py`

- `trust_workspace()` 在 `store = ...` 之后、任何 `load_trusted_workspaces` /
  mkdir / open 之前加入写侧守卫：
  ```python
      if store.is_symlink():
          log.warning("refusing to write symlinked trust store %s", store)
          return False
  ```
  与读侧 `load_trusted_workspaces` 的 `return set()` 对称，且 `:trust` 会因
  `False` 给出真实反馈（不再谎报成功）。
- 模块 docstring `:14-17` 改为「读写两侧都拒绝 store 文件本身为符号链接」，
  保留「父目录为链接不受影响」的说明；`trust_workspace` docstring 补一句
  「返回 ``False`` 也用于符号链接 store」。
- 不改 `_POSIX` / `_chmod_quietly` / `_has_symlink_component` / `is_trusted`。

### 4.2 `tests/test_trust.py`

- 新增 `test_trust_workspace_refuses_symlinked_store(tmp_path, monkeypatch, caplog)`：
  - arrange：真实 store 写一行已 resolve 的 root、`link -> real` 符号链接
    （不支持则 `pytest.skip`）、`monkeypatch.setattr(logging.getLogger("yate"), "propagate", True)`；
  - act / assert：`trust.trust_workspace(root, link) is False`；
    `caplog.text` 含 `"refusing to write symlinked trust store"`；
    `real.read_text()` 不包含新的重复行（写侧零副作用）；
    `trust.is_trusted(root, link) is False`。
- 既有 `test_symlinked_trust_store_is_refused`（读侧）与 3 个 chmod 用例不动。

### 4.3 `yate/services/extensions/bridges.py:462-470`

在 `DataExtensionBridge` docstring 的「absolute paths and ``..`` are rejected
by :mod:`yate.services.data_store`」之后补一句：真实路径校验同样在该模块，
解析后逃出根目录的符号链接（含中间目录）会被拒绝；失败仍按既有约定降级为
`None` / `False` / `[]`。不改任何行为。

### 4.4 双语文档（4 文件）

- `yate/docs/extensions.en.md` Trust model 段：把 "A trust store that is
  itself a symlink is ignored" 改为 "is ignored on read and refused on write
  (`:trust` reports the refusal)"；中文镜像同步。
- `yate/resources/manual.en.md` / `.zh.md` `:trust` 段：补一句「信任库文件本身
  为符号链接时，读写两侧均拒绝」；不改其它要点。
- 不写本机绝对路径；不承诺内容指纹 / Windows ACL。

**F2 验收命令**：
```powershell
.venv\Scripts\python.exe -m pyright yate/services/trust.py yate/services/extensions/bridges.py tests/test_trust.py
.venv\Scripts\python.exe -m pytest tests/test_trust.py tests/test_extensions.py tests/test_theme_trust.py tests/test_config.py tests/test_extension_flows.py tests/test_extension_bridges.py -q
.venv\Scripts\python.exe -m pytest tests/test_trust.py --cov=yate --cov-branch --cov-fail-under=0 -q
.venv\Scripts\python.exe -m tools.mdlint --auto-lang --check yate/docs/extensions.en.md yate/docs/extensions.zh.md yate/resources/manual.en.md yate/resources/manual.zh.md
```
mdlint 仍会返回 1（存量基线），按主计划 wave-3 的口径比较父提交基线：
归一化违规集合新增必须为 0（主代理复核）。

## 五、F3 — 记录订正与收尾（主代理，不与 F1/F2 并行）

1. 在 `.trae/reviews/2026-11-08-extension-trust-hardening.md` 追加
   `## 5. 主代理复核勘误与处置`：#6 的数字来自任务书而非方案文档、实测
   6 笔提交；#5 登记为另案并写理由；blocker/major 修复提交号与复跑证据。
2. `.trae/reviews/README.md` 登记 #64（日期 2026-11-08，范围
   `af81d11..HEAD`，1 blocker / 1 major / 4 minor，迭代后结论），散文增量段
   与编号表同步；不改动其它评审条目。
3. 回填主计划 §六 / `overview.md` §六 的 wave-4 行。
4. **主代理亲跑六道全量门禁**（pyright 全量 / pytest `-n auto` / 架构 /
   覆盖率 `--cov-fail-under=75` / smoke / changelog check），每道独立工具
   调用轮次；blocker / major 归零后才允许收尾。
5. 迭代后由 `code-review-expert` 复审（范围 `aa72147..HEAD`），直到
   0 blocker / 0 major；minor 逐条裁决。

## 六、波次表

| 波次 | 任务 | 并行 | 允许启动条件 | 文件重叠 |
|---|---|---|---|---|
| wave-4 | F1 ∥ F2 | 2 个 `plan-executor`，`bypassPermissions` | 本计划批准（无人值守视为通过） | 无（F1 改 api.py + Lua 测试；F2 改 trust.py + trust 测试 + bridges.py + 4 文档） |
| wave-4b | F3 | 主代理 | F1/F2 全部验收退出码 0 且主代理复核 | 记录类文件，不与代码重叠 |

## 七、风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| `_argv_values` 把普通 Python 映射也当 Lua 表 | 只对同时可 `list()` 迭代的 `Sequence[str]` 走原路径；`.values` 分支按鸭子类型，且逐项 `isinstance(str)` 校验 | `git checkout -- <F1 两个文件>` |
| `runtime.execute` 返回对象经 lupa 包装不是 `ShellResult` | 用例先打印/断言实测类型，按证据调整（可用 `.output` 属性探测），不得删断言 | 同上 |
| 写侧拒绝符号链接 store 影响 dotfiles 用户 | 与读侧既有拒绝保持一致；文档明示；`:trust` 现在给真实失败反馈 | `git checkout -- <F2 八个文件>` |
| 双语文档新增行触发 mdlint 新违规 | 增补短句、遵守行宽；主代理做父提交基线归一化对比 | 同上 |
| 子代理回报丢失 | 按「只认落盘结果」查 `git status`，主代理独立重跑全部验收 | 主代理兜底实现 |

## 八、执行记录（回填）

| 项 | 结果 | 提交 | 备注 |
|---|---|---|---|
| F1 | `plan-executor` 回报完整；主代理复核 pyright 0 / 合并回归 297 passed·1 skipped | `24f3ba4` | lupa 真往返返回真实 `ShellResult`，`{1,2}` 触发清晰 `TypeError`；无偏离 |
| F2 | `plan-executor` 回报完整；主代理复核 pyright 0 / 合并回归同上 / 4 文档 mdlint 基线 146、当前 146、归一化差异 0 | `f526733` | 主代理补回 `bridges.py` 被误删的原子写说明，并整理 `extensions.zh.md` 断行 |
| F3 记录 / 门禁 | 评审记录 §6 勘误 + 索引 #64/#65 已落盘；六道全量门禁首轮与 minor 修复后两轮全绿 | `323d3b6`、`d83a9ce`、`aa112a0` | 首轮 3468 passed·10 skipped / 覆盖率 92.94%；终轮 3479 collected（3469 passed·10 skipped）/ 覆盖率 92.96% / 冒烟 121/121·1464 / changelog 0 / diffcheck 0 |
| 复审 | 首轮 spawn 零产出 → 拆两路重试均交付 APPROVE；0 blocker / 0 major，首轮 blocker/major 归零 | 见 §九 | 新增 5 minor：当轮修 3、登记 2；修复后重跑六道门禁 |

## 九、第二波复审（#65）与 minor 处置（步骤 5 回填）

- 首轮复审 spawn 返回 `-` 且无落盘记录；按 `subagent-workflow.md` §五.4
  变更配置重试一次（批大小 1→2、任务粒度拆 F1/F2），两路
  `code-review-expert` 均交付：
  `.trae/reviews/2026-11-08-extension-trust-hardening-r2-lua.md`（APPROVE，
  0 blocker / 0 major / 3 minor）与
  `.trae/reviews/2026-11-08-extension-trust-hardening-r2-trust.md`
  （APPROVE，0 blocker / 0 major / 2 minor）。首轮 blocker #1 与 major #2
  均判定归零；两路均确认 `shell.py` 未被 F1 改动、`bridges.py` 只有 docstring
  变动、Lua 真往返用例非 skip 且非空转。
- 六道全量门禁（主代理亲跑，修复 minor 前）：pyright 0 / 全量
  3468 passed·10 skipped / 架构 37 / 覆盖率 92.94% /
  冒烟 121/121·1464 checks / changelog 0 / diffcheck 0。
- 新 minor 裁决：

  | # | 来源 | 裁决 |
  |---|---|---|
  | 1 | `_argv_values` 会把普通 `dict` 按 `values()` 读取 | **登记另案**：调用方契约是 `Sequence[str]`，pyright strict 已拒绝 dict；逐项 `str` 校验兜底，无合法调用方路径 |
  | 2 | 负向用例只锁 `Exception` 不锁异常类 | **当轮修**：实测 lupa 边界异常仍为 `TypeError`（`EXC_TYPE TypeError`），收紧为 `pytest.raises(TypeError, ...)` |
  | 3 | 同模块存在两种 Lua 表读取惯例 | **登记另案**：可维护性项，归并需重审全模块，收益低于回归风险 |
  | 4 | `:trust` 失败提示固定归因「cwd 含符号链接」，符号链接 store 场景失真 | **当轮修**：提示改为「workspace or trust store contains a symlink component」并补 `test_trust_cwd_reports_symlinked_store_refusal` |
  | 5 | `extensions.zh.md` 把「同一信任级别」断行 | **当轮修**：整句重排 |

- 上述 3 处当轮修复涉及 `yate/flows/extension_flows.py`、
  `tests/test_extension_flows.py`、`tests/test_lua_extensions.py`、
  `yate/docs/extensions.zh.md`；按规则修复后须**重跑六道全量门禁**，
  并在主计划 / overview / 索引回填最终结果。
