# Python 代码评审（python-code-review 框架）— IKJPVB 打包瘦身与布局改动

- **评审对象**：分支 `enh/pack-bundle-layout`（issue IKJPVB）的 Python 代码：
  `pack/_common.py`（`EXCLUDES` + `SpecInputs.excludes` + `collect()`）、
  `pack/yate.spec`、`pack/yate-onefile.spec`、`tests/test_pack_spec.py`、
  `pyproject.toml` 的 pyright 覆盖面。
- **评审方法**：按 `.trae/skills/python-code-review/SKILL.md` 六维度框架
  （正确性 / 安全 / 性能 / Pythonic / 可维护性 / 错误处理）与三级严重等级，
  对照 `.trae/rules/python-coding-style.md` §五检查清单逐条核对；每轮修复后重跑
  同一框架，直到一轮零发现为止（迭代记录见 §三）。
  **工具说明**：本会话未提供 `lsp` 工具，LSP 语义分析不可用，按该 skill 的回退
  规则改用 `read_file` / `search_content` / `pyright` 取证。
- **对比基线**：[2026-10-03-python-code-review.md](2026-10-03-python-code-review.md)
  （83 项全量评审）。其中 R-66 指出两个 spec 约 90 行构建逻辑重复——已由本分支
  之前的 `pack/_common.py` 抽取解决，本次沿用该共享结构，未引入新的重复。
- **首轮结论**：`MINOR ISSUES` — 0 CRITICAL / 4 WARNING / 5 SUGGESTION（R-01…R-09）。
- **第二轮（issue note_51452120：统一布局 + 内容目录改名）**：见 §九（R-20…R-24），
  结论 `MINOR ISSUES` — 0 CRITICAL / 0 WARNING / 5 SUGGESTION，并由主代理补跑真实构建。

---

## 一、问题跟踪记录

状态图例：✅ 已修并销账 ｜ 🔧 待修 ｜ 📌 仅登记（无代码动作） ｜ ⏸ 明确不修 ｜ 👀 待观察

| # | 严重度 | 问题描述 | 影响范围 | 状态 |
|---|---|---|---|---|
| R-01 | WARNING | `tests/test_pack_spec.py:10-13` 模块 docstring 仍无条件宣称 `EXE(contents_directory=".")`，与同文件 `:215-240` 的平台三元式断言矛盾 | 仅文档一致性；后来者读守卫语义会得到相反结论 | ✅ 已修（`a0d1813`：改为平台限定 + 点明守卫断言的是三元形状） |
| R-02 | WARNING | `EXCLUDES` 的前提"yate 不用 PIL"无守卫：将来 `yate/**` 引入 PIL 会构建成功但运行时 ImportError，且构建报告不指向 `EXCLUDES` | 冻结产物可用性（用户双击 exe 才暴露） | ✅ 已修（`a0d1813`：新增 `test_yate_sources_when_scanned_never_import_excluded_modules` 扫 `yate/**`） |
| R-03 | WARNING | `pack/` 不在 `pyproject.toml` 的 pyright `include` 内，而两个 `.spec` 由 PyInstaller `exec` 当 Python 脚本运行 | 构建期代码不受 strict 门禁；"加字段 + 两个 spec 各传一处"最易漏接 | ✅ 已修（`a0d1813`：`include` 增加 `"pack"`，实测仍 0 errors） |
| R-04 | WARNING | issue 的"无 `_internal`"诉求在 POSIX 上结构性未达成（exe 与 `yate/` 包数据目录同名，`api.py:529-532` + `:1189-1194`） | Linux/macOS 单目录产物仍带 `_internal/` | 📌 仅登记（代码侧已是最优取舍；README 双语已写明"平铺仅限 Windows"。**余留人工动作：在 issue IKJPVB 回执该平台限定**） |
| R-05 | SUGGESTION | `_load_common()` 无缓存，每次调用重新 exec 模块 → 每次得到不同类对象，将来 `isinstance(..., SpecInputs)` 静默恒假 | 守卫正确性（未来误判难定位） | ✅ 已修（`a0d1813`：`@functools.lru_cache(maxsize=1)` + docstring 说明原因） |
| R-06 | SUGGESTION | `[source] = excludes_value.args` 解包失败抛 `ValueError`；`:162-171` 裸 `next()` 同类 | 守卫失败信息不可读（python-coding-style §4.5） | ✅ 已修（`a0d1813`：先断言参数长度为 1 再解包；`next()` 残留改为带说明的 `_functions` / `_returned_call`） |
| R-07 | SUGGESTION | 清单条目断言强度低于用例名：`"PIL."`、`"PIL Image"`、`"pil"` 都能通过 | 拼错的条目会静默不生效（PyInstaller 按模块名区分大小写匹配） | ✅ 已修（`a0d1813`：每段须为合法标识符 + 拒绝大小写变体重复）。**残余局限**：单条仅大小写错误在 CI 无法判定（`build` extra 不含 Pillow，无法探测可导入性），已在用例 docstring 与本表标注 |
| R-08 | SUGGESTION | `Analysis(excludes=...)` 守卫只查属性名不查宿主，`excludes=other.excludes` 也能通过 | 清单转发链被换对象时守卫漏报 | ✅ 已修（`a0d1813`：断言 `.value` 是 `Name` 且 `id == "inputs"`；负向演练确认被拦） |
| R-09 | SUGGESTION | `pack/_common.py` `EXCLUDES` 注释 13 行，把体积数字与 import 链路压在代码上 | issue 关闭后数字腐化；三处副本漂移 | ✅ 已修（`a0d1813`：压缩为前提 + 指向守卫用例与 `xref`/`warn` 取证报告；数字只留在 plan §7.2 与 README 双语） |

| R-10 | WARNING | R-02 新增守卫只扫 `*.py`，漏掉随包分发、运行时由 `importlib.util.spec_from_file_location` 导入的 `yate/extensions/*.py.example` | 冻结产物可用性（扩展示例 import 被排除包 → 用户侧 ImportError） | ✅ 已修（`cb082c2`：`_yate_sources()` 纳入 `extensions/*.py.example`，实测扫描面 120 个文件 / 其中 10 个扩展） |
| R-11 | WARNING | R-02 新增守卫的动态 import 分支只匹配裸 `__import__` 名称，`importlib.import_module("PIL")`（`ast.Attribute`）与 `from importlib import import_module` 形式漏检 | 同上，守卫可被绕过 | ✅ 已修（`cb082c2`：新增 `_dynamic_import_name` 覆盖三种写法；负向演练确认三种全部被拦） |
| R-12 | SUGGESTION | `pack/*.spec` 仍无静态类型检查——R-03 只把 `pack/_common.py` 纳入 pyright，pyright 只分析 `.py` | 两个 spec 的类型/语法错误只能在真实构建时暴露 | 📌 仅登记（补偿手段已到位：AST 守卫逐个关键字断言 + 每次改动的真实构建；已在守卫模块 docstring 写明该边界） |
| R-13 | SUGGESTION | 守卫的残余局限：运行时拼出的模块名（`name = "PIL"` 后 `import_module(name)`）无法静态识别 | 理论上可绕过前提守卫 | 📌 仅登记（已在用例 docstring 与本表标注；静态守卫的固有上限，需靠 code review 拦截） |
| R-14 | SUGGESTION | `_parse()` 未memo：R-05 已按同一理由 memo 了 `_load_common()`，但每次断言都重新读盘+解析同一批文件 | 守卫自身的一致性与无谓开销 | ✅ 已修（`6618a15`：`@functools.lru_cache(maxsize=None)`，docstring 写明"树不被修改"这一前提） |
| R-15 | SUGGESTION | CI（`.github/workflows/test.yml`）只跑 pytest 与 changelog 门禁，**不跑 pyright**；R-03 把 `pack/` 纳入 strict 门禁的收益只体现在本地/代理侧 | 门禁强制性（既存事实，非本次引入） | 📌 仅登记（`tools.changelog check` 实测退出码 0，"unreleased lag" 被显式容忍，故 changelog 门禁不是本次的阻塞项；pyright 由 `task-orchestration.md` 收尾门禁约束） |
| R-16 | WARNING | 前提守卫只覆盖三种"运行时会被执行"里的两种：`yate/yaterc.example`（`yate/config.py:280-281` compile/exec）与 `yate/resources/theme_examples/*.example`（`yate/editor_view/theme.py:686-688`）仍不在扫描面 | 与 R-10 同根因（同为 data 收集 + exec 执行），修一半 | ✅ 已修（`842f830`：改按 `*.example` 后缀匹配，一次覆盖扩展示例 / yaterc / 主题模板；负向演练确认主题模板里的 PIL import 被拦，扫描面 123 个文件） |
| R-17 | SUGGESTION | `test_analysis_excludes_..._is_not_an_empty_literal` 已被 `inputs.excludes` 断言完全蕴含（`[]` 是 `ast.List` 不是 `ast.Attribute`），永远不会独立失败 | 死断言 + 阅读噪音 | ✅ 已修（`842f830`：删除该参数化用例，意图并入存活用例的 docstring 与失败信息） |
| R-18 | SUGGESTION | `pack/_common.py` 的 EXCLUDES 注释仍留 `13.1 MiB`——R-09 声称已把体积数字移出代码 | 与 R-09 自述不一致；数字随依赖升级腐化 | ✅ 已修（`842f830`：只留"纯负载"的定性结论与取证报告指向） |
| R-19 | SUGGESTION | `pyproject.toml` 的 include 注释声称"两个 spec 也受 strict 门禁"，与实测不符（pyright 只认 `.py`，`filesAnalyzed` 里 pack 只贡献 `_common.py`） | 注释误导读者以为 spec 已被门禁罩住 | ✅ 已修（`842f830`：注释改为只提 `_common.py`，并写明 spec 由 AST 守卫 + 真实构建覆盖，与 R-12 登记一致） |

### 修复过程中的自我发现

| # | 发现 | 处置 |
|---|---|---|
| S-01 | R-07 首版修复只加"合法标识符"检查，负向演练当场显示 `("pil",)` 仍通过 | 追加大小写变体重复检查；单条大小写错误的不可判定性如实登记为残余局限 |
| S-02 | `git add -A` 两次把临时提交信息文件（`.cm3.txt` / `.cm_i1.txt`）一并入库 | 各补一笔 `chore:` 提交删除（`47b639f` / `2b78fd7`）；后续用精确 pathspec 暂存 |

---

## 二、发现明细

**R-01 [WARNING] `tests/test_pack_spec.py:10-13` — 模块 docstring 与守卫实现矛盾**

修复 POSIX 撞名缺陷时 `pack/yate.spec` 的模块 docstring 与行内注释都改成了平台限定，本测试
文件的模块 docstring 被漏掉，仍无条件写 `EXE(contents_directory=".")`；同一文件 `:215-240`
的实现却已断言 `IfExp(sys.platform == "win32", ".", "_internal")`。测试 docstring 是读守卫
语义的第一入口，此处会给出与代码相反的结论。修复：改为平台限定表述。

**R-02 [WARNING] 排除清单的前提无守卫**

`pack/_common.py` 排除 `PIL`，守卫只钉住"清单里要有 PIL/numpy"，没有任何东西钉住"yate 不用
PIL"。今天安全（`yate/**` 大小写敏感检索 0 命中），但一旦新特性 import 了 PIL，构建依旧成功、
只有用户双击 exe 才报 ImportError。修复：新增 AST 扫描 `yate/**` 的守卫用例，并把该用例名写进
`EXCLUDES` 注释，使前提与守卫互相指名。

**R-03 [WARNING] `pack/` 不在 pyright 门禁范围**

`pyproject.toml` 的 `include` 不含 `pack/`，两个 `.spec`（PyInstaller 以 `exec` 当脚本运行）
与 `_common.py` 不受 pyright strict 约束；本次新增的正是这类跨文件契约。修复：`include` 增加
`"pack"`，实测纳入后仍 0 errors。

**R-04 [WARNING] issue 诉求在 POSIX 上结构性未达成**

`pack/yate.spec` 的平台条件式意味着 Linux/macOS 仍产出 `_internal/`。根因是 exe 与内置
`yate/` 包数据目录同名（`api.py:529-532` 的 `.exe` 后缀仅在 `is_win or is_cygwin` 追加，
`:1189-1194` 的 `os.makedirs` 撞同名文件即 `SystemExit`），不改 exe 基名或数据前缀就不可能
平铺。代码无需再改；余留人工动作 = 在 issue IKJPVB 回执平台限定。

**R-05 [SUGGESTION] `_load_common()` 无缓存**

每次调用重新 exec 模块 → 每次得到不同的类对象，将来 `isinstance(inputs, SpecInputs)` 会静默
恒假且不报错。修复：`@functools.lru_cache(maxsize=1)`，docstring 记录原因。

**R-06 [SUGGESTION] 解包失败抛 `ValueError`**

`list(EXCLUDES, ...)` 一旦被加第二个参数，失败信息是 `not enough values to unpack`。修复：先取
`args` 并断言长度为 1，再解包。

**R-07 [SUGGESTION] 清单条目断言强度不足**

`"PIL."`、`"PIL Image"`、`"pil"` 都能通过，而这三者在 PyInstaller 的 `excludes` 里语义都不对。
修复：要求每段为合法标识符 + 拒绝大小写变体重复；残余局限见跟踪表。

**R-08 [SUGGESTION] `Analysis` 守卫只查属性名**

`excludes=other.excludes` 也能通过。修复：追加断言宿主为 `inputs`（负向演练已确认被拦）。

**R-09 [SUGGESTION] `EXCLUDES` 注释承载取证细节**

13 行注释里塞了体积数字与 import 链路，issue 关闭后腐化。修复：压缩为前提 + 指向守卫用例与
`build/<name>/xref-<name>.html` / `warn-<name>.txt`。

---

## 三、迭代记录

| 轮次 | 范围 | 结论 | 处置 |
|---|---|---|---|
| 1 | `pack/_common.py` / 两个 spec / `tests/test_pack_spec.py` | `MINOR ISSUES`：0 CRITICAL / 4 WARNING / 5 SUGGESTION | 全部修复（`a0d1813`），R-04 转 📌 仅登记 |
| 2 | 同上（迭代 1 修复后复审） | `MINOR ISSUES`：0 CRITICAL / 2 WARNING / 2 SUGGESTION（R-10…R-13，其中 2 项由主代理自查发现） | 全部处置（`cb082c2` 修R-10/R-11，R-12/R-13 转 📌 仅登记） |
| 3 | 同上（迭代 2 修复后复审） | `MINOR ISSUES`：0 CRITICAL / 0 WARNING / 2 SUGGESTION（R-14 自查发现、R-15 既存事实） | R-14 已修（`6618a15`），R-15 转 📌 仅登记 |
| 4 | 同上（迭代 3 修复后复审，主代理自查） | 📈 0 CRITICAL / 0 WARNING / 2 SUGGESTION（R-14、R-15） | R-14 已修（`6618a15`），R-15 转 📈 仅登记 |
| 5 | 同上（迭代 4，另起独立只读评审复核） | `MINOR ISSUES` — 0 CRITICAL / 1 WARNING / 3 SUGGESTION（R-16…R-19） | 全部修复（`842f830`） |
| 6 | 同上（迭代 5 修复后终审） | ✅ `LOOKS GOOD` — 0 CRITICAL / 0 WARNING / 0 SUGGESTION | 循环终止 |

## 四、第二轮复审（迭代 1 修复后）

结论：`MINOR ISSUES` —0 CRITICAL / 2 WARNING / 2 SUGGESTION（R-10…R-13）。
两条 WARNING 都是**修复 R-02 时新引入的覆盖洞**，由主代理在复审中自查发现并经负向演练确认：
守卫的扫描面与动态 import 识别都不完整（R-10、R-11）。两条 SUGGESTION 是覆盖边界本身
（R-12 pyright 不检查 `.spec`；R-13 运行时拼名不可静态识别），只能登记为已知局限。

实测：`python -m pytest tests/ -p no:cacheprovider` → **1919 passed, 8 skipped**（退出码 0）；
`python -m pyright`（`include` 已含 `pack/`）→ **0 errors, 0 warnings, 0 informations**；
`python -m pytest tests/test_architecture.py -q` → 22 passed。

负向演练（真实守卫函数 + 内存合成 AST，6 组）：`from PIL import Image`、
`importlib.import_module('numpy')`、`from importlib import import_module` + `import_module('PIL')`、
`__import__('PIL.Image')` 全部 REJECTED；`importlib.import_module('textual')`（无关包）与
真实 `yate/` 树（含 10 个扩展文件）ACCEPTED；运行时拼名按预期 ACCEPTED（R-13 已登记）。

## 五、第三轮复审（迭代 2 修复后）

结论：`MINOR ISSUES` — 0 CRITICAL / 0 WARNING / 2 SUGGESTION。

- **R-14**（自查发现）：`_parse()` 未 memo，与 R-05 修过的 `_load_common()` 理由相同却待遇不同，
  属修复引入的不一致。已修（`6618a15`）。
- **R-15**（既存事实，非本次引入）：核实 CI 配置后确认 `.github/workflows/test.yml` 只跑
  pytest 与 changelog 门禁，**不跑 pyright**——即 R-03 的收益只在本机/代理侧生效。同时实测
  `python -m tools.changelog check` 退出码 0（"unreleased CHANGELOG.md lags 45 commit(s)"
  被显式容忍，released段落后判定为最新），故 changelog 门禁不构成本分支的阻塞项。两点均登记，
  不改CI 配置（超出本任务范围，且属项目级决策）。

实测（退出码全0）：`python -m pytest tests/ -p no:cacheprovider` → **1919 passed, 8 skipped**；
`python -m pyright`（`include` 含 `pack/`）→ **0 errors, 0 warnings, 0 informations**；
`python -m pytest tests/test_architecture.py -q` → 22 passed；
`python -m pytest tests --cov=yate --cov-branch --cov-fail-under=75` → **91.24%**（阈值 75%）；
行宽自查：四个改动文件均无 > 100 字符行（python-coding-style §1.1）。

## 六、第四轮复审（迭代 3 修复后，主代理自查）

结论：`LOOKS GOOD` — 0 CRITICAL / 0 WARNING / 0 SUGGESTION，六维度逐项过完：

| 维度 | 结论 |
|---|---|
| 正确性 | `EXCLUDES` 单一事实源 + `frozen=True` dataclass + 每次 `list(EXCLUDES)` 新建，spec 间无共享可变状态；`_load_common` / `_parse` 的 memo 不改变语义（树与模块均不被修改）；平台三元式与 PyInstaller `api.py:529-532` 的 `.exe` 后缀条件一致 |
| 安全 | 无secrets、无 `subprocess`/`eval`/`pickle`；守卫只读文件，无写入 |
| 性能 | 两处 memo 生效；`yate/**` 扫描 120 个文件（含 10 个扩展），单次测试开销可忽略；未在循环内做 I/O |
| Pythonic | 推导式 + `enumerate`/`zip` 类写法符合 §6.2；`@lru_cache` 优于手写缓存字典；未用 `Any`/`# type: ignore` |
| 可维护性 | 每个守卫 docstring 写明"守什么 + 局限"；`_EXCLUDES` 注释与守卫互相指名；pyproject 的 `include` 附注解释为何含 `pack` |
| 错误处理 | 无裸 `except`；所有守卫失败路径都给出带说明的 assert（`StopIteration` / `ValueError` 已清除） |

**本轮非零发现**：R-14（已修）与 R-15（既存事实，转 📈）。R-04（issue 回执）
与 R-12/R-13/R-15（覆盖边界）为登记类事项，不在代码内闭环。

## 七、第五轮复审（迭代 4 修复后，独立只读评审）

由独立评审成员按 `python-code-review` 框架复核，**不预设跟踪表的结论**。结论：
`MINOR ISSUES` — 0 CRITICAL / 1 WARNING / 3 SUGGESTION（R-16…R-19），已全部修复（`842f830`）。

评审的独立取证（我逐条复核后确认属实）：

- R-16：`pack/_common.py` 的 datas 清单里还有两类运行时被 `exec()` 的 Python ——
  `yate/yaterc.example`（`yate/config.py:280-281`）与 `yate/resources/theme_examples/*.example`
  （`yate/editor_view/theme.py:686-688`）—— 与 R-10 同根因，守卫只补了一半。
  我实测 10 个 `.example` 文件全部可 `ast.parse`，故按后缀纳入扫描是安全的；
  修后扫描面 123 个文件，负向演练确认"主题模板里 import PIL"被拦。
- R-17：冗余用例（`[]` 非 `ast.Attribute`，已被存活性断言蕴含）。
- R-18：`EXCLUDES` 注释残留 `13.1 MiB`，与 R-09 的自述不符。
- R-19：`pyproject.toml` 注释overclaim（`pyright pack/yate.spec` 实测 22 errors，
  证明 pyright 认得 `.spec` 但不把它纳入分析；`filesAnalyzed` 中 pack 只贡献 1 个文件）。

评审同时**独立验证并认可**了 R-04 / R-05 / R-11 / R-13 与 "`EXCLUDES` 前提本身安全"，
其取证包括：`pygments/formatters/img.py:21-25` 的 `try/except ImportError` 包裹、
`pygments/lexers/python.py` 里的字符串比对并非真实 import、site-packages 全量扫描
（除 PIL 自身 / PyInstaller hook / `_pytest` / `pip` 外无第三方真依赖，且本 venv 未装 numpy）。

评审声明的证据边界（如实登记）：其为只读评审，未跑真实 PyInstaller 构建，
故 issue 的两条核心诉求只做了源码级交叉验证；真实构建的复测由主代理承担
—— 见 §八。

## 八、终审（迭代 5 修复后）

`LOOKS GOOD` — **0 CRITICAL / 0 WARNING / 0 SUGGESTION**，六维度逐项过完：

| 维度 | 结论 |
|---|---|
| 正确性 | `EXCLUDES` 单一来源 + `frozen=True` dataclass + 每次 `list(EXCLUDES)` 新建；两处 `lru_cache` 不改语义（模块与 AST 树均不被修改）；`*.example` 扫描面对10 个模板全部可解析 |
| 安全 | 无 secrets / `subprocess` / `eval` / `pickle`；守卫只读文件，无写盘 |
| 性能 | `_load_common` / `_parse` 均memo；`yate/**` 扫描 123 个文件，单次测试开销可忽略；循环内无 I/O |
| Pythonic | 推导式、`set` 合并 + `sorted`、lru_cache 优于手写字典；无 `Any` / `# type: ignore` / `TYPE_CHECKING` |
| 可维护性 | 每条守卫 docstring 写明"守什么 + 局限"；`_EXCLUDES` 注释与守卫互相指名；pyproject 注释不再 overclaim |
| 错误处理 | 无裸 `except`；全部失败路径为带说明的 assert（`StopIteration` / `ValueError` 已清除） |

### 真实构建复测（补缪独立评审声明的证据边界）

独立评审为只读评审、未跑构建，本轮由主代理补跑：

```
python -m PyInstaller --noconfirm --clean --distpath dist --workpath build pack/yate.spec
```

| 环节 | 实测结果 |
|---|---|
| 构建 | `Build complete!`（退出码 0） |
| 产物路径 | `dist\yate\yate.exe` 存在（`Test-Path` → `True`） |
| 平铺布局 | `dist\yate\_internal` 不存在（`Test-Path` → `False`） |
| 体积 | **54.8 MiB / 327 文件**（与迭代 1 记录的 54.8 MiB 一致） |
| PIL | `dist/yate/PIL` 不存在（`False`） |
| 冒烟 | `dist\yate\yate.exe --version` → `yate 0.2.9 … yet another terminal editor (Textual based)`，退出码 0 |

构建产物与临时脚本已清理；修复本身不影响 Windows 产物行为。

最终门禁（主代理亲跑，退出码全 0）：

| 命令 | 结果 |
|---|---|
| `python -m pyright` | 0 errors, 0 warnings, 0 informations |
| `python -m pytest tests/ -p no:cacheprovider` | 1917 passed, 8 skipped |
| `python -m pytest tests/test_architecture.py -q` | 22 passed |
| `python -m pytest tests --cov=yate --cov-branch --cov-fail-under=75` | 91.24% |
| `python -m pytest tests/test_pack_spec.py --collect-only -q` | 9（8 个函数 + 1 个参数化×2） |
| 行宽自查（4 个改动文件） | 无 > 100 字符行 |

**循环终止**：第6 轮零发现，"修复 → 复审 → 登记"闭环结束。R-04（issue 回执）与
R-12 / R-13 / R-15（覆盖边界与既存事实）为登记类事项，不在代码内闭环。

## 九、第二轮评审（issue note_51452120：统一布局与内容目录改名）

评审对象：`master...enh/pack-bundle-layout` 第二轮 diff（`0e30a38`、`106e47c`、
`3914673`、`dcf1f72`）——`pack/yate.spec` 的 `CONTENTS_DIRNAME`、`pack/pack.ps1` /
`pack/pack.sh` 的内容目录校验、`tests/test_pack_spec.py` 的布局守卫重写、
`README.md` / `README.zh.md` 的布局说明。

评审方法：同一 `python-code-review` 六维度框架 + 负向演练 + **真实构建复测**
（本轮主代理亲跑，弥补第一轮"评审成员为只读评审、无构建证据"的边界）。

### 9.1 问题跟踪

| # | 严重度 | 问题描述 | 影响范围 | 状态 |
|---|---|---|---|---|
| R-20 | SUGGESTION | `tests/test_pack_spec.py` 的绑定扫描把 `and` / `or` 混写在一个推导条件里，语义正确（`and` 优先）但读者需自行推导优先级 | 可读性（守卫是他人维护的契约面） | ✅ 已修（主代理补显式括号） |
| R-21 | SUGGESTION | 两个脚本用正则从 spec 里"解析"常量（`^(CONTENTS_DIRNAME: str = "...")$`）：若常量定义换形式（去注解、换引号、拆行），提取会失败 | 构建脚本与 spec 的耦合方式 | 📌 仅登记：失败是 **fail-fast**（脚本明确报错退出），不会静默校验错目录；提取式集中在一行，失败信息直指 spec |
| R-22 | SUGGESTION | `pack/pack.sh` 的新校验在本机**未经 shell 实测**（无 bash） | Linux 构建路径的验证覆盖 | 📌 仅登记（计划 §9.2 L2）：已人工核对 `sed` 提取式；建议与遗留项 L1 的 Linux 构建一并验证 |
| R-23 | SUGGESTION | README 目录树同时列出 `yate.exe` 与 `yate` 两行，字面上像"同一产物两者并存" | 读者第一印象 | 📌 仅观察：两行各自带平台注释（Windows 入口 / POSIX 入口），语义无误；改成"二选一"写法反而更啰嗦 |
| R-24 | SUGGESTION | `_internal` 在历史文档中残留（`.trae/documents/dist-copy-plan.md:61`、本计划 §7 的历史章节） | 全仓检索时的噪音 | ⏸ 不修：历史计划与决策记录按"只追加不改写"原则保留（第一轮即已登记） |

### 9.2 独立验证（非引用成员自述，主代理亲跑）

| 环节 | 实测 |
|---|---|
| 真实构建 | `python -m PyInstaller --noconfirm --clean --distpath dist --workpath build pack/yate.spec` → `Build complete!`，退出码 0 |
| 布局 | 顶层仅 `runtime/` + `yate.exe`；`dist\yate\_internal` 不存在；`dist\yate\runtime\yate\resources\app.tcss` 存在；`dist\yate\runtime\PIL` 不存在 |
| 体积 | 327 文件 / 54.8 MiB（与第一轮平铺产物一致——`contents_directory` 只改落盘位置） |
| 冒烟 | `--version` 退出码 0；`--diag` 退出码 0 且 `prefix = …\dist\yate\runtime`，**实证 `sys._MEIPASS` 指向内容目录**（计划 F13 成立，`yate/paths.py` 确实无需改动） |
| 守卫负向演练 | 7 组退化形态（平铺字面量 / 平台三元 / `_internal` / 撞 exe 基名 / 空串 / 多级路径 / 删掉关键字）**全部 REJECTED**；演练后 spec 字节级还原（`spec restored: True`，`git diff` 为空） |
| 全量门禁 | `pyright` 0 errors；`pytest tests/` **1922 passed, 8 skipped**；架构 + 打包守卫 **36 passed**；覆盖率 **91.26%**（阈值 75%） |

### 9.3 子代理产出（只认落盘）

| 成员 | 名下文件 | 复核结论 |
|---|---|---|
| `pack-spec-guards` | `tests/test_pack_spec.py` | 有产出；主代理重跑 14 passed + pyright 0 errors，另做 R-20 修正 |
| `pack-readme` | `README.md`、`README.zh.md` | 有产出；双语语义一致，无残留旧布局的当前时态表述，未越界改其它文件 |

### 9.4 结论

`MINOR ISSUES` — 0 CRITICAL / 0 WARNING / 5 SUGGESTION（R-20 已修，R-21…R-24 登记）。
六维度：正确性（单一常量 + COLLECT 继承 + 守卫双段断言）／安全（只读正则、无写入）／
性能（仅构建期）／Pythonic（无 `Any`、无 `type: ignore`）／可维护性（docstring 写明
"守什么 + 局限"，POSIX 未验证如实标注）／错误处理（无裸 `except`，脚本失败均 fail-fast）。
**遗留人工动作**：Linux 上跑一次 `pack/pack.sh`（计划 L1/L2）、在 issue 回执本轮取舍（L3）。

### 9.5 成员待裁决项的处理（延迟送达的报告）

两名成员在团队回收后才送达完整报告，其中三项待裁决/待核实事项，主代理逐条处理如下。

**（1）提交归属偏离（成员提出，主代理已核实并登记）**

`pack-spec-guards` 报告"我改 96 行，但 `git diff --numstat` 显示 239/34"，怀疑工作区带着
第一轮未提交内容。主代理实测核实：

| 事实 | 取证 |
|---|---|
| 本轮起点 HEAD（`fadd935`）的 `tests/test_pack_spec.py` 为 **281 行**，与 `842f830` 完全一致（`git diff 842f830 fadd935 -- tests/test_pack_spec.py` 为空） | 提交态历史本身干净，**不是**"某次提交被回退" |
| 该 281 行版本**不含** `_SPEC_HELPER_FIELDS`、`_REVIEWED_DYNAMIC_IMPORTS`、`test_collect_when_common_parsed_fills_every_spec_input_field`、`test_spec_when_parsed_reads_every_spec_input_field`、`test_dynamic_imports_when_scanned_are_reviewed_not_invisible` | 这 5 项正是第一轮评审 R-07/R-08/R-12/R-13 的产物，第一轮**在工作区改完并跑过门禁，但从未提交** |
| 该 281 行版本**已含** `@functools.lru_cache(maxsize=1)` / `(maxsize=None)` | R-05（`_load_common` memo）、R-14（`_parse` memo）当时已提交 |
| 本轮 `3914673` 一次引入 9 个函数/用例 | 其中 2 个是本轮布局守卫，另 5 项函数 + 2 个用例属第一轮遗留补交 |

结论：**属实的是"第一轮遗留未提交产出被本轮提交顺带带入"**，而非成员所推测的历史回退。
处置：

- **不改代码**——被顺带提交的内容正是评审记录里已登记的项目，且已由本轮门禁独立验证
  （`pytest tests/` 1922 passed、`pyright` 0 errors、守卫 14 passed）；
- **不改写历史**——分支未推送，但拆分提交需重写 `3914673` 与其后的 docs 提交，
  收益仅为提交粒度，风险高于收益；`git-commit-message.md` 的"每步单独提交"要求
  在此记为**事后登记的偏离**；
- 若日后有人追问"这些用例是哪来的"，本节与 §9.2 的门禁数字即为答案。

**（2）README 目录树里运行时文件写成「Python 运行时 / the Python runtime」**

成员自问是否要改成计划 §8.1 的 `python3xx.dll` 占位。裁决：**保留成员的写法**。
理由：该树现在同时代表 Windows 与 POSIX，`python313.dll` 只在 Windows 成立，写死
具体文件名会让 Linux/macOS 的读者读到假信息；抽象表述与计划的占位意图一致。

**（3）README 新增的「整目录一起拷贝」部署句**

成员自问是否越界。裁决：**保留**。这不是新增约定而是本次布局变更的直接后果——
内容目录必须与入口同级随目录整体分发，不写会让用户只拷 `yate.exe` 而拿到无法启动的
产物。原 README 缺的正是这句，补写属于"只改与本布局相关的句子"。

另：成员报告的"README 里 `_internal` 只剩历史语气"与"无 >100 字符的新增行"，主代理
diff 复核一致（`README.md` 另有 26 处 >100 字符的既有行，非本次引入，不擅自重排）。

### 9.6 外部 AI 队友评审登记（PR 58 评论 note_51452441）

- **来源**：<https://gitee.com/jermaine/yate/pulls/58#note_51452441_conversation_191423547>
- **评论者**：`pull_review_bot_2f642dd39f557e6f`（PR 观察者）｜2026-10-06 09:26:43，结论更新于 09:31:44
- **四维结论**：功能性 ✅ 通过｜安全性 ✅ 通过｜性能 ✅ 通过｜可维护性 ⚠️ 待优化
- **总评**：**无阻断项，1 个改进建议，可优化后合并**；风险等级 low。

评论对改动的判断（与本记录 §9.4 一致）：排除清单前提由 `yate/**`（含 `.py` 与
`.example`）的 AST 扫描守护、动态导入白名单精确匹配两处真实调用、布局契约钉住跨平台
统一的 `runtime/` 并规避 POSIX exe 撞名缺陷；只读文件、无危险调用；开销仅在构建期测试。

**改进项（1 条）**：`pack/pack.ps1` / `pack/pack.sh` 以正则
`^CONTENTS_DIRNAME: str = "([^"]+)"` 提取内容目录名，强绑定 spec 的声明形式——去注解、
换引号或拆行都会提取失败；建议在 `pack/yate.spec` 的常量定义处补注释显式声明"该形式被
脚本正则依赖，请勿随意改写"。

主代理裁决：

| 项 | 结论 |
|---|---|
| 与本记录的关系 | 与 §9.1 的 **R-21** 同根因（脚本 ↔ spec 的解析耦合），已在第一轮登记为"仅登记"：失败是 fail-fast，不会静默校验错目录 |
| 是否采纳 | **本轮不实施**（用户指示本轮只登记、不做其他改动）。建议本身成本极低——在 `pack/yate.spec:66-70` 的 `#:` 注释里加一句"脚本按 `CONTENTS_DIRNAME: str = "..."` 单行形式正则提取，改写声明形式前请同步两个脚本" |
| 后续处置 | 登记为待办（见计划 §9.2 L5），下一轮动 `pack/yate.spec` 时顺带补上；或直接在 review 记录里以本节为闭环依据 |
