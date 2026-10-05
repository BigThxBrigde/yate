# Python 代码评审（python-code-review 框架）— IKJPVB 打包瘦身与布局改动

- **评审对象**：分支 `enh/pack-bundle-layout`（issue IKJPVB）的 Python 代码：
  `pack/_common.py`（`EXCLUDES` + `SpecInputs.excludes` + `collect()`）、
  `pack/yate.spec`（`excludes=` / `contents_directory=`）、`pack/yate-onefile.spec`
  （`excludes=`）、`tests/test_pack_spec.py`（新建）。
- **评审方法**：按 `.trae/skills/python-code-review/SKILL.md` 六维度框架
  （正确性 / 安全 / 性能 / Pythonic / 可维护性 / 错误处理）与三级严重等级，
  对照 `.trae/rules/python-coding-style.md` §五检查清单逐条核对。
  **工具说明**：本会话未提供 `lsp` 工具，LSP 语义分析不可用，按该 skill 的回退
  规则改用 `read_file` / `search_content` / `pyright` 取证，未以文本匹配冒充语义结论。
- **对比基线**：`.trae/reviews/2026-10-03-python-code-review.md`（83 项全量评审）。
  其中 R-66 指出两个 spec 约 90 行构建逻辑重复——已由本分支之前的
  `pack/_common.py` 抽取解决，本次改动沿用该共享结构，未引入新的重复。
- **实测门禁**（本 worktree，退出码全 0）：

  | 命令 | 结果 |
  |---|---|
  | `python -m pytest tests/test_pack_spec.py tests/test_architecture.py -q` | 32 passed |
  | `python -m pyright yate/ tests/ tools/` | 0 errors, 0 warnings, 0 informations |
  | `python -m pyright pack/`（显式补测，见 R-03） | 0 errors, 0 warnings, 0 informations |

- **总体结论**：`MINOR ISSUES` — **0 CRITICAL / 4 WARNING / 5 SUGGESTION**（编号 R-01…R-09）。

---

## R. 打包改动（`pack/`）

**R-01 [WARNING] `tests/test_pack_spec.py:10-13` — 模块 docstring 仍无条件宣称"平铺"，与守卫实现矛盾**

问题：修复 POSIX 撞名缺陷时，`pack/yate.spec` 的模块 docstring 与行内注释都改成了
平台限定，但本测试文件的模块 docstring 被漏掉：仍写
``EXE(contents_directory=".")``、"the one-folder spec keeps the flat layout -- the
runtime files sit next to ``yate.exe``"。同一文件 `:215-240` 的实现却已断言
`IfExp(sys.platform == "win32", ".", "_internal")`。测试文件的 docstring 是后来者读
守卫语义的第一入口，此处会给出与代码相反的结论。

修复：把该段改为平台限定表述——Windows 平铺（`contents_directory="."`）、
其它平台保留 `_internal`，且守卫断言的是这个三元形状。

**R-02 [WARNING] 排除清单的前提无守卫：将来 `yate/` 引入 PIL 会静默产出坏 exe**

问题：`pack/_common.py:77-80` 排除 `PIL`，`tests/test_pack_spec.py:149-153` 只钉住
"清单里要有 PIL/numpy"，没有任何东西钉住"yate 不用 PIL"。今天安全（实测
`yate/**` 对 `import PIL|from PIL|numpy` 大小写敏感检索 0 命中），但一旦某个新特性
（如截图、缩略图）import 了 PIL，构建依旧成功、只有用户双击 exe 才报 ImportError，
构建报告也不会指向 `EXCLUDES`。这正是 `tests/test_architecture.py` 已有的"构建期假设"
守卫面（如同 R12 的 devtools 通道禁令）。

修复：按 `EDITOR_FORBIDDEN_IMPORTS`（`tests/test_architecture.py:168`）的现成形态，
加一条"`yate/**` 禁止 import `EXCLUDES` 内的包"用例（AST 扫 `ast.Import` 的
`alias.name` 与 `ast.ImportFrom` 的 `node.module` 首段）。

**R-03 [WARNING] `pack/` 不在 pyright 门禁范围，而它三个文件都是 Python 语法**

问题：`pyproject.toml:100-107` 的 `include = ["yate", "tools", "tests"]` 不含 `pack/`，
因此两个 `.spec`（PyInstaller 以 `exec` 方式当作 Python 脚本运行）与 `_common.py`
**不受 pyright strict 约束**。本次改动新增的正是"dataclass 加字段 + 两个 spec 各传一处"
这种最容易漏接一处的跨文件契约。实测 `pyright pack/` 零诊断，说明当前干净——所以这是
零成本的门禁补齐而不是返工。

修复：`pyproject.toml` 的 `include` 增加 `"pack"`（实测纳入后仍 0 errors）。

**R-04 [WARNING] issue 的"无 `_internal`"诉求在 POSIX 上结构性未达成，需在 issue 回执**

问题：`pack/yate.spec:92` 的平台条件式意味着 Linux/macOS 仍产出 `_internal/`
（`pack/pack.sh:107` 的 `dist/yate/yate` 不变，两份 README 里 `dist/yate/yate` 的承诺
因此继续成立）。根因是 exe 与内置 `yate/` 包数据目录同名：
`PyInstaller/building/api.py:529-532` 的 `.exe` 后缀仅在 `is_win or is_cygwin`
分支追加，`:1189-1194` 的 `os.makedirs` 撞上同名文件即 `SystemExit`。不改 exe 基名
或数据前缀就不可能平铺——属有意取舍（Windows 才是 issue 截图与主要分发场景）。

修复：无需改代码；需在 issue IKJPVB 上明确回复"平铺仅 Windows，POSIX 因
exe/包目录同名保留 `_internal/`"，避免需求方按"未完成"处理。

## S. 守卫测试（`tests/test_pack_spec.py`）

**R-05 [SUGGESTION] `:50-67` `_load_common()` 无缓存，每次调用重新 exec 模块**

问题：三个用例各调一次 `_excludes()`，模块被 exec 3 次（本身开销可忽略，该模块顶层
只碰 stdlib）。更实质的是**每次得到不同的类对象**：将来若加
`isinstance(inputs, SpecInputs)` 之类判断会静默失效（同名不同类恒为 `False`），
且这种失效不会报错。

修复：`@functools.lru_cache(maxsize=None)` 装饰 `_load_common()`，或改为模块级常量
一次性取值。

**R-06 [SUGGESTION] `:188` `[source] = excludes_value.args` 解包失败抛 `ValueError`**

问题：与本轮刚修掉的裸 `next()` 同类。`list(EXCLUDES, ...)` 一旦被加上第二个参数，
失败信息是 `not enough values to unpack (expected 1, got 2)`，而不是带说明的断言。

修复：先取 `args = excludes_value.args`，断言其长度为 1，再解包。

**R-07 [SUGGESTION] `:156-161` 用例名说 "module names"，断言强度低于名称**

问题：只校验非空与无首尾空白；`"PIL."`（尾点）、`"PIL Image"`（含内部空格）、
`"pil"`（大小写）都能通过，而这三者在 PyInstaller 的 `excludes` 里语义都不对。

修复：补一条分段断言——每个 `.` 分段都应为合法标识符（`part.isidentifier()`）。

**R-08 [SUGGESTION] `:200-201` 只查属性名、不查宿主对象**

问题：`excludes=other.excludes` / `excludes=getattr(inputs, "excludes")` 都能通过。
上一轮判"不改"（keyword 被改名会先被 `:176-190` 的 `collect()` 守卫拦下），本次按
框架复核**维持该判断**——绑死中间变量名会让 spec 重构无谓地红。但如实登记残余风险：
将来若 inventory 经第二个对象转发，这条守卫会漏。两行即可加固（同时断言
`.value` 是 `Name` 且 `id == "inputs"`）。

**R-09 [SUGGESTION] `pack/_common.py:64-76` `EXCLUDES` 注释 13 行，取证细节压在代码上**

问题：注释里塞了 13.1 MiB / 68.4 MiB、`pygments.formatters.img` 链路、
`PIL._typing` 的 numpy 等细节。issue 关闭后这些数字只会腐化，而真相已在
`.trae/documents/pack-bundle-layout-plan.md` §7.2 与 README 双语里各存一份。

修复：压缩为 3-4 行（"均为运行期从不使用的传递依赖；PIL 由
`pygments.formatters.img` 拖入，yate 仅在 `tools/pack/icon.py` 动态用它重生成已入库的
`pack/yate.ico`；新增条目前用 `build/<name>/xref-<name>.html` 取证"），数字与链路细节留给文档。

---

## 优势

- **单一事实源**：`EXCLUDES` 集中在 `pack/_common.py`，两个 spec 只消费
  `inputs.excludes`；`excludes=[]` 这一"issue 前的形态"被守卫钉死，不会静默回退。
- **不共享可变状态**：`collect()` 每次 `excludes=list(EXCLUDES)` 造新 list，
  `SpecInputs` 是 `frozen=True` dataclass —— 两个 spec 各拿一份，互不污染。
- **守卫不是空转断言**：主代理用真实守卫函数 + 内存合成 AST 跑过 5 组负向演练
  （正确形态 ACCEPTED；旧写法 / 写死 `_internal` / 两分支对调 / 删掉关键字全部
  REJECTED 且各带原因），这条证据比断言本身更有价值。
- **跨平台缺陷的处置留痕**：plan §7.8/§7.9 记录了缺陷根因（PyInstaller 源码行号）、
  方案 A/B/C 的取舍与否决理由、守卫形状断言的局限声明，未把"Windows 构建成功"
  误当作跨平台结论。
- **用户可见文档与实现同步**：README 双语都写明"平铺仅限 Windows"及原因，并订正了
  早已过期的单文件体积数字（`~16 MB` → `~20 MB`）。

## 处置建议

0 CRITICAL ——**可合并**。R-01/R-02 建议在合并前做（前者是文档漂移，后者是防止未来
静默产出坏 exe 的守卫缺口）；R-03/R-04 是门禁补齐与 issue 回执；R-05…R-09 为
可读性与健壮性改进，可登记待办。