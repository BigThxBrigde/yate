# 2026-10-17 仓库结构 / 分层 / 模块组织审计

- 分支：`enh/full-repo-audit`（worktree `../yate-full-repo-audit` @ `bdb74eb`）
- 范围：整体仓库（`yate/`、`tests/`、`tools/`、`pack/`、`typings/`、根级配置与文档）在**项目结构、
  分层依赖、模块组织**三个面上的混乱/不合理项
- 形态：**只读事实文档** —— 只记录发现、核对结论与修复建议，不含修复排期、不含任何代码改动
  （doc-conventions §二.1）
- 交叉引用：同日/相邻审核 [`2026-10-16-full-repo-audit.md`](2026-10-16-full-repo-audit.md)、
  [`2026-10-16-repo-structure-audit.md`](2026-10-16-repo-structure-audit.md)、
  [`2026-10-07-repo-architecture-audit.md`](2026-10-07-repo-architecture-audit.md)；
  凡与上述记录重复的既有结论只引用不重报
- 取证方式：主代理亲跑的只读探针（AST 导入图 + Tarjan 强连通分量 + 体量/命名/信号扫描 +
  文档路径引用核对），全部结论附 `文件:行号` 与可复现命令；子代理未参与本轮的判定环节

## 一、基线门禁（主代理亲测，worktree 沙箱 `.venv`）

| 门禁 | 命令 | 结果 |
|---|---|---|
| 类型 | `.venv\Scripts\python.exe -m pyright yate/ tests/ tools/` | 0 errors / 0 warnings / 0 informations，exit 0 |
| 架构守卫 | `.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q` | 31 passed，exit 0 |
| 工作区 | `git status --short` | 干净（零改动起步） |
| 代码体量 | `splitlines()` 口径 | `yate/` 139 个 `.py` / 33,174 行；`tools/` 60 个 / 12,729 行；`tests/` 99 个 |

## 二、结构全景（实测）

| 位置 | 形态 | 文件数 / 行数 | 备注 |
|---|---|---|---|
| `yate/`（根） | 16 个单文件模块 | 5,488 | L4 外壳 + L3 调度 + L1 模型 + L0 叶子混层平铺（规则允许，见 §一 依赖图） |
| `yate/editor_view/` | 24 模块平铺 | 8,822 | 占 `yate/` 26.6%，最大子包 |
| `yate/editor_core/` | 9 | 2,724 | |
| `yate/services/` | 10 + `extensions/` 子包（7） | 4,067 | 异构聚合包 |
| `yate/editor_lsp/` | 5 | 1,750 | |
| `yate/editor_term/` | 6 | 1,746 | |
| `yate/keymaps/` | 5 | 1,775 | **跨层包**（详见 S-1） |
| `yate/flows/` | 11 | 2,234 | 与规则 R11 枚举的 10 模块逐一对齐 |
| `yate/editor_syntax/` | 8（+`ts_backend/` 3） | 2,207 | |
| `yate/editor_sprites/` | 29（`chars/` 27 + `_shared`） | 1,421 | 数据模块，按名装载 |
| `yate/keyproto/` | 7 | 800 | |
| `yate/extensions/` | 2 `.py` + 9 `*.example` | 140 | 随包示例 |
| `tests/` | 99 文件**平铺**、无子目录 | — | by-behavior-domain 约定（`tests/README.md`） |
| `tools/` | 8 子包（changelog/pack/probes/release/smoke_test+scenarios/translate/yxp+example） | 12,729 | 结构清晰，每包 `__main__` 入口 |
| `pack/` | 7 文件（2 spec + 3 脚本 + `_common.py` + ico） | — | 构建期专用（详见 S-6） |
| `typings/` | 1 stub（`pyperclip/__init__.pyi`） | — | 光秃目录，合规 |

## 三、逐维度发现

分级沿用 pr-review 口径：`[BLOCKER]`（红门禁 / 架构硬违规）/ `[MAJOR]`（规则口径缺口、结构不一致）/
`[MINOR]`（可读性、可维护性、登记项）/ `[INFO]`（记录与待验）。**本轮无 BLOCKER。**

### 维度 A 分层与依赖方向

依赖图实测（AST 解析 + 最长前缀解析 + Tarjan SCC，覆盖 `yate/` 全部 139 模块）：
**向上连线仅 3 处**（见 S-1、S-2），其余全部严格向下；无未解析的内部导入。

- **[MAJOR] S-1 `keymaps` 包的分层登记与实际依赖不符（规则 §一 的 L0 清单不成立）**
  - 规则 §一 把 `keymaps/base|vim|vsc` 划入 **L0 叶子**、`keymaps/registry.py` 划入 **L1**，
    且 L0 定义要求"不 import 上层"。
  - 实测反例：`yate/keymaps/base.py:17` 运行期 `from yate.session import EditorSession`
    （`yate.session` 属 L1），由 `ActionContext.__init__`（`yate/keymaps/base.py:230,233`）
    直接持有并暴露 `buffer` / `doc`（`:237-245`）。
  - 实现方已知情并写进了 docstring：`yate/registries.py:5-6`
    "…``keymaps.base`` itself imports :mod:`yate.session`"；规则文本未同步。
  - 同一包还跨两层：`yate/keymaps/__init__.py:15` 再导出 `keymaps.base`（L0）、
    `:23` 再导出 `keymaps.registry`（L1）。
  - 影响：`import yate.keymaps` 连带拉起 `yate.session`；新增 keymap 模块"可依赖什么"无确定答案；
    规则 §一 / §二 表格与代码不再互相印证。
  - 建议（择一，均不改行为）：**(a) 低成本**——§一 与 §二 把 `keymaps/` 整体登记为 L1
    （`base`/`vim`/`vsc`/`registry` 同层），并写明 `ActionContext`/`KeyUi` 的 L1 归属；
    **(b) 结构性**——把 `ActionContext` / `KeyUi` / `ActionFunc` / `ActionRunner`
    （`yate/keymaps/base.py:190-245`）迁出到 L1 模块（`yate/registries.py` 或新建
    `yate/action_context.py`），`keymaps/` 只保留 `Keymap`/`KeyBinding`/键解析（仅依赖
    `editor_core`），使 §一 的 L0 清单真正成立；同步 §一、R2 描述、`UI_FREE_FILES` 守卫面。

- **[MAJOR] S-2 L2 → L3 向上连线未登记（`editor_view/statusbar.py`）**
  - 实测：`yate/editor_view/statusbar.py:29-30`
    `from yate.services.extensions import ExtensionLoader`、
    `from yate.services.extensions.bridges import UiExtensionBridge`。
  - 其中直引 `bridges` 子模块已由 `tests/test_architecture.py` 的
    `EXTENSION_SUBMODULE_FROZEN`（R14）冻结；但**门面** `yate.services.extensions`
    在 §一 依赖图中位于 L3，被 L2 组件引用属向上连线，规则文本（§一 依赖图 / R11 / R14）
    未登记该例外（R11 只约束 L3 `flows/` → L2 `editor_view` 的方向与其冻结集合）。
  - 影响：低（行为正确、bridges 有守卫锁定）；但"依赖只向下"的口径出现未登记缺口，
    后续 L2 组件照此上取 L3 服务将无据可依。
  - 建议：**(a)** 在 §一 依赖图与 R14 条目显式登记"L2 状态类组件可读 L3 扩展门面（只取公共名）"，
    并为其增加守卫白名单；**(b)** 或改为由 L3 注入扩展段数据（回调/L1 数据对象）给 statusbar，
    恢复严格向下。

- **[INFO] 包根 ⇄ 子模块导入环系统性存在（6 个包）**
  - 仅按显式内部导入记账时有 3 处环：`editor_core` ⇄ `search`（`yate/editor_core/search.py:8`）、
    `editor_lsp` ⇄ `client`（`yate/editor_lsp/client.py:11`）、
    `editor_syntax` ⇄ `engine`（`yate/editor_syntax/engine.py:6`）。
  - 计入"子模块导入隐含拉起父包 `__init__`"后共 **6 个包**成环：`editor_core`(4 节点)、
    `editor_syntax`(6)、`services.extensions`(3)、`editor_lsp`(2)、`editor_term`(2)、`keymaps`(2)。
  - 成因是 §三.5③「叶包 `__init__` 有限再导出」+「子模块以包根为跳板导入同级子模块」的组合，
    属该约定的固有副作用；`from pkg import submodule` 有 sys.modules 回退，当前可运行
    （pyright 0、31 架构用例绿 实测）。
  - 建议：不必重构（收益/风险不划算），但把该性质显式化——在各 `editor_*/__init__.py`
    docstring 注明导入顺序契约，或新增守卫用例锁定"包根与子模块互指"的存量白名单。

### 维度 B 包与模块组织

- **[MINOR] S-3 `editor_view/` 24 模块单层平铺，三类职责混合**
  - 实测构成（`splitlines()`）：widget 类 `editor` 631、`panes` 694、`terminal` 559、`explorer` 542、
    `completion` 417、`commandline` 405、`chrome` 294、`statusbar` 251、`welcome` 128、`scrollbars` 130；
    screen/overlay 类 `palette` 650、`diffview` 581、`find_replace` 517、`manual` 453、`screensaver` 340、
    `modals` 130；支持层 `themes` 575、`diff_pane` 482、`highlighting` 416、`theme` 184、`icons` 179、
    `cells` 133、`theme_files` 102。
  - 建议：按子域拆子包（`widgets/` / `screens/` / `theme/` / `support/`）。**注意连带面**：
    R9 冻结的 widget id 与 `yate/resources/*.tcss` 选择器、`paths.load_tcss` 资源名、
    `UI_FROZEN_FILES` 键路径（`flows/* → yate.editor_view.*`）需同步；属另案立项
    （big-module-split 量级），非本轮改动。

- **[MINOR] S-4 `services/` 异构聚合，门户 docstring 不覆盖实际成员**
  - `yate/services/__init__.py:1` 只声明 "workspace tree, shell execution and extension loading"，
    实际 10 模块还含 `clipboard` / `fonts` / `trust` / `user_setup` / `events` / `idle_tracker` / `yxp`。
  - `yate/services/yxp.py`（705 行，扩展包安装器：读/校验/装卸/列举）与 `services/extensions/`
    （R14 扩展机件域）同域却分处；`services/events.py` / `user_setup.py` 的"不随迁"有 R14 明文背书
    （"非扩展机件"），`yxp.py` 没有任何归属说明。
  - 建议：补齐 `services/__init__.py` 的职责清单（一行一词），并在 R14 或 §二 显式登记
    `yxp.py` 的归属（留 `services/` 或收进 `services/extensions/`），二者择一写进规则。

- **[MINOR] S-5 两个 `pack` 命名空间并存、用途不同**
  - 仓库根 `pack/`：PyInstaller 规格与打包脚本（`yate.spec`、`yate-onefile.spec`、
    `pack.ps1/sh/bat`、构建期共享 `_common.py`）。
  - `tools/pack/`：`python -m tools.pack`（wiki 双语生成 1495 行、名册/图标/错误码）。
  - 影响：仅检索与阅读混淆（文档中"pack 目录/打包工具"需靠上下文消歧）。
  - 建议：`tools/pack/` 更名（如 `tools/pack_assets/` 或 `tools/wiki/`）并在两处 docstring 互指分工；
    改名需一次性同步 `python -m tools.pack` 引用、CI 与文档。

### 维度 C 文档与实现一致性

- **[MINOR] S-6 `tests/README.md` 覆盖表含失效路径且不完整**
  - 失效引用 1：`tests/README.md:6,22` 仍写 `overlays.py`（2026-10-07 已更名
    `yate/flows/overlay_flows.py`，`yate/flows/` 实测无 `overlays.py`）。
  - 失效引用 2：`tests/README.md:26` 仍写 `yate/services/extensions.py`（2026-10-13 R14 已子包化，
    探针实测该路径不存在；现存 `yate/services/extensions/` 目录）。
  - 不完整：表内只列 7 个根模块；实测 `yate/` 139 模块中 **92 个**无同名 `tests/test_<name>.py`
    （`editor_view/*` 多数、`editor_core/*` 9、`editor_term/*` 6、`editor_lsp/*` 4 等均未登记）。
  - 建议：修正两处失效路径；覆盖表改为"约定 + 抽检"表述（README 已声明 by-behavior-domain 约定，
    逐模块登记维护成本高于收益），或按包补登记。

- **[MINOR] S-7 `editor_view/theme.py` 门面再导出与 §三.5② 口径冲突、例外未登记**
  - §三.5② 规定"UI / 服务包**禁止** re-export"，且例外的注明位置按 §三.5③ 是"各包
    `__init__.py` docstring"（守卫 `test_leaf_package_reexports_carry_exception_note` 只覆盖叶包）。
  - 实测：`yate/editor_view/theme.py:14` docstring 自述再导出，`:32/:41/:46` 分别再导出
    `cells` / `theme_files` / `themes` 的符号；例外由 §三.7 的 big-module-split d 波记录背书，
    但 `yate/editor_view/__init__.py` 未声明该例外，§三.5② 亦未登记。
  - 建议：在 §三.5② 或 §三.7 显式登记 `editor_view/theme.py`（门面再导出例外），
    与 `keymaps/__init__.py` 同口径处理，避免后续被守卫/评审判为回潮。

- **[MINOR] S-8 `yate/dist_meta.py` 事实层级未登记（L0 清单与守卫面双缺口）**
  - 实测：53 行、stdlib-only（`re` + `importlib.metadata`），运行期被 `yate/diagnostics.py:24` 消费，
    构建期被 `pack/_common.py:169-170` 经 `importlib.import_module("yate.dist_meta")` 消费
    ——事实层级为 L0。
  - 但 §一 L0 清单与守卫面 `UI_FREE_FILES`（`session.py`/`registries.py`/`config.py`/`yaterc.py`/
    `yaterc_options.py`）均未登记它，新增同类 L0 单文件时无参照。
  - 建议：§一 L0 行补 `dist_meta.py`；若确认其 UI-free 语义，同步加入 `UI_FREE_FILES`。

### 维度 D 体量与职责单一

- **[MINOR] S-9 `yate/editor.py` 1024 行（豁免在册，已登记为下一个 big-module-split 候选）**
  - 实测构成：构造工厂 + `:set` setter + 命令分发 + explorer 分节 + L3 唯一 App 能力分发
    （`self.app` 实测全仓仅此文件，12 处）；规则 §三.7 已登记该候选。
  - 建议：延续既有计划，优先外移 explorer 分节与 `:set` setter；§四"能力注入"部分
    （`App[None]` 持有与语义 Callable 分发）应留在 `editor.py`，不随拆分流。
- **[INFO] 阈值面零漂移**：`yate/` + `tools/` + `pack/` 内 >800 行文件恰为 5 个
  ——`yate/editor.py` 1024、`yate/editor_core/buffer.py` 1069、`yate/editor_syntax/langdefs.py` 813、
  `yate/keymaps/vim.py` 1184、`tools/pack/wiki.py` 1495，与 `SIZE_EXEMPT_FILES` 及 §三.7 名单逐项一致。

### 维度 E 测试与工具布局

- **[INFO] S-10 `tests/` 99 文件平铺无子目录**
  - 分布：`app_*` 12、`smoke_*` 4、`pack_*` 4、`editor_*`/`extension_*`/`theme_*` 各 3，
    其余约 50 为单域单文件。
  - `tests/README.md` 已声明"按行为域而非模块一对一"的约定，属**已文档化的组织方式**，非缺陷。
  - 可选建议：按域分子目录（`ui/`、`core/`、`tools/`），需同步 `pyproject.toml` 的 `testpaths`、
    CI 与打包脚本引用；收益有限，登记不立项。
- **[INFO] `tools/` 结构清晰**：8 个工具各自成包（`__init__` + `__main__` + `cli.py` + 领域模块），
  冒烟场景按功能域拆到 `tools/smoke_test/scenarios/`（21 模块）；`tools/probes/` 2 个开发期探针，
  已被 `pyproject.toml` 的 pyright `exclude` 排除（`tools/probes/**`），属既有设计。

### 维度 F 打包与资源布局

- **[INFO] S-11 `yate/resources/`、`yate/docs/` 为无 `__init__.py` 的命名空间目录（待打包验收确认）**
  - 运行期经 `importlib.resources.files("yate.resources")` 读取（`yate/paths.py:76`、
    `yate/editor_view/manual.py:69`），开发态实测可用（全量测试绿）。
  - `pyproject.toml:166-172` 的注释声明 hatchling 会自动包含包内非 Python 文件
    （`resources/*.tcss`、`resources/manual.*.md`、`docs/*.md`、`extensions/*.example`）。
  - **本次未实测 wheel 内容**（worktree 未安装 hatchling，`pip show hatchling` 返回未安装），
    故仅登记为待验项：打包验收时应确认 wheel 内含上述资源文件；若缺失，
    需在 `[tool.hatch.build.targets.wheel]` 显式声明。
- **[INFO] 文档双轨已文档化、非缺陷**：`yate/docs/*.md`（站外权威，4 对双语）与
  `yate/resources/manual.*.md`/`changelog.*.md`（应用内权威）的分工与权威归属
  已在 `yate/docs/README.md` 明文写清，`resources` 侧为运行期渲染所需 → 维持现状。

### 维度 G 结构纪律核对（全部实测通过，零违规）

| 检查 | 实测结果 |
|---|---|
| R1 仅 `cli.py` 导入 `yate.app` | `yate/` 内仅 `yate/cli.py`（`tools/`、`tests/` 不在 R1 拦截面） |
| R2 Protocol 白名单 | 恰 4 个：`editor_syntax/engine.py:33 SyntaxBackend`、`ts_backend/backend.py:93,98 _TsPoint/_TsNode`、`editor_view/editor.py:50 PaneRegistry` |
| R6 无 `TYPE_CHECKING` | 0（2 处命中均为守卫测试内的断言字符串） |
| 命名守卫 | 违规 0（AST 精确扫描 `*Feature`/`*Host`/`*Ops`/`*Delegate`/`*Controller`；`PaneHost` 在白名单） |
| 绝对导入 | 相对导入 0（`yate/`、`tools/`、`tests/`） |
| R12 日志通道 | `self.log`/`self.app.log` 命中 2 处，均为注释/docstring（`yate/app.py:186-190` 注释、`yate/keyproto/driver_windows.py:114` docstring） |
| 能力注入 | `self.app` 仅 `yate/editor.py`（12 处）；`*Flows` 模块零 App 句柄 |
| 孤儿模块 | **无**（唯一未被 `yate/` 内部导入的 `yate/extensions/python_lsp.py` 由扩展 loader 按路径装载，符合插件模型） |
| 包根惰性 | `editor_view/__init__.py`、`services/__init__.py` 明文"deliberately not re-exported"；叶包 re-export（`editor_core`、`keymaps`）带 §三.5③ 例外注明 |
| 体量阈值 | >800 行 5 文件与豁免名单逐项一致（见维度 D） |

## 四、处置汇总

| 级别 | 编号 | 主题 | 归属层 | 建议类型 |
|---|---|---|---|---|
| MAJOR | S-1 | `keymaps` 分层登记与实际依赖不符 | 规则 §一/§二 + 代码（择一） | 规则同步（a）/ 结构治理（b） |
| MAJOR | S-2 | L2 → L3 扩展门面向上连线未登记 | 规则 §一/R14 + 代码（择一） | 规则登记（a）/ 注入改造（b） |
| MINOR | S-3 | `editor_view/` 平铺无子域分组 | 代码结构 | 另案立项 |
| MINOR | S-4 | `services/` 异构聚合 + 门面 docstring 不覆盖 | 文档 + 规则 R14 | 文档同步 + 归属登记 |
| MINOR | S-5 | 根 `pack/` 与 `tools/pack/` 同名不同物 | 目录命名 | 改名（需联动引用） |
| MINOR | S-6 | `tests/README.md` 失效路径 + 覆盖不全 | 文档 | 文档修正 |
| MINOR | S-7 | `editor_view/theme.py` 门面例外未登记 | 规则 §三.5/§三.7 | 规则登记 |
| MINOR | S-8 | `dist_meta.py` L0 层级未登记 | 规则 §一 + 守卫面 | 规则/守卫同步 |
| MINOR | S-9 | `editor.py` 1024 行职责混杂 | 代码结构 | 既有拆分候选（登记） |
| INFO | 环 6 包 / S-10 / S-11 | 导入环、测试平铺、资源命名空间目录 | — | 记录 / 待验 |

**给修复实施者的口径提醒**：S-1、S-2、S-7、S-8 均为"规则文本与实现不一致"或"未登记例外"，
属**口径治理**而非缺陷修复；S-3、S-5、S-9 涉及多文件联动（守卫面、tcss 资源名、CLI 引用），
实施前须按 `plan-before-execute.md` 立项并列出独占文件清单。本次审计**未改动任何产品代码**。

> **2026-10-17 处置更新（修复计划落地）**：本记录 §四 的发现已按
> [`../documents/repo-structure-layering-audit-review-fixes-plan.md`](../documents/repo-structure-layering-audit-review-fixes-plan.md)
> （总纲与子计划 a–f 见
> [`../documents/repo-structure-layering-audit-review-fixes-plans/overview.md`](../documents/repo-structure-layering-audit-review-fixes-plans/overview.md)）
> 执行完毕：
>
> - **S-1 已修（层秩干净切分）**：键位记法下沉为 L0 单文件 `yate/keymaps/keys.py`，`keymaps/` 其余
>   （`base`/`vim`/`vsc`/`registry`/`__init__`）收敛为 L1，L0 消费者 `yate/keyproto/legacy.py` 改从
>   `keys.py` 取记法 —— 切分后**全仓零 L0→L1 连线**，无需任何 L0 例外（提交 `c525d70` / `a4e9bf0`）；
> - **S-2 已登记并冻结**：`editor_view/statusbar.py`（L2）→ `yate.services.extensions`（并含冻结的
>   `.bridges`）为切分后全仓**唯一**向上连线，已写入规则 §一 / R14，并由新守卫
>   `test_no_unregistered_upward_imports` 冻结（提交 `e13cce3` / `a812261`）；
> - **S-6 / S-7 / S-8 / S-4 已修**：`tests/README.md` 失效路径与覆盖表口径（`846e5ed`）；
>   `editor_view/theme.py` 门面例外、`dist_meta.py` 层级与守卫面、`services/yxp.py` 归属（`e13cce3`）；
>   `services/` 门户 docstring 成员清单（`f80727b`）；
> - **S-11 已关闭**：隔离构建 wheel 实测 —— `yate/resources/` 25 项、`yate/docs/` 9 项、
>   `yate/extensions/` 12 项、总条目 215，退出码 0，`pyproject.toml` 声明成立；
> - **仍为另案**：S-3（`editor_view/` 子域化）、S-5（`tools/pack` 改名）、S-9（`editor.py` 拆分）、
>   S-10（`tests/` 平铺）。
>
> 门禁终态（主代理亲跑）：`pyright yate/ tests/ tools/` 0/0/0（exit 0）；架构守卫
> **32 passed**（exit 0）；全量 `pytest tests/ -q --cov --cov-fail-under=75` **91.92%**（exit 0）；
> 向上连线实测 **2 条**（statusbar ×2）。

## 五、修复建议（按成本分组；本记录不含排期）

1. **零行为风险、可直接同步的规则/文档修正**：S-1(a)、S-2(a)、S-7、S-8（§一/§二/§三/守卫面文本）、
   S-6（`tests/README.md` 两处失效路径）、S-4 前半（`services/__init__.py` docstring 职责清单）。
2. **需要立项的结构调整**：S-1(b)（`ActionContext`/`KeyUi` 迁出 `keymaps`）、
   S-2(b)（扩展段数据改注入）、S-3（`editor_view` 子域拆分）、S-5（`tools/pack` 更名）、
   S-9(续)（`editor.py` 拆分）。
3. **登记观察、不做动作**：6 包导入环（性质文档化或加守卫白名单）、`tests/` 平铺、
   `tools/probes/` 布局、S-11（打包验收时实测 wheel 资源）。
4. **修复立项格式**：如需落地，按 doc-conventions §二.2 另立
   `../documents/repo-structure-layering-audit-review-fixes-plan.md`（与本记录互链），
   逐项写明独占文件清单与验收命令；本记录保持只读事实文档形态。

## 六、复现口径（只读探针）

本轮结论由一次性探针产出，探针脚本置于仓库外临时目录、未入库（misc-rules §二）。
关键度量可用下列最小片段复现（`yate/` 为基准目录，`.venv\Scripts\python.exe` 执行）：

```python
# 1) 体量：splitlines() 口径（守卫同源）
import pathlib
for p in sorted(pathlib.Path("yate").rglob("*.py")):
    n = len(p.read_text(encoding="utf-8").splitlines())
    if n > 600:
        print(n, p.as_posix())

# 2) 向上连线：AST 取内部导入 → 最长前缀解析 → 比对分层表（L0<L1<L2<L3<L4）
#    本轮实测输出：keymaps/base → session；editor_view/statusbar → services.extensions(.bridges)
#    （另有 keymaps/__init__ → keymaps.registry，为"单包跨两层"口径项，并入 S-1）

# 3) 导入环：对内部导入图（含子模块导入隐含拉起父包 __init__）跑 Tarjan SCC
#    本轮实测：6 个包成环（editor_core / editor_syntax / editor_lsp / editor_term /
#    keymaps / services.extensions），环内边均为"包根 re-export ⇄ 子模块导入"
```

其余机械核对命令（可直接执行）：

```powershell
git ls-files "*.pyc" | Measure-Object -Line                       # 已跟踪 pyc：0
git --no-pager status --short                                     # 工作区干净
```
