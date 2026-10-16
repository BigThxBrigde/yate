# 2026-10-16 全仓库多维度审核（Gitee IKMD0E）

- Issue：[Gitee IKMD0E](https://gitee.com/jermaine/yate/issues/IKMD0E)（ENH - 全仓库多维度审核）
- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit` @ `b36f9b3` + 计划提交）
- 审核方案：[`../documents/full-repo-audit-plan.md`](../documents/full-repo-audit-plan.md)
- 修复方案：[`../documents/full-repo-audit-review-fixes-plan.md`](../documents/full-repo-audit-review-fixes-plan.md)
- 形态：只读事实文档（记录发现与核对结论，不放修复排期）
- wave-1 取证：3 个只读子代理分域并行（正确性+健壮性 / 安全+性能 / 可维护+扩展+文档规范），
  全部 BLOCKER/MAJOR 发现经主代理独立复核（复现命令实测）后方可写入本记录

## 一、基线门禁（主代理亲测）

| 门禁 | 结果 |
|---|---|
| `pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 |
| `pytest tests/ -q` | 全绿（100% 通过），exit 0（含架构测试 31 用例） |
| 豁免名单行数（`splitlines()` 口径复测） | editor.py 1024 / vim.py 1184 / buffer.py 1069 / wiki.py 1495 / langdefs.py 813 / logs.py 690 —— 与规则 §三.7 登记逐项一致，零漂移 |
| 逼近阈值观察项 | `services/yxp.py` 705、`editor_view/panes.py` 694（维持 IKMCZW 登记） |
| 分支 diff 面 | 计划文档 1 个文件，零产品代码改动（修复前） |

## 二、逐维度结论

### 维度 1 功能正确性 — 2 MAJOR + 1 MINOR

- **[MAJOR] F-1 `yate/editor_term/emulator.py:591-601`**：EL mode 1 在 autowrap 挂起（pen）态越界。
  `_print` 会把 `cur[1]` 推到 `== self.cols`（`emulator.py:380-383`），此时 `EL1` 的
  `range(0, col + 1)` 取到 `line[self.cols]` → `IndexError`。`K` 不在清 pen 集合
  `"HfABCDEFGdsu"`（`emulator.py:492`）内，pen 态跨序列存活。
  **主代理复现实测**：`TerminalEmulator(cols=10).feed(b"0123456789"); feed(b"\x1b[1K")`
  → `IndexError: list assignment index out of range`（emulator.py:601）。既有测试
  `test_erase_line_modes` 的 EL1 用例先发 `\x1b[3G` 重定位光标，pen 态未覆盖（守卫缺口）。
- **[MAJOR] F-2 `yate/editor_term/emulator.py:546-549, 670-676`**：`S`/`T`（scroll region）
  count 无上界——同文件 `_insert_chars:630` / `_delete_chars:638` / `_insert_lines:655` /
  `_delete_lines:665` 均做了 `min(count, …)` 钳制，唯 `S`/`T` 漏钳；
  `ESC[999999999S` 触发 O(count×rows) 循环。
  **主代理复现实测**：`feed(b"\x1b[999999999S")` 挂死（探针 idle 超时被强制终止，即证据本身）。
- **[MINOR] F-3 `yate/keymaps/vim.py:483-489, 946-956, 1018`**：count 无上界，`9999999999j`
  型输入一次挂起十亿次单步移动。需用户超长键入触达，非外部不可信输入，登记不修。
- 其余热路径（`buffer.py` 全文、`flows/` 11 文件）边界抽查零发现（空输入/None/零值/越界钳制/
  可变默认参数逐项核对通过）；2026-10-12 review 的 H1/H5/M5 已修复态复核成立，不重报。

### 维度 2 安全性 — 1 MAJOR + 6 核对通过

7 项疑点逐一按"输入源 → 传播 → 汇点"链路确证：

- **[MAJOR] F-4 项目 rc 与 cwd/themes 无信任门控（trust 不变量旁路）**：
  `yaterc.py:83-96` 项目 rc 自 cwd 及祖先目录发现 → `cli.py:364-379` 启动无条件 exec
  （全内建可用）；`cli.py:369-372` 无条件加载 `Path.cwd()/themes/*.py` exec
  （`theme_files.py:70`）。与 `yate/services/trust.py:3-5` 自声明不变量
  "Opening a repository must never execute the repository's own code" 直接冲突：
  克隆一个仓库并在其中打开 yate 即执行仓库自带 Python（复现：目录内放 `yaterc`
  内容为任意 Python → 在该目录启动 yate 即执行）。旁路放大：项目 rc 可声明
  `extensions = ["./extensions/evil.py"]`，rc 声明路径无条件加载
  （`loader.py:285-293` 仅门控默认 `./extensions`），绕过 `:trust` 门控。
  `yaterc.en.md` 将其登记为 vimrc 式设计，但 vim 的 `exrc` 同类机制亦有确认门槛——
  本记录按 trust.py 自声明不变量判 MAJOR，定性"设计取舍 vs 不变量冲突"，修复方案见修复方案文档。
- 核对通过 6 项：`services/shell.py:72-74` shell=True（输入=用户 `:!` / 扩展显式调用，
  cwd/pid 不进入命令串）；`tools/pack/wiki.py:627-636` shell=True（`--translate-cmd`
  本地 CLI 参数，翻译文本走 stdin）；`pty_proc.py:255` subprocess（argv 列表 + noqa: S603 在位）；
  lua runtime（chunkname 常量、无用户可控插值；信任级=Python 扩展，lupa 默认 runtime
  不收口登记为观察项 MINOR）；`yxp.py` zip-slip 回归面完整（名字规范化/双校验/手工提取/
  symlink/TOCTOU digest）；危险文件操作 7 文件输入源全部用户显式或自产路径。
- `# type/pyright: ignore` 13+1 处逐处核对：理由注记全部完备（场景成立），核对通过。
- 外联面：yate/ 0 真实外联；tools/ 仅 `tools/changelog/gitee.py:110-118` urlopen
  （构建工具、CLI 参数输入源、超时+异常在位）。

### 维度 3 性能 — 5 MINOR 疑点登记（不做无 profiler 优化）

| # | 位置 | 疑点 |
|---|---|---|
| P-1 | `yate/flows/prompt_flows.py:54-58` → `editor_core/search.py:50-64` | live search 每键击全 buffer 逐行 `finditer` 重扫 |
| P-2 | `yate/editor_core/search.py:71-81` | `_index_at_or_after` 线性 O(matches)，替换确认逐次按键调用 |
| P-3 | `yate/editor_term/emulator.py:436-446, 655-672` | 滚动/插删行逐行平移，O(count×rows) |
| P-4 | `yate/editor_term/emulator.py:612-620` | `_erase_display` 每行重复构造 blank 行 |
| P-5 | `yate/services/workspace.py:117-124, 171-176` | 目录遍历循环内 `read_text`（.gitignore 语义所需） |

全仓循环内字符串拼接 24 处逐处目检均不在循环体内；未发现确证重复计算。修复须先 profiler 实测。

### 维度 4 可维护性 — 2 MINOR

- **F-5** `tests/test_workspace_filter.py:56`：注释提及 `Optional[Path]`（§3.2 "全仓 0 处"
  口径漂移为注释 1 处）。
- **F-6** `tools/yxp/__init__.py`：纯 docstring 模块缺 `from __future__ import annotations`
  （tools/ 60 个 `.py` 唯一缺失）。
- 其余零发现：公共 docstring 抽查（yxp.py / cli.py / wiki.py / mouse_flows /
  extension_flows / api.py）全齐；遗留写法 yate/ tools/ 0 处；嵌套 ≤3；魔法数均有具名常量；
  `from __future__` yate/ 139/139、tools/ 59/60。

### 维度 5 健壮性 — 1 MINOR（3+1 处静默吞异常）

- 裸 `except:` 0（复核通过）；`except Exception` 26 处全部带 `noqa: BLE001 - <理由>`。
- **F-7 [MINOR]** 实质静默吞异常 4 处（无 log 无反馈，字面违反 python-coding-style §4.5
  第 3 条）：`editor_lsp/manager.py:366-368, 444-447`（didOpen/didChange 通知失败静默）、
  `services/user_setup.py:278-280`、`services/fonts.py:224-227`。登记待办。
- best-effort 类静默块（logs.py / client.py / pty_proc.py / shell.py / terminal.py 共 14 处）
  均有注释背书属"explicitly silenced"豁免口径，登记备案不立项；EAFP 形态 4 处不属吞异常。
- 资源泄漏零确证发现（open 全 `with`；Popen 3 处管理完整；`tools/probes/pb6_real_input_harness.py:268`
  Popen 无 terminate 兜底登记 MINOR——开发探针、短生命周期）。

### 维度 6 可扩展性 — 零发现

门面 `__all__` 14 名逐名核对一致且可解析；双语手册引用的导入路径/API 名/桥方法/事件面/
缓冲方法 100% 存在于实现；`*Flows` 接入清单（§三.8 六步）逐项通过（10 个流程模块 +
`LspSync` + 纯函数模块命名、editor.py 类属性声明 9 个、工厂构造、组装注释齐全）。

### 维度 7 项目结构 / 维度 8 职责单一性 — 零新增发现（增量复核）

交叉引用 [2026-10-16-repo-structure-audit.md](2026-10-16-repo-structure-audit.md)（同日 IKMCZW）；
本轮增量复核：豁免名单行数零漂移（§一）、包 `__init__` 惰性约定无回潮、无新增错位文件。

### 维度 9 架构边界规则 — 零发现

R1–R14 违规信号 grep 全 0（`import yate.app` 出界 / TYPE_CHECKING / `Optional[` / `self.log` /
类级 `ScrollBar.renderer` / `X = Callable[` / 相对导入 / 扩展机件直引）；架构测试 31 用例全绿。

### 维度 10 门禁规则 — 全绿

四道门禁见 §一基线；覆盖率基线引分支既有记录 91.92%（≥75%），终态实测在修复后 Step 7 执行。

### 维度 11 代码文档规范 — 2 MINOR + 1 疑点

- **F-8** `yate/services/extensions/lua/__init__.py:10`：docstring 含中文（"architecture
  boundaries §三.5"），misc-rules §四 要求 docstring 英文。
- **F-9** `yate/docs/extensions.en.md:373` vs `extensions.zh.md:346`：SCSS/LESS 留在
  regex 后端的理由语义宽严不一（en "no grammar for them exists" 绝对断言 vs zh "PyPI
  没有对应的 tree-sitter 语法包" 限定 PyPI），双语同步硬约束（doc-conventions §三）下的语义偏差。
- **F-10（登记不修）** `tools/probes/verify_matrix.ps1` 约 20 行中文注释（存量证据附件，
  doc-review-sweep 已登记其形态争议）；`tools/changelog/__init__.py:12`（`[缺中文]`
  段标记名）与 `tools/probes/pb6_real_input_harness.py:211`（实测证据引述 `key=先`）
  属引述性中文，misc-rules §四无解释性条款，规则空白待裁决。
- 其余零发现：yate/ 内 `#` 中文注释 0 处；双语手册 4 对全部成对；`#:` 抽查 17+ 文件合规；
  根文档四件俱在无改名。

### 维度 12 规则纪律性 — 2 MINOR（存量）

- **F-11** `.trae/reviews/2026-09-26-readonly-feature.md` 文件名命中 `*-feature` 后缀禁令
  （doc-conventions §六；与 doc-review-sweep "命名违规 26→0" 结论存在口径出入——该文件
  未收录其违规表）。存量随下次修改迁移，登记不修。
- **F-12** `.trae/documents/ext-api-parity-plans/` 子计划文件为下划线分词
  （`plan_a.md`…`plan_d.md`，规范形态 `<task>-<subtask>-plan-<a|b...>.md`）。
  存量随下次修改迁移，登记不修。（子代理报告曾误指 architecture-boundaries.md:10 引用
  数量漂移——经主代理复核该行引用的是 app-layering-refactoring-plans/，实存 plan_a–g
  且命名合规，误报驳回。）
- 其余零发现：`*-ops*` 0 文件；日期混排 0 文件；documents 内无 README.md；git log
  最近 40 条全 conventional 英文；SIZE_EXEMPT_FILES 与规则 §三.7 两处同步一致。

## 三、处置汇总

| 级别 | 编号 | 处置 |
|---|---|---|
| MAJOR | F-1（EL1 pen 越界） | 确证真问题 → 修复（见修复方案文档 Fix-A） |
| MAJOR | F-2（S/T count 无上界） | 确证真问题 → 修复（Fix-B） |
| MAJOR | F-4（trust 不变量旁路） | 确证真问题 → 修复（Fix-C） |
| MINOR | F-3 / F-5~F-12 / P-1~P-5 / lua runtime 观察项 / pb6 Popen | 登记待办，不阻塞收尾 |
| 误报驳回 | 子代理报告 2 条（architecture-boundaries.md:10 引用漂移；F8 数量漂移） | 主代理复核后驳回，理由见 F-12 |

修复方案：[`../documents/full-repo-audit-review-fixes-plan.md`](../documents/full-repo-audit-review-fixes-plan.md)
（与本记录互链；仅限审核确证的 BLOCKER/MAJOR + 文档漂移，禁止顺手重构）。
