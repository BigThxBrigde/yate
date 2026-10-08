# big-module-split 计划（issue IKK5F7）

来源：<https://gitee.com/jermaine/yate/issues/IKK5F7>（ENHANCE - 大模块拆分）。
分支 `ref/big-module-split`，worktree `../yate-big-module-split`（独立 `.venv` 已自证）。
子计划总纲：[`.trae/documents/big-module-split-plans/overview.md`](big-module-split-plans/overview.md)。

## 一、目标与非目标

### 目标

1. 拆分 `yate/editor_syntax/regex_backend.py`（实测 1225 行）：语言定义
   （`LangSpec`、词表、注册表、内置语言登记）抽到新模块
   `yate/editor_syntax/regex_langdefs.py`（用户定名）；`regex_backend.py`
   只留 regex 构建与 tokenizer 引擎。两文件均降到 800 行以下。
2. 其余可拆模块按子计划波次 b–f 逐波拆分（每波独立提交 + 验收命令）。
3. 规则侧落地：`tests/test_architecture.py` 新增
   `test_source_files_within_size_threshold` 守卫（>800 行必须登记豁免）；
   同步校准 `architecture-boundaries.md` §三.7 行数与豁免名单
   （b–f 各波随拆分完成同步收缩名单，见各子计划"规则侧同步"节）。

### 非目标

- `keymaps/vim.py` 与 `yate/editor.py` 的拆分（§二 论证维持豁免）。
- 架构分层调整：全部拆分为同包/同层内部切分，不改任何依赖方向。

### 模块处置总表

> **行数口径**：本表"实测"列为**含空行**口径（PowerShell
> `Get-Content <file> | Measure-Object -Line`，等价 `.Count`，2026-10-08
> worktree HEAD ab820d4）。issue 原文行数是**不含空行**口径（如
> regex_backend 1097），两套数字不可混用；issue 所列 `config.py: 924` 已
> 过时——A9 拆分后（加载器迁入 `yaterc.py`）实测 330 行，不再超标。

| 文件 | 实测 | 处置 | 波次 | 拆分后预估 |
|---|---|---|---|---|
| `editor_syntax/regex_backend.py` | 1225 | 拆 → `regex_langdefs.py` | a | ~490 / ~780 |
| `editor_view/diffview.py` | 1035 | 拆 → `diff_pane.py` | b | ~600 / ~490 |
| `editor_view/editor.py` | 1007 | 拆 → `highlighting.py` + `welcome.py` | c | ~680 / ~300 / ~115 |
| `keymaps/vim.py` | 1117 | **维持豁免**（详见 §二） | — | 1117 |
| `editor.py` | 933 | **维持豁免**（详见 §二） | — | 933 |
| `editor_core/buffer.py` | 888 | 拆词运动 → `words.py` | e | ~822（仍豁免）/ ~85 |
| `editor_term/emulator.py` | 861 | 拆 → `palette.py` + `keys.py` | e | ~775 / ~50 / ~80 |
| `editor_lsp/manager.py` | 833 | 拆解析 → `parsing.py` | f | ~630 / ~230 |
| `editor_view/theme.py` | 805 | 拆 → `themes.py` + `cells.py` + `theme_files.py` | d | ~140 / ~500 / ~80 / ~75 |
| `yaterc.py` | 803 | 拆 → `yaterc_options.py` | f | ~200 / ~630 |

## 二、维持豁免的文件（否决理由，均已实测核对）

- **`keymaps/vim.py`（1117）**：模块 docstring 一句话可概括；全部职责块经
  `self` 上 9 个 chord 状态字段交织引用（NORMAL 分发横跨 9 块、VISUAL 与
  NORMAL 共用寄存器状态、count 语义散布三处），不存在"互不引用的职责块"，
  不满足 A11 拆分判据。唯一低耦合候选（build_bindings + 类目常量，~97 行）
  迁出后 vim.py 仍 ~1020 行，无解阈值，纯 churn。剪贴板桥接还被
  `tests/test_vim_keymap.py:1458` monkeypatch 钉住。→ 维持豁免并更新登记行数。
- **`yate/editor.py`（933）**：构造工厂群 ~243 行是流程模块显式构造注入纪律
  的直接产物（顺序敏感，注释记录依赖链）；Editor 类核心 ~500 行是全仓唯一
  L3 App 句柄持有者/能力分发点，方法皆为 3–15 行薄动词；已有 6 个职责
  迁入 flows/*（docstring 标注 "Extracted from yate.editor"）。唯一候选
  `theme_flows.py` 仅迁 ~78 行，且触发 R11 `UI_FROZEN_FILES` 新登记 +
  commands.py apply 映射改动，成本 > 收益。→ 维持豁免并更新登记行数。

## 三、波次调度（子计划见 big-module-split-plans/）

| 波次 | 子计划 | 内容 | 触碰面 |
|---|---|---|---|
| a | [big-module-split-regex-langdefs-plan-a.md](big-module-split-plans/big-module-split-regex-langdefs-plan-a.md) | regex_langdefs 抽取 + 行数守卫 + 规则校准 | editor_syntax、tests、.trae/rules |
| b | [big-module-split-diff-pane-plan-b.md](big-module-split-plans/big-module-split-diff-pane-plan-b.md) | diffview → diff_pane | editor_view、3 个测试、tools |
| c | [big-module-split-view-highlight-plan-c.md](big-module-split-plans/big-module-split-view-highlight-plan-c.md) | editor_view/editor → highlighting + welcome | editor_view、1 个测试 |
| d | [big-module-split-theme-registry-plan-d.md](big-module-split-plans/big-module-split-theme-registry-plan-d.md) | theme → themes/cells/theme_files（门面） | editor_view（40+ 引用零改动） |
| e | [big-module-split-leaf-extracts-plan-e.md](big-module-split-plans/big-module-split-leaf-extracts-plan-e.md) | buffer→words；emulator→palette/keys | editor_core、editor_term、keymaps、flows、tests |
| f | [big-module-split-lsp-yaterc-plan-f.md](big-module-split-plans/big-module-split-lsp-yaterc-plan-f.md) | manager→parsing；yaterc→yaterc_options | editor_lsp、yaterc、tests |

**调度纪律（硬性）**：

- **a 波先行**：b–f 依赖 a 落地的行数守卫与全量豁免名单。
- **b–f 必须串行，不得并行**：产品源码文件波次间互不重叠，但每波都要改
  `tests/test_architecture.py`（豁免集合逐波收缩）与
  `.trae/rules/architecture-boundaries.md` §三.7（豁免名单收缩）两个共享
  文件——文件重叠即不可并行。上一波验收命令全部退出码 0 才进入下一波。
- 每波收尾跑该波子计划所列验收命令；全部波次结束后统一全量门禁
  （pyright + pytest + 架构测试 + 覆盖率，命令见 plan f 末节）。

依赖关系图与执行状态追踪表见
[big-module-split-plans/overview.md](big-module-split-plans/overview.md)。

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| 循环导入 | 每个子计划显式声明 import 方向并验证单向 |
| 测试 monkeypatch 私有名失效 | 子计划逐个登记 patch 面（如 `_tokenize_with_states`、`_welcome_lines`、`CHANGE_DEBOUNCE_S`、`copy_text`）并同步改 patch 目标或保留薄委托 |
| 架构守卫白名单（UI_FROZEN_FILES / UI_FREE_FILES）漂移 | 各子计划列出需登记/无需登记的判定 |
| 共享守卫文件导致并行冲突 | b–f 强制串行（§三），每波独占 `tests/test_architecture.py` 与 rules §三.7 的修改窗口 |
| 回滚 | 每波独立提交，`git revert` 单笔回退 |

## 五、执行记录（回填，与 overview.md §三 状态追踪表同构）

| 波次 | 状态 | 验收命令退出码 | 提交（hash/说明） | 偏离记录 |
|---|---|---|---|---|
| a（regex_langdefs + 行数守卫） | 已完成 | 4/4 退出码 0（pyright `yate/editor_syntax/` 零诊断；pytest 5 文件 `-q` 通过，1 个 py-tree-sitter 可选依赖既有 skip；`available_filetypes()` 探针 = 72，与 HEAD 基线一致；行数实测 regex_langdefs 794 / regex_backend 500） | （待主代理提交） | 实测行数 794/500，略高于预估 ~780/~490（含模块 docstring 与 `__all__` 开销），均在阈值内。私有注册表再导出为满足 pyright 零诊断，除 `regex_backend.__all__` 外还需在声明模块 `regex_langdefs.__all__` 登记 `_LANGUAGES` / `_NAME_TO_KEY`（否则 `reportPrivateUsage` 报错），导入方向仍单向、无行为改动 |
| b（diffview → diff_pane） | 已完成 | 3/3 退出码 0（pyright `yate/editor_view/` 零诊断；pytest 4 文件 `-q` 96 passed；行数实测 diff_pane 475 / diffview 581）。波次收尾前置项 `pyright yate/ tests/ tools/` 另测零诊断 | （待主代理提交） | 实测行数 475/581，与预估 ~490/~600 相符（迁移时 diff_pane 无日志调用，未引入 `yate.logs` 依赖，导入面与 plan-b 依赖清单一致） |
| c（editor_view/editor 拆分） | 待执行 | — | — | — |
| d（theme 拆分） | 待执行 | — | — | — |
| e（words + palette/keys） | 待执行 | — | — | — |
| f（parsing + yaterc_options） | 待执行 | — | — | — |
| 全量门禁 | 待执行 | — | — | — |

回填纪律：状态只允许 `待执行 → 执行中 → 已完成`；"已完成"必须附验收命令
实际退出码与提交 hash；偏离计划须在"偏离记录"列写明实测依据。本表与
[overview.md §三](big-module-split-plans/overview.md) 逐行对应，两处同步回填。
