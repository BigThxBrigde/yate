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
| 3 | 同上（迭代 2 修复后复审） | 见 §五 | 见 §五 |

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

待回填。
