# big-module-split 计划（issue IKK5F7）

来源：<https://gitee.com/jermaine/yate/issues/IKK5F7>（ENHANCE - 大模块拆分）。
分支 `ref/big-module-split`，worktree `../yate-big-module-split`（独立 `.venv` 已自证）。
子计划：[`.trae/documents/big-module-split-plans/overview.md`](big-module-split-plans/overview.md)。

## 一、目标与非目标

### 目标

1. 拆分 `yate/editor_syntax/regex_backend.py`（实测 1225 行）：语言定义
   （`LangSpec`、词表、注册表、内置语言登记）抽到新模块
   `yate/editor_syntax/regex_langdefs.py`（用户定名）；`regex_backend.py`
   只留 regex 构建与 tokenizer 引擎。两文件均降到 800 行以下。
2. 其余可拆模块按子计划波次 b–f 逐波拆分（每波独立提交 + 全量门禁）。
3. 规则侧落地：`tests/test_architecture.py` 新增
   `test_source_files_within_size_threshold` 守卫（>800 行必须登记豁免）；
   同步校准 `architecture-boundaries.md` §三.7 行数与豁免名单。

### 模块处置总表（实测行数，2026-10-08 口径含空行）

| 文件 | 实测 | 处置 | 波次 | 拆分后预估 |
|---|---|---|---|---|
| `editor_syntax/regex_backend.py` | 1225 | 拆 → `regex_langdefs.py` | a | ~490 / ~780 |
| `editor_view/diffview.py` | 1035 | 拆 → `diff_pane.py` | b | ~600 / ~490 |
| `editor_view/editor.py` | 1007 | 拆 → `highlighting.py` + `welcome.py` | c | ~680 / ~300 / ~115 |
| `keymaps/vim.py` | 1117 | **维持豁免**（详见 §二） | — | 1117 |
| `editor.py` | 934 | **维持豁免**（详见 §二） | — | 934 |
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
- **`yate/editor.py`（934）**：构造工厂群 ~243 行是流程模块显式构造注入纪律
  的直接产物（顺序敏感，注释记录依赖链）；Editor 类核心 ~500 行是全仓唯一
  L3 App 句柄持有者/能力分发点，方法皆为 3–15 行薄动词；已有 6 个职责
  迁入 flows/*（docstring 标注 "Extracted from yate.editor"）。唯一候选
  `theme_flows.py` 仅迁 ~78 行，且触发 R11 `UI_FROZEN_FILES` 新登记 +
  commands.py apply 映射改动，成本 > 收益。→ 维持豁免并更新登记行数。

## 三、波次调度（子计划见 big-module-split-plans/）

| 波次 | 子计划 | 内容 | 触碰面 |
|---|---|---|---|
| a | `regex-langdefs-plan-a.md` | regex_langdefs 抽取 + 行数守卫 + 规则校准 | editor_syntax、tests、.trae/rules |
| b | `diff-pane-plan-b.md` | diffview → diff_pane | editor_view、3 个测试、tools |
| c | `view-highlight-plan-c.md` | editor_view/editor → highlighting + welcome | editor_view、1 个测试 |
| d | `theme-registry-plan-d.md` | theme → themes/cells/theme_files（门面） | editor_view（40+ 引用零改动） |
| e | `leaf-extracts-plan-e.md` | buffer→words；emulator→palette/keys | editor_core、editor_term、keymaps、flows、tests |
| f | `lsp-yaterc-plan-f.md` | manager→parsing；yaterc→yaterc_options | editor_lsp、yaterc、tests |

波次间文件不重叠，可并行执行（每波收尾跑该波验收命令；最终统一全量门禁）。
守卫用例的豁免名单随波次推进逐波收缩（a 波落全量名单，b–f 各自移除已完成项）。

## 四、风险与回滚

| 风险 | 缓解 |
|---|---|
| 循环导入 | 每个子计划显式声明 import 方向并验证单向 |
| 测试 monkeypatch 私有名失效 | 子计划逐个登记 patch 面（如 `_tokenize_with_states`、`CHANGE_DEBOUNCE_S`、`copy_text`）并同步改 patch 目标 |
| 架构守卫白名单（UI_FROZEN_FILES / UI_FREE_FILES）漂移 | 各子计划列出需登记/无需登记的判定 |
| 回滚 | 每波独立提交，`git revert` 单笔回退 |

## 五、执行记录（回填）

- 波次 a：待执行。
- 波次 b–f：待执行。
