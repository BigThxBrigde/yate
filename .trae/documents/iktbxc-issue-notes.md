# IKTBXC issue 输入笔记（逐字任务素材，无分析）

Issue: <https://gitee.com/jermaine/yate/issues/IKTBXC>
标题：`refactor: keyproto/legacy.py、editor_components/editor.py 更名与 cmdline_completions 层级归位 —— 命名自查修复、守卫与规则文档同步`
状态：待办的 / enhancement / 创建于 2026-11-06 10:22 / 0 条评论。
Worktree：`yate-naming-hygiene`，分支 `ref/naming-hygiene`，基线 `master@3e92532`。

## 所述目标

对模块/子包进行关键命名评审。两次较早的评审只核对了规则合规性（snake_case、禁用后缀守卫、37 项架构测试全绿），漏掉了三类债务：名称/角色不匹配、层级错误、同一词不同含义。本 issue 收敛 5 项已确认的命名/结构债务，**零运行时行为变更**，并明确列出评估过但未更改的项，以防范围蔓延。

## P0-1：`yate/keyproto/legacy.py` 名称/角色不匹配

- 现状：docstring 首行写着 "Legacy key codec"、"Formerly `yate.editor_components.keys`"；容易被误读为等待删除的弃用兼容层。
- 事实：本仓库**当前唯一**的按键名 -> 原始字节序列编解码器，有 9 处活跃引用：`yate/app.py:30`、`yate/editor_dispatch.py:23`、`yate/editor_term/keys.py:12`、`yate/keyproto/__init__.py:13`、`tests/test_term_keys.py:12`、`tests/test_keyproto.py:30`、`tests/test_app_textual.py:23`；另在 `editor_dispatch.py:123`、`editor_term/keys.py:4` 有 docstring 引用。`keyproto/__init__.py:13` 将其列为三种编解码器之一。
- 建议：`git mv` 到 `key_codec.py`；更新所有 import / docstring / 规则文本引用。重写模块 docstring 首行，说明 "legacy" 指的是终端按键命名体系。

## P0-2：`yate/editor_components/editor.py` 跨层重名

- 现状：模块 `editor`，主类 `EditorView`（:74）；顶层 `yate/editor.py` 持有 L3 的 `Editor`。L2/L3 存在两个 `editor.py`，只能靠调用方记忆区分。
- 引用面 22 处：`yate/editor.py:61`、`yate/editor_dispatch.py:19`、`yate/editor_compose.py`、`flows/mouse_flows.py:19`、`flows/completion_flows.py:24`、8 个测试、`tools/smoke_test/scenarios/multi_cursor.py:18`、`tests/test_architecture.py:213/225`（`UI_FROZEN_FILES` 键）、`editor_components/__init__.py`、`welcome.py`、`highlighting.py`、`panes.py` 的 docstring。
- 建议：`git mv` 到 `view.py`（或 `text_view.py`），与 `EditorView` 对齐。**禁止**：`editor_view.py` —— 该词组是 2026-11-02 改掉的旧包名；复用它会回退重命名并混淆文档。
- 同步：`UI_FROZEN_FILES` 键、所有 docstring、测试、冒烟场景。

## P1-3：`yate/flows/cmdline_completions.py` 不属于 L3

- 现状：位于 L3 的 `flows/`，登记在 R11 的 flows 枚举中。
- 事实：docstring 自述 "pure functions" / "owns no state and imports no UI"；依赖仅 `yate.registries`（L1）、`yate.services.workspace`（L0）、`yate.session`（L1），**零 L3 依赖**。实际接线是 `editor_compose.py:127-133` 向 L2 的 `PromptBar` 回调注入一个 `partial`，并非流程编排。规则 §三.6 已把 `cmdline_completions` 归类为 "pure computation implemented with functions"。
- 层级副作用：L0 的 `yate/config.py:12` docstring 与 `:290` 注释回指 `:mod:yate.flows.cmdline_completions`；`services/extensions/api.py:411` 注释与 `tests/test_cmdline_completions.py` 也引用该路径。
- 建议：`git mv` 到 `yate/services/cmdline_completions.py`（L0 叶子服务，与 `services/workspace.py` 同层）或 `yate/cmdline_completions.py`；同步 `architecture-boundaries.md` §一 L3 清单 / R11 枚举 / §三.6、`editor_compose.py:33`、`config.py`、`api.py:411`、`tests/test_architecture.py` 及相关测试。

## P2（明确不在本 issue 的门禁批次内；另行评审）

- P2-4：`editor_sprites/` 混用全称与缩写：`characters.py`（字符注册表）与 `chars/`（27 个位图数据模块）用两种拼写表示同一概念（`characters.py:25` import `yate.editor_sprites.chars`，`chars/__init__.py:3` 写着 "Imported by `yate.editor_sprites.characters` only"）。建议 `characters.py` -> `registry.py`、`chars/` -> `characters/`，同步 27 个模块 import 与 `python-coding-style.md` §1.2 的 `_shared` 条目。
- P2-5：`palette` 有三种含义：`editor_components/palette.py:1`（命令面板 + 快速打开，`PaletteScreen`）、`editor_term/palette.py:1`（xterm 256 色表，`palette_color`）、`editor_sprites/render.py`（sprite 的 `Palette` 类型）。三者都是领域标准术语，并非硬缺陷。若要清理，建议 `editor_components/palette.py` -> `command_palette.py`，并按既往重命名波的惯例同步测试重命名。

## 明确的非目标（否决理由、硬边界）

| 项目 | 否决理由 |
|---|---|
| `flows/` -> `editor_flows` | L3 同级 `actions/commands/diagnostics` 是无前缀短名；包/文件/类命名已对齐；约 90 处纯改动点；R11 / §三.8 / 守卫都锚定在 `flows/` 上 |
| `services/` 混合 L0/L3 | `services/__init__.py:15` 已自述 L3 机制子包；R14 冻结 `yate.services.extensions` 的 14 个公开名（插件 API）；迁移会破坏插件生态，属已登记的历史妥协 |
| `yate/extensions/` 插件目录 vs `services/extensions/` 机制包 | `loader.py:296` 的 `cwd/"extensions"` 与 `:310` 的 `yate_home()/"extensions"` 是运行时面向用户的约定；改动属破坏性 |
| 跨包同名 `diff.py` | 命名空间隔离，行业惯例 |

## 目标 / 非目标

目标：消除名称/角色不匹配，把纯函数移到正确层级，统一同一概念的命名。

非目标：
- 零运行时行为变更、零依赖方向变更；diff 仅为 `git mv` + import 行 / 路径字符串 / docstring / 规则文档 / 测试名；
- 不重命名类（`EditorView` / `PaletteScreen` / `LspSync` 保持）；
- 不改变插件公共 API，不改变面向用户的目录约定（`./extensions`、`~/.yate/extensions`），不回改 CHANGELOG 历史笔记或 `tools/changelog/zh_overrides.json`；
- `.trae/documents/` 历史计划文档不回改（既有约定）；
- 不借机拆分文件，不改大小豁免清单。

## 实现与验收（逐字）

按主题分三个独立提交（保留 `git mv` 重命名跟踪与逐提交可回退性）：
- wave 1：P0-1 `keyproto/legacy.py` -> `key_codec.py`（1 个文件 + 9 处引用）；
- wave 2：P0-2 `editor_components/editor.py` -> `view.py`（含 `UI_FROZEN_FILES` 键与 docstring）；
- wave 3：P1-3 `cmdline_completions` 层级迁移（含规则文档 §一 / R11 / §三.6 同步）；
- P2 项单独评审，不属于本 issue 的门禁批次。

验收命令（均退出码 0）：
```powershell
.venv\Scripts\python.exe -m pyright yate/ tests/ tools/ pack/
.venv\Scripts\python.exe -m pytest tests/ -q -n auto
.venv\Scripts\python.exe -m pytest tests/test_architecture.py -q
.venv\Scripts\python.exe -m pytest tests/ --cov=yate --cov-branch -n auto --cov-fail-under=75
.venv\Scripts\python.exe -m tools.smoke_test run --jobs 4
```

残余 grep 预期 0：`keyproto.legacy` / `editor_components.editor` / `flows.cmdline_completions`（豁免 CHANGELOG 历史笔记与 `.trae/documents/` 历史文档）。已改扫描路径的守卫（R11 冻结面、层级 rank、命名守卫）各需一次负向演练：临时恢复一处违规 -> 确认被拦截 -> 还原并复验转绿。

## 风险与回滚

| 风险 | 缓解措施 |
|---|---|
| 字符串补丁目标 / docstring 路径遗漏 | 残余 grep 三重 + pyright + 全量 pytest；`git grep` 逐命中人工分诊，不做盲目全局替换 |
| 守卫变聋（路径改了但集合 / 扫描根没改） | 负向演练 x3，确认拦截后还原 |
| `git mv` 重命名跟踪丢失 | 严格 `git mv`（绝不删除+创建），提交后抽查 `git log --follow` |
| 插件 / 冒烟场景 import 旧路径 | 全量冒烟 121 场景 + `python -m yate --help` 基线 |
| 规则文档 / 代码漂移 | `architecture-boundaries.md` 与 `tests/test_architecture.py` 在同一波同步，不做事后补丁 |

回滚：三个独立提交，逐个 `git revert`；worktree 沙箱隔离，主仓不受影响。

## 协调者收集的笔记（仅事实，无分析）

- 无人值守会话：用户指示进入无人值守模式，不提问、不审批。计划审批视为已授予；所有子代理带 `bypassPermissions` spawn；门禁执行不豁免。
- 接手时仓库状态：`master` 在 `3e92532` 干净；现有 worktree 为 `yate-enew-args-lsp-attach`、`yate-filemgr-theme-beautify`、`yate-multi-dim-review-r2`（本新任务均未复用）。
